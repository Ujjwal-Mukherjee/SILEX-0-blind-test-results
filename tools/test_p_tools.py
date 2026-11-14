#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for parse_p_reply.py, intake_p.py and check_p.py. Everything runs in a TEMP folder; no real result file is read except the pilot reply (copied), and nothing real is written.
Test replies are made from the 40 gold items (read from the private kit zip) and from the pilot reply, with mutations made only for the test.
Run:  python3 -I test_p_tools.py [KIT]      Re-run after any change to the three programs.
"""
import csv, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, HERE)
import parse_p_reply as pp  # noqa: E402

TMP = tempfile.mkdtemp(prefix="p_tools_test_")
RES = os.path.join(TMP, "res")
os.makedirs(RES)
fails = []


def ok(cond, msg, ctx=None):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)
        if ctx is not None:
            print("      context: " + str(ctx)[-700:].replace("\n", "\n      "))


# ---------- material: gold items by item id
z = zipfile.ZipFile(os.path.join(KIT, "silex_kit_PRIVATE.zip"))
gold_md = z.read("silex_kit/gold_blocks.md").decode("utf-8")
by_key = dict(re.findall(r"<!-- item (\w+) -->\n```silex\n(.*?)\n```", gold_md, flags=re.S))
order = list(csv.DictReader(open(os.path.join(KIT, "order.csv"), newline="", encoding="utf-8")))
GOLD = {r["id"]: by_key[r["key"]] for r in order}
assert len(GOLD) == 40 and all(GOLD.values())
B1 = ["#%02d" % k for k in range(1, 21)]
B2 = ["#%02d" % k for k in range(21, 41)]


def reply(gold, ids, over=None, fence="```silex"):
    """A reply in the format the packet asks for. over: id -> replacement block text (None = leave out)."""
    over = over or {}
    out = []
    for i in ids:
        t = over[i] if i in over else gold[i]
        if t is None:
            continue
        out.append(f"{i}\n{fence}\n{t}\n```\n")
    return "\n".join(out)


# the temp results folder looks like the real one: rules file and earlier recv files (so the counter starts at recv36)
shutil.copy(os.path.join(REAL, "P_handling_rules.md"), RES)
for k in range(1, 36):
    open(os.path.join(RES, f"recv{k:02d}_label-old.txt"), "w").write(f"old reply {k}\n")


def file_reply(text, model, run, label, given_batch=None, how="attached", guide="attached", note="", continues=None, dry=False, results=None, src_name="src.txt"):
    src = os.path.join(TMP, src_name)
    open(src, "w", encoding="utf-8", newline="").write(text)
    cmd = [sys.executable, "-I", os.path.join(HERE, "intake_p.py"), "--results", results or RES, "--src", src, "--model", model, "--run", str(run),
           "--label", label, "--received", "2026-11-14 12:00", "--how", how, "--guide", guide]
    if given_batch:
        cmd += ["--given-batch", str(given_batch)]
    if note:
        cmd += ["--note", note]
    if continues:
        cmd += ["--continues", continues]
    if dry:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def cells():
    return list(csv.DictReader(open(os.path.join(RES, "cells_P.csv"), newline="", encoding="utf-8")))


def last():
    return cells()[-1]


def run_check(only, out=None, kit=KIT, include_review=False):
    out = out or os.path.join(TMP, "validity")
    cmd = [sys.executable, "-I", os.path.join(HERE, "check_p.py"), "--results", RES, "--kit", kit, "--out", out, "--only", ",".join(only)]
    if include_review:
        cmd.append("--include-review")
    p = subprocess.run(cmd, capture_output=True, text=True)
    rows = []
    if os.path.exists(os.path.join(out, "items.csv")):
        rows = list(csv.DictReader(open(os.path.join(out, "items.csv"), newline="", encoding="utf-8")))
    return p.returncode, p.stdout + p.stderr, rows


def item(rows, cell, iid):
    return next(r for r in rows if r["cell"] == cell and r["item"] == iid)


# ---------- 1 the checker's comment rule, copied
ok(pp.strip_comment("⊨(jb,dn) # note") == ("⊨(jb,dn) ", "# note"), "strip_comment: trailing comment found")
ok(pp.strip_comment("#(↾(jbs,bx))") == ("#(↾(jbs,bx))", None), "strip_comment: # followed by ( is the count root, not a comment")
ok(pp.strip_comment('⇨(F,"fix # it")') == ('⇨(F,"fix # it")', None), "strip_comment: # inside quotation marks is not a comment")
ok(pp.strip_comment("# whole line")[0] == "", "strip_comment: a comment-only line has no code")

# ---------- 2 headings and fences in all their forms
variants = ("### #01\n```silex\n" + GOLD["#01"] + "\n```\n\n**#02**\n~~~\n" + GOLD["#02"] + "\n~~~\n\n#03:\n``` silex\n" + GOLD["#03"] + "\n```\n\nItem #04\n"
            + GOLD["#04"] + "\n\n- **#05**\n  ```silex\n" + GOLD["#05"] + "\n  ```\n")
r = pp.parse_parts([variants])
ok(r["order"] == ["#01", "#02", "#03", "#04", "#05"], "headings: ###, bold, colon, 'Item', bullet+bold all read")
ok(all(r["items"][i]["status"] == "block" for i in ["#01", "#02", "#03", "#05"]) and r["items"]["#04"]["status"] == "unfenced",
   "fences: backticks, tildes, a space before the tag, an indented fence; no fence = unfenced")
ok(all(r["items"][i]["blocks"][0]["text"] == GOLD[i] for i in r["order"]), "block text equals the gold text for all five forms")

# ---------- 3 gold replies: filed and checked
gb1, gb2 = reply(GOLD, B1), reply(GOLD, B2)
rc, out = file_reply(gb1, "claude", 9, "Claude run 9 P batch 1", 1)
ok(rc == 0 and last()["status"] == "data" and last()["recv"] == "recv36" and last()["batch"] == "1", "gold batch 1 filed as recv36, status data, batch 1")
rc, out = file_reply(gb2, "claude", 9, "Claude run 9 P batch 2", 2)
ok(last()["status"] == "data" and last()["recv"] == "recv37" and last()["batch"] == "2", "gold batch 2 filed as recv37, status data, batch 2")
f36 = glob.glob(os.path.join(RES, "recv36_*.txt"))[0]
ok(not (os.stat(f36).st_mode & 0o222), "reply saved read-only")
ok(open(f36, encoding="utf-8").read() == gb1, "reply saved byte for byte")
rc, out, rows = run_check(["P-claude-9-b1", "P-claude-9-b2"])
ok(rc == 0 and len(rows) == 40 and all(r["valid"] == "1" for r in rows), "check_p: all 40 gold items valid (checker ok on every message)")
ok(all(r["chars"] == r["gold_chars"] for r in rows), "length: characters equal the gold measure (order.csv silex_chars) for all 40 items")

# ---------- 4 the pilot reply, as a file
pilot = open(os.path.join(REAL, "P-claude-pilot-b1.txt"), encoding="utf-8").read()
rc, out = file_reply(pilot, "gemini", 9, "pilot as gemini run 9 P batch 1", 1)
ok(last()["status"] == "data", "pilot reply: filed, status data")
rc, out, rows = run_check(["P-gemini-9-b1"])
ok(len(rows) == 20 and sum(int(r["valid"]) for r in rows) == 20, "pilot reply: 20 of 20 valid (as in the pilot record)")

# ---------- 5 mutations of the gold batch 1
def blk(t, fence="```silex"):
    return f"{fence}\n{t}\n```\n"


l12 = GOLD["#12"].split("\n")
l12[1] += " # define"
m10a, m10b = GOLD["#10"].split("\n---\n")
mut = {
    "#01": GOLD["#01"].replace("\n", "\n# first message\n", 1),                  # comment line
    "#02": GOLD["#02"].replace("⍰", "⨂", 1),                           # unknown root
    "#03": "NONE\nA request to every receiver cannot be said.",                    # NONE with a reason line inside
    "#05": GOLD["#05"] + "\nthe job is done",                                      # English line
    "#12": "\n".join(l12),                                                         # trailing comment
    "#14": GOLD["#14"].replace("⊨(jb,fn)", "⨂(jb,fn)", 1),               # failing line later retracted by its sender
}
pieces = []
for i in B1:
    if i == "#04":
        continue                                                                   # missing: no heading, no block
    if i == "#06":
        pieces.append(f"{i}\n{GOLD[i]}\n")                                          # no fence
    elif i == "#07":
        pieces.append(f"{i}\n" + blk(GOLD[i].replace("⇨", "⨂", 1)) + f"Corrected version:\n{i}\n" + blk(GOLD[i]))
    elif i == "#08":
        pieces.append(f"{i}\n" + blk(GOLD[i].replace("≥", "⨂", 1)) + f"{i}\n" + blk(GOLD[i]))
    elif i == "#10":
        pieces.append(f"{i}\n" + blk(m10a) + blk(m10b))                              # split into two blocks
    else:
        pieces.append(f"{i}\n" + blk(mut.get(i, GOLD[i])))
text = "\n".join(pieces)
rc, out = file_reply(text, "grok", 9, "Grok run 9 P batch 1 (mutated)", 1)
rep = pp.parse_parts([text])
ok(rep["items"]["#06"]["status"] == "unfenced", "mutation: #06 without a fence is read as unfenced text")
ok(any(d["id"] == "#07" and "correction word" in d["reason"] for d in rep["dups"]), "mutation: #07 repeated after 'Corrected version:' - the later heading is kept")
ok(any(d["id"] == "#08" and d["reason"].startswith("first") for d in rep["dups"]), "mutation: #08 repeated with no correction word - the first heading is kept")
ok(len(rep["items"]["#10"]["blocks"]) == 2, "mutation: #10 with two blocks is read as split")
ok(last()["status"] == "review" and "FEWER THAN 20" in out, "mutation reply has 19 items (#04 missing): held for review by the form check")
cell = "P-grok-9-b1"
rc, out, rows = run_check([cell], include_review=True)
g = lambda i: item(rows, cell, i)
ok(len(rows) == 20, "check_p with --include-review checks the held reply: 20 item rows (the missing item included)")
ok(g("#01")["valid"] == "0" and g("#01")["checker_ok"] == "1" and "comment" in g("#01")["reasons"], "#01 comment line: invalid (broken rule) but checker-ok without the comment rule")
ok(g("#02")["valid"] == "0" and g("#02")["checker_ok"] == "0" and "E-LEX" in g("#02")["verdicts"], "#02 unknown root: invalid, verdict E-LEX")
ok(g("#03")["valid"] == "0" and "NONE" in g("#03")["reasons"] and g("#03")["checker_ok"] == "0", "#03 NONE with a reason line inside: invalid")
ok(g("#04")["valid"] == "0" and g("#04")["reasons"] == "missing", "#04 no heading and no block: missing, invalid")
ok(g("#05")["valid"] == "0" and g("#05")["problems"] != "0", "#05 English line inside the block: invalid (checker verdict)")
ok(g("#06")["valid"] == "1" and g("#06")["blocks"] == "1", "#06 unfenced but correct SILEX: valid (the missing fence is noted, not a verdict)")
ok(g("#07")["valid"] == "1", "#07 corrected version counts: valid")
ok(g("#08")["valid"] == "0", "#08 first (faulty) block counts when no correction word: invalid")
ok(g("#10")["valid"] == "0" and g("#10")["joined_ok"] == "1" and "split" in g("#10")["reasons"], "#10 split into two blocks: each block alone fails (message 2 answers a message that is not there); joined variant is ok")
ok(g("#12")["valid"] == "0" and g("#12")["checker_ok"] == "1" and g("#12")["comment_lines"] == "1", "#12 trailing comment: invalid by rule, checker-ok")
ok(g("#14")["valid"] == "0" and g("#14")["retracted"] != "0", "#14 failing line taken back by its own sender: still counts as a verdict (retracted > 0), invalid")
ok(g("#09")["valid"] == "1" and g("#11")["valid"] == "1" and g("#20")["valid"] == "1", "untouched items stay valid")
rc, o2, rows2 = run_check([cell], out=os.path.join(TMP, "validity_empty"))
ok(rc != 0 and "no P reply" in o2 and not rows2, "check_p without --include-review leaves the held reply out (nothing to check)")

# ---------- 6 form flags (hold or note), each on its own cell
def filed(text, model, run, label, given_batch=None, **kw):
    rc, out = file_reply(text, model, run, label, given_batch, **kw)
    return last(), out


row, out = filed("No items here at all.\n", "chatgpt", 9, "no headings", 1)
ok(row["status"] == "review" and "NO ITEM HEADING" in out, "no heading: held for review")
row, out = filed(reply(GOLD, B1[:19]), "chatgpt", 8, "19 items", 1)
ok(row["status"] == "review" and "FEWER THAN 20" in out, "19 items: held (cut off? ask the user)")
row, out = filed(reply(GOLD, B1[:19] + ["#21"]), "chatgpt", 7, "stray item", 1)
ok(row["status"] == "review" and "OUTSIDE ONE BATCH" in out, "an item of the other batch: held")
row, out = filed("Intro.\n" + reply(GOLD, B1) + "\nI searched the web for the syntax.\n", "chatgpt", 6, "search words", 1)
ok(row["status"] == "review" and "SEARCH OR CODE-RUN" in out, "search words outside the blocks: held")
row, out = filed("```silex\n" + GOLD["#01"] + "\n```\n" + reply(GOLD, B1), "chatgpt", 5, "orphan block", 1)
ok(row["status"] == "review" and "BEFORE ANY HEADING" in out, "a block before any heading: held")
one_fence = "```silex\n" + "\n".join(f"{i}\n{GOLD[i]}" for i in B1) + "\n```\n"
row, out = filed(one_fence, "chatgpt", 4, "one block for all", 1)
ok(row["status"] == "review" and "SEVERAL ITEM HEADINGS" in out, "one block holding all the items: held", (row, out))
# a heading inside the block: read as the heading, not as a comment
inner_dup = "".join(f"{i}\n```silex\n{i}\n{GOLD[i]}\n```\n\n" for i in B1)
row, out = filed(inner_dup, "chatgpt", 11, "heading twice (outside and inside)", 1)
rc, o2, rows = run_check(["P-chatgpt-11-b1"])
ok(row["status"] == "data" and "HEADING INSIDE THE BLOCK" in out and all(r["valid"] == "1" and r["comment_lines"] == "0" for r in rows) and len(rows) == 20,
   "heading repeated inside each block: read as the heading, not a comment; all 20 gold items valid", (row, out, rows[:2]))
inner_only = "".join(f"```silex\n{i}\n{GOLD[i]}\n```\n\n" for i in B1)
row, out = filed(inner_only, "chatgpt", 12, "heading only inside the block", 1)
rc, o2, rows = run_check(["P-chatgpt-12-b1"])
ok(row["status"] == "data" and len(rows) == 20 and all(r["valid"] == "1" for r in rows), "no heading outside, one inside each block: 20 items, all valid", (row, out))
row, out = filed("".join(f"{i} (item)\n```silex\n{GOLD[i]}\n```\n\n" for i in B1), "chatgpt", 13, "inline headings", 1)
ok(row["status"] == "review" and "START LIKE AN ITEM NUMBER" in out, "heading with more text on its line: held", (row, out))
noted = "Worked for 12s\nHere are the messages:\n\n" + reply(GOLD, B1) + "\nLet me know if you want changes.\n"
row, out = filed(noted, "chatgpt", 3, "notes only", 2)
ok(row["status"] == "data" and "TEXT BEFORE ITEM 1" in out and "LABEL MISMATCH" in out and "status line" in out and "AFTER THE LAST ITEM" in out,
   "status line, intro, closing remark and wrong label: only noted, still data")
row, out = filed(reply(GOLD, B1[:-1]) + "\n#20\n", "chatgpt", 2, "missing last", 1)
ok(row["status"] == "review", "heading with no block and no text counts as missing (19 items): held", (row, out))
CR = reply(GOLD, B1).replace("\n", "\r\n")
row, out = filed(CR, "gemini", 8, "crlf", 1)
rc, o2, rows = run_check(["P-gemini-8-b1"])
ok(row["status"] == "data" and all(r["valid"] == "1" for r in rows), "CRLF line endings: filed, and all 20 gold items valid")
row, out = filed(gb1, "claude", 9, "same cell again", 1)
ok(row["status"] == "duplicate-of-recv36", "byte-identical re-send: duplicate, not counted")
row, out = filed(gb1.replace("#01", "#01 ", 1) + "\n", "claude", 9, "same cell, other bytes", 1)
ok(row["status"] == "conflict" and "CELL ALREADY FILLED" in out, "a different reply for a filled cell: conflict")
n_before = len(glob.glob(os.path.join(RES, "recv*_*.txt")))
rc, out = file_reply(reply(GOLD, B1), "grok", 1, "dry", 1, dry=True)
ok("dry run" in out and len(glob.glob(os.path.join(RES, "recv*_*.txt"))) == n_before, "dry run writes nothing")

# ---------- 7 a reply cut off and continued
full = reply(GOLD, B2)
k12 = full.index("#32\n```silex\n")
cut = full.index("\n", k12 + len("#32\n```silex\n")) + 1       # after the first SILEX line of #32
p1, p2 = full[:cut], full[cut:]
row, out = filed(p1, "grok", 5, "cut part 1", 2)
first = row["recv"]
ok(row["status"] == "review" and "OPEN BLOCK" in out, "cut-off reply: held (ends inside an open block)")
rc, out = file_reply(p2, "grok", 5, "cut part 2 (continued)", 2, continues=first)
cs = {c["recv"]: c for c in cells()}
ok(rc == 0 and cs[first]["status"] == "data" and cs[first]["parts"].count("+") == 1, "continuation joined mid-block: first part now data, parts listed")
ok(cs[last()["recv"]]["status"] == f"continuation-of-{first}", "continuation row names the part it continues")
rc, o2, rows = run_check(["P-grok-5-b2"])
ok(len(rows) == 20 and all(r["valid"] == "1" for r in rows), "joined cut-off reply: all 20 gold items valid after the join")
k35 = full.index("#35\n```silex\n")
cut35 = full.index("\n", k35 + len("#35\n```silex\n")) + 1
p1b = full[:cut35]
p2b = full[k35:]                                                 # the continuation starts again at #35 (a restart)
row, out = filed(p1b, "grok", 4, "cut part 1 again", 2)
first = row["recv"]
rc, out = file_reply(p2b, "grok", 4, "cut part 2 restart", 2, continues=first)
cs = {c["recv"]: c for c in cells()}
ok(cs[first]["status"] == "data" and "restart" in out and "never closed" in json.load(open(os.path.join(RES, "parsed_p", f"{first}.json")))["parse"]["dups"][0]["reason"],
   "continuation that restarts the block: the unclosed block is dropped, status data")
rc, o2, rows = run_check(["P-grok-4-b2"])
ok(len(rows) == 20 and all(r["valid"] == "1" for r in rows), "restarted continuation: all 20 gold items valid")
rc, out = file_reply(p2b + "\n(other bytes)\n", "claude", 5, "wrong model continuation", 2, continues=first)
ok(rc != 0 and "not claude" in out, "a continuation that names another model's reply is refused", out)
rc, out = file_reply(p2b + "\n(other bytes again)\n", "grok", 3, "wrong run continuation", 2, continues=first)
ok(rc != 0 and "run 3" in out, "a continuation that names another run's reply is refused", out)
rc, out = file_reply(p2b + "\n(and again)\n", "grok", 4, "no such part", 2, continues="recv99")
ok(rc != 0 and "no such row" in out, "a continuation of an unknown reply is refused", out)

# ---------- 8 STEP 2
def step2(txt, model="claude", run=9, dry=False):
    cmd = [sys.executable, "-I", os.path.join(HERE, "intake_p.py"), "--results", RES, "--step2", txt, "--model", model, "--run", str(run),
           "--received", "11:59", "--guide", "pasted"]
    if dry:
        cmd.append("--dry-run")
    return subprocess.run(cmd, capture_output=True, text=True).stdout


o = step2("SILEX-0 has 104 roots, and the packs are described in section 7.")
ok("CORRECT" in o, "STEP 2 right answer recognised")
o = step2("It has 107 roots; packs are in section 6.", model="grok", run=3)
ok("WRONG" in o and "new chat" in o, "STEP 2 wrong answer recognised, protocol rule shown")
log = open(os.path.join(RES, "received_log_P.md"), encoding="utf-8").read()
ok(log.count("STEP 2 answer given 11:59") == 2 and log.index("STEP 2 answer given 11:59") < log.index("## Handling decisions") and "Guide given: pasted" in log,
   "both STEP 2 lines sit at the end of the Metadata part and carry how the guide was given")
rows_t = [i for i, l in enumerate(log.split("\n")) if re.match(r"^\| recv\d+ \|", l)]
ok(rows_t == list(range(rows_t[0], rows_t[0] + len(rows_t))), "log table rows stay in one block")
ok(log.index("recv36 (arm P") < log.index("## Metadata the protocol asks for") and log.index("| recv36 |") < log.index("## Form-check notes"), "row before the notes heading, paragraph before the Metadata heading")
ok("The checker has not been run on it." in log, "the log says the checker was not run at filing")

# ---------- 9 the guard on the frozen files
bad_kit = os.path.join(TMP, "bad_kit")
shutil.copytree(KIT, bad_kit, ignore=shutil.ignore_patterns("*.zip"))
os.chmod(os.path.join(bad_kit, "silex_check.py"), 0o644)
open(os.path.join(bad_kit, "silex_check.py"), "a").write("\n# changed\n")
rc, out, rows = run_check(["P-claude-9-b1"], out=os.path.join(TMP, "validity_bad"), kit=bad_kit)
ok(rc != 0 and "HASH MISMATCH" in out and not rows, "check_p stops when the checker file differs from the manifest")

# ---------- 9b settling a hold, and the grid
def settle(*args):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "settle_p.py"), "--results", RES] + list(args), capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


held_row = next(c for c in cells() if c["status"] == "review" and c["model"] == "chatgpt" and c["run"] == "8")
rc, o = settle("--recv", held_row["recv"], "--status", "data", "--why", "the user says the reply really had 19 items", "--when", "2026-11-14 13:00")
ok(rc == 0 and next(c for c in cells() if c["recv"] == held_row["recv"])["status"] == "data", "settle: a held reply made data", o)
log = open(os.path.join(RES, "received_log_P.md"), encoding="utf-8").read()
ok("settled with the user: review -> data" in log and "really had 19 items" in log, "settle: dated line added to the log")
conf = next(c for c in cells() if c["status"] == "conflict")
rc, o = settle("--recv", conf["recv"], "--status", "data", "--why", "x")
ok(rc != 0 and "already held" in o, "settle: a conflict cannot be made data while the cell is held by another data reply", o)
rc, o = settle("--recv", conf["recv"], "--status", "excluded", "--why", "second reply for the same cell; the first one counts")
ok(rc == 0 and next(c for c in cells() if c["recv"] == conf["recv"])["status"] == "excluded", "settle: a conflict can be excluded")
rc, o = settle("--recv", "recv99", "--status", "data", "--why", "x")
ok(rc != 0 and "no such row" in o, "settle: unknown row refused")
rc, o = settle("--grid")
ok(rc == 0 and "run 1 claude" in o and "cells with a data reply:" in o and "Held or in conflict:" in o, "grid prints the 4 x 3 x 2 cells and what is held", o)
rc, o = settle("--recv", held_row["recv"], "--status", "excluded", "--why", "test: a data row can be excluded")
ok(rc == 0 and next(c for c in cells() if c["recv"] == held_row["recv"])["status"] == "excluded", "settle: a data row can be excluded")
rc, o2, rows = run_check(["P-chatgpt-8-b1"], out=os.path.join(TMP, "validity_excl"))
ok(rc != 0 and not rows, "check_p leaves an excluded reply out")

# ---------- 10 the real folder was not touched
real_new = [p for p in glob.glob(os.path.join(REAL, "*")) if os.path.basename(p) in ("cells_P.csv", "received_log_P.md", "parsed_p", "validity_P")]
ok(not real_new, "no cells_P.csv, received_log_P.md, parsed_p or validity_P in the real folder after the tests")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
