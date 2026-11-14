#!/usr/bin/env python3
"""Check the FORM of a judge's reply to one sheet. Never changes a score, never guesses a missing one.

The frozen judge prompt asks for one line per item, exactly:
  #NN | F1=1 F2=0 F3=1 | false=0 | reason for any 0, at most 12 words

Rules (written before any judging; same for every sheet):
  - Every item of the sheet must have exactly one line, with exactly the sheet's facts F1..Fk, each 0 or 1,
    and false=<whole number>. Anything else makes that item "redo": the judge is asked again for those
    items only, with the same prompt. Nothing is filled in by me.
  - Cosmetic wrappers (leading "-", "*", ">" or backticks) are stripped and noted as a warning.
  - Other text (a heading, a "SHEET XXXX" echo, remarks) is ignored and noted as a warning.
  - A 0 without a reason, or a reason over 12 words, is a warning only.

Usage:
  python3 -I check_judge_reply.py --map sheets_map_PRIVATE.csv --kit KITDIR --code CODE --reply FILE [--json OUT]
Exit code: 0 clean or warnings only, 1 some items need a redo, 2 usage or file problem.
"""
import argparse, csv, json, os, re, sys

LINE = re.compile(r"^(#\d{2})\s*\|\s*((?:F\d+\s*=\s*[01]\s*)+)\|\s*false\s*=\s*(\d+)\s*(?:\|\s*(.*))?$")
PAIR = re.compile(r"F(\d+)\s*=\s*([01])")
WRAP = re.compile(r"^[\s>*`_\-•]+")


def expected_facts(kit):
    ex = {}
    with open(os.path.join(kit, "facts.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = re.match(r"^(#\d{2})\.F(\d+)$", r["fact_id"])
            ex.setdefault(m.group(1), set()).add(int(m.group(2)))
    return ex


def check(reply, exp_items, exp_facts):
    problems, warnings, got, seen = [], [], {}, {}
    for raw in reply.splitlines():
        line = raw.strip()
        if not line:
            continue
        stripped = line
        if not line.startswith("#"):
            stripped = WRAP.sub("", line).rstrip("`* ")
        if not re.match(r"^#\d{2}\b", stripped):
            warnings.append(f"ignored text: {line[:70]!r}")
            continue
        if stripped != line:
            warnings.append(f"decorated line, wrapper stripped: {line[:40]!r}")
        stripped = stripped.rstrip("`* ")
        m = LINE.match(stripped)
        item = stripped[:3]
        if not m:
            problems.append((item, "malformed line: " + stripped[:70]))
            seen[item] = seen.get(item, 0) + 1
            continue
        item = m.group(1)
        seen[item] = seen.get(item, 0) + 1
        if seen[item] > 1:
            problems.append((item, "item appears more than once"))
            continue
        pairs = PAIR.findall(m.group(2))
        ks = [int(k) for k, _ in pairs]
        if len(ks) != len(set(ks)):
            problems.append((item, "a fact is scored twice"))
            continue
        if item not in exp_items:
            problems.append((item, "item is not on this sheet"))
            continue
        missing = sorted(exp_facts[item] - set(ks))
        extra = sorted(set(ks) - exp_facts[item])
        if missing or extra:
            problems.append((item, f"facts differ from the sheet: missing {['F%d' % k for k in missing]} extra {['F%d' % k for k in extra]}"))
            continue
        reason = (m.group(4) or "").strip().rstrip("|").strip()
        scores = {f"F{k}": int(v) for k, v in pairs}
        if 0 in scores.values() and not reason:
            warnings.append(f"{item}: a 0 without a reason")
        if len(reason.split()) > 12:
            warnings.append(f"{item}: reason has {len(reason.split())} words (limit 12)")
        got[item] = dict(scores=scores, false=int(m.group(3)), reason=reason)
    for it in sorted(exp_items):
        if it not in seen:
            problems.append((it, "no line for this item"))
    # an item with any problem is redone as a whole; drop a line that was kept but has a duplicate
    bad = {it for it, _ in problems}
    for it in list(got):
        if it in bad:
            del got[it]
    return got, problems, warnings, sorted(bad)


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
    got, problems, warnings, redo = check(open(a.reply, encoding="utf-8").read(), exp_items, expected_facts(a.kit))
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
