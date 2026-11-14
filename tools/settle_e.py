#!/usr/bin/env python3
"""Settle a held or conflicting English-baseline (arm E) reply after talking it over with the user, and show the grid of what has been filed.
FORM ONLY. Never opens a key.

  python3 -I settle_e.py --results DIR --recv recvNN --status data|excluded --why "reason" [--when "2026-11-14 12:30"]
      Changes the status of that row in cells_E.csv and adds a dated line to the Handling decisions part of received_log_E.md.
      Only a row that is review or conflict (or data, to exclude it) can be changed. A row cannot be made data while another data row holds the same cell.
  python3 -I settle_e.py --results DIR --grid
      Prints the 4 models x 2 batches grid (recv number and status of each cell) and what is left.
"""
import argparse, datetime, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import intake_e as ie   # noqa: E402

MODELS = ["claude", "chatgpt", "grok", "gemini"]


def grid(results):
    rows = ie.read_cells(os.path.join(results, "cells_E.csv"))
    print("cell = recv number and status of batch 1 | batch 2.")
    print(f"{'model':<12}{'batch 1':<24}{'batch 2':<24}")
    filled = 0
    runs = sorted({int(r["run"]) for r in rows if r["run"]} | {1})
    for run in runs:
        for m in MODELS:
            cell = []
            for b in (1, 2):
                rr = [r for r in rows if r["model"] == m and r["run"] == str(run) and r["batch"] == str(b) and r["arm"] == "E"
                      and not r["status"].startswith(("duplicate-of-", "continuation-of-"))]
                if any(r["status"] == "data" for r in rr):
                    filled += 1
                cell.append(", ".join(f"{r['recv']} {r['status']}" for r in rr) or "-")
            print(f"{m + ' r' + str(run):<12}{cell[0]:<24}{cell[1]:<24}")
    held = [r["recv"] + " " + r["status"] for r in rows if r["status"] in ("review", "conflict")]
    print(f"cells with a data reply: {filled} of {8 * len(runs)}.   Held or in conflict: {held or 'none'}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--recv")
    ap.add_argument("--status", choices=["data", "excluded"])
    ap.add_argument("--why", default="")
    ap.add_argument("--when", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--grid", action="store_true")
    a = ap.parse_args()
    if a.grid:
        return grid(a.results)
    if not (a.recv and a.status and a.why):
        sys.exit("--recv, --status and --why are required (or use --grid)")
    cp = os.path.join(a.results, "cells_E.csv")
    rows = ie.read_cells(cp)
    row = next((r for r in rows if r["recv"] == a.recv), None)
    if row is None:
        sys.exit(f"no such row: {a.recv}")
    if row["status"] not in ("review", "conflict", "data"):
        sys.exit(f"{a.recv} is {row['status']}: only review, conflict or data rows can be settled")
    if a.status == "data":
        other = next((r["recv"] for r in rows if r["recv"] != a.recv and r["status"] == "data" and (r["arm"], r["model"], r["run"], r["batch"]) ==
                      (row["arm"], row["model"], row["run"], row["batch"])), None)
        if other:
            sys.exit(f"cell E-{row['model']}-{row['run']}-b{row['batch']} is already held by {other} (data); exclude one of the two first")
    old = row["status"]
    row["status"] = a.status
    ie.write_cells(cp, rows)
    lp = os.path.join(a.results, "received_log_E.md")
    lines = open(lp, encoding="utf-8").read().rstrip("\n").split("\n")
    lines.append(f"- {a.when}: {a.recv} (E-{row['model']}-{row['run']}-b{row['batch']}) settled with the user: {old} -> {a.status}. Reason: {a.why}")
    open(lp, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{a.recv}: {old} -> {a.status}; logged in received_log_E.md (Handling decisions)")


if __name__ == "__main__":
    main()
