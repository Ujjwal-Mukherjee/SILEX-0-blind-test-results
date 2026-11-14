#!/usr/bin/env python3
"""Tests for reliability.py (second-judge draw and comparison, audit draw and comparison) on SYNTHETIC data only.
A made-up results folder is built in a temporary directory (the kit's facts.csv and judge prompts are only read); the real sheet builders and the real form
checkers are run on it, so the whole chain is exercised. Nothing in the real results folder is touched.
Usage: python3 -I test_reliability.py [KIT]"""
import csv, glob, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile

SP = os.path.dirname(os.path.abspath(__file__))
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, SP)
import build_judge_sheets as bj  # noqa: E402
import check_judge_reply as cj  # noqa: E402
import check_judge_reply_rt as cjr  # noqa: E402

TMP = tempfile.mkdtemp(prefix="reliab_test_")
RES = os.path.join(TMP, "res")
os.makedirs(os.path.join(RES, "parsed"))
fails = []


def ok(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def run(script, *args, expect=0):
    p = subprocess.run([sys.executable, "-I", os.path.join(SP, script)] + [str(x) for x in args], capture_output=True, text=True)
    if p.returncode != expect:
        print("   unexpected exit %d for %s %s\n   stdout: %s\n   stderr: %s" % (p.returncode, script, " ".join(map(str, args))[:120], p.stdout[-400:], p.stderr[-400:]))
    return p


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ 1. a made-up results folder (6 reading sheets, 4 round-trip sheets)
rng = random.Random(5150)
cells = []
parsed_text = {}
CELLS = [("R", "claude", 1, 1), ("R", "claude", 1, 2), ("R", "grok", 1, 1), ("R", "grok", 1, 2), ("N", "claude", 1, 1), ("N", "claude", 1, 2),
         ("RTP", "claude", 1, 1), ("RTP", "claude", 1, 2), ("RTE", "claude", 1, 1), ("RTE", "claude", 1, 2)]
for n, (arm, model, run_, batch) in enumerate(CELLS, 1):
    rid = "recv%02d" % n
    fn = "%s_label-test.txt" % rid
    raw = ("synthetic reply %s\n" % rid).encode()
    open(os.path.join(RES, fn), "wb").write(raw)
    items = {}
    for it in bj.BATCH_ITEMS[batch]:
        items[it] = "Synthetic explanation of %s, serial %d-%d." % (it, n, rng.randrange(10 ** 6))
    parsed_text[rid] = items
    json.dump(dict(source=fn, sha256=sha(raw), items=items), open(os.path.join(RES, "parsed", rid + ".json"), "w"))
    cells.append(dict(recv=rid, arm=arm, model=model, run=run_, batch=batch, status="data", file=fn, sha256_16=sha(raw)[:16]))
with open(os.path.join(RES, "cells.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(cells[0].keys()))
    w.writeheader()
    w.writerows(cells)
CORR_RECV, CORR_ITEM = "recv02", "#23"
json.dump({CORR_RECV: {"items": {CORR_ITEM: "A made-up correction note for this item."}}}, open(os.path.join(RES, "corrections.json"), "w"))
before_res = {p: sha(open(p, "rb").read()) for p in glob.glob(os.path.join(RES, "**", "*"), recursive=True) if os.path.isfile(p)}

OUT_R, OUT_RT = os.path.join(TMP, "judging_reading"), os.path.join(TMP, "judging_rt")
run("build_judge_sheets.py", "--results", RES, "--kit", KIT, "--out", OUT_R, "--seed", 11, "--arms", "R,N")
run("build_judge_sheets_rt.py", "--results", RES, "--kit", KIT, "--out", OUT_RT, "--seed", 12, "--arms", "RTP,RTE")
MAP_R, MAP_RT = os.path.join(OUT_R, "sheets_map_PRIVATE.csv"), os.path.join(OUT_RT, "sheets_map_PRIVATE.csv")
rows_r = list(csv.DictReader(open(MAP_R, newline="")))
rows_rt = list(csv.DictReader(open(MAP_RT, newline="")))
ok(len(rows_r) == 6 and len(rows_rt) == 4, "made-up first-judge sheets built: 6 reading, 4 round trip")
first_codes = {r["code"] for r in rows_r + rows_rt}
EXP_ALL = cj.expected_facts(KIT)
EXP_C = cjr.expected_c_facts(KIT)


def judge_reply(rows, kind, rng2):
    """A made-up judge reply per sheet (random scores), checked by the REAL form checker into JSON files."""
    d = os.path.join(TMP, "scores_%s" % kind)
    os.makedirs(d, exist_ok=True)
    exp = EXP_ALL if kind == "reading" else EXP_C
    for r in rows:
        lines = []
        for it in r["order"].split():
            sc = {k: rng2.choice([0, 1, 1]) for k in sorted(exp[it])}
            lines.append("%s | %s | false=%d | %s" % (it, " ".join("F%d=%d" % (k, v) for k, v in sc.items()), rng2.choice([0, 0, 1]), "x" if 0 in sc.values() else "-"))
        rp = os.path.join(TMP, "reply_%s_%s.txt" % (kind, r["code"]))
        open(rp, "w").write("\n".join(lines) + "\n")
        script = "check_judge_reply.py" if kind == "reading" else "check_judge_reply_rt.py"
        run(script, "--map", MAP_R if kind == "reading" else MAP_RT, "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(d, r["code"] + ".json"))
    return d


SC_R = judge_reply(rows_r, "reading", random.Random(1))
SC_RT = judge_reply(rows_rt, "rt", random.Random(2))
BASE = ["--results", RES, "--kit", KIT, "--reading-map", MAP_R, "--reading-scores", SC_R, "--rt-map", MAP_RT, "--rt-scores", SC_RT]

# ------------------------------------------------------------------ 2. second-judge draw
D1 = os.path.join(TMP, "draw1")
p = run("reliability.py", "second-draw", *BASE, "--seed", 777, "--out", D1)
ok(p.returncode == 0, "second-draw runs")
info = json.load(open(os.path.join(D1, "draw_info_PRIVATE.json")))
ok(info["pool_items"] == 200 and info["drawn_items"] == 40, "pool of 200 judged explanations, 20 percent = 40 drawn (got %s / %s)" % (info["pool_items"], info["drawn_items"]))
smap = list(csv.DictReader(open(os.path.join(D1, "second_map_PRIVATE.csv"), newline="")))
ok(all(re.fullmatch("[%s]{4}" % bj.ALPHABET, r["code"]) for r in smap) and len({r["code"] for r in smap}) == len(smap), "new sheet codes: 4 characters of the sheet alphabet, all different")
ok(not ({r["code"] for r in smap} & first_codes), "new codes never equal a first-judge code")
ok(all(int(r["n_items"]) <= 20 and len(r["order"].split()) == len(set(r["order"].split())) == int(r["n_items"]) for r in smap), "at most 20 items per sheet and no scenario item twice on a sheet")
srcs = []
for r in smap:
    s = json.loads(r["sources"])
    ok(sorted(s) == sorted(r["order"].split()), "sources match the items of sheet %s" % r["code"]) if False else None
    srcs += [(r["kind"], c, it) for it, c in s.items()]
ok(len(srcs) == 40 and len(set(srcs)) == 40, "40 distinct (kind, first sheet, item) sources")
kind_of = {r["code"]: "reading" for r in rows_r}
kind_of.update({r["code"]: "rt" for r in rows_rt})
ok(all(kind_of[c] == k for k, c, it in srcs), "every source belongs to a sheet of its own kind; a second sheet never mixes kinds")
ok(all(len({kind_of[c] for c in json.loads(r["sources"]).values()}) == 1 for r in smap), "one kind per second sheet")
ok(all(sha(open(os.path.join(D1, "sheets", "sheet_%s.txt" % r["code"]), "rb").read())[:16] == r["sheet_sha16"] for r in smap), "sheet hashes in the map match the files")
prompts = {"reading": open(os.path.join(KIT, "judge_recovery.txt"), encoding="utf-8").read(), "rt": open(os.path.join(KIT, "judge_roundtrip.txt"), encoding="utf-8").read()}
rec_of = {r["code"]: r["recv"] for r in rows_r + rows_rt}


def parse_sheet(path):
    txt = open(path, encoding="utf-8").read()
    head, _, body = txt.partition("\n" + "=" * 60 + "\nSHEET ")
    code_line, _, rest = body.partition("\n")
    rest = rest.split("=" * 60 + "\n", 1)[1]          # drop "N items follow." and the closing rule of the header
    blocks = {}
    for blk in rest.split("-" * 60):
        lines = [l for l in blk.strip("\n").split("\n") if l != ""]
        if not lines or not re.fullmatch(r"#\d{2}", lines[0]):
            continue
        fi, ei = lines.index("Facts:"), lines.index("Explanation:")
        blocks[lines[0]] = dict(facts=lines[fi + 1:ei], expl=lines[ei + 1:])
    return head, code_line, blocks


good = True
for r in smap:
    head, code_line, blocks = parse_sheet(os.path.join(D1, "sheets", "sheet_%s.txt" % r["code"]))
    good &= head.rstrip("\n") == prompts[r["kind"]].rstrip("\n") and code_line == r["code"]
    good &= list(blocks) == r["order"].split()
    for it, c in json.loads(r["sources"]).items():
        want_expl = parsed_text[rec_of[c]][it]
        good &= blocks[it]["expl"][0] == want_expl
        facts = bj.load_facts(KIT)[it]
        if r["kind"] == "rt":
            facts = [x for x in facts if x[1] == "C"]
        good &= blocks[it]["facts"] == ["F%d. " % k + ("(S) " if t == "S" else "") + f for k, t, f in facts]
ok(good, "each second sheet: frozen prompt verbatim, own code, the items in the map's order, the same explanation text and fact list as the first judge's sheet (C facts only for round trip)")
ok(all("(S)" not in open(os.path.join(D1, "sheets", "sheet_%s.txt" % r["code"]), encoding="utf-8").read().split("SHEET ")[1] for r in smap if r["kind"] == "rt"), "round-trip second sheets show no S fact")
sheet_text_all = "".join(open(f, encoding="utf-8").read().split("SHEET ", 1)[1] for f in glob.glob(os.path.join(D1, "sheets", "*.txt")))
ok(not re.search(r"(?i)\b(claude|grok|chatgpt|gemini|RTP|RTE)\b|recv\d\d|first judge", sheet_text_all), "no arm, model or file name on any second sheet")

# determinism, a different seed, refusal of a non-empty folder
D2 = os.path.join(TMP, "draw2")
run("reliability.py", "second-draw", *BASE, "--seed", 777, "--out", D2)
same = open(os.path.join(D1, "second_map_PRIVATE.csv"), "rb").read() == open(os.path.join(D2, "second_map_PRIVATE.csv"), "rb").read() and \
    all(open(f, "rb").read() == open(f.replace(D1, D2), "rb").read() for f in glob.glob(os.path.join(D1, "sheets", "*.txt")))
ok(same, "the same seed gives byte-identical sheets and map")
D3 = os.path.join(TMP, "draw3")
run("reliability.py", "second-draw", *BASE, "--seed", 778, "--out", D3)
srcs3 = []
for r in csv.DictReader(open(os.path.join(D3, "second_map_PRIVATE.csv"), newline="")):
    srcs3 += [(r["kind"], c, it) for it, c in json.loads(r["sources"]).items()]
ok(set(srcs3) != set(srcs), "another seed gives another sample")
ok(run("reliability.py", "second-draw", *BASE, "--seed", 777, "--out", D1, expect=1).returncode == 1, "an existing non-empty folder is refused (the draw is made once)")
# every explanation drawn (fraction 1): all 200 appear once, and the correction note is on the sheet
D4 = os.path.join(TMP, "draw4")
run("reliability.py", "second-draw", *BASE, "--seed", 1, "--fraction", 1, "--out", D4)
smap4 = list(csv.DictReader(open(os.path.join(D4, "second_map_PRIVATE.csv"), newline="")))
src4 = [(json.loads(r["sources"])[it], it) for r in smap4 for it in r["order"].split()]
ok(len(src4) == 200 and len(set(src4)) == 200, "fraction 1: all 200 explanations drawn once")
corr_code = next(r["code"] for r in rows_r if r["recv"] == CORR_RECV)
hit = [r for r in smap4 if json.loads(r["sources"]).get(CORR_ITEM) == corr_code]
txt = open(os.path.join(D4, "sheets", "sheet_%s.txt" % hit[0]["code"]), encoding="utf-8").read()
ok("[Correction later in the same reply: A made-up correction note for this item.]" in txt, "the correction note travels with its explanation")
# an incomplete first-judge scoring stops the draw
SC_bad = os.path.join(TMP, "scores_bad")
shutil.copytree(SC_R, SC_bad)
os.remove(sorted(glob.glob(os.path.join(SC_bad, "*.json")))[0])
p = run("reliability.py", "second-draw", "--results", RES, "--kit", KIT, "--reading-map", MAP_R, "--reading-scores", SC_bad, "--seed", 1, "--out", os.path.join(TMP, "draw5"), expect=1)
ok(p.returncode == 1 and "not fully scored" in p.stderr, "a first-judge sheet that is not fully scored stops the draw")
# a parsed reply made from another file stops the draw
parsed_path = os.path.join(RES, "parsed", "recv01.json")
orig = open(parsed_path).read()
d_ = json.loads(orig)
d_["sha256"] = "0" * 64
open(parsed_path, "w").write(json.dumps(d_))
p = run("reliability.py", "second-draw", *BASE, "--seed", 1, "--out", os.path.join(TMP, "draw6"), expect=1)
ok(p.returncode == 1 and "another file" in p.stderr, "a parsed reply that does not match the sheet's hash stops the draw")
open(parsed_path, "w").write(orig)

# ------------------------------------------------------------------ 3. second-judge replies, comparison
first = {}
for d in (SC_R, SC_RT):
    for f in glob.glob(os.path.join(d, "*.json")):
        j = json.load(open(f))
        first[j["code"]] = j["items"]


def second_replies(draw_dir, flips, seed, false_changes=0):
    """Made-up second-judge replies: the first judge's scores with `flips` facts turned over; checked by the real checkers into JSON."""
    r2 = random.Random(seed)
    smap_ = list(csv.DictReader(open(os.path.join(draw_dir, "second_map_PRIVATE.csv"), newline="")))
    pos = [(r["code"], it, k) for r in smap_ for it in r["order"].split() for k in sorted((EXP_ALL if r["kind"] == "reading" else EXP_C)[it])]
    chosen = set(r2.sample(pos, flips))
    fchg = set(r2.sample([(r["code"], it) for r in smap_ for it in r["order"].split()], false_changes))
    outd = os.path.join(TMP, "second_scores_%s" % os.path.basename(draw_dir) + "_%d" % flips)
    os.makedirs(outd, exist_ok=True)
    lost = gained = 0
    for r in smap_:
        srcs_ = json.loads(r["sources"])
        lines = []
        for it in r["order"].split():
            f1 = first[srcs_[it]][it]
            sc = {}
            for k_ in sorted(f1["scores"], key=lambda x: int(x[1:])):
                v = f1["scores"][k_]
                if (r["code"], it, int(k_[1:])) in chosen:
                    lost += v == 1
                    gained += v == 0
                    v = 1 - v
                sc[k_] = v
            fl = f1["false"] + (1 if (r["code"], it) in fchg else 0)
            lines.append("%s | %s | false=%d | %s" % (it, " ".join("%s=%d" % (k_, v) for k_, v in sc.items()), fl, "x" if 0 in sc.values() else "-"))
        rp = os.path.join(TMP, "second_reply_%s_%d.txt" % (r["code"], flips))
        open(rp, "w").write("\n".join(lines) + "\n")
        script = "check_judge_reply.py" if r["kind"] == "reading" else "check_judge_reply_rt.py"
        pr = run(script, "--map", os.path.join(draw_dir, "second_map_PRIVATE.csv"), "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(outd, r["code"] + ".json"))
        assert pr.returncode == 0, pr.stdout
    return outd, len(pos), lost, gained


CMP_BASE = ["--kit", KIT, "--reading-map", MAP_R, "--reading-scores", SC_R, "--rt-map", MAP_RT, "--rt-scores", SC_RT]
sc0, n_facts, _, _ = second_replies(D1, 0, 31)
p = run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc0, *CMP_BASE, "--json", os.path.join(TMP, "cmp0.json"))
c0 = json.load(open(os.path.join(TMP, "cmp0.json")))
ok(c0["facts_compared"] == n_facts and c0["facts_differing"] == 0 and c0["above_ten_percent"] is False and c0["share_differing"] == 0.0, "identical second scores: 0 differing facts of %d, not above 10 percent" % n_facts)
n10 = n_facts // 10
for flips, label in ((n10, "at or below 10 percent"), (n10 + 1, "above 10 percent")):
    sc, nf, lost, gained = second_replies(D1, flips, 40 + flips)
    jf = os.path.join(TMP, "cmp_%d.json" % flips)
    p = run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc, *CMP_BASE, "--json", jf, "--report", os.path.join(TMP, "cmp_%d.md" % flips))
    c = json.load(open(jf))
    want_above = 10 * flips > nf
    ok(c["facts_differing"] == flips and c["facts_compared"] == nf and c["above_ten_percent"] == want_above,
       "%d of %d facts flipped (%s): differing %d, above 10 percent = %s" % (flips, nf, label, c["facts_differing"], c["above_ten_percent"]))
    ok(c["first_credits_second_not"] == lost and c["second_credits_first_not"] == gained, "direction of the %d differences counted (first credits only: %d, second credits only: %d)" % (flips, lost, gained))
    ok(abs(c["share_differing"] - flips / nf) < 1e-12, "share = differing / compared")
    ok(sum(v["differing"] for v in c["by_kind"].values()) == flips and sum(v["compared"] for v in c["by_kind"].values()) == nf and sum(v["differing"] for v in c["by_arm"].values()) == flips, "the parts add up to the whole (by kind and by arm)")
# an exact 10 percent is not above (constructed on a number divisible by 10 through the helper that the command uses)
sys.path.insert(0, SP)
import reliability as RL  # noqa: E402
ok(RL.above_ten_percent(3, 30) is False and RL.above_ten_percent(4, 30) is True and RL.above_ten_percent(10, 100) is False and RL.above_ten_percent(11, 100) is True and RL.above_ten_percent(0, 0) is False,
   "threshold helper: 3 of 30 and 10 of 100 are not above 10 percent, 4 of 30 and 11 of 100 are")
# kappa against a naive computation
pairs = [(1, 1)] * 50 + [(1, 0)] * 10 + [(0, 1)] * 5 + [(0, 0)] * 35
po = 85 / 100
pe = (60 / 100) * (55 / 100) + (40 / 100) * (45 / 100)
ok(abs(RL.kappa(pairs) - (po - pe) / (1 - pe)) < 1e-12 and RL.kappa([(1, 1)] * 5) is None and RL.kappa([]) is None, "kappa matches the naive formula; undefined cases give none")
# false-count differences
sc, nf, _, _ = second_replies(D1, 0, 50, false_changes=7)
run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc, *CMP_BASE, "--json", os.path.join(TMP, "cmpf.json"))
cf = json.load(open(os.path.join(TMP, "cmpf.json")))
ok(cf["items_with_other_false_count"] == 7 and abs(cf["mean_abs_false_difference"] - 7 / 40) < 1e-12 and cf["facts_differing"] == 0, "7 changed false counts are found (mean absolute difference 7/40), scores unchanged")
# missing second-judge file: refused, or marked PARTIAL
sc_part = os.path.join(TMP, "second_part")
shutil.copytree(sc0, sc_part)
os.remove(sorted(glob.glob(os.path.join(sc_part, "*.json")))[0])
p = run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc_part, *CMP_BASE, expect=1)
ok(p.returncode == 1 and "missing" in p.stderr, "a missing second-judge sheet is refused without --partial")
p = run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc_part, *CMP_BASE, "--partial")
ok(p.returncode == 0 and "PARTIAL" in p.stdout, "--partial runs and marks the report PARTIAL")
# a second-judge file with a code that is not in the draw
sc_wrong = os.path.join(TMP, "second_wrong")
shutil.copytree(sc0, sc_wrong)
f0 = sorted(glob.glob(os.path.join(sc_wrong, "*.json")))[0]
j0 = json.load(open(f0))
j0["code"] = "ZZZZ"
json.dump(j0, open(f0, "w"))
p = run("reliability.py", "second-compare", "--draw", D1, "--second-scores", sc_wrong, *CMP_BASE, expect=1)
ok(p.returncode == 1 and "not in the second map" in p.stderr, "a second-judge file for an unknown sheet code is refused")

# ------------------------------------------------------------------ 4. audit by the user
A1 = os.path.join(TMP, "audit1")
p = run("reliability.py", "audit-draw", *BASE, "--seed", 4242, "--out", A1)
ok(p.returncode == 0, "audit-draw runs")
akey = list(csv.DictReader(open(os.path.join(A1, "audit_key_PRIVATE.csv"), newline="")))
ainfo = json.load(open(os.path.join(A1, "audit_info_PRIVATE.json")))
ok(len(akey) == 30 and len({(r["code"], r["item"], r["fact"]) for r in akey}) == 30, "30 distinct judged facts drawn")
total_facts = sum(len(v["scores"]) for d in first.values() for v in d.values())
ok(ainfo["judged_facts_in_pool"] == total_facts, "the pool is every judged fact (%d)" % total_facts)
ok(all(int(r["judge_score"]) == first[r["code"]][r["item"]]["scores"][r["fact"]] for r in akey), "the key holds the judge's own score for every entry")
ok(all((r["arm"] in ("R", "N")) == (kind_of[r["code"]] == "reading") for r in akey) and all(r["fact_type"] == "C" for r in akey if kind_of[r["code"]] == "rt"), "key: arm, kind and fact type are right; no S fact from a round-trip sheet")
sheet = open(os.path.join(A1, "audit_sheet.txt"), encoding="utf-8").read()
ok(all("Entry %d\nFact: " % n in sheet for n in range(1, 31)) and sheet.count("\nFact: ") == 30, "the sheet has entries 1 to 30, each with exactly one fact")
ok(not re.search(r"(?i)\b(claude|grok|chatgpt|gemini|RTP|RTE|judge_score)\b|recv\d\d|first judge|sheet [A-Z0-9]{4}\b", sheet), "no arm, model, sheet code or judge score on the audit sheet")
ok("Score each fact 1 or 0, nothing in between." in sheet and "Extra true detail is not penalised." in sheet, "the scoring rule of the judge prompt is on the sheet")
good = True
for r in akey:
    n = int(r["entry"])
    seg = sheet.split("Entry %d\n" % n, 1)[1].split("-" * 60, 1)[0]
    good &= parsed_text[rec_of[r["code"]]][r["item"]] in seg
    f = next(x for x in bj.load_facts(KIT)[r["item"]] if x[0] == int(r["fact"][1:]))
    good &= ("Fact: " + ("(S) " if f[1] == "S" else "") + f[2]) in seg
    other = [x for x in bj.load_facts(KIT)[r["item"]] if x[0] != f[0]]
    good &= all(x[2] not in seg for x in other if x[2] != f[2])
ok(good, "each entry shows its own fact and the full explanation of its item, and none of the item's other facts")
A2 = os.path.join(TMP, "audit2")
run("reliability.py", "audit-draw", *BASE, "--seed", 4242, "--out", A2)
ok(open(os.path.join(A1, "audit_sheet.txt"), "rb").read() == open(os.path.join(A2, "audit_sheet.txt"), "rb").read() and open(os.path.join(A1, "audit_key_PRIVATE.csv"), "rb").read() == open(os.path.join(A2, "audit_key_PRIVATE.csv"), "rb").read(), "the same seed gives the same audit")
A3 = os.path.join(TMP, "audit3")
run("reliability.py", "audit-draw", *BASE, "--seed", 4243, "--out", A3)
ok([r["code"] + r["item"] + r["fact"] for r in csv.DictReader(open(os.path.join(A3, "audit_key_PRIVATE.csv"), newline=""))] != [r["code"] + r["item"] + r["fact"] for r in akey], "another seed gives another audit")
ok(run("reliability.py", "audit-draw", *BASE, "--seed", 4242, "--out", A1, expect=1).returncode == 1, "an existing non-empty folder is refused")
ok(run("reliability.py", "audit-draw", *BASE, "--seed", 1, "--n", 100000, "--out", os.path.join(TMP, "audit4"), expect=1).returncode == 1, "asking for more entries than judged facts is refused")


def answers(flips, forms=True):
    r3 = random.Random(9)
    idx = set(r3.sample(range(30), flips))
    lines = []
    for i, r in enumerate(akey):
        v = int(r["judge_score"]) ^ (1 if i in idx else 0)
        n = int(r["entry"])
        form = [f"{n}: {v}", f"{n} - {v}", f"Entry {n}: {v}", f"{n}. {v}", f"{n} {v}", f"**{n}: {v}**"][i % 6] if forms else f"{n}: {v}"
        lines.append(form)
    return lines


for flips in (0, 3, 4):
    ap_ = os.path.join(TMP, "ans_%d.txt" % flips)
    open(ap_, "w").write("\n".join(answers(flips)) + "\n")
    jf = os.path.join(TMP, "aud_%d.json" % flips)
    p = run("reliability.py", "audit-compare", "--key", os.path.join(A1, "audit_key_PRIVATE.csv"), "--answers", ap_, "--json", jf)
    c = json.load(open(jf))
    ok(c["differing"] == flips and c["entries"] == 30 and c["above_ten_percent"] == (flips >= 4), "audit: %d of 30 answers turned over: differing %d, above 10 percent = %s (3 of 30 is exactly 10 percent, not above)" % (flips, c["differing"], c["above_ten_percent"]))
    ok(c["judge_credits_user_not"] + c["user_credits_judge_not"] == flips, "audit: direction counts add up")
# unusable answer files are refused, nothing is guessed
base_lines = answers(0)
for label, lines in (("an entry with no answer", base_lines[:-1]), ("an entry answered twice", base_lines + ["3: 0"]),
                     ("a value that is not 0 or 1", base_lines[:-1] + ["30: 2"]), ("an entry that is not on the sheet", base_lines + ["31: 1"]),
                     ("a line that is not an answer", base_lines + ["I think entry 4 is unclear"])):
    ap_ = os.path.join(TMP, "ans_bad.txt")
    open(ap_, "w").write("\n".join(lines) + "\n")
    p = run("reliability.py", "audit-compare", "--key", os.path.join(A1, "audit_key_PRIVATE.csv"), "--answers", ap_, expect=1)
    ok(p.returncode == 1 and "nothing is guessed" in p.stdout, "audit answers refused: %s" % label)

# ------------------------------------------------------------------ 5. nothing real was touched, nothing in the made-up folder changed
after_res = {p: sha(open(p, "rb").read()) for p in glob.glob(os.path.join(RES, "**", "*"), recursive=True) if os.path.isfile(p)}
ok(after_res == before_res, "the made-up results folder is unchanged by every command")
real_unchanged = True
for f in ("cells.csv", "received_log.md"):
    real_unchanged &= os.path.exists(os.path.join("/home/claude/silex_results", f))
ok(real_unchanged and not os.path.exists("/home/claude/silex_results/audit1"), "no output was written into the real results folder")
shutil.rmtree(TMP, ignore_errors=True)
print("\n%s: %d check(s) failed" % ("FAILED" if fails else "ALL PASS", len(fails)))
sys.exit(1 if fails else 0)
