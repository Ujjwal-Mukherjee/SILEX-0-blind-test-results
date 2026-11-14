#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for parse_e_reply.py, intake_e.py, settle_e.py and build_roundtrip_e.py (arm E, English baseline).
Everything runs in a TEMP folder; nothing real is written. Test replies are made from the scenario text of the frozen E_batch files (the English facts are turned into
"A to B: ..." lines) with mutations made only for the test. No key is opened.
Run:  python3 -I test_e_tools.py [KIT]      Re-run after any change to the programs.
"""
import csv, glob, hashlib, json, os, re, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, HERE)
import parse_e_reply as pe        # noqa: E402
import build_roundtrip_e as bre   # noqa: E402
import build_roundtrip_p as brp   # noqa: E402

TMP = tempfile.mkdtemp(prefix="e_tools_test_")
RES = os.path.join(TMP, "res")
os.makedirs(RES)
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

# ---------- material: English replies made from the scenarios of the frozen E batches
B1 = ["#%02d" % k for k in range(1, 21)]
B2 = ["#%02d" % k for k in range(21, 41)]


def gold_from_scenarios():
    gold = {}
    for fn in ("E_batch1.txt", "E_batch2.txt"):
        body = open(os.path.join(KIT, fn), encoding="utf-8").read().split("SCENARIOS\n", 1)[1]
        for blk in body.strip().split("\n\n"):
            lines = blk.split("\n")
            msgs = []
            for l in lines[1:]:
                m = re.match(r"Message \d+ \(([^)]*)\)(?:[^:]*)?: (.*)$", l)
                msgs.append(f"{m.group(1)}: {m.group(2)}" if m else l)
            gold[lines[0].strip()] = "\n".join(msgs)
    return gold


GOLD = gold_from_scenarios()
assert len(GOLD) == 40 and all(GOLD.values())


def reply(ids, over=None, head="{i}", sep="\n\n", fence=False, tail=""):
    """over: id -> replacement text (None = leave the item out)."""
    over = over or {}
    out = []
    for i in ids:
        t = over[i] if i in over else GOLD[i]
        if t is None:
            continue
        body = f"```\n{t}\n```" if fence else t
        out.append(head.format(i=i) + "\n" + body)
    return sep.join(out) + "\n" + tail


def file_reply(text, model, run, label, given_batch=None, how="attached", note="", continues=None, dry=False, results=None, src_name="src.txt", tool="intake_e.py"):
    src = os.path.join(TMP, src_name)
    open(src, "w", encoding="utf-8", newline="").write(text)
    cmd = [sys.executable, "-I", os.path.join(HERE, tool), "--results", results or RES, "--src", src, "--model", model, "--run", str(run),
           "--label", label, "--received", "2026-11-14 12:00", "--how", how]
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
    return list(csv.DictReader(open(os.path.join(RES, "cells_E.csv"), newline="", encoding="utf-8")))


def last():
    return cells()[-1]


def settle(*args, results=None):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "settle_e.py"), "--results", results or RES] + list(args), capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


# the temp results folder looks like the real one: rules file and earlier recv files (so the counter starts after them)
shutil.copy(os.path.join(REAL, "E_handling_rules.md"), RES)
for k in range(1, 61):
    open(os.path.join(RES, f"recv{k:02d}_label-old.txt"), "w").write(f"old reply {k}\n")

# ---------- 1 message lines (rule 13)
for line, want in [("A to B: A asks.", True), ("- A to B: A asks.", True), ("**A to B:** A asks.", True), ("1. A to B (reply): x", True),
                   ("Message 1 (A to B): x", True), ("A to B and E: x", True), ("Note: B declines to review", False), ("B declines to review", False),
                   ("A to B", False), ("this is a very long head that has the word to inside it but is far longer than forty characters on both sides of it to go: x", False)]:
    ok(pe.is_message_line(line) == want, f"message line {'yes' if want else 'no'}: {line[:50]!r}")

# ---------- 2 headings in all their forms, text kept as written
variants = ("### #01\nA to B: one\n\n**#02**\nA to B: two\n\n#03:\nA to B: three\n\nItem #04\nA to B: four\n\n- **#05**\n  A to B: five\n")
r = pe.parse_parts([variants])
ok(r["order"] == ["#01", "#02", "#03", "#04", "#05"], "headings: ###, bold, colon, 'Item', bullet+bold all read")
ok(all(r["items"][i]["status"] == "unfenced" and r["items"][i]["state"] == "text" for i in r["order"]), "unfenced English is the normal case: status unfenced, state text")
ok(r["items"]["#05"]["text"] == "  A to B: five", "text is kept as written (leading spaces stay)")

# ---------- 3 a # in the English is text (no comment rule)
r = pe.parse_parts(["#01\nA to B: job #5 is stuck # really\nB to A: ok (#3)\n"])
ok(r["items"]["#01"]["text"] == "A to B: job #5 is stuck # really\nB to A: ok (#3)" and r["items"]["#01"]["chars"] == len(r["items"]["#01"]["text"]), "a # inside the English is ordinary text and counts")
ok(r["items"]["#01"]["blocks"][0]["comments"] == [], "arm E has no comments")

# ---------- 4 rules (horizontal rule lines) are not text
r = pe.parse_parts(["#01\nA to B: one\n---\nB to A: two\n\n***\n#02\nA to B: three\n___\n"])
ok(r["items"]["#01"]["text"] == "A to B: one\nB to A: two" and r["items"]["#02"]["text"] == "A to B: three", "horizontal-rule lines (---, ***, ___) are not text; blank lines are dropped")
ok(r["items"]["#01"]["messages"] == 2 and r["items"]["#01"]["other_lines"] == 0, "two message lines, no other line")

# ---------- 5 the last item: closing remarks (rule 9)
r = pe.parse_parts(["#19\nA to B: one\n\n#20\nA to B: last\nB to A: reply\n\nLet me know if you want changes.\n"])
ok(r["items"]["#20"]["text"] == "A to B: last\nB to A: reply" and [t["text"] for t in r["trailing"]] == ["Let me know if you want changes."], "a closing remark after a blank line is text after the last item")
r = pe.parse_parts(["#20\nA to B: last\n---\nHope this helps.\n"])
ok(r["items"]["#20"]["text"] == "A to B: last" and r["trailing"][0]["text"] == "Hope this helps.", "a closing remark after a rule is text after the last item")
r = pe.parse_parts(["#20\nA to B: last\nthe job is stuck\n"])
ok(r["items"]["#20"]["text"] == "A to B: last\nthe job is stuck" and r["items"]["#20"]["other_lines"] == 1 and not r["trailing"], "a line directly under the last message line stays in the item (listed as a non-message line)")
r = pe.parse_parts(["#20\nNothing to say here.\n\nBye.\n"])
ok(r["items"]["#20"]["text"] == "Nothing to say here.\nBye." and not r["trailing"], "a last item with no message line is not cut")
r = pe.parse_parts(["#01\nA to B: one\n\nThanks!\n\n#02\nA to B: two\n"])
ok(r["items"]["#01"]["text"] == "A to B: one\nThanks!", "only the LAST item of a reply is cut; a remark in another item stays as written")

# ---------- 6 fences
r = pe.parse_parts(["#01\n```\nA to B: one\n```\nsome remark\n\n#02\n```text\nA to B: two\n```\n```\nB to A: three\n```\n\n#03\nA to B: x\n"])
ok(r["items"]["#01"]["text"] == "A to B: one" and r["items"]["#01"]["status"] == "block", "a fenced item: the block is the text")
ok(r["items"]["#01"]["outside"] and r["items"]["#01"]["outside"][0]["text"] == "some remark", "text outside the fence is recorded, not part of the item")
ok(r["items"]["#02"]["text"] == "A to B: two\nB to A: three" and len(r["items"]["#02"]["blocks"]) == 2, "several fenced blocks are joined in order by one newline")

# ---------- 7 NONE / empty / missing
r = pe.parse_parts(["#01\nNONE\n\n#02\nNone - cannot be said\n\n#03\nNone of the jobs is stuck, A tells B.\n\n#04\n\n#05\n---\n\n#06\n**None**\n"])
ok(r["items"]["#01"]["state"] == "none" and r["items"]["#02"]["state"] == "none" and r["items"]["#06"]["state"] == "none", "NONE, 'None - reason' and bold None are NONE items")
ok(r["items"]["#03"]["state"] == "text", "'None of the jobs ...' is text, not NONE")
ok(r["items"]["#04"]["state"] == "missing" and r["items"]["#05"]["state"] == "empty", "a heading with nothing is missing; a heading with only a rule is empty")

# ---------- 8 repeated headings
r = pe.parse_parts(["#01\nA to B: first\n\nCorrected version:\n#01\nA to B: second\n\n#02\nA to B: x\n\n#02\nA to B: y\n"])
ok(r["items"]["#01"]["text"] == "A to B: second" and any(d["id"] == "#01" and "correction word" in d["reason"] for d in r["dups"]), "a correction word keeps the later heading")
ok(r["items"]["#02"]["text"] == "A to B: x" and any(d["id"] == "#02" and d["reason"].startswith("first") for d in r["dups"]), "no correction word keeps the first heading")

# ---------- 9 search words only outside the items
r = pe.parse_parts(["I searched the web first.\n\n#01\nA to B: A searched the queue and looked up the job, https://x.example\n"])
ok(r["tool_words"] == ["searched"], "search words in the preamble are found", r["tool_words"])
r = pe.parse_parts(["#01\nA to B: A searched the queue and looked up the job, https://x.example\n\n#02\nA to B: x\n\nI ran the code to check.\n"])
ok(r["tool_words"] == ["i ran"], "search words inside an item are the writer's English and are not looked at; one after the last item is", r["tool_words"])

# ---------- 10 filing: a clean batch
b1 = reply(B1)
rc, out = file_reply(b1, "claude", 1, "Claude E batch 1", 1, note="Claude Sonnet 5.5 Extra")
ok(rc == 0 and last()["status"] == "data" and last()["recv"] == "recv61" and last()["batch"] == "1", "clean batch 1 filed as recv61, status data, batch 1", out)
f61 = glob.glob(os.path.join(RES, "recv61_*.txt"))[0]
ok(not (os.stat(f61).st_mode & 0o222) and open(f61, encoding="utf-8").read() == b1, "reply saved byte for byte and read-only")
j = json.load(open(os.path.join(RES, "parsed_e", "recv61.json"), encoding="utf-8"))
ok(j["cell"] == "E-claude-1-b1" and j["parse"]["items"]["#02"]["chars"] == len(GOLD["#02"]) and j["parse"]["items"]["#13"]["chars"] == len(GOLD["#13"]), "parsed json: cell name and characters per item equal the text lengths")
log = open(os.path.join(RES, "received_log_E.md"), encoding="utf-8").read()
ok("recv61" in log and "E_handling_rules.md" in log and hashlib.sha256(open(os.path.join(RES, "E_handling_rules.md"), "rb").read()).hexdigest() in log, "the log is created with the rules hash and a row for recv61")
rc, out = file_reply(reply(B2), "claude", 1, "Claude E batch 2", 2)
ok(rc == 0 and last()["status"] == "data" and last()["batch"] == "2", "clean batch 2 filed, batch 2")

# ---------- 11 dry run, duplicate, conflict, label mismatch
before = sorted(os.listdir(RES))
rc, out = file_reply(reply(B1), "grok", 1, "Grok E batch 1", 1, dry=True)
ok(rc == 0 and sorted(os.listdir(RES)) == before and "dry run" in out, "a dry run writes nothing")
rc, out = file_reply(reply(B1), "claude", 1, "Claude E batch 1 again", 1)
ok(last()["status"] == "duplicate-of-recv61" and "DUPLICATE" in out, "a byte-identical re-send is a duplicate, kept once")
rc, out = file_reply(reply(B1, {"#03": "A to B: different"}), "claude", 1, "Claude E batch 1 re-run", 1)
ok(last()["status"] == "conflict" and "CELL ALREADY FILLED" in out, "another reply for a filled cell is a conflict (held)")
rc, out = file_reply(reply(B2, head="**{i}**"), "grok", 1, "Grok E batch 2 (mislabelled)", 1)
ok(last()["status"] == "data" and last()["batch"] == "2" and "LABEL MISMATCH" in out, "the item numbers decide the batch; a label mismatch is noted")

# ---------- 12 holds
rc, out = file_reply("Hello, here is my answer.\n", "gemini", 1, "Gemini E no headings")
ok(last()["status"] == "review" and "NO ITEM HEADING" in out, "no heading: held")
rc, out = file_reply(reply(B1[:12]), "gemini", 1, "Gemini E batch 1 (cut)", 1)
ok(last()["status"] == "review" and "FEWER THAN 20" in out, "12 of 20 items: held (cut off?)")
held = last()["recv"]
tail_part = reply(B1[12:])
rc, out = file_reply(tail_part, "gemini", 1, "Gemini E batch 1 continued", 1, continues=held)
rows = cells()
ok(rows[-1]["status"] == f"continuation-of-{held}" and [r for r in rows if r["recv"] == held][0]["status"] == "data", "the continuation lifts the hold: first part now data", out)
ok("JOINED (text)" in out, "the junction of a joined plain-text reply is listed for a look (rule 14)")
j = json.load(open(os.path.join(RES, "parsed_e", f"{held}.json"), encoding="utf-8"))
ok(len(j["parse"]["order"]) == 20 and j["parse"]["items"]["#20"]["text"] == GOLD["#20"], "the joined reply has all 20 items")
rc, out = file_reply("Sure, let me look it up.\n\n" + reply(B2), "chatgpt", 1, "ChatGPT E batch 2 (preamble)", 2)
ok(last()["status"] == "data" and "TEXT BEFORE ITEM 1" in out, "a preamble is noted, not held")
rc, out = file_reply("I searched the web for this.\n\n" + reply(B2), "chatgpt", 7, "ChatGPT E batch 2 (search words)", 2)
ok(last()["status"] == "review" and "SEARCH OR CODE-RUN WORDS" in out, "search words outside the items: held")
rc, out = file_reply(reply(B1).replace("#05\n", "#05 (fifth)\n", 1), "chatgpt", 8, "ChatGPT E batch 1 (inline heading)", 1)
ok(last()["status"] == "review" and "START LIKE AN ITEM NUMBER" in out, "'#05 (fifth)' is not a heading: held")
# Note 1 (2026-11-14): "#NN <message line>" starts an item; the rest of that line and the lines below it are the item's text (found on the first ChatGPT replies)
one_line2 = "Worked for 10s\n\n" + "\n\n".join(f"{i} " + " ".join(GOLD[i].split("\n")) for i in B2) + "\n"
rc, out = file_reply(one_line2, "chatgpt", 10, "ChatGPT E batch 2 (every item on one line)", 2)
ok(last()["status"] == "data" and last()["batch"] == "2" and "NUMBER AND FIRST MESSAGE ON ONE LINE" in out and "LABEL MISMATCH" not in out and "app status line" in out,
   "Note 1: every item on one line is data, batch 2 from the item numbers, listed in a note, status line noted", out)
j = json.load(open(os.path.join(RES, "parsed_e", f"{last()['recv']}.json"), encoding="utf-8"))
ok(len(j["parse"]["order"]) == 20 and all(j["parse"]["items"][i]["text"] == " ".join(GOLD[i].split("\n")) for i in B2),
   "Note 1: the item text is the rest of the line exactly as written (nothing repaired, line breaks not put back)")
ok(bre.item_text(j["parse"]["items"]["#21"]) == " ".join(GOLD["#21"].split("\n")), "Note 1: the round-trip builder takes the one-line text as it is")
one_line1 = "\n\n".join(f"{i} " + " ".join(GOLD[i].split("\n")) for i in B1) + "\n"
rc, out = file_reply(one_line1, "chatgpt", 11, "ChatGPT E batch 2 (label wrong, every item on one line)", 2)
ok(last()["status"] == "data" and last()["batch"] == "1" and "LABEL MISMATCH" in out, "Note 1: label says 2, the numbers say 1: batch 1, label mismatch noted", out)
mixed = "\n\n".join((f"{i} " + " ".join(GOLD[i].split("\n"))) if k % 2 else f"{i}\n{GOLD[i]}" for k, i in enumerate(B1)) + "\n"
rc, out = file_reply(mixed, "chatgpt", 12, "ChatGPT E batch 1 (some items on one line, some not)", 1)
ok(last()["status"] == "data" and "10 item(s)" in out, "Note 1: a reply that mixes both forms is data (10 items on one line are listed)", out)
comment = "\n\n".join(f"{i} (item)\n{GOLD[i]}" for i in B2) + "\n"
rc, out = file_reply(comment, "chatgpt", 13, "ChatGPT E batch 2 (a comment after each number)", 2)
ok(last()["status"] == "review" and last()["batch"] == "2" and "NO ITEM HEADING FOUND" in out and "START LIKE AN ITEM NUMBER" in out and "LABEL MISMATCH" not in out,
   "'#21 (item)' is not a message line: held (rule 7), and the batch still comes from the item numbers", out)
rc, out = file_reply(reply(B1) + "\n" + reply(B2[:3]), "chatgpt", 9, "ChatGPT E both batches", 1)
ok(last()["status"] == "review" and "OUTSIDE ONE BATCH" in out, "headings from both batches: held")

# ---------- 13 settle and grid
rc, out = settle("--recv", last()["recv"], "--status", "excluded", "--why", "test: both batches in one reply", "--when", "2026-11-14 12:30")
ok(rc == 0 and last()["status"] == "excluded", "settle: a held reply is excluded with a reason")
dup = [r for r in cells() if r["status"].startswith("duplicate-of-")][0]["recv"]
rc, out = settle("--recv", dup, "--status", "excluded", "--why", "x")
ok(rc != 0 and "only review, conflict or data" in out, "settle: refuses a row that is a duplicate", out)
conf =[r for r in cells() if r["status"] == "conflict"][0]["recv"]
rc, out = settle("--recv", conf, "--status", "data", "--why", "test")
ok(rc != 0 and "already held" in out, "settle: a conflict cannot become data while another data row holds the cell", out)
rc, out = settle("--grid")
ok(rc == 0 and "claude r1" in out and "cells with a data reply:" in out, "grid prints", out)
log = open(os.path.join(RES, "received_log_E.md"), encoding="utf-8").read()
ok("settled with the user" in log and "test: both batches in one reply" in log, "settle: dated line in the log")

# ---------- 13b reparse_e.py: a held reply is re-read under Note 1 and the hold is lifted if nothing else is wrong
sys.path.insert(0, HERE)
import intake_e as ie_mod   # noqa: E402


def reparse(*args, results=None):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "reparse_e.py"), "--results", results or RES] + list(args), capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


rc, out = file_reply("Worked for 5s\n\n" + "\n\n".join(f"{i} " + " ".join(GOLD[i].split("\n")) for i in B1) + "\n", "grok", 14, "Grok E batch 1 (reparse test)", 1)
rid = last()["recv"]
rows = ie_mod.read_cells(os.path.join(RES, "cells_E.csv"))
[r for r in rows if r["recv"] == rid][0]["status"] = "review"      # the state the old parser left such a reply in
ie_mod.write_cells(os.path.join(RES, "cells_E.csv"), rows)
rc, out = reparse("--recv", rid, "--dry-run")
ok(rc == 0 and "no hold remains" in out and "dry run" in out and last()["status"] == "review", "reparse: a dry run changes nothing", out)
rc, out = reparse("--recv", rid, "--when", "2026-11-14 12:40")
rows = ie_mod.read_cells(os.path.join(RES, "cells_E.csv"))
row = [r for r in rows if r["recv"] == rid][0]
keep = os.path.join(RES, "parsed_e", f"{rid}.before_note1.json")
ok(rc == 0 and row["status"] == "data" and row["batch"] == "1", "reparse: the hold is lifted (review -> data)", out)
ok(os.path.exists(keep) and not os.access(keep, os.W_OK) or os.path.exists(keep) and (os.stat(keep).st_mode & 0o222) == 0, "reparse: the first parse is kept, read-only")
j = json.load(open(os.path.join(RES, "parsed_e", f"{rid}.json"), encoding="utf-8"))
ok(j["reread"]["under"].startswith("Note 1") and len(j["parse"]["order"]) == 20, "reparse: the parse is rewritten with the current parser and says so")
log = open(os.path.join(RES, "received_log_E.md"), encoding="utf-8").read()
ok(f"{rid} re-read under Note 1" in log and "2026-11-14 12:40" in log, "reparse: a paragraph and a dated line are in the log")
rc, out = reparse("--recv", rid)
ok(rc != 0 and "only a held reply" in out, "reparse: a reply that is data is refused", out)
rc, out = file_reply("Worked for 6s\n\n" + comment, "grok", 15, "Grok E batch 2 (reparse still held)", 2)
rid2 = last()["recv"]
rc, out = reparse("--recv", rid2)
ok(rc != 0 and "STILL HELD" in out and "nothing changed" in out and last()["status"] == "review", "reparse: a reply that is still held is not changed", out)

# ---------- 14 the round-trip packets (build_roundtrip_e.py)
RES2 = os.path.join(TMP, "res2")
os.makedirs(RES2)
shutil.copy(os.path.join(REAL, "E_handling_rules.md"), RES2)
for k in range(1, 61):
    open(os.path.join(RES2, f"recv{k:02d}_label-old.txt"), "w").write(f"old reply {k}\n")
variants_by_model = {
    "claude": dict(),
    "chatgpt": dict(head="**{i}**"),
    "grok": dict(fence=True),
    "gemini": dict(over1={"#05": "NONE", "#09": ""}, tail="\nHope this helps!\n"),
}
for m, kw in variants_by_model.items():
    kw = dict(kw)
    o1 = kw.pop("over1", None)
    tail = kw.pop("tail", "")
    t1 = reply(B1, over=o1, **kw)
    t2 = reply(B2, tail=tail, **kw)
    for k, t in ((1, t1), (2, t2)):
        rc, out = file_reply(t, m, 1, f"{m} E batch {k}", k, results=RES2, src_name=f"src_{m}{k}.txt")
        assert rc == 0, out
rows2 = list(csv.DictReader(open(os.path.join(RES2, "cells_E.csv"), newline="", encoding="utf-8")))
held2 = [r for r in rows2 if r["status"] == "review"]
ok(len(rows2) == 8 and [(r["model"], r["batch"]) for r in held2] == [("gemini", "1")], "seven replies are data; the gemini batch with an empty item is held (19 of 20 items)", [(r["recv"], r["status"]) for r in rows2])
rc, out = settle("--recv", held2[0]["recv"], "--status", "data", "--why", "test: the user says that is all there is", results=RES2)
rows2 = list(csv.DictReader(open(os.path.join(RES2, "cells_E.csv"), newline="", encoding="utf-8")))
ok(rc == 0 and all(r["status"] == "data" for r in rows2), "after settling it as data all 8 rows are data", out)

OUT = os.path.join(TMP, "out")


def build(args, results=RES2, out=OUT, kit=KIT):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build_roundtrip_e.py"), "--results", results, "--kit", kit, "--out", out, "--writers", args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


rc, out = build("claude:1,chatgpt:1,grok:1,gemini:1")
ok(rc == 0, "build for all four writers succeeds", out)
c = bre.chat_numbers(brp.DEFAULT_SEED)
ok(sorted(c.values()) == [1, 2, 3, 4] and c == bre.chat_numbers(brp.DEFAULT_SEED), "chat numbers: a permutation of 1..4, the same when asked twice")
files = sorted(os.listdir(OUT))
ok(files == sorted([f"RT-E_chat{n}_packet{b}.txt" for n in (1, 2, 3, 4) for b in (1, 2)] + ["rt_key_E_PRIVATE.csv", "README_RT_E.txt"]), "8 packets, the key file and the README", files)
hdr = bre.english_header(KIT)
o1, o2 = brp.item_order(brp.DEFAULT_SEED, B1), brp.item_order(brp.DEFAULT_SEED, B2)
rt = open(os.path.join(KIT, "reader_prompts.txt"), encoding="utf-8").read()
ok(hdr in rt and hdr.startswith("READING TEST (plain English)") and hdr.endswith("ITEMS"), "the opening text is the English reader text of reader_prompts.txt, up to ITEMS")


def parse_packet(text):
    i = text.index("\nITEMS\n") + len("\nITEMS")
    return text[:i], re.findall(r"(#\d\d)\n```\n(.*?)\n```(?:\n\n|\n$)", text[i + 2:], flags=re.S)


for m in ("claude", "chatgpt", "grok", "gemini"):
    for b in (1, 2):
        f = os.path.join(OUT, f"RT-E_chat{c[m]}_packet{b}.txt")
        text = open(f, encoding="utf-8").read()
        head, items = parse_packet(text)
        ok(head == (hdr if b == 1 else brp.header_for(hdr, 2)), f"{m} batch {b}: opening text and item range")
        ok([i for i, _ in items] == (o1 if b == 1 else o2), f"{m} batch {b}: 20 items in the same seeded order as the SILEX packets")
        ok(text.endswith("```\n") and not text.endswith("\n\n") and not os.stat(f).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), f"{m} batch {b}: layout and read-only")
        ok(not bre.BANNED.search(text), f"{m} batch {b}: no writer, model, run or arm word")
        rep = [r for r in bre.load_replies(RES2) if r["model"] == m and r["batch"] == b][0]
        parsed = pe.parse_parts(rep["texts"])
        got = dict(items)
        ok(all(got[i] == (parsed["items"][i]["text"] if parsed["items"][i]["state"] == "text" else "NONE") for i in got), f"{m} batch {b}: every item is the writer's text as parsed (NONE for no text)")
# specific forms
t = dict(parse_packet(open(os.path.join(OUT, f"RT-E_chat{c['gemini']}_packet1.txt"), encoding="utf-8").read())[1])
ok(t["#05"] == "NONE" and t["#09"] == "NONE", "a NONE item and a missing item are shown as a block holding NONE")
t = dict(parse_packet(open(os.path.join(OUT, f"RT-E_chat{c['gemini']}_packet2.txt"), encoding="utf-8").read())[1])
ok("Hope this helps" not in "\n".join(t.values()), "the closing remark after the last item is not shown to the reader")
t = dict(parse_packet(open(os.path.join(OUT, f"RT-E_chat{c['grok']}_packet1.txt"), encoding="utf-8").read())[1])
ok(t["#02"] == GOLD["#02"], "a fenced item is shown as its text without the writer's fence")
t = dict(parse_packet(open(os.path.join(OUT, f"RT-E_chat{c['chatgpt']}_packet1.txt"), encoding="utf-8").read())[1])
ok(t["#02"] == GOLD["#02"], "a bold heading does not change the text")
key = list(csv.DictReader(open(os.path.join(OUT, "rt_key_E_PRIVATE.csv"), newline="", encoding="utf-8")))
ok(len(key) == 8 and all(int(r["chat"]) == c[r["writer"]] for r in key) and all(r["source_cell"] == f"E-{r['writer']}-1-b{r['packet']}" for r in key), "the key: 8 rows, fixed chat numbers, source cells")
ok(all(r["sha256_16"] == hashlib.sha256(open(os.path.join(OUT, r["file"]), "rb").read()).hexdigest()[:16] for r in key), "the key's hashes match the packet files")
ok(sum(int(r["none_items"]) for r in key if r["writer"] == "gemini") == 2 and all(int(r["none_items"]) == 0 for r in key if r["writer"] != "gemini"), "the key counts the NONE items (gemini 2, others 0)")
readme = open(os.path.join(OUT, "README_RT_E.txt"), encoding="utf-8").read()
ok(not re.search(r"(?i)claude|chatgpt|grok|gemini", readme), "the README names no writer")

# rebuild and refusals
before = {f: hashlib.sha256(open(os.path.join(OUT, f), "rb").read()).hexdigest() for f in os.listdir(OUT) if f.startswith("RT-E_")}
rc, out = build("claude:1,chatgpt:1,grok:1,gemini:1")
ok(rc == 0 and before == {f: hashlib.sha256(open(os.path.join(OUT, f), "rb").read()).hexdigest() for f in os.listdir(OUT) if f.startswith("RT-E_")}, "a second identical build leaves every packet unchanged")
OUT2 = os.path.join(TMP, "out2")
rc1, _ = build("gemini:1", out=OUT2)
rc2, _ = build("claude:1,grok:1,chatgpt:1", out=OUT2)
after = {f: hashlib.sha256(open(os.path.join(OUT2, f), "rb").read()).hexdigest() for f in os.listdir(OUT2) if f.startswith("RT-E_")}
ok(rc1 == 0 and rc2 == 0 and after == before, "a two-step build gives the same packets as the one-step build")
rc, out = build("claude:1,claude:2")
ok(rc != 0 and "twice" in out, "a writer named twice stops the build")
rc, out = build("llama:1")
ok(rc != 0 and "unknown writer" in out, "an unknown writer stops the build")
rc, out = build("claude:2", out=os.path.join(TMP, "o9"))
ok(rc != 0 and "no single data reply" in out, "a writer run with no data reply stops the build")
victim = os.path.join(OUT, f"RT-E_chat{c['claude']}_packet1.txt")
os.chmod(victim, 0o644)
open(victim, "a", encoding="utf-8").write("tamper\n")
rc, out = build("claude:1")
ok(rc != 0 and "not overwritten" in out, "a packet that exists with other content is not overwritten")
BADKIT = os.path.join(TMP, "badkit")
os.makedirs(BADKIT)
for f in ("MANIFEST.sha256", "SILEX-0-GRAMMAR.md", "silex_check.py", "reader_prompts.txt"):
    shutil.copy(os.path.join(KIT, f), BADKIT)
open(os.path.join(BADKIT, "silex_check.py"), "a", encoding="utf-8").write("\n# changed\n")
rc, out = build("claude:1", out=os.path.join(TMP, "o10"), kit=BADKIT)
ok(rc != 0 and "HASH MISMATCH" in out, "a changed checker stops the build")
# a model name inside an English text stops the build
RES3 = os.path.join(TMP, "res3")
shutil.copytree(RES2, RES3)
cl = [r for r in bre.load_replies(RES3) if r["model"] == "claude" and r["batch"] == 1][0]
rows3 = list(csv.DictReader(open(os.path.join(RES3, "cells_E.csv"), newline="", encoding="utf-8")))
fn = [r["file"] for r in rows3 if r["model"] == "claude" and r["batch"] == "1"][0]
os.chmod(os.path.join(RES3, fn), 0o644)
txt = open(os.path.join(RES3, fn), encoding="utf-8").read().replace("A asks how many jobs are busy.", "A asks Gemini how many jobs are busy.")
open(os.path.join(RES3, fn), "w", encoding="utf-8").write(txt)
rc, out = build("claude:1", results=RES3, out=os.path.join(TMP, "o11"))
ok(rc != 0 and "could name a writer" in out, "a model name inside an item stops the build", out)
# an item text holding a fence line stops the build
try:
    bre.item_text({"status": "unfenced", "state": "text", "text": "A to B: x\n```evil"})
    ok(False, "a text holding a fence line stops the build")
except SystemExit:
    ok(True, "a text holding a fence line stops the build")

# ---------- 15 the real folder is untouched
real_after = snapshot(REAL)
changed = [k for k in set(real_before) | set(real_after) if real_before.get(k) != real_after.get(k)]
ok(not changed, "the real results folder is unchanged by the tests", changed[:5])

shutil.rmtree(TMP, ignore_errors=True)
print()
print("ALL %s" % ("PASS" if not fails else f"DONE, {len(fails)} FAIL"))
sys.exit(1 if fails else 0)
