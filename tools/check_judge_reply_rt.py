#!/usr/bin/env python3
"""Check the FORM of a judge's reply to one round-trip sheet (arms RTP and RTE). Never changes a score, never guesses a missing one.

Same rules as check_judge_reply.py (RT_handling_rules.md, rule 9), with one difference: the sheet shows the C facts only, so the expected facts of an item
are its C facts with their numbers from facts.csv. A line that scores an S fact, or leaves out a C fact, makes that item "redo".

Usage:
  python3 -I check_judge_reply_rt.py --map sheets_map_PRIVATE.csv --kit KITDIR --code CODE --reply FILE [--json OUT]
Exit code: 0 clean or warnings only, 1 some items need a redo, 2 usage or file problem.
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_judge_reply as cj   # noqa: E402


def expected_c_facts(kit):
    ex = {}
    with open(os.path.join(kit, "facts.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["type"] != "C":
                continue
            m = re.match(r"^(#\d{2})\.F(\d+)$", r["fact_id"])
            ex.setdefault(m.group(1), set()).add(int(m.group(2)))
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--reply", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.map, newline="", encoding="utf-8")) if r["code"] == a.code]
    if len(rows) != 1:
        print(f"sheet code {a.code!r} not found exactly once in the map", file=sys.stderr)
        sys.exit(2)
    exp_items = set(rows[0]["order"].split())
    got, problems, warnings, redo = cj.check(open(a.reply, encoding="utf-8").read(), exp_items, expected_c_facts(a.kit))
    status = "redo" if redo else ("notes" if warnings else "clean")
    print(f"sheet {a.code}: {len(got)} of {len(exp_items)} items usable; status: {status}")
    for it, msg in problems:
        print(f"  PROBLEM {it}: {msg}")
    for w in warnings:
        print(f"  note: {w}")
    if redo:
        print("  ask the judge again for: " + " ".join(redo))
    if a.json:
        json.dump(dict(code=a.code, status=status, redo_items=redo, problems=[f"{i}: {m}" for i, m in problems],
                       warnings=warnings, items=got), open(a.json, "w"), indent=1)
    sys.exit(1 if redo else 0)


if __name__ == "__main__":
    main()
