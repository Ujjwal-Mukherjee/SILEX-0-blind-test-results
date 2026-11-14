#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for intake_rt.py, build_judge_sheets_rt.py and check_judge_reply_rt.py (round trip, arms RTP and RTE).
SYNTHETIC reader replies and judge replies only, in a TEMP folder; nothing real is written or scored. No key is opened.
Run:  python3 -I test_rt_tools.py [KIT]      Re-run after any change to the programs.
"""
import csv, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, HERE)
import build_roundtrip_p as brp     # noqa: E402
import build_judge_sheets as bj     # noqa: E402
import check_judge_reply_rt as cjr  # noqa: E402

TMP = tempfile.mkdtemp(prefix="rt_tools_test_")
RES = os.path.join(TMP, "res")
os.makedirs(os.path.join(RES, "parsed"))
fails = []


def ok(cond, msg, ctx=None):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)
        if ctx is not None:
            print("      context: " + str(ctx)[-700:].replace("\n", "\n      "))


def snapshot(folder):
    out = {}
    for root, _, files in os.walk(folder):
        if "__pycache__" in root:
            continue
        for f in files:
            p = os.path.join(root, f)
            st = os.stat(p)
            out[p] = (st.st_mtime_ns, st.st_size)
    return out


real_before = snapshot(REAL)
B1 = ["#%02d" % k for k in range(1, 21)]
B2 = ["#%02d" % k for k in range(21, 41)]
O1, O2 = brp.item_order(brp.DEFAULT_SEED, B1), brp.item_order(brp.DEFAULT_SEED, B2)

# a minimal results folder: the headings the log needs, an empty cell table, earlier recv files so that the counter starts at recv60
open(os.path.join(RES, "cells.csv"), "w", encoding="utf-8").write("recv,arm,model,run,batch,status,run_assumed,file,sha256_16\n")
open(os.path.join(RES, "received_log.md"), "w", encoding="utf-8").write(
    "# Received log (test)\n\n| recv | received | label | file | sha | items | batch | cell | form check |\n|---|---|---|---|---|---|---|---|---|\n"
    "| recv59 | x | x | x | x | x | x | x | x |\n\n## Form check\n\n## Metadata the protocol asks for, per reply\n\n## Handling decisions (test)\n")
for k in range(1, 60):
    open(os.path.join(RES, f"recv{k:02d}_label-old.txt"), "w").write(f"old reply {k}\n")


def reply(order, tag, words=12, over=None, extra="", head="{i}"):
    over = over or {}
    out = []
    for i in order:
        body = over[i] if i in over else f"The messages of {i} say what {tag} reads: " + " ".join(f"w{k}" for k in range(words))
        out.append(head.format(i=i) + "\n" + body)
    return "\n\n".join(out) + "\n" + extra


def intake(text, arm, chat, label, given=None, dry=False, model="grok", name="src.txt", how="attached"):
    src = os.path.join(TMP, name)
    open(src, "w", encoding="utf-8", newline="").write(text)
    cmd = [sys.executable, "-I", os.path.join(HERE, "intake_rt.py"), "--results", RES, "--src", src, "--arm", arm, "--model", model, "--chat", str(chat),
           "--label", label, "--received", "2026-11-14 12:00", "--how", how]
    if given:
        cmd += ["--given-batch", str(given)]
    if dry:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def cells():
    return list(csv.DictReader(open(os.path.join(RES, "cells.csv"), newline="", encoding="utf-8")))


# ---------- 1 intake: clean replies in packet order
rc, out = intake(reply(O1, "a1"), "RTP", 1, "RT P chat 1 packet 1", 1)
c = cells()[-1]
ok(rc == 0 and c["status"] == "data" and c["recv"] == "recv60" and (c["arm"], c["model"], c["run"], c["batch"]) == ("RTP", "grok", "1", "1"), "clean RTP reply in packet order: recv60, data, cell (RTP, grok, chat 1, batch 1)", out)
ok("packet order: True" in out and "notes: none" in out, "in packet order: no note")
f60 = glob.glob(os.path.join(RES, "recv60_*.txt"))[0]
ok(not (os.stat(f60).st_mode & 0o222) and os.path.exists(os.path.join(RES, "parsed", "recv60.json")), "saved read-only; parsed json written")
rc, out = intake(reply(B1, "b1"), "RTE", 1, "RT E chat 1 packet 1", 1)
ok(cells()[-1]["status"] == "data" and "not in the order of the packet (they are in numeric order)" in out, "numeric order: a note, still data (the packets are shuffled)", out)
rc, out = intake(reply(O2, "c2"), "RTP", 2, "RT P chat 2 packet 1 (mislabelled)", 1)
ok(cells()[-1]["status"] == "data" and cells()[-1]["batch"] == "2" and "LABEL MISMATCH" in out, "the item numbers decide the batch; a label mismatch is noted")

# ---------- 2 holds
rc, out = intake(reply(O1[:19], "d"), "RTP", 3, "RT P chat 3 packet 1")
ok(cells()[-1]["status"] == "review" and "ITEMS: found 19" in out, "19 items: held")
rc, out = intake(reply(O1, "e", over={"#05": " ".join(["word"] * 130)}), "RTP", 4, "RT P chat 4 packet 1")
ok(cells()[-1]["status"] == "review" and "OVER 120 WORDS" in out, "130 words in one item: held")
rc, out = intake(reply(O1, "f", over={"#07": "I used a web search to find it."}), "RTE", 2, "RT E chat 2 packet 1")
ok(cells()[-1]["status"] == "review" and "SEARCH-LIKE WORDS" in out, "search-like words: held")
guide_text = "The guide says in section 7 that the pinned pack decides this."
rc, out = intake(reply(O1, "g", over={"#09": guide_text}), "RTE", 3, "RT E chat 3 packet 1")
ok(cells()[-1]["status"] == "review" and "GUIDE WORDS IN AN RTE REPLY" in out, "guide words in an RTE reply: held")
rc, out = intake(reply(O1, "h", over={"#09": guide_text}), "RTP", 3, "RT P chat 3 packet 1 (guide words)")
ok(cells()[-1]["status"] == "data" and "GUIDE WORDS" not in out, "the same words in an RTP reply (the reader has the guide): not held")
rc, out = intake(reply(O1, "i") + "\nCorrection: item #03 is only mentioned, not asserted.\n", "RTP", 4, "RT P chat 4 packet 1 (trailer)")
ok("TRAILER after the last item" in out, "a trailer is noted (corrections.json before sheets)")
last_tr = cells()[-1]["recv"]

# ---------- 3 duplicate, conflict, dry run
text = reply(O1, "a1")
rc, out = intake(text, "RTP", 1, "RT P chat 1 packet 1 again")
ok(cells()[-1]["status"] == "duplicate-of-recv60" and "DUPLICATE" in out, "a byte-identical re-send is a duplicate")
rc, out = intake(reply(O1, "a1-rerun"), "RTP", 1, "RT P chat 1 packet 1 re-run")
ok(cells()[-1]["status"] == "conflict" and "CELL ALREADY FILLED" in out, "another reply for a filled cell is a conflict")
before = sorted(os.listdir(RES))
rc, out = intake(reply(O2, "z"), "RTP", 4, "dry", dry=True)
ok(rc == 0 and sorted(os.listdir(RES)) == before and "dry run" in out, "a dry run writes nothing")
log = open(os.path.join(RES, "received_log.md"), encoding="utf-8").read()
ok("RTP-grok-chat1-b1" in log and "reader Grok, chat 1" in log, "the log holds the cell and the form-check paragraph")

# ---------- 4 STEP 2
def step2(txt, arm="RTP", chat=1):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "intake_rt.py"), "--results", RES, "--step2", txt, "--arm", arm, "--model", "grok", "--chat", str(chat), "--received", "12:01"],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


rc, out = step2("104 roots, section 7.")
ok(rc == 0 and "CORRECT" in out, "STEP 2 right answer is accepted and logged")
rc, out = step2("It has 105 roots, section 6.")
ok(rc == 0 and "WRONG" in out and "start a new chat once" in out, "STEP 2 wrong answer is flagged")
rc, out = step2("104 roots, section 7", arm="RTE")
ok(rc != 0 and "STEP 2 belongs to RTP" in out, "STEP 2 for an RTE chat is refused")
log = open(os.path.join(RES, "received_log.md"), encoding="utf-8").read()
ok("Reader Grok, arm RTP, chat 1: STEP 2 answer given 12:01, correct" in log, "STEP 2 line in the log")

# ---------- 5 judge sheets
# the data rows made above (clean replies of both arms, a mislabelled one, one with a trailer) become sheets
data_rows = [r for r in cells() if r["status"] == "data"]
trailer_row = [r for r in data_rows if r["recv"] == last_tr]
if trailer_row:
    json.dump({"_note": "test", last_tr: {"items": {"#03": "Correction: item #03 is only mentioned, not asserted."}}}, open(os.path.join(RES, "corrections.json"), "w"))
SH = os.path.join(TMP, "sheets_out")
p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build_judge_sheets_rt.py"), "--results", RES, "--kit", KIT, "--out", SH, "--seed", "99"], capture_output=True, text=True)
ok(p.returncode == 0, "round-trip judge sheets build", p.stdout + p.stderr)
m = list(csv.DictReader(open(os.path.join(SH, "sheets_map_PRIVATE.csv"), newline="", encoding="utf-8")))
ok(len(m) == len(data_rows) and {r["arm"] for r in m} == {"RTP", "RTE"}, "one sheet per data reply of both arms", (len(m), len(data_rows)))
prompt = open(os.path.join(KIT, "judge_roundtrip.txt"), encoding="utf-8").read()
allf = bj.load_facts(KIT)
cf = {it: [(k, t, f) for k, t, f in lst if t == "C"] for it, lst in allf.items()}
for r in m:
    txt = open(os.path.join(SH, "sheets", f"sheet_{r['code']}.txt"), encoding="utf-8").read()
    ok(txt.startswith(prompt.rstrip("\n")), f"sheet {r['code']}: starts with judge_roundtrip.txt verbatim")
    ok(not re.search(r"(?i)\(S\)|\bRTP\b|\bRTE\b|\bchat\b|\bgrok\b|\bpacket\b|\brecv", txt.split("=" * 60, 1)[1]), f"sheet {r['code']}: no S-fact mark, arm, chat, reader or file label below the prompt")
    items = r["order"].split()
    ok(sorted(items) == (B1 if r["batch"] == "1" else B2) and len(items) == 20, f"sheet {r['code']}: 20 items of its batch")
    shows = {}
    for blk in txt.split("\n" + "-" * 60 + "\n"):
        mm = re.search(r"(?m)^(#\d{2})\nFacts:\n(.*?)\nExplanation:", blk, flags=re.S)
        if mm:
            shows[mm.group(1)] = re.findall(r"(?m)^F(\d+)\. ", mm.group(2))
    ok(all([int(k) for k in shows[i]] == [k for k, _, _ in cf[i]] for i in items), f"sheet {r['code']}: each item shows exactly its C facts with their own numbers")
order_file = open(os.path.join(SH, "judge_order_PRIVATE.txt"), encoding="utf-8").read()
ok(all(r["code"] in order_file for r in m), "the presentation order lists every sheet code")

# ---------- 6 judge reply checker
code = m[0]["code"]
items = m[0]["order"].split()
exp = cjr.expected_c_facts(KIT)


def judge_lines(its, drop=None, extra=None):
    lines = []
    for it in its:
        ks = sorted(exp[it])
        if drop and drop[0] == it:
            ks = [k for k in ks if k != drop[1]]
        if extra and extra[0] == it:
            ks = ks + [extra[1]]
        lines.append(f"{it} | " + " ".join(f"F{k}=1" for k in ks) + " | false=0 | ")
    return "\n".join(lines) + "\n"


def run_check(text, name):
    path = os.path.join(TMP, name)
    open(path, "w", encoding="utf-8").write(text)
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "check_judge_reply_rt.py"), "--map", os.path.join(SH, "sheets_map_PRIVATE.csv"), "--kit", KIT, "--code", code, "--reply", path],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


rc, out = run_check(judge_lines(items), "j_ok.txt")
ok(rc == 0 and "status: clean" in out, "a judge reply that scores exactly the C facts is clean", out)
s_item = next(i for i in items if any(t == "S" for _, t, _ in allf[i]))
s_k = next(k for k, t, _ in allf[s_item] if t == "S")
rc, out = run_check(judge_lines(items, extra=(s_item, s_k)), "j_s.txt")
ok(rc == 1 and "facts differ from the sheet" in out and s_item in out, "a reply that scores an S fact makes that item redo", out)
c_item = items[0]
rc, out = run_check(judge_lines(items, drop=(c_item, sorted(exp[c_item])[0])), "j_drop.txt")
ok(rc == 1 and "missing" in out and c_item in out, "a reply that leaves out a C fact makes that item redo", out)

# ---------- 7 the real folder is untouched
real_after = snapshot(REAL)
changed = [k for k in set(real_before) | set(real_after) if real_before.get(k) != real_after.get(k)]
ok(not changed, "the real results folder is unchanged by the tests", changed[:5])

shutil.rmtree(TMP, ignore_errors=True)
print()
print("ALL %s" % ("PASS" if not fails else f"DONE, {len(fails)} FAIL"))
sys.exit(1 if fails else 0)
