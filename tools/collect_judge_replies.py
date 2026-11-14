#!/usr/bin/env python3
"""Collect the reply files that judge agents wrote and check their FORM (JUDGING_PROCEDURE.md). It never prints, sums or compares a score, and never fills in anything.

For every sheet code of the given private map that has a file WORK/outbox/reply_CODE.txt:
  - the file is copied byte for byte to REPLIES/reply_CODE.txt (read-only) and its sha256 is written to REPLIES/collected_log.csv;
  - its form is checked with the same rules as check_judge_reply.py (reading sheets) or check_judge_reply_rt.py (round-trip sheets): one line per item, exactly the sheet's
    facts, 0 or 1, a false count. The result goes to SCORES/CODE.json (the shape of check_judge_reply.py --json) for the aggregator and the reliability tools.
  - what is printed: the sheet code, how many items are usable, the status (clean, notes, redo) and, for a redo, the items with a problem and the problem. No score, no reason.
With --suffix _redo1 (a redo pass, JUDGING_PROCEDURE.md rule 7) the copy is reply_CODE_redo1.txt and the JSON is CODE_redo1.json, next to the first reply's files; the outbox file is still reply_CODE.txt
(the redo sheet has the same code and the map is the redo map made by make_redo_sheet.py).
A reply file that is already collected and unchanged is skipped. An outbox file that differs from the collected one is NOT collected: it is reported (a second reply for
a sheet is a redo and is handled by hand, not overwritten). A sheet with no reply file is listed as missing.
The kind of a sheet is read from the map: arm R or N = reading; arm RTP or RTE = round trip; a map with a `kind` column (second-judge maps) uses that column.

Usage:
  python3 -I collect_judge_replies.py --outbox WORK/outbox --map MAP --kit KIT --replies REPLIES --scores SCORES [--codes AB12,CD34] [--suffix _redo1]
Exit code: 0 all sheets of the map collected with status clean or notes, 1 some sheet missing, redo, or changed, 2 usage.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_judge_reply as cj  # noqa: E402
import check_judge_reply_rt as cjr  # noqa: E402


def kind_of(row):
    if row.get("kind") in ("reading", "rt"):
        return row["kind"]
    if row.get("arm") in ("R", "N"):
        return "reading"
    if row.get("arm") in ("RTP", "RTE"):
        return "rt"
    sys.exit("collect_judge_replies.py: sheet %s has no usable kind or arm" % row.get("code"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outbox", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--replies", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--codes")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    if not re.fullmatch(r"(_[a-z0-9]+)?", a.suffix):
        print("--suffix must look like _redo1", file=sys.stderr)
        sys.exit(2)
    rows = list(csv.DictReader(open(a.map, newline="", encoding="utf-8")))
    if a.codes:
        want = set(a.codes.split(","))
        rows = [r for r in rows if r["code"] in want]
        if len(rows) != len(want):
            print("some --codes are not in the map", file=sys.stderr)
            sys.exit(2)
    os.makedirs(a.replies, exist_ok=True)
    os.makedirs(a.scores, exist_ok=True)
    exp = {"reading": cj.expected_facts(a.kit), "rt": cjr.expected_c_facts(a.kit)}
    log_path = os.path.join(a.replies, "collected_log.csv")
    new_log = not os.path.exists(log_path)
    logf = open(log_path, "a", newline="", encoding="utf-8")
    lw = csv.writer(logf)
    if new_log:
        lw.writerow(["code", "sha256", "bytes", "collected", "status", "items_usable"])
    bad = 0
    for r in sorted(rows, key=lambda x: x["code"]):
        code = r["code"]
        src = os.path.join(a.outbox, "reply_%s.txt" % code)
        dst = os.path.join(a.replies, "reply_%s%s.txt" % (code, a.suffix))
        if not os.path.exists(src):
            print("%s: MISSING (no reply file in the outbox)" % code)
            bad += 1
            continue
        data = open(src, "rb").read()
        if os.path.exists(dst):
            if open(dst, "rb").read() == data:
                print("%s: already collected, unchanged" % code)
            else:
                print("%s: the outbox file differs from the collected reply; NOT collected (a second reply is a redo, handled by hand)" % code)
                bad += 1
            continue
        text = data.decode("utf-8", errors="replace")
        order = set(r["order"].split())
        got, problems, warnings, redo = cj.check(text, order, exp[kind_of(r)])
        status = "redo" if redo else ("notes" if warnings else "clean")
        with open(dst, "wb") as f:
            f.write(data)
        os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        json.dump(dict(code=code, status=status, redo_items=redo, problems=["%s: %s" % (i, m) for i, m in problems], warnings=warnings, items=got),
                  open(os.path.join(a.scores, code + a.suffix + ".json"), "w"), indent=1)
        lw.writerow([code + a.suffix, hashlib.sha256(data).hexdigest(), len(data), datetime.datetime.now().isoformat(timespec="seconds"), status, len(got)])
        logf.flush()
        print("%s: %d of %d items usable; status: %s" % (code, len(got), len(order), status))
        for it, msg in problems:
            print("  PROBLEM %s: %s" % (it, msg))
        if redo:
            print("  ask the judge again for: " + " ".join(redo))
            bad += 1
    logf.close()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
