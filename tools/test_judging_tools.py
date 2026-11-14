#!/usr/bin/env python3
"""Tests for build_judge_sheets.py and check_judge_reply.py on SYNTHETIC judge replies only.
No real scoring happens here: the 'scores' are random numbers made up for the test."""
import csv, json, os, random, re, shutil, subprocess, sys, tempfile

SP = os.path.dirname(os.path.abspath(__file__))
KIT = "/home/claude/silex_blind_test"
RESULTS = "/home/claude/silex_results"
OUT = tempfile.mkdtemp(prefix="judge_test_")  # sheets are built here fresh, and removed at the end
subprocess.run([sys.executable, "-I", os.path.join(SP, "build_judge_sheets.py"), "--results", RESULTS, "--kit", KIT,
                "--out", OUT, "--seed", "424242"], check=True, capture_output=True)
sys.path.insert(0, SP)
import check_judge_reply as cj  # noqa: E402

exp_facts = cj.expected_facts(KIT)
rows = list(csv.DictReader(open(os.path.join(OUT, "sheets_map_PRIVATE.csv"), newline="", encoding="utf-8")))
b1 = next(r for r in rows if r["batch"] == "1")
b2 = next(r for r in rows if r["batch"] == "2")
items = b1["order"].split()
rng = random.Random(7)
fails = []


def ok(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def synth(its, rng):
    lines, truth = [], {}
    for it in its:
        ks = sorted(exp_facts[it])
        sc = {f"F{k}": rng.choice([0, 1, 1, 1]) for k in ks}
        fl = rng.choice([0, 0, 0, 1])
        reason = "" if all(sc.values()) else "does not say who the request goes to"
        lines.append(f"{it} | " + " ".join(f"{k}={v}" for k, v in sc.items()) + f" | false={fl} | {reason}")
        truth[it] = dict(scores=sc, false=fl)
    return lines, truth


def run(lines, row=b1):
    its = set(row["order"].split())
    return cj.check("\n".join(lines) + "\n", its, exp_facts)


# 1. clean reply: every score comes back exactly as written
lines, truth = synth(items, rng)
got, prob, warn, redo = run(lines)
ok(not prob and not redo and len(got) == 20, "clean reply: 20 of 20 items usable, no problems")
ok(all(got[i]["scores"] == truth[i]["scores"] and got[i]["false"] == truth[i]["false"] for i in truth),
   "clean reply: scores and false counts come back exactly as written")

# 2. a missing item line
l2 = [l for l in lines if not l.startswith(items[3])]
got, prob, warn, redo = run(l2)
ok(redo == [items[3]] and len(got) == 19, "missing line: only that item is redone, 19 kept")

# 3. an extra fact (F9) and a missing fact
l3 = list(lines)
i0 = next(i for i, l in enumerate(l3) if l.startswith(items[0]))
l3[i0] = l3[i0].replace(" | false=", " F9=1 | false=", 1)
got, prob, warn, redo = run(l3)
ok(items[0] in redo and len(got) == 19, "extra fact F9: that item is redone")
l3 = list(lines)
i1 = next(i for i, l in enumerate(l3) if l.startswith(items[1]))
l3[i1] = re.sub(r"F2=[01] ", "", l3[i1], count=1)
got, prob, warn, redo = run(l3)
ok(items[1] in redo and len(got) == 19, "missing fact F2: that item is redone")

# 4. a duplicated line: the item is redone (the first copy is not trusted either)
got, prob, warn, redo = run(lines + [lines[5]])
ok(redo == [items[5]] and items[5] not in got, "duplicate line: that item is redone, neither copy kept")

# 5. a malformed line
l5 = list(lines)
l5[2] = l5[2].replace("|", "", 1)
got, prob, warn, redo = run(l5)
ok(len(redo) == 1 and len(got) == 19, "malformed line: that item is redone")

# 6. text around the lines is ignored with notes only
l6 = ["Here are the scores.", "SHEET " + b1["code"]] + lines + ["Let me know if you want more detail."]
got, prob, warn, redo = run(l6)
ok(not redo and len(got) == 20 and len(warn) == 3, "extra text: 20 usable, three notes, no redo")

# 7. decorated lines
l7 = list(lines)
l7[0] = "- " + l7[0]
l7[1] = "`" + l7[1].rstrip() + "`"
l7[2] = "**" + l7[2].rstrip() + "**"
got, prob, warn, redo = run(l7)
ok(not redo and len(got) == 20 and sum("decorated" in w for w in warn) == 3, "decorated lines: parsed, three notes")

# 8. a 0 without a reason, and a long reason: notes only
l8 = list(lines)
j = next(i for i, l in enumerate(l8) if "=0" in l.split("|")[1])
head = l8[j].rsplit("|", 1)[0]
l8[j] = head + "|"
k2 = next(i for i, l in enumerate(l8) if i != j and "=0" in l.split("|")[1])
l8[k2] = l8[k2].rsplit("|", 1)[0] + "| " + " ".join(["word"] * 14)
got, prob, warn, redo = run(l8)
ok(not redo and len(got) == 20 and any("without a reason" in w for w in warn) and any("14 words" in w for w in warn),
   "zero without reason / reason over 12 words: notes only")

# 9. an item from the other batch
l9 = list(lines) + ["#25 | F1=1 F2=1 F3=1 F4=1 | false=0 |"]
got, prob, warn, redo = run(l9)
ok(redo == ["#25"] and len(got) == 20, "item from the other batch: flagged, the 20 real items stay usable")

# 10. everything on one line cannot be read
got, prob, warn, redo = run([" ".join(lines)])
ok(len(got) <= 1 and len(redo) >= 19, "all on one line: not accepted, items redone")

# 11. batch 2 sheet works with its own items
l11, t11 = synth(b2["order"].split(), random.Random(3))
got, prob, warn, redo = run(l11, b2)
ok(not redo and len(got) == 20, "batch 2 sheet: clean")

# 12. command line: exit codes and JSON file
with tempfile.TemporaryDirectory() as td:
    good = os.path.join(td, "good.txt")
    open(good, "w").write("\n".join(lines) + "\n")
    bad = os.path.join(td, "bad.txt")
    open(bad, "w").write("\n".join(l2) + "\n")
    base = [sys.executable, "-I", os.path.join(SP, "check_judge_reply.py"), "--map",
            os.path.join(OUT, "sheets_map_PRIVATE.csv"), "--kit", KIT]
    r = subprocess.run(base + ["--code", b1["code"], "--reply", good, "--json", os.path.join(td, "o.json")],
                       capture_output=True, text=True)
    ok(r.returncode == 0 and json.load(open(os.path.join(td, "o.json")))["status"] == "clean", "CLI: clean reply exits 0, status clean")
    r = subprocess.run(base + ["--code", b1["code"], "--reply", bad], capture_output=True, text=True)
    ok(r.returncode == 1 and "ask the judge again for" in r.stdout, "CLI: missing item exits 1 and names the item")
    r = subprocess.run(base + ["--code", "ZZZZ", "--reply", good], capture_output=True, text=True)
    ok(r.returncode == 2, "CLI: unknown sheet code exits 2")

shutil.rmtree(OUT, ignore_errors=True)
print()
print("ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
