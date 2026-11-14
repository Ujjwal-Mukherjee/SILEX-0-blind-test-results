#!/usr/bin/env python3
"""Strict side-note copy for Test F (F_handling_rules.md, Note 1, "Strict side note"). FORM ONLY: this program never scores and never opens the key.

The primary result of Test F reads a line that holds several item codes as several answers (Note 1 of Test F). The strict reading applies README_F.txt literally:
of a line only its FIRST answer counts, the other answers of the same line count as no answer. This program makes the copy that score_f.py is then run on:

  OUT/cells_F.csv                 a copy of RES/cells_F.csv
  OUT/parsed_f/recvNN.json        a copy of each parsed reply of a row with status data, in which, for every line number that holds several answers, only the first answer
                                  (in the order of the parse) is kept; the other answers are removed from "answers" and "order"
  OUT/corrections_F.json          a copy of RES/corrections_F.json if there is one
  OUT/strict_info.json            what was dropped, per reply (item codes and line numbers), and the hash of this program

A reply with one answer per line is copied unchanged. Nothing is changed in RES. OUT must not exist or must be empty.

Usage:  python3 -I make_strict_copy_f.py --results RES --out OUT
"""
import argparse, csv, hashlib, json, os, shutil, sys


def strict_copy_of(parsed):
    """-> (new parsed dict, list of (item code, line number) dropped)."""
    d = json.loads(json.dumps(parsed))            # deep copy
    seen, dropped = set(), []
    for iid in list(d["order"]):
        ln = d["answers"][iid]["line_no"]
        if ln in seen:
            dropped.append((iid, ln))
            del d["answers"][iid]
            d["order"].remove(iid)
        else:
            seen.add(ln)
    return d, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out) and os.listdir(a.out):
        sys.exit("OUT must not exist or must be empty")
    os.makedirs(os.path.join(a.out, "parsed_f"), exist_ok=True)
    cells = os.path.join(a.results, "cells_F.csv")
    shutil.copyfile(cells, os.path.join(a.out, "cells_F.csv"))
    corr = os.path.join(a.results, "corrections_F.json")
    if os.path.exists(corr):
        shutil.copyfile(corr, os.path.join(a.out, "corrections_F.json"))
    info = {"program_sha256_16": hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16], "replies": {}}
    n_data = 0
    with open(cells, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["status"] != "data":
                continue
            n_data += 1
            src = os.path.join(a.results, "parsed_f", r["recv"] + ".json")
            parsed = json.load(open(src, encoding="utf-8"))
            new, dropped = strict_copy_of(parsed)
            json.dump(new, open(os.path.join(a.out, "parsed_f", r["recv"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            info["replies"][r["recv"]] = {"cell": f'{r["arm"]}-{r["model"]}-{r["run"]}-b{r["batch"]}', "answers_before": len(parsed["order"]),
                                          "answers_kept": len(new["order"]), "dropped": [[i, ln] for i, ln in dropped]}
    json.dump(info, open(os.path.join(a.out, "strict_info.json"), "w", encoding="utf-8"), indent=1)
    changed = [k for k, v in info["replies"].items() if v["dropped"]]
    print(f"strict copy of {n_data} data replies in {a.out}; replies with dropped answers: {len(changed)} ({', '.join(changed) if changed else 'none'})")


if __name__ == "__main__":
    main()
