#!/usr/bin/env python3
"""Tests for intake.py and the trailer gate of build_judge_sheets.py, run on a TEMP COPY of the results folder.
The replies used are variants of real replies made only for the test; nothing is written to the real folder.
Fixed 2026-11-14 02:1x IST: the first version hard-coded recv20/recv22 and run 2 (the state of the folder at 20:5x on 13 Nov). The test now takes the
next recv number from the temp copy and uses RUN = 9, a run number the real data never uses, so it passes however far the real folder has grown."""
import csv, glob, json, os, re, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
KIT = "/home/claude/silex_blind_test"
TMP = tempfile.mkdtemp(prefix="intake_test_")
RES = os.path.join(TMP, "silex_results")
shutil.copytree(REAL, RES, ignore=shutil.ignore_patterns("tools", "judging", "__pycache__"))
fails = []


def ok(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def raw(rid):
    return open(glob.glob(os.path.join(RES, f"{rid}_*.txt"))[0], encoding="utf-8").read()


def variant_all_different(text, tag):
    out = []
    for ln in text.split("\n"):
        out.append(ln if (not ln.strip() or re.match(r"^#\d{2}$", ln.strip())) else ln + f" ({tag})")
    return "\n".join(out)


def variant_mostly_same(text):
    done, out = 0, []
    for ln in text.split("\n"):
        if done < 2 and ln.strip() and not re.match(r"^#\d{2}$", ln.strip()):
            ln, done = ln + " (v2)", done + 1
        out.append(ln)
    return "\n".join(out)


def intake(text, arm, model, run, label, given_batch=None, dry=False, how="attached"):
    src = os.path.join(TMP, "src.txt")
    open(src, "w", encoding="utf-8").write(text)
    cmd = [sys.executable, "-I", os.path.join(HERE, "intake.py"), "--results", RES, "--src", src, "--arm", arm, "--model", model,
           "--run", str(run), "--label", label, "--received", "2026-11-13 23:00", "--how", how]
    if given_batch:
        cmd += ["--given-batch", str(given_batch)]
    if dry:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def cells():
    return list(csv.DictReader(open(os.path.join(RES, "cells.csv"), newline="", encoding="utf-8")))


def last_row():
    return cells()[-1]


RUN = 9  # unused in the real data (the plan has runs 1 to 3), so no filled cell of the temp copy is in the way


def next_n():
    return max(int(re.match(r"recv(\d+)_", os.path.basename(f)).group(1)) for f in glob.glob(os.path.join(RES, "recv*_*.txt"))) + 1


def rid(n):
    return f"recv{n:02d}"


n_files = len(glob.glob(os.path.join(RES, "recv*_*.txt")))
log0 = open(os.path.join(RES, "received_log.md"), encoding="utf-8").read()

# T1 dry run on an exact copy of recv16: duplicate, nothing written
rc, out = intake(raw("recv16"), "R", "gemini", RUN, "dry", 1, dry=True)
ok(rc == 0 and "DUPLICATE" in out and "dry run" in out, "dry run on an identical file: reports DUPLICATE")
ok(len(glob.glob(os.path.join(RES, "recv*_*.txt"))) == n_files and open(os.path.join(RES, "received_log.md"), encoding="utf-8").read() == log0,
   "dry run writes nothing")

# T2 real duplicate
n2 = next_n()
rc, out = intake(raw("recv16"), "R", "gemini", RUN, "Gemini R run 9 batch 1 (dup)", 1)
r = last_row()
ok(r["status"] == "duplicate-of-recv16" and r["recv"] == rid(n2), f"duplicate: cells.csv row marked duplicate-of-recv16 as {rid(n2)}")
f = glob.glob(os.path.join(RES, f"{rid(n2)}_*.txt"))[0]
ok(not (os.stat(f).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)), "duplicate: file saved read-only")
ok(f"| {rid(n2)} |" in open(os.path.join(RES, "received_log.md"), encoding="utf-8").read(), "duplicate: row added to the log table")
ok(not os.path.exists(os.path.join(RES, "parsed", f"{rid(n2)}.json")), "duplicate: no parsed file made")

# T3 almost the same as an earlier reply: held for review
rc, out = intake(variant_mostly_same(raw("recv16")), "R", "gemini", RUN, "Gemini R run 9 batch 1", 1)
ok(last_row()["status"] == "review" and "SAME ITEM TEXT" in out, "18 of 20 items identical to an earlier reply: held for review")

# T4 a clean new reply
new17 = variant_all_different(raw("recv17"), "x")
n4 = next_n()
rc, out = intake(new17, "R", "gemini", RUN, "Gemini R run 9 batch 2", 2)
r = last_row()
ok(r["status"] == "data" and r["batch"] == "2" and r["run"] == str(RUN) and r["recv"] == rid(n4), f"clean reply: status data, cell gemini R run {RUN} batch 2 as {rid(n4)}")
log = open(os.path.join(RES, "received_log.md"), encoding="utf-8").read()
ok(f"| {rid(n4)} |" in log and f"{rid(n4)} (arm R, Gemini, run {RUN})" in log and f"R-gemini-{RUN}-b2" in log, "clean reply: table row and form-check paragraph in the log")
tbl_rows = [i for i, l in enumerate(log.split("\n")) if re.match(r"^\| recv\d+ \|", l)]
ok(tbl_rows == list(range(tbl_rows[0], tbl_rows[0] + len(tbl_rows))), "log table rows stay in one block")
ok(log.index(f"{rid(n4)} (arm R") < log.index("## Metadata the protocol asks for") and log.index(f"| {rid(n4)} |") < log.index("## Form check"),
   "new row sits before the Form check heading, new paragraph before the Metadata heading")

# T5 same cell again: conflict
rc, out = intake(variant_all_different(raw("recv17"), "y"), "R", "gemini", RUN, "Gemini R run 9 batch 2 again", 2)
ok(last_row()["status"] == "conflict" and "CELL ALREADY FILLED" in out, "same cell filled twice: status conflict, reported")

# T6 guide words in an N reply
t = raw("recv18").replace("#01\n", "#01\nThe guide says it is pinned. ", 1)
rc, out = intake(variant_all_different(t, "n"), "N", "gemini", RUN, "Gemini N test", 1)
ok(last_row()["status"] == "review" and "GUIDE WORDS IN AN N REPLY" in out, "guide words in an N reply: held for review")

# T7 over the word limit
t = raw("recv16")
t = re.sub(r"(?m)^(#05)\n(.*)$", lambda m: m.group(1) + "\n" + m.group(2) + " " + " ".join(["extra"] * 130), t, count=1)
rc, out = intake(variant_all_different(t, "o"), "R", "claude", RUN, "Claude R over", 1)
ok(last_row()["status"] == "review" and "OVER 120 WORDS" in out, "an item over 120 words: held for review")

# T8 label mismatch is a note, not a hold (item numbers rule)
rc, out = intake(variant_all_different(raw("recv19"), "m"), "N", "grok", RUN, "Grok N label says batch 1", 1)
ok(last_row()["batch"] == "2" and last_row()["status"] == "data" and "LABEL MISMATCH" in out, "label says batch 1, items are batch 2: filed as batch 2 with a note")

# T9 trailer: noted, and the sheet builder refuses until corrections.json has an entry
t = variant_all_different(raw("recv16"), "t").rstrip("\n") + "\n\nNote: item #05 should say job instead of jobs.\n"
rc, out = intake(t, "R", "grok", RUN, "Grok R run 9 batch 1 trailer", 1)
ok("TRAILER" in out and last_row()["status"] == "data", "trailer after the last item: noted, reply still data")
rc = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build_judge_sheets.py"), "--results", RES, "--kit", KIT,
                     "--out", os.path.join(TMP, "sheets_out"), "--seed", "1"], capture_output=True, text=True)
ok(rc.returncode != 0 and "no entry for it" in (rc.stdout + rc.stderr), "sheet builder refuses a trailer without a corrections.json entry")
last = last_row()["recv"]
c = json.load(open(os.path.join(RES, "corrections.json")))
c[last] = {"source": "test", "items": {"#05": "Note: item #05 should say job instead of jobs."}}
json.dump(c, open(os.path.join(RES, "corrections.json"), "w"))
rc = subprocess.run([sys.executable, "-I", os.path.join(HERE, "build_judge_sheets.py"), "--results", RES, "--kit", KIT,
                     "--out", os.path.join(TMP, "sheets_out"), "--seed", "1"], capture_output=True, text=True)
n_data = sum(1 for r in cells() if r["status"] == "data")
ok(rc.returncode == 0 and f"sheets built: {n_data}" in rc.stdout, f"after the entry is added, sheets build for all {n_data} data rows (held and duplicate rows are skipped)")

# T10 STEP 2
base =[sys.executable, "-I", os.path.join(HERE, "intake.py"), "--results", RES, "--arm", "R", "--model", "gemini", "--run", str(RUN), "--received", "22:59"]
r1 = subprocess.run(base + ["--step2", "SILEX-0 has 104 roots, and the packs are described in section 7."], capture_output=True, text=True)
ok("CORRECT" in r1.stdout, "STEP 2 right answer recognised")
r2 = subprocess.run(base + ["--step2", "SILEX-0 has 107 roots, packs in section 6."], capture_output=True, text=True)
ok("WRONG" in r2.stdout and "new chat" in r2.stdout, "STEP 2 wrong answer recognised, protocol rule shown")
log = open(os.path.join(RES, "received_log.md"), encoding="utf-8").read()
ok(log.count("STEP 2 answer given 22:59") == 2 and log.index("STEP 2 answer given 22:59") < log.index("## Handling decisions"),
   "both STEP 2 lines sit at the end of the Metadata part")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
