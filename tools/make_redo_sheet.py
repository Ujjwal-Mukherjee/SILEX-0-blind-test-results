#!/usr/bin/env python3
"""Make a redo sheet (JUDGING_PROCEDURE.md rule 7): a copy of one judge sheet that keeps only the items whose reply had a form problem.
FORM ONLY: it cuts the text of an existing sheet file and changes nothing else. The frozen prompt, the sheet code, the facts and the explanations stay byte for byte as they were;
only the line "N items follow." gets the new number.

  - the sheet is cut at its item blocks (a block ends with a line of 60 dashes); the number of blocks must equal the number of items in the map's `order`, otherwise nothing is made;
  - the redo items must be items of the sheet;
  - the redo map (code, the other columns of the map row, `order` = the redo items) is for collect_judge_replies.py --suffix, which stores the redo reply next to the first one
    (reply_CODE_redo1.txt and CODE_redo1.json); the aggregator and the reliability tools merge both, the first usable scoring of an item being kept.

Usage:
  python3 -I make_redo_sheet.py --sheet SHEETFILE --map MAP --code CODE --items "#07 #12" --out-sheets DIR --out-map FILE
"""
import argparse
import csv
import json
import os
import re
import sys

RULE = "-" * 60
HEADER_END = "=" * 60


def die(msg):
    print("make_redo_sheet.py: " + msg, file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out-sheets", required=True)
    ap.add_argument("--out-map", required=True)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.map, newline="", encoding="utf-8")) if r["code"] == a.code]
    if len(rows) != 1:
        die("sheet code %r not found exactly once in the map" % a.code)
    row = rows[0]
    order = row["order"].split()
    want = a.items.split()
    if not want or len(set(want)) != len(want) or any(it not in order for it in want):
        die("--items must be distinct items of the sheet (%s)" % " ".join(order))
    text = open(a.sheet, encoding="utf-8").read()
    marker = "\n" + HEADER_END + "\nSHEET " + a.code + "\n"
    if text.count(marker) != 1:
        die("the sheet file does not have the header of sheet %s" % a.code)
    head, _, body = text.partition(marker)
    m = re.match(r"(\d+) items follow\.\n" + re.escape(HEADER_END) + "\n", body)
    if not m or int(m.group(1)) != len(order):
        die("the header does not say %d items follow" % len(order))
    rest = body[m.end():]
    parts = rest.split(RULE + "\n")
    # every block ends with the rule line, so the last piece after the final rule is empty
    if parts[-1].strip() != "":
        die("text after the last item block")
    blocks = parts[:-1]
    found = {}
    for blk in blocks:
        first = next((ln for ln in blk.split("\n") if ln != ""), "")
        if not re.fullmatch(r"#\d{2}", first):
            die("an item block does not start with an item number")
        if first in found:
            die("item %s twice in the sheet" % first)
        found[first] = blk
    if sorted(found) != sorted(order):
        die("the blocks of the sheet are not the items of the map")
    # the builder (build_judge_sheets.sheet_text) puts a blank line after the header and after every rule line except the last
    kept = [found[it].lstrip("\n") for it in order if it in want]       # the sheet's own order
    out_text = head + marker + "%d items follow.\n%s\n\n" % (len(kept), HEADER_END) + "\n".join(b + RULE + "\n" for b in kept)
    os.makedirs(a.out_sheets, exist_ok=True)
    dst = os.path.join(a.out_sheets, "sheet_%s.txt" % a.code)
    if os.path.exists(dst):
        die("%s exists already" % dst)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(out_text)
    new_row = dict(row)
    new_row["order"] = " ".join(it for it in order if it in want)
    if "n_items" in new_row:
        new_row["n_items"] = str(len(kept))
    if "sources" in new_row:                      # a second-judge map: keep only the sources of the redo items
        src = json.loads(new_row["sources"])
        new_row["sources"] = json.dumps({it: v for it, v in src.items() if it in want}, sort_keys=True)
    with open(a.out_map, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(new_row.keys()))
        w.writeheader()
        w.writerow(new_row)
    print("redo sheet %s: %d of %d items (%s) in %s" % (a.code, len(kept), len(order), " ".join(it for it in order if it in want), dst))


if __name__ == "__main__":
    main()
