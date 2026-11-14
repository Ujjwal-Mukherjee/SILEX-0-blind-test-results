#!/usr/bin/env python3
"""Stage blind judge sheets for judge agents (JUDGING_PROCEDURE.md). FORM ONLY: this program only copies and groups files; it never reads a score.

  - copies the sheet files (sheet_CODE.txt) of one or more sheet folders into WORK/inbox/ (read-only copies) and makes an empty WORK/outbox/;
    WORK holds nothing else: no map, no key, no log. An agent is told to open only the files of its own list.
  - puts the codes in a random order (seed given by the caller and written in the log before the call) and splits them into groups of at most --per-agent sheets
    (sizes made as equal as possible); one judge agent gets one group.
  - writes, for each group, the exact text to give to the agent (GROUPS/group_NN_prompt.txt) and the private list of groups (GROUPS/groups_PRIVATE.csv, codes only).

Usage:
  python3 -I stage_judging.py --sheets DIR [DIR ...] --workdir WORK --groups GROUPS --seed N [--per-agent 6]
WORK and GROUPS must not exist yet or must be empty: staging is done once per judge pass.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import stat
import sys

PROMPT = """You are a scoring judge. You have {n} tasks. Each task is one file under {inbox}/ (listed below). Each file is a complete, self-contained scoring task: do exactly what it says. Treat every file as a separate task and judge each on its own.

For each file, write your reply to the file named next to it under {outbox}/: exactly the lines the sheet asks for and nothing else (no heading, no comments, no blank lines between items).

Do not read or list any other file or folder, and do not use search, code execution or any tool other than reading the listed files and writing the reply files. When all reply files are written, answer with the single word: done

Tasks (read from -> write to):
{tasks}
"""


def die(msg):
    print("stage_judging.py: " + msg, file=sys.stderr)
    sys.exit(1)


def empty_or_new(path):
    if os.path.exists(path) and os.listdir(path):
        die("%s exists and is not empty; staging is done once per judge pass" % path)
    os.makedirs(path, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", nargs="+", required=True)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--groups", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--per-agent", type=int, default=6)
    a = ap.parse_args()
    if a.per_agent < 1:
        die("--per-agent must be at least 1")
    found = {}
    for d in a.sheets:
        for fn in sorted(os.listdir(d)):
            m = re.fullmatch(r"sheet_([A-Z0-9]{4})\.txt", fn)
            if not m:
                die("%s/%s is not a sheet file (sheet_CODE.txt)" % (d, fn))
            if m.group(1) in found:
                die("sheet code %s occurs twice" % m.group(1))
            found[m.group(1)] = os.path.join(d, fn)
    if not found:
        die("no sheets")
    empty_or_new(a.workdir)
    empty_or_new(a.groups)
    inbox, outbox = os.path.join(a.workdir, "inbox"), os.path.join(a.workdir, "outbox")
    os.makedirs(inbox)
    os.makedirs(outbox)
    for code, src in sorted(found.items()):
        data = open(src, "rb").read()
        dst = os.path.join(inbox, "sheet_%s.txt" % code)
        with open(dst, "wb") as f:
            f.write(data)
        os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    codes = sorted(found)
    random.Random(a.seed).shuffle(codes)
    ng = math.ceil(len(codes) / a.per_agent)
    base, extra = divmod(len(codes), ng)
    sizes = [base + 1] * extra + [base] * (ng - extra)       # as equal as possible, none above --per-agent
    groups, i = [], 0
    for sz in sizes:
        groups.append(codes[i:i + sz])
        i += sz
    rows = []
    for g, cs in enumerate(groups, 1):
        tasks = "\n".join("%d. %s/sheet_%s.txt -> %s/reply_%s.txt" % (i, inbox, c, outbox, c) for i, c in enumerate(cs, 1))
        text = PROMPT.format(n=len(cs), inbox=inbox, outbox=outbox, tasks=tasks)
        with open(os.path.join(a.groups, "group_%02d_prompt.txt" % g), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        rows.append(dict(group=g, n=len(cs), codes=" ".join(cs)))
    with open(os.path.join(a.groups, "groups_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["group", "n", "codes"])
        w.writeheader()
        w.writerows(rows)
    json.dump(dict(seed=a.seed, per_agent=a.per_agent, n_sheets=len(codes), n_groups=len(groups),
                   prompt_template_sha256=hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
                   script_sha16=hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16]), open(os.path.join(a.groups, "stage_info_PRIVATE.json"), "w"), indent=2)
    print("staged %d sheets in %s; %d groups of %s sheets (seed %d); prompts in %s" % (len(codes), inbox, len(groups), "/".join(str(len(c)) for c in groups), a.seed, a.groups))


if __name__ == "__main__":
    main()
