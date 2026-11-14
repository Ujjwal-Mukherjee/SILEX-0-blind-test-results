#!/usr/bin/env python3
"""Score Test F (find the fault) from the intake files and the private key. Run ONCE, after the last run is in
(and any time on made-up data in a test). The place score is a program's: no judge, no reading of a phrase for meaning.

  python3 -I score_f.py --results RES --kit KITDIR [--out DIR] [--include-review]

Reads   RES/cells_F.csv (rows with status data; with --include-review also rows held for review)
        RES/parsed_f/recvNN.json   RES/corrections_F.json (optional)   KITDIR/key_F_PRIVATE.csv
Writes  nothing, unless --out DIR is given: then DIR/scores_f_items.csv (one row per answered item, WITH the key: private until the last run is scored)
        and DIR/scores_f_summary.json.

Definitions (fixed before any reply was read; the same text is in README_F.txt):
  claimed      the answer is anything other than "none" (a readable place, or an answer whose place could not be read)
  found        faulty item, claimed, and the place is exactly the checker's place (A1.2 = line 2 of A1, A1.h = the header of A1)
  lenient      found, or the place is one the key lists as also acceptable (the first definition of a word defined twice)
  detected     faulty item and claimed (right place or not)
  false alarm  clean item and claimed
  unreadable   claimed, but no place could be read from the answer: counts as claimed, never as found
  An item with no answer line counts as no answer (neither found, nor detected, nor a false alarm) and is listed.
Baselines: a random place among all the places of an item (every line and every header) finds the fault with probability 1/n_places;
always answering "none" finds nothing and raises no false alarm.
"""
import argparse, csv, json, math, os, sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cut_words(s, n=12):
    w = s.split()
    return " ".join(w[:n])


def load_key(kit):
    rows = list(csv.DictReader(open(os.path.join(kit, "key_F_PRIVATE.csv"), newline="", encoding="utf-8")))
    key = {}
    for r in rows:
        r["faulty"] = r["verdict"] != "ok"
        r["also"] = [x for x in r["also_accept"].replace(";", " ").replace(",", " ").split() if x]
        r["n_places"] = int(r["n_places"])
        key[r["id"]] = r
    return key


def load_runs(results, include_review):
    cp = os.path.join(results, "cells_F.csv")
    cells = list(csv.DictReader(open(cp, newline="", encoding="utf-8")))
    ok = ("data", "review") if include_review else ("data",)
    corr_p = os.path.join(results, "corrections_F.json")
    corr = json.load(open(corr_p, encoding="utf-8")) if os.path.exists(corr_p) else {}
    runs = {}
    applied = []
    for c in cells:
        if c["status"] not in ok:
            continue
        pj = os.path.join(results, "parsed_f", f"{c['recv']}.json")
        data = json.load(open(pj, encoding="utf-8"))
        ans = {i: dict(v) for i, v in data["answers"].items()}
        for iid, ch in corr.get(c["recv"], {}).items():
            if iid in ans:
                if "place" in ch:
                    ans[iid]["place"] = ch["place"]
                if "phrase" in ch:
                    ans[iid]["phrase"] = ch["phrase"]
                applied.append((c["recv"], iid, ch.get("reason", "")))
        k = (c["arm"], c["model"], int(c["run"]))
        run = runs.setdefault(k, {"batches": {}, "answers": {}})
        if int(c["batch"]) in run["batches"]:
            sys.exit(f"cells_F.csv has two data rows for {k} batch {c['batch']}: fix the status before scoring")
        run["batches"][int(c["batch"])] = c["recv"]
        run["answers"].update(ans)
    return runs, applied


def score_run(key, run):
    batches = sorted(run["batches"])
    ids = [i for i, k in key.items() if int(k["batch"]) in batches]
    t = defaultdict(int)
    rows, missing = [], []
    for iid in ids:
        k = key[iid]
        ans = run["answers"].get(iid)
        place = ans["place"] if ans else "NOANSWER"
        answered = ans is not None
        claimed = answered and place != "none"
        found = k["faulty"] and claimed and place == k["location"]
        lenient = k["faulty"] and claimed and (place == k["location"] or place in k["also"])
        detected = k["faulty"] and claimed
        fa = (not k["faulty"]) and claimed
        unread = answered and place is None
        if not answered:
            missing.append(iid)
        t["faulty"] += k["faulty"]
        t["clean"] += (not k["faulty"])
        t["found"] += found
        t["lenient"] += lenient
        t["detected"] += detected
        t["false_alarm"] += fa
        t["unreadable"] += unread
        rows.append(dict(id=iid, batch=k["batch"], tag=k["tag"], verdict=k["verdict"], key_location=k["location"], key_also=" ".join(k["also"]),
                         answered_place=("(no answer)" if not answered else ("(unreadable)" if place is None else place)),
                         found=int(found), lenient=int(lenient), detected=int(detected), clean=int(not k["faulty"]), false_alarm=int(fa),
                         phrase=cut_words(ans["phrase"]) if ans else ""))
    return dict(t), rows, missing


def pct(k, n):
    return f"{100 * k / n:.0f}%" if n else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out")
    ap.add_argument("--include-review", action="store_true")
    a = ap.parse_args()
    key = load_key(a.kit)
    runs, applied = load_runs(a.results, a.include_review)
    if not runs:
        sys.exit("no data rows in cells_F.csv")

    per_run, item_rows = {}, []
    print("TEST F: per run (a run = the chats of one model in one arm; two batches make a complete run)")
    print(f"{'arm':3} {'model':8} {'run':>3} {'batches':>7} | {'found':>8} {'lenient':>8} {'detected':>9} | {'false alarms':>12} | {'unreadable':>10}")
    for k in sorted(runs):
        t, rows, missing = score_run(key, runs[k])
        per_run[k] = t
        for r in rows:
            item_rows.append(dict(arm=k[0], model=k[1], run=k[2], recv=runs[k]["batches"][int(r["batch"])], **r))
        flag = "" if len(runs[k]["batches"]) == 2 else "  (ONE BATCH ONLY)"
        if missing:
            flag += f"  (no answer for {missing})"
        print(f"{k[0]:3} {k[1]:8} {k[2]:>3} {'+'.join(str(b) for b in sorted(runs[k]['batches'])):>7} | "
              f"{t['found']:>3}/{t['faulty']:<4} {t['lenient']:>3}/{t['faulty']:<4} {t['detected']:>4}/{t['faulty']:<4} | "
              f"{t['false_alarm']:>6}/{t['clean']:<5} | {t['unreadable']:>10}{flag}")

    def agg(keys):
        t = defaultdict(int)
        for k in keys:
            for f, v in per_run[k].items():
                t[f] += v
        return t

    print("\nPer arm and model (all runs pooled). Interval = Wilson 95% on the pooled faulty items;")
    print("the runs of one model are not independent, so read the interval as an orientation only.")
    print(f"{'arm':3} {'model':8} {'runs':>4} | {'found':>13} {'95% interval':>13} | {'lenient':>8} | {'detected':>9} | {'false alarms':>12}")
    groups = defaultdict(list)
    for k in per_run:
        groups[(k[0], k[1])].append(k)
    summary = {}
    for g in sorted(groups):
        t = agg(groups[g])
        lo, hi = wilson(t["found"], t["faulty"])
        nr = len(groups[g])
        print(f"{g[0]:3} {g[1]:8} {nr:>4} | {t['found']:>4}/{t['faulty']:<4} {pct(t['found'], t['faulty']):>4} {f'{100*lo:.0f}-{100*hi:.0f}%':>13} | "
              f"{pct(t['lenient'], t['faulty']):>8} | {pct(t['detected'], t['faulty']):>9} | {t['false_alarm']:>5}/{t['clean']:<5}{pct(t['false_alarm'], t['clean']):>2}")
        summary[f"{g[0]}-{g[1]}"] = dict(t, runs=nr, wilson_found=[lo, hi])
    arms = sorted({k[0] for k in per_run})
    for arm in arms:
        t = agg([k for k in per_run if k[0] == arm])
        lo, hi = wilson(t["found"], t["faulty"])
        print(f"{arm:3} {'ALL':8} {sum(1 for k in per_run if k[0] == arm):>4} | {t['found']:>4}/{t['faulty']:<4} {pct(t['found'], t['faulty']):>4} {f'{100*lo:.0f}-{100*hi:.0f}%':>13} | "
              f"{pct(t['lenient'], t['faulty']):>8} | {pct(t['detected'], t['faulty']):>9} | {t['false_alarm']:>5}/{t['clean']:<5}{pct(t['false_alarm'], t['clean']):>2}")
        summary[f"{arm}-ALL"] = dict(t, wilson_found=[lo, hi])

    # baselines on the items that were answered
    seen = {r["id"] for r in item_rows}
    exp = sum(1 / key[i]["n_places"] for i in seen if key[i]["faulty"])
    nf = sum(1 for i in seen if key[i]["faulty"])
    print(f"\nBaselines per complete run: a random place finds {exp:.1f} of {nf} faulty items ({pct(exp, nf)}) and raises a false alarm on every clean item;"
          f" always answering none finds 0 and raises none.")

    # by verdict
    print("\nBy verdict (found / answered faulty items; two items per verdict per run, so for description only)")
    verdicts = sorted({k["verdict"] for k in key.values() if k["faulty"]})
    cols = sorted(groups)
    print(f"{'verdict':10} " + " ".join(f"{c[0] + '-' + c[1][:6]:>10}" for c in cols))
    for v in verdicts:
        line = []
        for c in cols:
            rs = [r for r in item_rows if (r["arm"], r["model"]) == c and r["verdict"] == v]
            line.append(f"{sum(r['found'] for r in rs)}/{len(rs)}".rjust(10))
        print(f"{v:10} " + " ".join(line))

    # item difficulty per arm
    print("\nItems found by no run of the arm / by every run of the arm (strict place)")
    for arm in arms:
        n_runs_by_batch = {b: len({(r["model"], r["run"]) for r in item_rows if r["arm"] == arm and int(r["batch"]) == b}) for b in (1, 2)}
        never, always = [], []
        for i in sorted(seen):
            if not key[i]["faulty"]:
                continue
            rs = [r for r in item_rows if r["arm"] == arm and r["id"] == i]
            if not rs:
                continue
            if sum(r["found"] for r in rs) == 0:
                never.append(f"{i}({key[i]['verdict']})")
            if sum(r["found"] for r in rs) == len(rs):
                always.append(i)
        print(f"  {arm}: found by no run: {never or '(none)'}; found by every run: {always or '(none)'}")

    if applied:
        print("\nCorrections applied from corrections_F.json:")
        for x in applied:
            print("  ", x)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        cols_out = list(item_rows[0].keys())
        with open(os.path.join(a.out, "scores_f_items.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols_out)
            w.writeheader()
            w.writerows(item_rows)
        json.dump(dict(per_run={f"{k[0]}-{k[1]}-{k[2]}": v for k, v in per_run.items()}, summary=summary,
                       random_baseline_found=exp, faulty_items=nf), open(os.path.join(a.out, "scores_f_summary.json"), "w"), indent=1)
        print(f"\nwritten: {a.out}/scores_f_items.csv, scores_f_summary.json (they hold the key: private until the last run is scored)")


if __name__ == "__main__":
    main()
