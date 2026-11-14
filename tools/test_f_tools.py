#!/usr/bin/env python3
"""Tests of the Test F tools (parse_f_reply.py, intake_f.py, score_f.py, reparse_f.py) on MADE-UP replies in temporary folders.
Nothing real is read or written: the real results folder is never touched. The key is read only from the kit folder given
(default: the folder above this tools folder if it holds the key, else /home/claude/silex_blind_test_F).
  python3 -I test_f_tools.py [KITDIR]
Exit 0 = all pass. Re-run after any change to the tools."""
import csv, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_f_reply as pf  # noqa: E402
import score_f  # noqa: E402

KIT = sys.argv[1] if len(sys.argv) > 1 else next(p for p in (os.path.dirname(HERE), "/home/claude/silex_blind_test_F", "/home/claude/silex_blind_test_F_CANDIDATE") if os.path.exists(os.path.join(p, "key_F_PRIVATE.csv")))
KEY = list(csv.DictReader(open(os.path.join(KIT, "key_F_PRIVATE.csv"), newline="", encoding="utf-8")))
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "   <-- " + str(detail)))


def run(args):
    p = subprocess.run([sys.executable, "-B", "-I"] + args, capture_output=True, text=True)   # -B: no .pyc files, so a frozen kit folder stays as hashed
    return p.returncode, p.stdout + p.stderr


def fresh():
    td = tempfile.mkdtemp(prefix="ftest_")
    res = os.path.join(td, "res")
    os.makedirs(res)
    open(os.path.join(res, "recv05_label-dummy.txt"), "w").write("a reading-test reply\n")   # the shared recv counter starts after it
    return td, res


def make_reply(batch, mode="perfect", tag="x", overrides=None, drop=(), fmt="plain"):
    rows = [r for r in KEY if int(r["batch"]) == batch]
    lines = []
    for r in rows:
        iid = r["id"]
        if iid in drop:
            continue
        if mode == "perfect":
            place = "none" if r["verdict"] == "ok" else r["location"]
        elif mode == "allnone":
            place = "none"
        elif mode == "wrong":
            place = "Z9.9"
        else:
            raise ValueError(mode)
        if overrides and iid in overrides:
            place = overrides[iid]
        phrase = "" if place == "none" else f"wrong form {tag}"
        if fmt == "plain":
            lines.append(f"{iid} | {place}" + (f" | {phrase}" if phrase else ""))
        elif fmt == "table":
            lines.append(f"| {iid} | {place} | {phrase} |")
        elif fmt == "bold":
            lines.append(f"- **{iid}** | `{place}` | {phrase}")
    if fmt == "table":
        lines = ["| item | place | what is wrong |", "|---|---|---|"] + lines
    return "\n".join(lines) + "\n"


def intake(res, text, arm="FR", model="claude", run_n=1, label=None, given=None, extra=()):
    src = os.path.join(os.path.dirname(res), f"src_{abs(hash((text, label, arm, model, run_n))) % 10**8}.txt")
    open(src, "w", encoding="utf-8").write(text)
    args = [os.path.join(HERE, "intake_f.py"), "--results", res, "--src", src, "--arm", arm, "--model", model, "--run", str(run_n),
            "--label", label or f"{arm} {model} run {run_n}", "--received", "2026-11-14 10:00", "--how", "inline"]
    if given:
        args += ["--given-batch", str(given)]
    return run(args + list(extra))


def cells(res):
    p = os.path.join(res, "cells_F.csv")
    return list(csv.DictReader(open(p, newline="", encoding="utf-8"))) if os.path.exists(p) else []


def score(res, out=None, extra=()):
    args = [os.path.join(HERE, "score_f.py"), "--results", res, "--kit", KIT]
    if out:
        args += ["--out", out]
    return run(args + list(extra))


def summary(out):
    return json.load(open(os.path.join(out, "scores_f_summary.json")))["per_run"]


# ------------------------------------------------------------------ parser
print("== parse_f_reply")
r = pf.parse("F01 | A1.2 | x\nF02 | none\n")
check("parser: plain lines", r["answers"]["F01"]["place"] == "A1.2" and r["answers"]["F02"]["place"] == "none" and not r["notes"], r)
r = pf.parse("| item | place | what |\n|---|---|---|\n| F01 | B1.3 | y |\n| F02 | none | |\n")
check("parser: markdown table, header and separator rows ignored", list(r["answers"]) == ["F01", "F02"] and r["answers"]["F01"]["place"] == "B1.3", r)
r = pf.parse("- **F03** | `A1.h` | z\n1. F04: line 2 of C2 - thing\nF05 | B1 header | w\nF06 | A1 line 3 | v\n")
check("parser: bullets, bold, numbering, 'line 2 of C2', 'A1 header', 'A1 line 3'",
      [r["answers"][k]["place"] for k in ("F03", "F04", "F05", "F06")] == ["A1.h", "C2.2", "B1.h", "A1.3"], r["answers"])
r = pf.parse("F07 | none | no fault here\nF08 | No fault found\nF09 | nothing wrong\n")
check("parser: none variants", all(r["answers"][k]["place"] == "none" for k in ("F07", "F08", "F09")), r["answers"])
r = pf.parse("F10 | A1.1 and A1.2 | x\nF11 | the program | y\n")
check("parser: two places take the first with a note; unreadable is None",
      r["answers"]["F10"]["place"] == "A1.1" and r["answers"]["F11"]["place"] is None and len(r["notes"]) == 2, r["notes"])
r = pf.parse("F01 | A1.1 | first\nF01 | A1.2 | second\n")
check("parser: a repeated id keeps the first and is listed", r["answers"]["F01"]["place"] == "A1.1" and r["dups"] == ["F01"], r)
r = pf.parse("Here you go:\nF01 | A1.1 | x\nThanks!\n")
check("parser: text before and after is kept apart", len(r["pre"]) == 1 and len(r["post"]) == 1 and len(r["answers"]) == 1, r)
r = pf.parse("f01 | a1.2 | lower case\n")
check("parser: lower case ids and places", r["answers"].get("F01", {}).get("place") == "A1.2", r)

# ------------------------------------------------------------------ intake
print("== intake_f")
td, res = fresh()
rc, out = intake(res, make_reply(1), given=1)
cs = cells(res)
check("intake: perfect FR batch 1 is data", rc == 0 and len(cs) == 1 and cs[0]["status"] == "data" and cs[0]["batch"] == "1", out)
check("intake: recv number continues the shared counter (dummy recv05 -> recv06)", cs and cs[0]["recv"] == "recv06", cs)
f06 = [f for f in os.listdir(res) if f.startswith("recv06_")]
check("intake: raw file saved read-only", len(f06) == 1 and not os.access(os.path.join(res, f06[0]), os.W_OK) or (len(f06) == 1 and oct(os.stat(os.path.join(res, f06[0])).st_mode)[-3:] == "444"), f06)
pj = json.load(open(os.path.join(res, "parsed_f", "recv06.json")))
check("intake: parsed_f holds 20 answers", len(pj["answers"]) == 20 and pj["answers"]["F01"]["place"] == "A1.2", list(pj["answers"])[:3])
log = open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read()
check("intake: log row and form-check paragraph", "| recv06 |" in log and "recv06 (arm FR, Claude, run 1)" in log, log[-400:])
before = sorted(os.listdir(res))
rc, out = intake(res, make_reply(1, tag="y"), model="grok", extra=["--dry-run"])
check("intake: dry run writes nothing", sorted(os.listdir(res)) == before and "dry run" in out, out)
rc, out = intake(res, make_reply(1), label="FR claude run 1 batch 1 again")
cs = cells(res)
check("intake: byte-identical re-send is a duplicate, no parsed file", cs[-1]["status"] == "duplicate-of-recv06" and not os.path.exists(os.path.join(res, "parsed_f", cs[-1]["recv"] + ".json")), (out, cs[-1]))
rc, out = intake(res, make_reply(1, tag="z"), run_n=1)
check("intake: a second, different reply for a filled cell is a conflict", cells(res)[-1]["status"] == "conflict" and "CELL ALREADY FILLED" in out, out)
shutil.rmtree(td)

td, res = fresh()
rc, out = intake(res, make_reply(2, tag="b2"), given=1)
check("intake: item numbers decide the batch, a wrong label is only a note", cells(res)[-1]["batch"] == "2" and cells(res)[-1]["status"] == "data" and "LABEL MISMATCH" in out, out)
rc, out = intake(res, make_reply(1, drop=("F07",), tag="a"), model="grok")
check("intake: 19 answers is held for review", cells(res)[-1]["status"] == "review" and "ITEMS:" in out, out)
bad = make_reply(1, tag="b") + "F03 | A1.1 | again\n"
rc, out = intake(res, bad, model="gemini")
check("intake: an item answered twice is held for review", cells(res)[-1]["status"] == "review" and "ANSWERED MORE THAN ONCE" in out, out)
rc, out = intake(res, make_reply(1, tag="c") + "Correction: F07 should be A1.2\n", model="chatgpt")
check("intake: a non-answer line that names an item is held (correction note)", cells(res)[-1]["status"] == "review" and "NAMES AN ITEM" in out, out)
rc, out = intake(res, "Here are the answers for F01 to F20:\n" + make_reply(1, tag="d"), model="claude", run_n=2)
check("intake: a preamble that only names the range is a note, not a hold", cells(res)[-1]["status"] == "data" and "TEXT BEFORE ITEM 1" in out, out)
shutil.rmtree(td)

td, res = fresh()
rc, out = intake(res, make_reply(1, tag="e", overrides={"F01": "the program", "F02": "somewhere", "F03": "all of it", "F05": "?"}))
check("intake: four unreadable places hold the reply", cells(res)[-1]["status"] == "review" and "COULD NOT BE READ" in out, out)
rc, out = intake(res, make_reply(1, tag="f", overrides={"F01": "the program", "F02": "somewhere"}), model="grok")
check("intake: two unreadable places are a note, the reply counts", cells(res)[-1]["status"] == "data" and "unreadable place" in out, out)
rc, out = intake(res, make_reply(1, tag="g").replace("wrong form g", "I searched online and found", 1), model="gemini")
check("intake: search words hold the reply", cells(res)[-1]["status"] == "review" and "SEARCH OR CODE-RUN" in out, out)
rc, out = intake(res, make_reply(1, tag="h").replace("wrong form h", "I ran the checker", 1), model="chatgpt")
check("intake: code-run words hold the reply", cells(res)[-1]["status"] == "review" and "SEARCH OR CODE-RUN" in out, out)
shutil.rmtree(td)

td, res = fresh()
rc, out = intake(res, make_reply(1, tag="i").replace("wrong form i", "E-SYN bracket", 1), arm="FN")
check("intake: a verdict code in an FN reply holds it", cells(res)[-1]["status"] == "review" and "GUIDE WORDS IN AN FN REPLY" in out, out)
rc, out = intake(res, make_reply(1, tag="j").replace("wrong form j", "E-SYN bracket", 1), arm="FR", model="grok")
check("intake: the same code in an FR reply is fine", cells(res)[-1]["status"] == "data", out)
rc, out = intake(res, make_reply(1, tag="k").replace("wrong form k", "breaks a rule of logic", 1), arm="FN", model="gemini")
check("intake: ordinary word 'rule' in an FN reply is a note only", cells(res)[-1]["status"] == "data" and "ordinary word" in out, out)
rc, out = intake(res, make_reply(1, tag="l", fmt="table"), arm="FN", model="chatgpt")
check("intake: a markdown-table reply is read (20 answers) and counts", cells(res)[-1]["status"] == "data" and "answers: 20" in out, out)
rc, out = intake(res, make_reply(2, tag="m", fmt="bold"), arm="FN", model="chatgpt")
check("intake: bullets, bold and backticks are read", cells(res)[-1]["status"] == "data" and "answers: 20" in out, out)
long = make_reply(1, tag="n").replace("wrong form n", "one two three four five six seven eight nine ten eleven twelve thirteen fourteen", 1)
rc, out = intake(res, long, arm="FN", model="claude")
check("intake: a phrase over 12 words is a note only", cells(res)[-1]["status"] == "data" and "over 12 words" in out, out)
same = make_reply(1, tag="o")
intake(res, same, arm="FR", model="claude", run_n=1)
rc, out = intake(res, same.rstrip("\n") + "\n\n", arm="FR", model="claude", run_n=2)
check("intake: the same places and phrases under another cell hold the reply (re-send in new bytes)", cells(res)[-1]["status"] == "review" and "SAME PLACE AND PHRASE" in out, out)
shutil.rmtree(td)

td, res = fresh()
rc, out = run([os.path.join(HERE, "intake_f.py"), "--results", res, "--step2", "SILEX-0 has 104 roots, in section 7.", "--arm", "FR", "--model", "claude", "--run", "1", "--received", "10:01"])
log = open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read()
check("step2: right answer is logged", "CORRECT" in out and "STEP 2 answer given 10:01, correct" in log, out)
rc, out = run([os.path.join(HERE, "intake_f.py"), "--results", res, "--step2", "about 60 roots, section 3", "--arm", "FR", "--model", "grok", "--run", "1", "--received", "10:02", "--dry-run"])
check("step2: wrong answer is reported, dry run writes nothing", "WRONG" in out and "about 60" not in open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read(), out)
rc, out = run([os.path.join(HERE, "intake_f.py"), "--results", res, "--step2", "104 roots, section 7", "--arm", "FN", "--model", "grok", "--run", "1"])
check("step2: refused for an FN chat", rc != 0 and "FR chats only" in out, out)
shutil.rmtree(td)
src = open(os.path.join(HERE, "intake_f.py"), encoding="utf-8").read() + open(os.path.join(HERE, "parse_f_reply.py"), encoding="utf-8").read()
check("intake and parser never open the key", not re.search(r"open\([^)]*key_F", src) and "--kit" not in src, "found a key reference")

# ------------------------------------------------------------------ scoring
print("== score_f")


def full_run(res, arm, model, run_n, mode="perfect", over1=None, over2=None, tag=None):
    t = tag or f"{arm}{model}{run_n}{mode}"
    intake(res, make_reply(1, mode, tag=t + "1", overrides=over1), arm=arm, model=model, run_n=run_n)
    intake(res, make_reply(2, mode, tag=t + "2", overrides=over2), arm=arm, model=model, run_n=run_n)


td, res = fresh()
out_dir = os.path.join(td, "out")
full_run(res, "FR", "claude", 1, "perfect")
full_run(res, "FR", "grok", 1, "allnone")
full_run(res, "FN", "gemini", 1, "wrong")
rc, txt = score(res, out_dir)
s = summary(out_dir)
check("score: perfect run = 30/30 found, 30/30 lenient, 30/30 detected, 0/10 false alarms",
      s["FR-claude-1"]["found"] == 30 and s["FR-claude-1"]["lenient"] == 30 and s["FR-claude-1"]["detected"] == 30 and s["FR-claude-1"]["false_alarm"] == 0 and s["FR-claude-1"]["faulty"] == 30 and s["FR-claude-1"]["clean"] == 10, s["FR-claude-1"])
check("score: all-none run = 0 found, 0 detected, 0 false alarms", s["FR-grok-1"]["found"] == 0 and s["FR-grok-1"]["detected"] == 0 and s["FR-grok-1"]["false_alarm"] == 0, s["FR-grok-1"])
check("score: wrong place everywhere = 0 found, 30 detected, 10 false alarms", s["FN-gemini-1"]["found"] == 0 and s["FN-gemini-1"]["detected"] == 30 and s["FN-gemini-1"]["false_alarm"] == 10, s["FN-gemini-1"])
check("score: random baseline line says 7.7 of 30", "finds 7.7 of 30" in txt, txt)
rows = list(csv.DictReader(open(os.path.join(out_dir, "scores_f_items.csv"), newline="", encoding="utf-8")))
check("score: items csv has 40 rows per run", len(rows) == 120 and {r["arm"] for r in rows} == {"FR", "FN"}, len(rows))
check("score: a per-verdict table lists all 15 verdicts", all(v in txt for v in ("E-SYN", "E-LEX", "E-ARITY", "E-KIND", "E-NAME", "E-REDEF", "E-HEAD", "E-TIME", "E-QUOTE", "E-ENGLISH", "E-BUDGET", "E-REF", "E-COUNT", "E-CODE", "E-MATH")), txt[-1500:])
shutil.rmtree(td)

td, res = fresh()
out_dir = os.path.join(td, "out")
f11 = next(r for r in KEY if r["verdict"] == "E-REDEF" and r["also_accept"])
f31 = [r for r in KEY if r["verdict"] == "E-REDEF"]
ov1 = {r["id"]: r["also_accept"] for r in f31 if r["batch"] == "1" and r["also_accept"]}
ov2 = {r["id"]: r["also_accept"] for r in f31 if r["batch"] == "2" and r["also_accept"]}
full_run(res, "FR", "claude", 1, "perfect", over1=ov1, over2=ov2)
score(res, out_dir)
s = summary(out_dir)["FR-claude-1"]
check("score: the first definition counts only in the lenient score", s["found"] == 28 and s["lenient"] == 30 and s["detected"] == 30, s)
shutil.rmtree(td)

td, res = fresh()
out_dir = os.path.join(td, "out")
clean1 = next(r["id"] for r in KEY if r["batch"] == "1" and r["verdict"] == "ok")
fault1 = next(r["id"] for r in KEY if r["batch"] == "1" and r["verdict"] != "ok")
full_run(res, "FR", "claude", 1, "perfect", over1={clean1: "the program", fault1: "the program"})
score(res, out_dir)
s = summary(out_dir)["FR-claude-1"]
check("score: unreadable place = claimed: a false alarm on a clean item, detected but not found on a faulty one",
      s["false_alarm"] == 1 and s["detected"] == 30 and s["found"] == 29 and s["unreadable"] == 2, s)
shutil.rmtree(td)

td, res = fresh()
out_dir = os.path.join(td, "out")
intake(res, make_reply(1, tag="half"), arm="FN", model="grok", run_n=1)
rc, txt = score(res, out_dir)
s = summary(out_dir)["FN-grok-1"]
check("score: one batch only is scored on its items and flagged", s["faulty"] == 15 and s["clean"] == 5 and s["found"] == 15 and "ONE BATCH ONLY" in txt, (s, txt))
shutil.rmtree(td)

td, res = fresh()
out_dir = os.path.join(td, "out")
full_run(res, "FR", "claude", 1, "perfect")
intake(res, make_reply(1, "perfect", tag="held", drop=("F07",)), arm="FR", model="grok", run_n=1)
intake(res, make_reply(2, "perfect", tag="held2"), arm="FR", model="grok", run_n=1)
rc, txt = score(res, out_dir)
grok_line = next((l for l in txt.split("Per arm and model")[0].split("\n") if " grok " in l), "")
check("score: a batch held for review is left out by default (grok has batch 2 only, flagged)", "ONE BATCH ONLY" in grok_line and "15/15" in grok_line, txt)
rc, txt = score(res, out_dir, ["--include-review"])
grok_line = next((l for l in txt.split("Per arm and model")[0].split("\n") if " grok " in l), "")
check("score: --include-review brings it in and lists the unanswered item", "no answer for ['F07']" in grok_line and "ONE BATCH ONLY" not in grok_line, txt)
shutil.rmtree(td)

td, res = fresh()
out_dir = os.path.join(td, "out")
full_run(res, "FR", "claude", 1, "allnone")
cs = cells(res)
json.dump({cs[0]["recv"]: {fault1: {"place": next(r["location"] for r in KEY if r["id"] == fault1), "reason": "model corrected itself in the same reply"}}},
          open(os.path.join(res, "corrections_F.json"), "w"))
rc, txt = score(res, out_dir)
s = summary(out_dir)["FR-claude-1"]
check("score: a recorded correction is applied and listed", s["found"] == 1 and "Corrections applied" in txt, (s, txt))
shutil.rmtree(td)

lo, hi = score_f.wilson(30, 30)
lo0, hi0 = score_f.wilson(0, 30)
check("score: Wilson interval (30/30 -> lower about 0.886; 0/30 -> upper about 0.114)", abs(lo - 0.886) < 0.002 and hi == 1.0 and abs(hi0 - 0.114) < 0.002 and lo0 == 0.0, (lo, hi, lo0, hi0))
check("score: a phrase is cut after 12 words", score_f.cut_words("a b c d e f g h i j k l m n") == "a b c d e f g h i j k l", "")

# ------------------------------------------------------------------ Note 1 of Test F: run-on lines, and reparse_f.py
print("== run-on lines (Note 1 of Test F) and reparse_f")
import reparse_f  # noqa: E402


def run_on_reply(batch, mode="perfect", tag="x", drop=(), app_line=True):
    """The lines of make_reply(...) joined into ONE line, after an app line: what a model that writes all its answers on one line sends."""
    body = make_reply(batch, mode, tag=tag, drop=drop).strip().split("\n")
    return ("Worked for 9s\n\n" if app_line else "") + " ".join(body) + "\n"


def flags_of(out):
    """The held reasons and the notes that intake_f.py printed."""
    sev, nts, mode = [], [], None
    for line in out.split("\n"):
        if line.startswith("HELD FOR REVIEW"):
            mode = "s"
        elif line.startswith("notes:"):
            mode = "n"
        elif line.startswith("(dry run") or line.startswith("written:"):
            mode = None
        elif line.startswith("  - ") and mode:
            (sev if mode == "s" else nts).append(line[4:])
    return sev, nts


REPARSE = os.path.join(HERE, "reparse_f.py")
r = pf.parse("F01 | A1.2 | first thing. F02 | none F03 | B1.h | third\n")
check("parser: one run-on line is cut at each item code (3 answers, places, phrases, line number kept)",
      list(r["answers"]) == ["F01", "F02", "F03"] and [r["answers"][k]["place"] for k in r["answers"]] == ["A1.2", "none", "B1.h"]
      and r["answers"]["F01"]["phrase"] == "first thing." and r["answers"]["F03"]["phrase"] == "third"
      and len({v["line_no"] for v in r["answers"].values()}) == 1 and any("RUN-ON LINE(S): 3 answers" in n for n in r["notes"]), r)
multi = pf.parse(make_reply(1, tag="same"))
one = pf.parse(run_on_reply(1, tag="same", app_line=False))
pick = lambda x: {k: (v["place"], v["phrase"]) for k, v in x["answers"].items()}
check("parser: the same 20 answers on 20 lines or on one line give the same places and phrases; only the one-line reply gets the note",
      pick(multi) == pick(one) and len(pick(one)) == 20 and not any("RUN-ON" in n for n in multi["notes"]) and any("RUN-ON" in n for n in one["notes"]), (multi["notes"], one["notes"]))
r = pf.parse("F01 | A1.2 | same as F02 and F03\n")
check("parser: an item code without a bar inside a phrase does not cut the line", list(r["answers"]) == ["F01"] and r["answers"]["F01"]["phrase"] == "same as F02 and F03" and not r["notes"], r)
r = pf.parse("- **F01** | `A1.2` | x **F02** | `none`\n")
check("parser: bullets, bold and backticks on a run-on line are stripped first, then the line is cut",
      list(r["answers"]) == ["F01", "F02"] and r["answers"]["F01"]["place"] == "A1.2" and r["answers"]["F02"]["place"] == "none", r)
r = pf.parse("Worked for 9s\n\nF01 | A1.2 | a. F02 | none\n")
check("parser: the app line stays apart as text before the first answer", len(r["pre"]) == 1 and r["pre"][0][1] == "Worked for 9s" and len(r["answers"]) == 2, r)

td, res = fresh()
rc, out = intake(res, run_on_reply(1), given=1, extra=["--dry-run"])
check("intake: a one-line reply of 20 answers is not held and the run-on is noted (dry run)",
      "held for review: nothing" in out and "RUN-ON LINE(S): 20 answers" in out and "answers: 20 (F01..F20)" in out, out)
rc, out = intake(res, run_on_reply(1), given=1)
cs = cells(res)
pj = json.load(open(os.path.join(res, "parsed_f", cs[0]["recv"] + ".json")))
check("intake: that reply is filed as data with 20 answers, and the log paragraph carries the note",
      cs[0]["status"] == "data" and len(pj["answers"]) == 20 and "RUN-ON" in open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read(), out)
shutil.rmtree(td)

td, res = fresh()
rc, out = intake(res, run_on_reply(1, drop=("F07",)), given=1)
cs = cells(res)
check("intake: a one-line reply with one answer missing is still held (ITEMS)", cs[0]["status"] == "review" and "ITEMS: found 19" in out, out)
rc, out = run([REPARSE, "--results", res, "--recv", cs[0]["recv"]])
check("reparse: a hold that remains keeps the row held and changes nothing",
      rc == 1 and "STILL HELD" in out and "nothing changed" in out and cells(res)[0]["status"] == "review"
      and not any(f.endswith(".before_note1.json") for f in os.listdir(os.path.join(res, "parsed_f"))), out)
shutil.rmtree(td)

td, res = fresh()
rc, out = intake(res, run_on_reply(1), given=1)
cs = cells(res)
rid = cs[0]["recv"]
pjp = os.path.join(res, "parsed_f", rid + ".json")
pj = json.load(open(pjp))
first = next(iter(pj["answers"]))
pj["answers"], pj["order"] = {first: pj["answers"][first]}, [first]       # what the frozen parser left: one answer on one line
json.dump(pj, open(pjp, "w"))
cs[0]["status"] = "review"
with open(os.path.join(res, "cells_F.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(reparse_f.inf.HEADER)
    for row in cs:
        w.writerow([row[h] for h in reparse_f.inf.HEADER])
log_before = open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read()
rc, out = run([REPARSE, "--results", res, "--recv", rid, "--dry-run"])
check("reparse: a held run-on reply is re-read in a dry run, and nothing is written",
      rc == 0 and "no hold remains" in out and "dry run" in out and cells(res)[0]["status"] == "review"
      and open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read() == log_before and len(json.load(open(pjp))["answers"]) == 1, out)
rc, out = run([REPARSE, "--results", res, "--recv", rid, "--when", "2026-11-14 18:40"])
keep = os.path.join(res, "parsed_f", rid + ".before_note1.json")
cs = cells(res)
pj = json.load(open(pjp))
check("reparse: the hold is lifted (data), 20 answers are parsed, the first parse is kept read-only",
      rc == 0 and cs[0]["status"] == "data" and cs[0]["batch"] == "1" and len(pj["answers"]) == 20 and os.path.exists(keep)
      and oct(os.stat(keep).st_mode)[-3:] == "444" and len(json.load(open(keep))["answers"]) == 1, (rc, out))
log = open(os.path.join(res, "received_log_F.md"), encoding="utf-8").read()
check("reparse: a form-check paragraph and a dated decision line are in the log",
      f"{rid} re-read under Note 1 of Test F (2026-11-14 18:40" in log and f"- 2026-11-14 18:40: {rid} (FR-claude-1-b1) re-read under Note 1" in log, log[-700:])
rc, out = run([REPARSE, "--results", res, "--recv", rid])
check("reparse: a row that is no longer held is refused", rc != 0 and "only a held reply" in out, out)
out_dir = os.path.join(td, "out")
rc, txt = score(res, out_dir)
check("score: the re-read reply is scored with its 20 answers (batch 1 only, flagged)", rc == 0 and "ONE BATCH ONLY" in txt, txt[-300:])
shutil.rmtree(td)

# the checks of reparse_f.evaluate must be those of intake_f.py: same held reasons and same notes on the same replies
td, res = fresh()
cases = [("perfect batch 1 (one answer per line)", make_reply(1, tag="agree1"), "FR", "claude", 1, 1),
         ("one-line batch 2", run_on_reply(2, tag="agree2"), "FR", "claude", 1, 2),
         ("one-line batch 1, F07 missing", run_on_reply(1, tag="agree3", drop=("F07",)), "FR", "grok", 1, 1),
         ("FN reply with a guide word", make_reply(1, tag="see section 7"), "FN", "gemini", 1, 1),
         ("label that disagrees with the item numbers", make_reply(2, tag="agree5"), "FR", "chatgpt", 1, 1)]
agree = True
for name, text, arm, mdl, rn, given in cases:
    rc, out = intake(res, text, arm=arm, model=mdl, run_n=rn, given=given, extra=["--dry-run"])
    ev = reparse_f.evaluate(text, arm, mdl, rn, given, cells(res), res, "")
    same_flags = flags_of(out) == (ev["severe"], ev["notes"])
    agree = agree and same_flags
    if not same_flags:
        print("   differs:", name, flags_of(out), (ev["severe"], ev["notes"]))
check("reparse_f.evaluate gives the same held reasons and notes as intake_f.py on five different replies", agree)
shutil.rmtree(td)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
