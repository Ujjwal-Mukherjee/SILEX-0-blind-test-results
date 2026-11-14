#!/usr/bin/env python3
"""Tests for stage_judging.py and collect_judge_replies.py on SYNTHETIC sheets and replies only, in temporary folders.
Nothing real is touched; the kit's facts.csv is only read.
Usage: python3 -I test_judging_stage.py [KIT]"""
import csv, glob, hashlib, json, os, random, re, shutil, stat, subprocess, sys, tempfile

SP = os.path.dirname(os.path.abspath(__file__))
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, SP)
import build_judge_sheets as bj  # noqa: E402
import check_judge_reply as cj  # noqa: E402
import check_judge_reply_rt as cjr  # noqa: E402

TMP = tempfile.mkdtemp(prefix="stage_test_")
fails = []


def ok(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def run(script, *args, expect=0):
    p = subprocess.run([sys.executable, "-I", os.path.join(SP, script)] + [str(x) for x in args], capture_output=True, text=True)
    if p.returncode != expect:
        print("   unexpected exit %d for %s\n   stdout: %s\n   stderr: %s" % (p.returncode, script, p.stdout[-300:], p.stderr[-300:]))
    return p


def sha(b):
    return hashlib.sha256(b).hexdigest()


rng = random.Random(33)
codes_a = sorted({"".join(rng.choice(bj.ALPHABET) for _ in range(4)) for _ in range(30)})[:14]
codes_b = [c for c in sorted({"".join(rng.choice(bj.ALPHABET) for _ in range(4)) for _ in range(40)}) if c not in codes_a][:9]
for d, cs in (("sheets_a", codes_a), ("sheets_b", codes_b)):
    os.makedirs(os.path.join(TMP, d))
    for c in cs:
        open(os.path.join(TMP, d, "sheet_%s.txt" % c), "w").write("frozen prompt\nSHEET %s\n%s\n" % (c, "x" * rng.randrange(50, 300)))
ALL = set(codes_a) | set(codes_b)

# ---------------------------------------------------------------- stage_judging
W1, G1 = os.path.join(TMP, "work1"), os.path.join(TMP, "groups1")
p = run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), os.path.join(TMP, "sheets_b"), "--workdir", W1, "--groups", G1, "--seed", 9, "--per-agent", 6)
ok(p.returncode == 0, "stage_judging runs (23 sheets, at most 6 per agent)")
rows = list(csv.DictReader(open(os.path.join(G1, "groups_PRIVATE.csv"), newline="")))
sizes = [int(r["n"]) for r in rows]
ok(sum(sizes) == 23 and max(sizes) <= 6 and max(sizes) - min(sizes) <= 1 and len(rows) == 4, "4 groups, sizes %s: none above 6, as equal as possible" % sizes)
allc = [c for r in rows for c in r["codes"].split()]
ok(sorted(allc) == sorted(ALL) and len(allc) == len(set(allc)), "every sheet is in exactly one group")
ok(sorted(os.listdir(W1)) == ["inbox", "outbox"] and os.listdir(os.path.join(W1, "outbox")) == [], "the work folder holds only inbox and an empty outbox")
inb = sorted(os.listdir(os.path.join(W1, "inbox")))
ok(inb == sorted("sheet_%s.txt" % c for c in ALL), "inbox: one file per sheet, nothing else")
same = all(open(os.path.join(W1, "inbox", f), "rb").read() == open(glob.glob(os.path.join(TMP, "sheets_?", f))[0], "rb").read() for f in inb)
ok(same and all(not (os.stat(os.path.join(W1, "inbox", f)).st_mode & stat.S_IWUSR) for f in inb), "inbox files are byte-identical, read-only copies")
pr = open(os.path.join(G1, "group_01_prompt.txt"), encoding="utf-8").read()
c1 = rows[0]["codes"].split()
ok(pr.count("sheet_") == len(c1) and all("sheet_%s.txt -> %s/reply_%s.txt" % (c, os.path.join(W1, "outbox"), c) in pr for c in c1), "prompt of group 1 lists exactly its own sheets with their reply files")
ok("Do not read or list any other file or folder" in pr and "answer with the single word: done" in pr and ("You have %d tasks" % len(c1)) in pr, "the prompt carries the fixed wrapper (own files only, no other tool, answer 'done')")
ok(not re.search(r"(?i)\b(claude|grok|chatgpt|gemini|RTP|RTE|round trip|reading test)\b|PRIVATE|sheets_map|\.csv", pr), "no model, arm, map or key word in any prompt")
for g in range(2, 5):
    pg = open(os.path.join(G1, "group_%02d_prompt.txt" % g), encoding="utf-8").read()
    assert not (set(rows[g - 1]["codes"].split()) & set(c1))
ok(sorted(os.listdir(G1)) == ["group_01_prompt.txt", "group_02_prompt.txt", "group_03_prompt.txt", "group_04_prompt.txt", "groups_PRIVATE.csv", "stage_info_PRIVATE.json"], "groups folder: four prompts, the private list, the info file")
W2, G2 = os.path.join(TMP, "work2"), os.path.join(TMP, "groups2")
run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), os.path.join(TMP, "sheets_b"), "--workdir", W2, "--groups", G2, "--seed", 9, "--per-agent", 6)
ok(open(os.path.join(G1, "groups_PRIVATE.csv")).read() == open(os.path.join(G2, "groups_PRIVATE.csv")).read() and all(open(os.path.join(G1, f"group_0{i}_prompt.txt")).read().replace(W1, "W") == open(os.path.join(G2, f"group_0{i}_prompt.txt")).read().replace(W2, "W") for i in range(1, 5)), "the same seed gives the same groups and prompts")
W3, G3 = os.path.join(TMP, "work3"), os.path.join(TMP, "groups3")
run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), os.path.join(TMP, "sheets_b"), "--workdir", W3, "--groups", G3, "--seed", 10, "--per-agent", 6)
ok(open(os.path.join(G1, "groups_PRIVATE.csv")).read() != open(os.path.join(G3, "groups_PRIVATE.csv")).read(), "another seed gives other groups")
ok(run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), "--workdir", W1, "--groups", os.path.join(TMP, "g9"), "--seed", 1, expect=1).returncode == 1, "a non-empty work folder is refused")
os.makedirs(os.path.join(TMP, "dup"))
shutil.copy(os.path.join(TMP, "sheets_a", "sheet_%s.txt" % codes_a[0]), os.path.join(TMP, "dup"))
ok(run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), os.path.join(TMP, "dup"), "--workdir", os.path.join(TMP, "w9"), "--groups", os.path.join(TMP, "g8"), "--seed", 1, expect=1).returncode == 1, "the same sheet code in two folders is refused")
os.makedirs(os.path.join(TMP, "odd"))
open(os.path.join(TMP, "odd", "map.csv"), "w").write("x")
ok(run("stage_judging.py", "--sheets", os.path.join(TMP, "odd"), "--workdir", os.path.join(TMP, "w7"), "--groups", os.path.join(TMP, "g7"), "--seed", 1, expect=1).returncode == 1, "a file that is not a sheet in the sheet folder is refused")
q = run("stage_judging.py", "--sheets", os.path.join(TMP, "sheets_a"), "--workdir", os.path.join(TMP, "w6"), "--groups", os.path.join(TMP, "g6"), "--seed", 3, "--per-agent", 13)
r6 = list(csv.DictReader(open(os.path.join(TMP, "g6", "groups_PRIVATE.csv"), newline="")))
ok([int(r["n"]) for r in r6] == [7, 7], "14 sheets at most 13 per agent: two groups of 7, not 13 and 1")

# ---------------------------------------------------------------- collect_judge_replies
EXP_ALL, EXP_C = cj.expected_facts(KIT), cjr.expected_c_facts(KIT)
ITEMS1 = bj.BATCH_ITEMS[1]
MAP = os.path.join(TMP, "map.csv")
mrows = []
cr, ct = "AAA2", "BBB3"
for code, arm in ((cr, "R"), (ct, "RTP"), ("CCC4", "R"), ("DDD5", "RTE"), ("EEE6", "N"), ("FFF7", "R")):
    mrows.append(dict(code=code, arm=arm, order=" ".join(ITEMS1)))
with open(MAP, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["code", "arm", "order"])
    w.writeheader()
    w.writerows(mrows)
OB, REP, SC = os.path.join(TMP, "outbox"), os.path.join(TMP, "replies"), os.path.join(TMP, "scores")
os.makedirs(OB)


def reply(kind, rng2, skip=None, extra=None, header=False):
    exp = EXP_ALL if kind == "reading" else EXP_C
    lines, truth = [], {}
    for it in ITEMS1:
        sc = {k: rng2.choice([0, 1, 1]) for k in sorted(exp[it])}
        fl = rng2.choice([0, 1])
        truth[it] = dict(scores={"F%d" % k: v for k, v in sc.items()}, false=fl)
        if it == skip:
            continue
        lines.append("%s | %s | false=%d | %s" % (it, " ".join("F%d=%d" % (k, v) for k, v in sc.items()), fl, "reason words" if 0 in sc.values() else "-"))
    if extra:
        lines.append(extra)
    return ("SHEET\n" if header else "") + "\n".join(lines) + "\n", truth


txt, t_clean = reply("reading", random.Random(1))
open(os.path.join(OB, "reply_%s.txt" % cr), "w").write(txt)
txt, t_rt = reply("rt", random.Random(2))
open(os.path.join(OB, "reply_%s.txt" % ct), "w").write(txt)
txt, _ = reply("reading", random.Random(3), header=True)               # a heading line: note only
open(os.path.join(OB, "reply_CCC4.txt"), "w").write(txt)
txt, _ = reply("rt", random.Random(4))
open(os.path.join(OB, "reply_DDD5.txt"), "w").write(txt)                # round trip sheet but the reply scores S facts too? built below
txt, _ = reply("reading", random.Random(5), skip="#07")                 # one item line missing: redo
open(os.path.join(OB, "reply_EEE6.txt"), "w").write(txt)
# FFF7 gets no reply file at all
CK = ["--outbox", OB, "--map", MAP, "--kit", KIT, "--replies", REP, "--scores", SC]
p = run("collect_judge_replies.py", *CK, expect=1)
out = p.stdout
ok(p.returncode == 1, "exit 1: one sheet is missing and one needs a redo")
ok("%s: 20 of 20 items usable; status: clean" % cr in out and "%s: 20 of 20 items usable; status: clean" % ct in out, "clean replies are collected (reading and round trip)")
ok("CCC4: 20 of 20 items usable; status: notes" in out, "a heading line in the reply gives status notes, all items usable")
ok("EEE6: 19 of 20 items usable; status: redo" in out and "ask the judge again for: #07" in out, "a missing item line gives status redo for that item only")
ok("FFF7: MISSING" in out, "a sheet without a reply file is listed as missing")
ok(not re.search(r"F\d+\s*=\s*[01]|false\s*=|reason words", out), "nothing printed shows a score, a false count or a reason")
j = json.load(open(os.path.join(SC, cr + ".json")))
def core(items):
    return {it: dict(scores=v["scores"], false=v["false"]) for it, v in items.items()}


ok(j["code"] == cr and j["status"] == "clean" and core(j["items"]) == t_clean, "JSON of a clean reading sheet: the scores are exactly those written")
j = json.load(open(os.path.join(SC, ct + ".json")))
ok(core(j["items"]) == t_rt, "JSON of a round-trip sheet: C facts only, scores exactly as written")
ok(os.path.exists(os.path.join(SC, "EEE6.json")) and len(json.load(open(os.path.join(SC, "EEE6.json")))["items"]) == 19, "the redo sheet keeps its 19 usable items in its JSON")
ok(all(open(os.path.join(REP, "reply_%s.txt" % c), "rb").read() == open(os.path.join(OB, "reply_%s.txt" % c), "rb").read() for c in (cr, ct, "CCC4", "DDD5", "EEE6")), "collected replies are byte-identical copies")
ok(all(not (os.stat(os.path.join(REP, "reply_%s.txt" % c)).st_mode & stat.S_IWUSR) for c in (cr, ct)), "collected replies are read-only")
lg = list(csv.DictReader(open(os.path.join(REP, "collected_log.csv"), newline="")))
ok(len(lg) == 5 and {r["code"]: r["status"] for r in lg}["EEE6"] == "redo" and all(r["sha256"] == sha(open(os.path.join(OB, "reply_%s.txt" % r["code"]), "rb").read()) for r in lg), "collected_log.csv has a row per collected reply with its sha256 and status")
# a second run: collected replies are skipped, a changed outbox file is not collected
p = run("collect_judge_replies.py", *CK, expect=1)
ok(p.stdout.count("already collected, unchanged") == 5, "a second run skips the five collected replies")
open(os.path.join(OB, "reply_%s.txt" % cr), "a").write("# edited\n")
p = run("collect_judge_replies.py", *CK, expect=1)
ok("%s: the outbox file differs from the collected reply; NOT collected" % cr in p.stdout, "an outbox file that changed after collection is not collected")
ok(open(os.path.join(REP, "reply_%s.txt" % cr), "rb").read() != open(os.path.join(OB, "reply_%s.txt" % cr), "rb").read() and core(json.load(open(os.path.join(SC, cr + ".json")))["items"]) == t_clean, "the collected copy and its JSON stay as first collected")
# a reply that scores an S fact on a round-trip sheet is a redo for that item
S_ITEM = next(it for it in ITEMS1 if len(EXP_ALL[it]) > len(EXP_C[it]))
lines = []
for it in ITEMS1:
    ks = sorted(EXP_ALL[it] if it == S_ITEM else EXP_C[it])
    lines.append("%s | %s | false=0 | -" % (it, " ".join("F%d=1" % k for k in ks)))
txt, _ = reply("reading", random.Random(6))
open(os.path.join(OB, "reply_FFF7.txt"), "w").write(txt)
p = run("collect_judge_replies.py", *CK, "--codes", "FFF7", expect=0)           # FFF7 is a reading sheet: S facts are expected, so this is clean
ok("FFF7: 20 of 20 items usable; status: clean" in p.stdout, "a reading sheet reply with S facts is clean")
MAP2 = os.path.join(TMP, "map2.csv")
with open(MAP2, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["code", "kind", "order"])
    w.writeheader()
    w.writerow(dict(code="GGG8", kind="rt", order=" ".join(ITEMS1)))
open(os.path.join(OB, "reply_GGG8.txt"), "w").write("\n".join(lines) + "\n")
p = run("collect_judge_replies.py", "--outbox", OB, "--map", MAP2, "--kit", KIT, "--replies", REP, "--scores", os.path.join(TMP, "scores2"), expect=1)
ok("GGG8: 19 of 20 items usable; status: redo" in p.stdout and "ask the judge again for: %s" % S_ITEM in p.stdout, "a map with a kind column: a round-trip reply that scores an S fact is a redo for that item")
ok(run("collect_judge_replies.py", *CK, "--codes", "NOPE", expect=2).returncode == 2, "an unknown --codes entry is a usage error")
# ---------------------------------------------------------------- audit_agent_transcript
PROMPT1 = os.path.join(G1, "group_01_prompt.txt")
inbox1, outbox1 = os.path.join(W1, "inbox"), os.path.join(W1, "outbox")


def transcript(calls, name, model="claude-fable-5-2"):
    lines = [json.dumps({"type": "user", "message": {"role": "user", "content": "task"}}),
             json.dumps({"type": "attachment", "attachment": {"type": "environment"}})]
    for tool, inp in calls:
        lines.append(json.dumps({"type": "assistant", "message": {"model": model, "content": [{"type": "thinking", "thinking": "..."}, {"type": "tool_use", "id": "t", "name": tool, "input": inp}]}}))
        lines.append(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "SECRET SHEET TEXT"}]}}))
    pth = os.path.join(TMP, name)
    open(pth, "w").write("\n".join(lines) + "\n")
    return pth


good_calls = []
for c in c1:
    good_calls.append(("Read", {"file_path": os.path.join(inbox1, "sheet_%s.txt" % c)}))
    good_calls.append(("Write", {"file_path": os.path.join(outbox1, "reply_%s.txt" % c), "content": "..."}))
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls, "t_good.jsonl"), "--prompt", PROMPT1)
ok(p.returncode == 0 and ("tool calls: %d (reads of own sheets %d of %d, writes of own replies %d of %d)" % (2 * len(c1), len(c1), len(c1), len(c1), len(c1))) in p.stdout and "FLAGGED" not in p.stdout, "an agent that only read its sheets and wrote its replies passes")
ok("SECRET" not in p.stdout, "the audit never prints transcript contents")
ok("models named in the transcript: claude-fable-5-2 x%d" % (2 * len(c1)) in p.stdout, "the model named in the transcript is reported")
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls, "t_m1.jsonl"), "--prompt", PROMPT1, "--expect-model", "claude-fable-5-2")
ok(p.returncode == 0 and "FLAGGED" not in p.stdout, "the expected model passes")
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls, "t_m2.jsonl", model="claude-opus-5-5"), "--prompt", PROMPT1, "--expect-model", "claude-fable-5-2", expect=1)
ok(p.returncode == 1 and "FLAGGED: model" in p.stdout, "another model than the expected one is flagged")
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls, "t_m3.jsonl", model=None), "--prompt", PROMPT1, "--expect-model", "claude-fable-5-2", expect=1)
ok(p.returncode == 1 and "no model" in p.stdout, "a transcript that names no model is flagged when a model is expected")
reread = good_calls + [("Read", {"file_path": os.path.join(outbox1, "reply_%s.txt" % c1[0])})]
p = run("audit_agent_transcript.py", "--transcript", transcript(reread, "t_reread.jsonl"), "--prompt", PROMPT1)
ok(p.returncode == 0, "reading back its own reply file is allowed")
other = [x for x in rows[1]["codes"].split()][0]
for label, extra in (("a sheet of another group", ("Read", {"file_path": os.path.join(inbox1, "sheet_%s.txt" % other)})),
                     ("a file outside inbox and outbox", ("Read", {"file_path": "/home/claude/silex_results/judging/sheets_map_PRIVATE.csv"})),
                     ("a Bash call", ("Bash", {"command": "ls /home/claude"})),
                     ("a Glob call", ("Glob", {"pattern": "**/*"})),
                     ("a write of another reply file", ("Write", {"file_path": os.path.join(outbox1, "reply_%s.txt" % other), "content": "x"})),
                     ("a web search", ("WebSearch", {"query": "silex"}))):
    p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls + [extra], "t_bad.jsonl"), "--prompt", PROMPT1, expect=1)
    ok(p.returncode == 1 and "FLAGGED: %s" % extra[0] in p.stdout, "flagged: %s" % label)
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls[:-1], "t_short.jsonl"), "--prompt", PROMPT1, expect=1)
ok(p.returncode == 1 and "reply never written" in p.stdout, "a reply that was never written is reported")
p = run("audit_agent_transcript.py", "--transcript", transcript(good_calls[1:], "t_short2.jsonl"), "--prompt", PROMPT1, expect=1)
ok(p.returncode == 1 and "sheet never read" in p.stdout, "a sheet that was never read is reported")
ok(run("audit_agent_transcript.py", "--transcript", os.path.join(TMP, "none.jsonl"), "--prompt", PROMPT1, expect=2).returncode == 2, "a missing transcript is a usage problem")

# ---------------------------------------------------------------- make_redo_sheet and the redo pass of collect_judge_replies
facts_all = bj.load_facts(KIT)
prompt_r = open(os.path.join(KIT, "judge_recovery.txt"), encoding="utf-8").read()
rr = random.Random(77)
order_full = ITEMS1[:]
rr.shuffle(order_full)
expl = {it: "Synthetic explanation of %s, serial %d." % (it, rr.randrange(10 ** 6)) for it in ITEMS1}
notes = {"#12": ["A made-up correction note."]}
sheet_full = bj.sheet_text(prompt_r, "RDO1", order_full, facts_all, expl, notes)
os.makedirs(os.path.join(TMP, "redo_in"))
open(os.path.join(TMP, "redo_in", "sheet_RDO1.txt"), "w", encoding="utf-8", newline="\n").write(sheet_full)
RMAP = os.path.join(TMP, "redo_map.csv")
with open(RMAP, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["code", "arm", "n_items", "order", "sheet_sha16"])
    w.writeheader()
    w.writerow(dict(code="RDO1", arm="R", n_items=20, order=" ".join(order_full), sheet_sha16="x"))
want_items = ["#12", "#03", "#07"]
p = run("make_redo_sheet.py", "--sheet", os.path.join(TMP, "redo_in", "sheet_RDO1.txt"), "--map", RMAP, "--code", "RDO1", "--items", " ".join(want_items),
        "--out-sheets", os.path.join(TMP, "redo_out"), "--out-map", os.path.join(TMP, "redo_out_map.csv"))
ok(p.returncode == 0, "make_redo_sheet runs")
kept_order = [it for it in order_full if it in want_items]
expected_text = bj.sheet_text(prompt_r, "RDO1", kept_order, facts_all, expl, notes)
got_text = open(os.path.join(TMP, "redo_out", "sheet_RDO1.txt"), encoding="utf-8").read()
ok(got_text == expected_text, "the redo sheet is exactly the sheet the builder would make for those items in the sheet's own order (prompt, code, facts, explanations, correction note, header count)")
ok("3 items follow." in got_text and got_text.startswith(prompt_r.rstrip("\n")), "the header says 3 items follow and the frozen prompt is verbatim at the top")
rm = list(csv.DictReader(open(os.path.join(TMP, "redo_out_map.csv"), newline="")))
ok(len(rm) == 1 and rm[0]["code"] == "RDO1" and rm[0]["order"].split() == kept_order and rm[0]["n_items"] == "3", "the redo map keeps the code and the arm, and lists the redo items in the sheet's order")
for label, items_, expect_msg in (("an item that is not on the sheet", "#07 #99", "distinct items"), ("a repeated item", "#07 #07", "distinct items"), ("no items", "", "distinct items")):
    q = run("make_redo_sheet.py", "--sheet", os.path.join(TMP, "redo_in", "sheet_RDO1.txt"), "--map", RMAP, "--code", "RDO1", "--items", items_,
            "--out-sheets", os.path.join(TMP, "redo_bad"), "--out-map", os.path.join(TMP, "redo_bad_map.csv"), expect=1)
    ok(q.returncode == 1 and expect_msg in q.stderr, "refused: %s" % label)
q = run("make_redo_sheet.py", "--sheet", os.path.join(TMP, "redo_in", "sheet_RDO1.txt"), "--map", RMAP, "--code", "RDO1", "--items", "#07",
        "--out-sheets", os.path.join(TMP, "redo_out"), "--out-map", os.path.join(TMP, "redo_out_map2.csv"), expect=1)
ok(q.returncode == 1 and "exists already" in q.stderr, "an existing redo sheet is not overwritten")
bad_sheet = os.path.join(TMP, "redo_in2")
os.makedirs(bad_sheet)
open(os.path.join(bad_sheet, "sheet_RDO1.txt"), "w", encoding="utf-8").write(sheet_full.replace("-" * 60 + "\n", "", 1))
q = run("make_redo_sheet.py", "--sheet", os.path.join(bad_sheet, "sheet_RDO1.txt"), "--map", RMAP, "--code", "RDO1", "--items", "#07", "--out-sheets", os.path.join(TMP, "redo_bad2"), "--out-map", os.path.join(TMP, "m3.csv"), expect=1)
ok(q.returncode == 1, "a sheet file that does not match its map's items is refused")
# first reply with two item lines missing, then the redo reply, collected with --suffix
OB1, OB2 = os.path.join(TMP, "ob_first"), os.path.join(TMP, "ob_redo")
os.makedirs(OB1)
os.makedirs(OB2)
exp_all = EXP_ALL


def lines_for(its, rng2):
    out, truth = [], {}
    for it in its:
        sc = {k: rng2.choice([0, 1, 1]) for k in sorted(exp_all[it])}
        out.append("%s | %s | false=0 | %s" % (it, " ".join("F%d=%d" % (k, v) for k, v in sc.items()), "x" if 0 in sc.values() else "-"))
        truth[it] = {"F%d" % k: v for k, v in sc.items()}
    return out, truth


first_lines, t1 = lines_for([it for it in order_full if it not in ("#07", "#12")], random.Random(8))
open(os.path.join(OB1, "reply_RDO1.txt"), "w").write("\n".join(first_lines) + "\n")
REP2, SC2 = os.path.join(TMP, "replies_x"), os.path.join(TMP, "scores_x")
p = run("collect_judge_replies.py", "--outbox", OB1, "--map", RMAP, "--kit", KIT, "--replies", REP2, "--scores", SC2, expect=1)
ok("RDO1: 18 of 20 items usable; status: redo" in p.stdout and "ask the judge again for: #07 #12" in p.stdout, "the first reply of the sheet: 18 usable, #07 and #12 to redo")
redo_lines, t2 = lines_for(["#12", "#07"], random.Random(9))
open(os.path.join(OB2, "reply_RDO1.txt"), "w").write("\n".join(redo_lines) + "\n")
p = run("collect_judge_replies.py", "--outbox", OB2, "--map", os.path.join(TMP, "redo_out_map.csv"), "--kit", KIT, "--replies", REP2, "--scores", SC2, "--suffix", "_redo1", expect=1)
ok("RDO1: 3 of 3" not in p.stdout and "RDO1: 2 of 3 items usable; status: redo" in p.stdout and "ask the judge again for: #03" in p.stdout, "the redo map lists 3 items (#03 was also asked here), so a redo reply that answers only 2 is again a redo for the missing one")
ok(sorted(os.listdir(REP2)) == ["collected_log.csv", "reply_RDO1.txt", "reply_RDO1_redo1.txt"], "the redo reply is stored next to the first one under its own name")
j1 = json.load(open(os.path.join(SC2, "RDO1.json")))
j2 = json.load(open(os.path.join(SC2, "RDO1_redo1.json")))
ok(j1["code"] == "RDO1" and j2["code"] == "RDO1", "both JSON files carry the sheet's own code (the aggregator and the reliability tools merge by that code)")
ok(set(j1["items"]) == set(ITEMS1) - {"#07", "#12"} and set(j2["items"]) == {"#07", "#12"} and not (set(j1["items"]) & set(j2["items"])), "first JSON holds the 18 usable items, the redo JSON the 2 redone ones; no item is in both")
ok({it: v["scores"] for it, v in j1["items"].items()} == t1 and {it: v["scores"] for it, v in j2["items"].items()} == t2, "the scores in both files are exactly those written")
lg2 = list(csv.DictReader(open(os.path.join(REP2, "collected_log.csv"), newline="")))
ok([r["code"] for r in lg2] == ["RDO1", "RDO1_redo1"], "the log has one row for the first reply and one for the redo reply")
ok(run("collect_judge_replies.py", "--outbox", OB2, "--map", RMAP, "--kit", KIT, "--replies", REP2, "--scores", SC2, "--suffix", "REDO", expect=2).returncode == 2, "a malformed --suffix is a usage error")

shutil.rmtree(TMP, ignore_errors=True)
print("\n%s: %d check(s) failed" % ("FAILED" if fails else "ALL PASS", len(fails)))
sys.exit(1 if fails else 0)
