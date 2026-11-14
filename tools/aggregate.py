#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregator of the SILEX blind test: computes the tables of ANALYSIS_PLAN.md and nothing else. Working script, not part of any frozen kit.

It scores nothing. The 0/1 scores come from the judge sheets (check_judge_reply.py / check_judge_reply_rt.py --json), the validity decisions from check_p.py
(validity_P*/items.csv), the lengths of the English from the parsed replies of arm E (cells_E.csv, parsed_e/). It opens the private sheet maps and the round-trip
keys, so it is run ONLY after the last judge reply is checked; without --partial it stops while any judged sheet is incomplete.

Usage:
  python3 -I aggregate.py --results RES --kit KIT --out OUTDIR \
      --reading-map MAP --reading-scores DIR \
      [--rt-map MAP --rt-scores DIR --rt-key-p FILE --rt-key-e FILE] \
      [--validity DIR ...] [--boot N] [--partial]
  --reading-scores / --rt-scores: a folder of the JSON files that check_judge_reply.py / check_judge_reply_rt.py wrote with --json (one per judge reply, any number per sheet;
      for an item scored twice the first file in name order is kept, a differing second scoring is listed).
  --validity: folders made by check_p.py (default: RES/validity_P and RES/validity_P_high where they exist).
OUTDIR must not exist or must be empty. The same inputs give byte-identical report.md, tables/ and summary.json (aggregate_info.json holds the time).
"""
import argparse, csv, datetime, glob, hashlib, io, json, math, os, platform, re, statistics, sys
from fractions import Fraction

import numpy as np

SEED = 20261114
BOOT = 10000
MODELS = ["claude", "chatgpt", "grok", "gemini"]
NAME = {"claude": "Claude", "chatgpt": "ChatGPT", "grok": "Grok", "gemini": "Gemini"}
ITEMS = ["#%02d" % i for i in range(1, 41)]
TIERS = [1, 2, 3, 4, 5]
# The writer run each round trip reads (rules 20 and 25 of P_handling_rules.md)
RT_SOURCE_RUN = {"claude": 1, "chatgpt": 4, "grok": 1, "gemini": 1}
# Writing sets (model, label, runs). ChatGPT has two: the high-setting set (runs 4 to 6, main) and the auto-mode set (runs 1 to 3).
WRITING_SETS = [("claude", "", (1, 2, 3)), ("chatgpt", "high setting", (4, 5, 6)), ("chatgpt", "auto mode", (1, 2, 3)),
                ("grok", "", (1, 2, 3)), ("gemini", "", (1, 2, 3))]
HERE = os.path.dirname(os.path.abspath(__file__))


def die(msg):
    sys.exit("aggregate.py: " + msg)


def sha16(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def isnan(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def pct(x, d=1):
    """Share in 0..1 -> points as text."""
    if isnan(x):
        return "n/a"
    return "%.*f" % (d, round(100.0 * float(x), d) + 0.0)


def spct(x, d=1):
    """Difference in 0..1 -> signed points as text."""
    if isnan(x):
        return "n/a"
    v = round(100.0 * float(x), d) + 0.0
    return "%+.*f" % (d, v)


def num1(x, d=1):
    if isnan(x):
        return "n/a"
    return "%.*f" % (d, round(float(x), d) + 0.0)


def interval(lo, hi, signed=False):
    f = spct if signed else pct
    return "[%s, %s]" % (f(lo), f(hi))


def yn(b):
    return "yes" if b else "no"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------ kit
class Kit:
    def __init__(self, kitdir):
        self.dir = kitdir
        self.order = {}
        for r in read_csv(os.path.join(kitdir, "order.csv")):
            self.order[r["id"]] = dict(batch=int(r["batch"]), tier=int(r["tier"]), gold=int(r["silex_chars"]))
        if sorted(self.order) != ITEMS:
            die("order.csv does not list #01 to #40")
        self.facts = []
        for r in read_csv(os.path.join(kitdir, "facts.csv")):
            m = re.match(r"^(#\d{2})\.F(\d+)$", r["fact_id"])
            if not m or m.group(1) != r["id"]:
                die("bad fact_id %r" % r["fact_id"])
            if r["type"] not in ("C", "S"):
                die("fact %s has type %r" % (r["fact_id"], r["type"]))
            t = int(r["tier"])
            if t != self.order[r["id"]]["tier"]:
                die("fact %s has tier %d but its item has tier %d" % (r["fact_id"], t, self.order[r["id"]]["tier"]))
            self.facts.append(dict(id=r["fact_id"], item=r["id"], k=int(m.group(2)), type=r["type"], tier=t))
        self.nf = len(self.facts)
        self.fidx = {(f["item"], f["k"]): j for j, f in enumerate(self.facts)}
        if len(self.fidx) != self.nf:
            die("duplicate fact ids in facts.csv")
        self.item_of = np.array([ITEMS.index(f["item"]) for f in self.facts])
        self.is_c = np.array([f["type"] == "C" for f in self.facts])
        self.is_s = ~self.is_c
        self.is_all = np.ones(self.nf, dtype=bool)
        self.tier_f = np.array([f["tier"] for f in self.facts])
        self.tier_i = np.array([self.order[i]["tier"] for i in ITEMS])
        for i in range(40):
            if not (self.is_c & (self.item_of == i)).any():
                die("%s has no C fact" % ITEMS[i])

    def item_sums(self, vec, mask):
        """Per item (length 40): sum of the scores and number of facts under the mask."""
        num = np.bincount(self.item_of[mask], weights=vec[mask], minlength=40)
        den = np.bincount(self.item_of[mask], minlength=40).astype(float)
        return num, den

    def expected(self, c_only):
        ex = {}
        for f in self.facts:
            if c_only and f["type"] != "C":
                continue
            ex.setdefault(f["item"], set()).add(f["k"])
        return ex


def share(vec, mask):
    n = int(mask.sum())
    return float(vec[mask].sum() / n) if n else float("nan")


# ------------------------------------------------------------------ bootstrap
def rng_for(tag):
    """k = 0: resamples over all items (or over a subset of items); k = tier: resamples within one tier."""
    return np.random.default_rng([SEED, tag])


def make_weights(rng, sel, B, n=40):
    """B x n matrix: how often each item is drawn when len(sel) items are drawn with replacement from the items in sel."""
    m = len(sel)
    idx = rng.integers(0, m, size=(B, m))
    W = np.zeros((B, n))
    np.add.at(W, (np.repeat(np.arange(B), m), np.asarray(sel)[idx].ravel()), 1.0)
    return W


def ci95(x):
    lo, hi = np.percentile(x, [2.5, 97.5])
    return float(lo), float(hi)


# ------------------------------------------------------------------ judged sheets
def load_judged(map_path, scores_dir, kit, c_only, notes):
    rows = read_csv(map_path)
    if not rows:
        die("%s: empty map" % map_path)
    exp = kit.expected(c_only)
    sheets = {}
    for r in rows:
        if r["code"] in sheets:
            die("sheet code %s twice in %s" % (r["code"], map_path))
        order = r["order"].split()
        batch = int(r["batch"])
        want = [i for i in ITEMS if kit.order[i]["batch"] == batch]
        if sorted(order) != want:
            die("sheet %s: its items are not the items of batch %d" % (r["code"], batch))
        sheets[r["code"]] = dict(code=r["code"], arm=r["arm"], model=r["model"], run=r["run"], batch=batch, order=order, items={})
    for fp in sorted(glob.glob(os.path.join(scores_dir, "*.json"))):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        code = d.get("code")
        if code not in sheets:
            die("%s: sheet code %r is not in the map" % (fp, code))
        sh = sheets[code]
        for item, v in d.get("items", {}).items():
            if item not in sh["order"]:
                die("%s: %s is not on sheet %s" % (fp, item, code))
            sc = {}
            for key, val in v["scores"].items():
                m = re.match(r"^F(\d+)$", key)
                if not m or type(val) is not int or val not in (0, 1):
                    die("%s: %s has the score %r for %r" % (fp, item, val, key))
                sc[int(m.group(1))] = val
            if set(sc) != exp[item]:
                die("%s: %s is scored on facts %s but the sheet type needs %s" % (fp, item, sorted(sc), sorted(exp[item])))
            fl = v["false"]
            if type(fl) is not int or fl < 0:
                die("%s: %s has the false count %r" % (fp, item, fl))
            if item in sh["items"]:
                old = sh["items"][item]
                if old["scores"] != sc or old["false"] != fl:
                    notes.append("sheet %s %s: scored again in %s with other values; the first scoring (%s) is kept" % (code, item, os.path.basename(fp), old["file"]))
                continue
            sh["items"][item] = dict(scores=sc, false=fl, file=os.path.basename(fp))
    for sh in sheets.values():
        sh["complete"] = all(i in sh["items"] for i in sh["order"])
    return sorted(sheets.values(), key=lambda s: s["code"])


def assemble(kit, sheets, keyfn, c_only, issues):
    """Runs from sheets: key -> dict(vec, false, batches, complete). A run is complete when both batches are complete."""
    runs = {}
    for s in sheets:
        k = keyfn(s)
        r = runs.setdefault(k, dict(vec=np.full(kit.nf, np.nan), false=np.full(40, np.nan), batches={}, codes=[]))
        if s["batch"] in r["batches"]:
            die("two sheets for %s batch %d" % (str(k), s["batch"]))
        r["batches"][s["batch"]] = s["code"]
        r["codes"].append(s["code"])
        if not s["complete"]:
            issues.append("sheet %s (%s batch %d) is incomplete: %d of %d items scored" % (s["code"], " ".join(str(x) for x in k), s["batch"], len(s["items"]), len(s["order"])))
            continue
        for item, v in s["items"].items():
            for kk, val in v["scores"].items():
                r["vec"][kit.fidx[(item, kk)]] = val
            r["false"][ITEMS.index(item)] = v["false"]
    need = kit.is_c if c_only else kit.is_all
    for k, r in runs.items():
        r["complete"] = bool(set(r["batches"]) == {1, 2} and not np.isnan(r["vec"][need]).any())
        if not r["complete"]:
            issues.append("run %s is not complete (batches present: %s); it is left out of every mean" % (" ".join(str(x) for x in k), sorted(r["batches"])))
    return runs


# ------------------------------------------------------------------ reading
def run_stats(kit, vec, false):
    d = {"n_facts": int(np.isfinite(vec).sum()), "false20": float(np.nansum(false) / 2.0)}
    d["all"] = share(vec, kit.is_all)
    d["C"] = share(vec, kit.is_c)
    d["S"] = share(vec, kit.is_s)
    for t in TIERS:
        m = kit.tier_f == t
        d["T%d" % t] = share(vec, m)
        d["T%d_C" % t] = share(vec, m & kit.is_c)
    return d


def reading_block(kit, runs, B):
    out = dict(runs=[], models={}, items=[])
    for k in sorted(runs, key=lambda k: (0 if k[0] == "R" else 1, MODELS.index(k[1]) if k[1] in MODELS else 9, k[2])):
        r = runs[k]
        if not r["complete"]:
            continue
        s = run_stats(kit, r["vec"], r["false"])
        out["runs"].append(dict(arm=k[0], model=k[1], run=k[2], **s))
    W = make_weights(rng_for(0), np.arange(40), B)
    nC = int(kit.is_c.sum())
    per_item = {}
    for m in MODELS:
        Rk = [k for k in sorted(runs) if k[0] == "R" and k[1] == m and runs[k]["complete"]]
        Nk = [k for k in sorted(runs) if k[0] == "N" and k[1] == m and runs[k]["complete"]]
        md = dict(R_runs=[k[2] for k in Rk], N_runs=[k[2] for k in Nk])
        Rm = Nm = None
        if Rk:
            Rm = np.mean([runs[k]["vec"] for k in Rk], axis=0)
            Rf = np.mean([runs[k]["false"] for k in Rk], axis=0)
            md["R"] = run_stats(kit, Rm, Rf)
            per = [run_stats(kit, runs[k]["vec"], runs[k]["false"]) for k in Rk]
            for key in ("all", "C", "S"):
                md["R_min_" + key] = min(p[key] for p in per)
                md["R_max_" + key] = max(p[key] for p in per)
        if Nk:
            Nm = np.mean([runs[k]["vec"] for k in Nk], axis=0)
            Nf = np.mean([runs[k]["false"] for k in Nk], axis=0)
            md["N"] = run_stats(kit, Nm, Nf)
        # prediction 1: R minus N on the C facts
        if Rk and Nk:
            numR, denC = kit.item_sums(Rm, kit.is_c)
            numN, _ = kit.item_sums(Nm, kit.is_c)
            credR = int(round(sum(float(runs[k]["vec"][kit.is_c].sum()) for k in Rk)))
            credN = int(round(sum(float(runs[k]["vec"][kit.is_c].sum()) for k in Nk)))
            gapF = Fraction(credR, nC * len(Rk)) - Fraction(credN, nC * len(Nk))
            dist = (W @ numR) / (W @ denC) - (W @ numN) / (W @ denC)
            lo, hi = ci95(dist)
            d_i = numR / denC - numN / denC
            dist2 = (W @ d_i) / W.sum(axis=1)
            lo2, hi2 = ci95(dist2)
            cs = [share(runs[k]["vec"], kit.is_c) for k in Rk]
            nsh = share(Nm, kit.is_c)
            md["p1"] = dict(gap=float(gapF), R_C=md["R"]["C"], N_C=md["N"]["C"], lo=lo, hi=hi, holds=bool(gapF >= Fraction(1, 5)), robust=bool(lo >= 0.2),
                            gap_lowest_run=min(cs) - nsh, gap_highest_run=max(cs) - nsh, mean_item_gap=float(d_i.mean()), item_lo=lo2, item_hi=hi2)
            per_item[m] = dict(R=numR / denC, N=numN / denC)
        # prediction 2: tier 1 above tier 5 (all facts, R mean)
        if Rk:
            c = {t: int(round(sum(float(runs[k]["vec"][kit.tier_f == t].sum()) for k in Rk))) for t in (1, 5)}
            n = {t: int((kit.tier_f == t).sum()) * len(Rk) for t in (1, 5)}
            num_all, den_all = kit.item_sums(Rm, kit.is_all)
            s1, s5 = np.where(kit.tier_i == 1)[0], np.where(kit.tier_i == 5)[0]
            W1, W5 = make_weights(rng_for(1), s1, B), make_weights(rng_for(5), s5, B)
            d2 = (W1 @ num_all) / (W1 @ den_all) - (W5 @ num_all) / (W5 @ den_all)
            lo, hi = ci95(d2)
            md["p2"] = dict(t1=md["R"]["T1"], t5=md["R"]["T5"], diff=md["R"]["T1"] - md["R"]["T5"], lo=lo, hi=hi,
                            holds=bool(c[1] * n[5] > c[5] * n[1]), tie=bool(c[1] * n[5] == c[5] * n[1]))
        out["models"][m] = md
    for i, it in enumerate(ITEMS):
        row = dict(item=it, tier=kit.order[it]["tier"])
        for m in MODELS:
            if m in per_item:
                row[m + "_R"], row[m + "_N"] = float(per_item[m]["R"][i]), float(per_item[m]["N"][i])
            else:
                row[m + "_R"] = row[m + "_N"] = float("nan")
        out["items"].append(row)
    return out


# ------------------------------------------------------------------ writing
def load_validity(dirs):
    rows = []
    for d in dirs:
        p = os.path.join(d, "items.csv")
        if not os.path.exists(p):
            die("%s has no items.csv" % d)
        for r in read_csv(p):
            r["_src"] = d
            rows.append(r)
    by, seen = {}, set()
    for r in rows:
        key = (r["model"], int(r["run"]))
        if (key, r["item"]) in seen:
            die("validity rows: %s run %s %s appears twice" % (r["model"], r["run"], r["item"]))
        seen.add((key, r["item"]))
        if r["valid"] not in ("0", "1"):
            die("validity rows: valid=%r for %s run %s %s" % (r["valid"], r["model"], r["run"], r["item"]))
        by.setdefault(key, {})[r["item"]] = r
    return by


def check_validity_summaries(dirs, by, issues):
    """The recomputed counts must equal the summary.json of check_p.py where one exists."""
    for d in dirs:
        p = os.path.join(d, "summary.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
        for name, v in s.get("per_run", {}).items():
            m, run = name.rsplit("-", 1)
            rows = by.get((m, int(run)), {})
            valid = sum(int(r["valid"]) for r in rows.values())
            if len(rows) != v["items"] or valid != v["valid"]:
                die("%s: summary.json says %s has %d valid of %d but items.csv gives %d of %d" % (d, name, v["valid"], v["items"], valid, len(rows)))


def writing_block(kit, by, B):
    out = dict(runs=[], sets=[], codes={}, reasons={}, hard=[], notes=[])
    for (m, run) in sorted(by, key=lambda k: (MODELS.index(k[0]) if k[0] in MODELS else 9, k[1])):
        rows = by[(m, run)]
        if sorted(rows) != ITEMS:
            out["notes"].append("%s run %d has %d items, not 40: left out" % (m, run, len(rows)))
            continue
        v = sum(int(r["valid"]) for r in rows.values())
        out["runs"].append(dict(model=m, run=run, items=40, valid=v, checker_ok=sum(int(r["checker_ok"] or 0) for r in rows.values()),
                                joined_ok=sum(int(r["joined_ok"] or 0) for r in rows.values())))
    W = make_weights(rng_for(0), np.arange(40), B)
    main = {}
    for model, label, runs in WRITING_SETS:
        present = [r for r in runs if (model, r) in by and sorted(by[(model, r)]) == ITEMS]
        s = dict(model=model, label=label, runs=present, missing=[r for r in runs if r not in present])
        if present:
            V = np.array([[int(by[(model, r)][i]["valid"]) for i in ITEMS] for r in present])
            CK = np.array([[int(by[(model, r)][i]["checker_ok"] or 0) for i in ITEMS] for r in present])
            JO = np.array([[int(by[(model, r)][i]["joined_ok"] or 0) for i in ITEMS] for r in present])
            n, valid = int(V.size), int(V.sum())
            lo, hi = ci95((W @ V.sum(axis=0)) / (W @ (len(present) * np.ones(40))))
            tiers = {}
            for t in TIERS:
                cols = np.where(kit.tier_i == t)[0]
                tiers[t] = dict(items=int(V[:, cols].size), valid=int(V[:, cols].sum()))
            s.update(items=n, valid=valid, share=valid / n, run_shares=[float(x) for x in V.mean(axis=1)], run_min=float(V.mean(axis=1).min()),
                     run_max=float(V.mean(axis=1).max()), lo=lo, hi=hi, checker_ok_share=float(CK.mean()), joined_ok_share=float(JO.mean()),
                     holds=bool(2 * valid >= n), tiers=tiers, invalid_per_item=[int((1 - V[:, i]).sum()) for i in range(40)])
        out["sets"].append(s)
    for model in MODELS:
        cand = [s for s in out["sets"] if s["model"] == model and s["runs"]]
        pref = [s for s in cand if s["label"] in ("", "high setting")]
        if pref:
            main[model] = dict(set=pref[0], provisional=False)
        elif cand:
            main[model] = dict(set=cand[0], provisional=True)
    out["main"] = main
    # verdict codes and reasons over every invalid item of every complete run
    codes, reasons = {}, {}
    for (m, run), rows in by.items():
        if sorted(rows) != ITEMS:
            continue
        for r in rows.values():
            if r["valid"] == "1":
                continue
            for c in [x for x in (r.get("verdicts") or "").split(";") if x]:
                codes[c] = codes.get(c, 0) + 1
            for c in [x for x in (r.get("reasons") or "").split(";") if x]:
                reasons[c] = reasons.get(c, 0) + 1
    out["codes"], out["reasons"] = codes, reasons
    # items invalid in at least 4 of the runs of the main sets
    tot = [0] * 40
    nruns = 0
    for model, md in main.items():
        nruns += len(md["set"]["runs"])
        for i in range(40):
            tot[i] += md["set"]["invalid_per_item"][i]
    out["hard"] = [(ITEMS[i], tot[i]) for i in range(40) if tot[i] >= 4]
    out["hard_runs"] = nruns
    return out


def median(xs):
    return float(statistics.median(xs)) if xs else float("nan")


def load_english(results, kit, issues):
    p = os.path.join(results, "cells_E.csv")
    if not os.path.exists(p):
        return None
    eng = {}
    for r in read_csv(p):
        if r["status"] != "data":
            continue
        pj = os.path.join(results, "parsed_e", r["recv"] + ".json")
        with open(pj, encoding="utf-8") as f:
            d = json.load(f)
        items = d["parse"]["items"]
        batch = int(r["batch"])
        for i in ITEMS:
            if kit.order[i]["batch"] != batch:
                continue
            it = items.get(i)
            if it is None:
                eng.setdefault((r["model"], int(r["run"])), {})[i] = dict(state="missing", chars=0, words=0, other=0)
            else:
                eng.setdefault((r["model"], int(r["run"])), {})[i] = dict(state=it["state"], chars=int(it["chars"]), words=int(it["words"]), other=int(it.get("other_lines", 0)))
    for k, v in eng.items():
        if sorted(v) != ITEMS:
            issues.append("English reply of %s run %d does not cover all 40 items (%d): left out" % (k[0], k[1], len(v)))
    return {k: v for k, v in eng.items() if sorted(v) == ITEMS}


def length_block(kit, by, eng):
    out = dict(silex=[], english=[])
    for model, label, runs in WRITING_SETS:
        chars, gold, ratio = [], [], []
        present = [r for r in runs if (model, r) in by and sorted(by[(model, r)]) == ITEMS]
        for r in present:
            for i in ITEMS:
                c = by[(model, r)][i]["chars"]
                if c != "":
                    chars.append(int(c))
                    gold.append(kit.order[i]["gold"])
                    ratio.append(int(c) / kit.order[i]["gold"])
        if present:
            out["silex"].append(dict(model=model, label=label, runs=present, n=len(chars), of=40 * len(present), median_chars=median(chars),
                                     median_gold=median(gold), median_ratio=median(ratio)))
    if eng:
        for model in MODELS:
            runs = sorted(r for (m, r) in eng if m == model)
            if not runs:
                continue
            e = eng[(model, runs[0])]
            pres = [i for i in ITEMS if e[i]["state"] == "text"]
            src = RT_SOURCE_RUN[model]
            both = []
            if (model, src) in by:
                for i in pres:
                    c = by[(model, src)][i]["chars"] if i in by[(model, src)] else ""
                    if c != "" and e[i]["chars"] > 0:
                        both.append(int(c) / e[i]["chars"])
            out["english"].append(dict(model=model, run=runs[0], n=len(pres), median_chars=median([e[i]["chars"] for i in pres]),
                                       median_words=median([e[i]["words"] for i in pres]),
                                       median_ratio_gold=median([e[i]["chars"] / kit.order[i]["gold"] for i in pres]),
                                       silex_src_run=src, n_both=len(both), median_silex_per_english=median(both),
                                       none_items=sum(1 for i in ITEMS if e[i]["state"] in ("none", "empty")), missing_items=sum(1 for i in ITEMS if e[i]["state"] == "missing")))
    return out


# ------------------------------------------------------------------ round trip
def load_rt_keys(path_p, path_e):
    kp, ke = read_csv(path_p), read_csv(path_e)
    cw_p, cw_e, runs_p, nonmsg = {}, {}, {}, {}
    for r in kp:
        c = int(r["chat"])
        if cw_p.setdefault(c, r["writer"]) != r["writer"]:
            die("rt key P: chat %d has two writers" % c)
        if runs_p.setdefault(r["writer"], int(r["writer_run"])) != int(r["writer_run"]):
            die("rt key P: writer %s has two source runs" % r["writer"])
    for r in ke:
        c = int(r["chat"])
        if cw_e.setdefault(c, r["writer"]) != r["writer"]:
            die("rt key E: chat %d has two writers" % c)
        nonmsg.setdefault(r["writer"], set()).update((r.get("items_with_non_message_lines") or "").split())
    for w, run in runs_p.items():
        if RT_SOURCE_RUN.get(w) != run:
            die("rt key P: writer %s reads run %d but the plan says run %s" % (w, run, RT_SOURCE_RUN.get(w)))
    return cw_p, cw_e, runs_p, nonmsg


def rt_block(kit, runs, reader, valid_masks, nonmsg, B):
    out = dict(reader=reader, writers={})
    W0 = {}
    for w in [x for x in MODELS if ("RTP", x) in runs or ("RTE", x) in runs]:
        P, E = runs.get(("RTP", w)), runs.get(("RTE", w))
        okP, okE = bool(P and P["complete"]), bool(E and E["complete"])
        d = dict(own=(w == reader), have_P=okP, have_E=okE, masks={}, tiers={})
        numP = numE = den = None
        if okP:
            numP, den = kit.item_sums(P["vec"], kit.is_c)
            d["false20_P"] = float(np.nansum(P["false"]) / 2.0)
        if okE:
            numE, den = kit.item_sums(E["vec"], kit.is_c)
            d["false20_E"] = float(np.nansum(E["false"]) / 2.0)
        masks = {"all items": np.ones(40, dtype=bool)}
        if w in valid_masks:
            masks["items valid in the SILEX source run"] = valid_masks[w]
        if w in nonmsg:
            masks["items whose English has message lines only"] = ~np.isin(np.array(ITEMS), sorted(nonmsg[w]))
        for name, mask in masks.items():
            sel = np.where(mask)[0]
            if len(sel) == 0:
                continue
            r = dict(n_items=int(len(sel)), n_facts=int(den[sel].sum()) if den is not None else None)
            if okP:
                r["cred_P"], r["shareP"] = int(round(numP[sel].sum())), float(numP[sel].sum() / den[sel].sum())
            if okE:
                r["cred_E"], r["shareE"] = int(round(numE[sel].sum())), float(numE[sel].sum() / den[sel].sum())
            if okP and okE:
                r["diff"] = r["shareP"] - r["shareE"]
                Wm = make_weights(rng_for(0), sel, B)
                dist = (Wm @ numP) / (Wm @ den) - (Wm @ numE) / (Wm @ den)
                r["lo"], r["hi"] = ci95(dist)
            d["masks"][name] = r
        for t in TIERS:
            sel = np.where(kit.tier_i == t)[0]
            r = dict(n_items=int(len(sel)))
            if okP:
                r["shareP"] = float(numP[sel].sum() / den[sel].sum())
            if okE:
                r["shareE"] = float(numE[sel].sum() / den[sel].sum())
            if okP and okE:
                r["diff"] = r["shareP"] - r["shareE"]
            d["tiers"][t] = r
        out["writers"][w] = d
    both = [w for w, d in out["writers"].items() if d["have_P"] and d["have_E"]]

    def mean_of(ws):
        if not ws:
            return None
        a = out["writers"]
        return dict(n=len(ws), P=float(np.mean([a[w]["masks"]["all items"]["shareP"] for w in ws])),
                    E=float(np.mean([a[w]["masks"]["all items"]["shareE"] for w in ws])),
                    diff=float(np.mean([a[w]["masks"]["all items"]["diff"] for w in ws])))
    out["mean_all"] = mean_of(both)
    out["mean_without_own"] = mean_of([w for w in both if w != reader])
    return out


# ------------------------------------------------------------------ report
def settings_text(results):
    p = os.path.join(results, "model_settings.md")
    return open(p, encoding="utf-8").read().rstrip("\n") if os.path.exists(p) else None


def build_report(ctx):
    kit, rd, wr, ln, rt = ctx["kit"], ctx.get("reading"), ctx.get("writing"), ctx.get("length"), ctx.get("rt")
    L = []
    A = L.append
    A("# SILEX blind test: results tables")
    A("")
    A("Made by tools/aggregate.py (sha256 %s...) under ANALYSIS_PLAN.md (sha256 %s...). %s Bootstrap: %d resamples of the items, numpy default_rng([%d, k]), 95%% percentile intervals (2.5 and 97.5)." %
      ((ctx.get("tool_sha") or "?")[:16], (ctx.get("plan_sha") or "not found")[:16], "PARTIAL RUN: some judged sheets are incomplete; read nothing from this as a result." if ctx["partial"] else "All judged sheets are complete.", ctx["boot"], SEED))
    A("Sections present: " + ", ".join(ctx["sections"]) + ".")
    A("")
    A("## 1. The four predictions")
    A("")
    rows = []
    if rd:
        for m in MODELS:
            md = rd["models"].get(m, {})
            p = md.get("p1")
            if p:
                rows.append(["1", NAME[m], "R %s, N %s, gap %s points (n: %d R runs, %d N run)" % (pct(p["R_C"]), pct(p["N_C"]), spct(p["gap"]), len(md["R_runs"]), len(md["N_runs"])),
                             "gap of 20.0 points or more on the C facts", yn(p["holds"]), "%s; robust (lower bound 20.0 or more): %s" % (interval(p["lo"], p["hi"], True), yn(p["robust"]))])
            else:
                rows.append(["1", NAME[m], "not computed (needs a complete R run and a complete N run)", "", "", ""])
        for m in MODELS:
            p = rd["models"].get(m, {}).get("p2")
            if p:
                rows.append(["2", NAME[m], "tier 1 %s, tier 5 %s, difference %s points" % (pct(p["t1"]), pct(p["t5"]), spct(p["diff"])), "tier 1 strictly above tier 5 (all facts, R mean)",
                             ("no (tie)" if p["tie"] else yn(p["holds"])), interval(p["lo"], p["hi"], True)])
            else:
                rows.append(["2", NAME[m], "not computed", "", "", ""])
    if wr:
        for m in MODELS:
            md = wr["main"].get(m)
            if not md:
                rows.append(["3", NAME[m], "no complete run", "", "", ""])
                continue
            s = md["set"]
            label = NAME[m] + ((" (%s, runs %s%s)" % (s["label"], "+".join(str(r) for r in s["runs"]), ", provisional: only the auto set exists yet" if md["provisional"] else "")) if s["label"] else "")
            rows.append(["3", label, "%d of %d items valid = %s%%" % (s["valid"], s["items"], pct(s["share"])), "50.0% or more of the written items valid", yn(s["holds"]), interval(s["lo"], s["hi"])])
        for s in wr["sets"]:
            if s["model"] == "chatgpt" and s["label"] == "auto mode" and s["runs"] and wr["main"].get("chatgpt", {}).get("set") is not s:
                rows.append(["3", "ChatGPT (auto mode, runs %s)" % "+".join(str(r) for r in s["runs"]), "%d of %d items valid = %s%%" % (s["valid"], s["items"], pct(s["share"])),
                             "50.0% or more of the written items valid", yn(s["holds"]), interval(s["lo"], s["hi"])])
    rows.append(["4", "all", "no prediction: length and the round-trip comparison with English are reported as found (sections 4 and 5)", "", "", ""])
    A(md_table(["#", "Model", "Result", "Rule", "Holds?", "95% interval"], rows))
    A("")
    A("Notes that go with every table:")
    A("")
    A("- Comparisons between models are descriptive. The thinking mode and the model tier were not controlled by the protocol (the settings the user stated are at the end of this report). Contrasts within one model (R minus N, tier 1 against tier 5, SILEX against English) are fair.")
    A("- ChatGPT's reading chats ran in auto mode. In the writing test it has two sets: auto mode (runs 1 to 3) and the high setting (runs 4 to 6, the highest on the user's subscription), whose results are the main set of the comparison with the other models. The decision to repeat the ChatGPT writing test was made after the auto-set results were seen.")
    A("- Gemini's three writing runs used three different models (stated in the settings); its share is pooled over them as pre-registered, and the runs are shown one by one in section 3.1.")
    A("- One author: Claude wrote the items and the key and is one of the four models tested. Validity measures form, not truth. Forty items, one fixed order.")
    if ctx.get("judge_note"):
        A("- Judging: " + ctx["judge_note"])
    A("")
    if rd:
        A("## 2. Reading with and without the guide (judge scores)")
        A("")
        A("### 2.1 By run (share of facts credited, points; tiers use all facts)")
        A("")
        rows = [[r["arm"], NAME[r["model"]], r["run"], r["n_facts"], pct(r["all"]), pct(r["C"]), pct(r["S"])] + [pct(r["T%d" % t]) for t in TIERS] + [num1(r["false20"])] for r in rd["runs"]]
        A(md_table(["Arm", "Model", "Run", "Facts", "All", "C", "S", "T1", "T2", "T3", "T4", "T5", "False per 20 items"], rows))
        A("")
        A("### 2.2 By model (arm R: mean of its runs, lowest and highest run; arm N: its run)")
        A("")
        rows = []
        for m in MODELS:
            md = rd["models"][m]
            if "R" in md:
                R = md["R"]
                rows.append([NAME[m], "R", len(md["R_runs"]), pct(R["all"]), "%s to %s" % (pct(md["R_min_all"]), pct(md["R_max_all"])), pct(R["C"]), "%s to %s" % (pct(md["R_min_C"]), pct(md["R_max_C"])), pct(R["S"])] +
                            [pct(R["T%d" % t]) for t in TIERS] + [num1(R["false20"])])
            if "N" in md:
                N = md["N"]
                rows.append([NAME[m], "N", len(md["N_runs"]), pct(N["all"]), "", pct(N["C"]), "", pct(N["S"])] + [pct(N["T%d" % t]) for t in TIERS] + [num1(N["false20"])])
        A(md_table(["Model", "Arm", "Runs", "All (mean)", "All (lowest to highest run)", "C (mean)", "C (lowest to highest run)", "S", "T1", "T2", "T3", "T4", "T5", "False per 20 items"], rows))
        A("")
        A("### 2.3 R minus N on the C facts")
        A("")
        rows = []
        for m in MODELS:
            p = rd["models"][m].get("p1")
            if p:
                rows.append([NAME[m], pct(p["R_C"]), pct(p["N_C"]), spct(p["gap"]), interval(p["lo"], p["hi"], True), spct(p["gap_lowest_run"]), spct(p["gap_highest_run"]),
                             spct(p["mean_item_gap"]), interval(p["item_lo"], p["item_hi"], True)])
        A(md_table(["Model", "R (C facts)", "N (C facts)", "Gap, pooled", "95% interval", "Gap, lowest R run", "Gap, highest R run", "Mean of per-item gaps", "95% interval"], rows))
        A("")
        A("Per item (C facts, R mean against N) is in tables/reading_items.csv.")
        A("")
    if wr:
        A("## 3. Writing: do the written items pass the checker?")
        A("")
        A("### 3.1 By run")
        A("")
        A(md_table(["Model", "Run", "Items", "Valid", "Valid %", "Checker-ok %", "Joined-ok %"],
                   [[NAME.get(r["model"], r["model"]), r["run"], r["items"], r["valid"], pct(r["valid"] / r["items"]), pct(r["checker_ok"] / r["items"]), pct(r["joined_ok"] / r["items"])] for r in wr["runs"]]))
        A("")
        A("### 3.2 By set, with the tiers")
        A("")
        rows = []
        for s in wr["sets"]:
            if not s["runs"]:
                rows.append([NAME[s["model"]] + (" " + s["label"] if s["label"] else ""), "none yet", "", "", "", "", "", "", "", "", "", ""])
                continue
            rows.append([NAME[s["model"]] + (" (%s)" % s["label"] if s["label"] else ""), "+".join(str(r) for r in s["runs"]), s["items"], s["valid"], pct(s["share"]), interval(s["lo"], s["hi"]),
                         "%s to %s" % (pct(s["run_min"]), pct(s["run_max"]))] + [pct(s["tiers"][t]["valid"] / s["tiers"][t]["items"]) for t in TIERS])
        A(md_table(["Set", "Runs", "Items", "Valid", "Valid %", "95% interval", "Lowest to highest run", "T1", "T2", "T3", "T4", "T5"], rows))
        A("")
        A("### 3.3 Why items failed (all complete runs)")
        A("")
        if wr["codes"] or wr["reasons"]:
            A(md_table(["Kind", "Code", "Count"], [["checker verdict", c, n] for c, n in sorted(wr["codes"].items(), key=lambda x: (-x[1], x[0]))] + [["other reason", c, n] for c, n in sorted(wr["reasons"].items(), key=lambda x: (-x[1], x[0]))]))
        else:
            A("No invalid item.")
        A("")
        A("Items invalid in 4 or more of the %d runs of the main sets: %s." % (wr["hard_runs"], ", ".join("%s (%d)" % x for x in wr["hard"]) if wr["hard"] else "none"))
        A("")
        for n in wr["notes"]:
            A("- " + n)
        A("")
    if ln:
        A("## 4. Length (descriptive only)")
        A("")
        A("### 4.1 The writer's SILEX against the gold SILEX (characters per item, items that have text)")
        A("")
        A(md_table(["Set", "Runs", "Items with text", "Median characters", "Median gold characters (same items)", "Median ratio writer / gold"],
                   [[NAME[s["model"]] + (" (%s)" % s["label"] if s["label"] else ""), "+".join(str(r) for r in s["runs"]), "%d of %d" % (s["n"], s["of"]), num1(s["median_chars"]), num1(s["median_gold"]), num1(s["median_ratio"], 2)] for s in ln["silex"]]))
        A("")
        if ln["english"]:
            A("### 4.2 The writer's English (arm E) and SILEX against English")
            A("")
            A(md_table(["Writer", "Items with text", "Median characters", "Median words", "Median ratio English / gold SILEX", "SILEX source run", "Items in both", "Median SILEX characters per English character"],
                       [[NAME[e["model"]], e["n"], num1(e["median_chars"]), num1(e["median_words"]), num1(e["median_ratio_gold"], 2), e["silex_src_run"], e["n_both"], num1(e["median_silex_per_english"], 2)] for e in ln["english"]]))
            A("")
    if rt:
        A("## 5. Round trip: SILEX against English (judge scores on the scenario's C facts)")
        A("")
        A("Reader model (the same in all eight chats): %s. Writers from the reader's own model family are marked with *." % NAME.get(rt["reader"], rt["reader"]))
        A("The SILEX the reader saw was written in run: %s (rules 20 and 25 of P_handling_rules.md); the English in run 1 of arm E." % ", ".join("%s %d" % (NAME[w], r) for w, r in sorted(ctx["rt_src"].items(), key=lambda x: MODELS.index(x[0]))))
        A("")
        rows = []
        for w, d in rt["writers"].items():
            m = d["masks"].get("all items", {})
            rows.append([NAME[w] + ("*" if d["own"] else ""), "%s of %s" % (m.get("cred_P", "n/a"), m.get("n_facts", "n/a")), pct(m.get("shareP")), "%s of %s" % (m.get("cred_E", "n/a"), m.get("n_facts", "n/a")), pct(m.get("shareE")),
                         spct(m.get("diff")), interval(m["lo"], m["hi"], True) if "lo" in m else "n/a", num1(d.get("false20_P")), num1(d.get("false20_E"))])
        A(md_table(["Writer", "SILEX: C facts credited", "SILEX %", "English: C facts credited", "English %", "SILEX minus English", "95% interval (paired, over items)", "False per 20 items, SILEX", "False per 20 items, English"], rows))
        A("")
        if rt["mean_all"]:
            a, b = rt["mean_all"], rt["mean_without_own"]
            A("Mean over writers: SILEX %s, English %s, difference %s (%d writers)." % (pct(a["P"]), pct(a["E"]), spct(a["diff"]), a["n"]))
            if b:
                A("Mean over writers without the reader's own family: SILEX %s, English %s, difference %s (%d writers)." % (pct(b["P"]), pct(b["E"]), spct(b["diff"]), b["n"]))
            A("")
        A("### 5.1 By tier (SILEX %, English %, difference in points)")
        A("")
        rows = []
        for w, d in rt["writers"].items():
            rows.append([NAME[w] + ("*" if d["own"] else "")] + ["%s / %s / %s" % (pct(d["tiers"][t].get("shareP")), pct(d["tiers"][t].get("shareE")), spct(d["tiers"][t].get("diff"))) for t in TIERS])
        A(md_table(["Writer", "T1", "T2", "T3", "T4", "T5"], rows))
        A("")
        A("### 5.2 Sensitivity checks (beside the main figure, never instead of it)")
        A("")
        rows = []
        for w, d in rt["writers"].items():
            for name, m in d["masks"].items():
                if name == "all items":
                    continue
                rows.append([NAME[w] + ("*" if d["own"] else ""), name, m["n_items"], pct(m.get("shareP")), pct(m.get("shareE")), spct(m.get("diff")), interval(m["lo"], m["hi"], True) if "lo" in m else "n/a"])
        A(md_table(["Writer", "Subset of items", "Items in subset", "SILEX %", "English %", "Difference", "95% interval"], rows) if rows else "No sensitivity set could be built.")
        A("")
    if ctx["issues"]:
        A("## 6. Lists")
        A("")
        for n in ctx["issues"]:
            A("- " + n)
        A("")
    if ctx.get("errata"):
        A("## Items dropped by the errata rule")
        A("")
        A(ctx["errata"])
        A("")
    if ctx.get("settings"):
        A("## Models and settings (model_settings.md, verbatim)")
        A("")
        A(ctx["settings"])
        A("")
    return "\n".join(L) + "\n"


def tables(ctx):
    """name -> (header, rows) for tables/*.csv."""
    T = {}
    rd, wr, ln, rt, kit = ctx.get("reading"), ctx.get("writing"), ctx.get("length"), ctx.get("rt"), ctx["kit"]
    r6 = lambda x: "" if isnan(x) else repr(round(float(x), 6))
    if rd:
        T["reading_by_run"] = (["arm", "model", "run", "facts", "all", "C", "S"] + ["T%d" % t for t in TIERS] + ["T%d_C" % t for t in TIERS] + ["false_per_20_items"],
                               [[r["arm"], r["model"], r["run"], r["n_facts"], r6(r["all"]), r6(r["C"]), r6(r["S"])] + [r6(r["T%d" % t]) for t in TIERS] + [r6(r["T%d_C" % t]) for t in TIERS] + [r6(r["false20"])] for r in rd["runs"]])
        rows = []
        for m in MODELS:
            md = rd["models"][m]
            for arm in ("R", "N"):
                if arm in md:
                    s = md[arm]
                    rows.append([m, arm, len(md[arm + "_runs"]), r6(s["all"]), r6(md.get(arm + "_min_all", s["all"])), r6(md.get(arm + "_max_all", s["all"])), r6(s["C"]),
                                 r6(md.get(arm + "_min_C", s["C"])), r6(md.get(arm + "_max_C", s["C"])), r6(s["S"])] + [r6(s["T%d" % t]) for t in TIERS] + [r6(s["T%d_C" % t]) for t in TIERS] + [r6(s["false20"])])
        T["reading_by_model"] = (["model", "arm", "runs", "all", "all_min", "all_max", "C", "C_min", "C_max", "S"] + ["T%d" % t for t in TIERS] + ["T%d_C" % t for t in TIERS] + ["false_per_20_items"], rows)
        T["prediction_1"] = (["model", "R_C", "N_C", "gap", "ci_lo", "ci_hi", "holds_point", "holds_robust", "gap_lowest_R_run", "gap_highest_R_run", "mean_item_gap", "item_ci_lo", "item_ci_hi"],
                             [[m, r6(p["R_C"]), r6(p["N_C"]), r6(p["gap"]), r6(p["lo"]), r6(p["hi"]), int(p["holds"]), int(p["robust"]), r6(p["gap_lowest_run"]), r6(p["gap_highest_run"]), r6(p["mean_item_gap"]), r6(p["item_lo"]), r6(p["item_hi"])]
                              for m in MODELS for p in [rd["models"][m].get("p1")] if p])
        T["prediction_2"] = (["model", "tier1", "tier5", "diff", "ci_lo", "ci_hi", "holds", "tie"],
                             [[m, r6(p["t1"]), r6(p["t5"]), r6(p["diff"]), r6(p["lo"]), r6(p["hi"]), int(p["holds"]), int(p["tie"])] for m in MODELS for p in [rd["models"][m].get("p2")] if p])
        T["reading_items"] = (["item", "tier"] + [m + "_" + a for m in MODELS for a in ("R_C", "N_C")],
                              [[r["item"], r["tier"]] + [r6(r[m + "_" + a]) for m in MODELS for a in ("R", "N")] for r in rd["items"]])
    if wr:
        T["writing_by_run"] = (["model", "run", "items", "valid", "checker_ok", "joined_ok"], [[r["model"], r["run"], r["items"], r["valid"], r["checker_ok"], r["joined_ok"]] for r in wr["runs"]])
        T["writing_by_set"] = (["model", "set", "runs", "items", "valid", "share", "ci_lo", "ci_hi", "run_min", "run_max", "holds_prediction_3", "main"] + ["T%d_valid" % t for t in TIERS] + ["T%d_items" % t for t in TIERS],
                               [[s["model"], s["label"], "+".join(str(r) for r in s["runs"]), s["items"], s["valid"], r6(s["share"]), r6(s["lo"]), r6(s["hi"]), r6(s["run_min"]), r6(s["run_max"]), int(s["holds"]),
                                 int(wr["main"].get(s["model"], {}).get("set") is s)] + [s["tiers"][t]["valid"] for t in TIERS] + [s["tiers"][t]["items"] for t in TIERS] for s in wr["sets"] if s["runs"]])
        T["writing_codes"] = (["kind", "code", "count"], [["verdict", c, n] for c, n in sorted(wr["codes"].items())] + [["reason", c, n] for c, n in sorted(wr["reasons"].items())])
    if ln:
        T["length_silex"] = (["model", "set", "runs", "items_with_text", "items", "median_chars", "median_gold_chars", "median_ratio"],
                             [[s["model"], s["label"], "+".join(str(r) for r in s["runs"]), s["n"], s["of"], r6(s["median_chars"]), r6(s["median_gold"]), r6(s["median_ratio"])] for s in ln["silex"]])
        T["length_english"] = (["model", "run", "items_with_text", "median_chars", "median_words", "median_ratio_to_gold", "silex_source_run", "items_in_both", "median_silex_per_english", "none_items", "missing_items"],
                               [[e["model"], e["run"], e["n"], r6(e["median_chars"]), r6(e["median_words"]), r6(e["median_ratio_gold"]), e["silex_src_run"], e["n_both"], r6(e["median_silex_per_english"]), e["none_items"], e["missing_items"]] for e in ln["english"]])
    if rt:
        rows = []
        for w, d in rt["writers"].items():
            for name, m in d["masks"].items():
                rows.append([w, int(d["own"]), name, m["n_items"], m.get("n_facts"), m.get("cred_P", ""), r6(m.get("shareP", float("nan"))), m.get("cred_E", ""), r6(m.get("shareE", float("nan"))),
                             r6(m.get("diff", float("nan"))), r6(m.get("lo", float("nan"))), r6(m.get("hi", float("nan"))), r6(d.get("false20_P", float("nan"))) if name == "all items" else "", r6(d.get("false20_E", float("nan"))) if name == "all items" else ""])
        T["roundtrip"] = (["writer", "reader_own_family", "items_kept", "items", "c_facts", "cred_silex", "silex", "cred_english", "english", "diff", "ci_lo", "ci_hi", "false_per_20_silex", "false_per_20_english"], rows)
        T["roundtrip_tiers"] = (["writer", "tier", "silex", "english", "diff"], [[w, t, r6(d["tiers"][t].get("shareP", float("nan"))), r6(d["tiers"][t].get("shareE", float("nan"))), r6(d["tiers"][t].get("diff", float("nan")))] for w, d in rt["writers"].items() for t in TIERS])
    return T


def summary_json(ctx):
    kit = ctx["kit"]
    s = dict(seed=SEED, boot=ctx["boot"], partial=ctx["partial"], sections=ctx["sections"])
    if ctx.get("reading"):
        s["reading"] = dict(models=ctx["reading"]["models"], runs=ctx["reading"]["runs"])
    if ctx.get("writing"):
        w = ctx["writing"]
        s["writing"] = dict(runs=w["runs"], sets=[{k: v for k, v in x.items() if k != "invalid_per_item"} for x in w["sets"]], hard=w["hard"], codes=w["codes"], reasons=w["reasons"],
                            main={m: dict(label=v["set"]["label"], runs=v["set"]["runs"], provisional=v["provisional"]) for m, v in w["main"].items()})
    if ctx.get("length"):
        s["length"] = ctx["length"]
    if ctx.get("rt"):
        s["roundtrip"] = ctx["rt"]
    return s


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, set):
        return sorted(o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reading-map")
    ap.add_argument("--reading-scores")
    ap.add_argument("--rt-map")
    ap.add_argument("--rt-scores")
    ap.add_argument("--rt-key-p")
    ap.add_argument("--rt-key-e")
    ap.add_argument("--validity", action="append")
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--judge-note", default="", help="one sentence for the report: who judged, with which prompts")
    a = ap.parse_args()
    if os.path.exists(a.out) and os.listdir(a.out):
        die("%s exists and is not empty" % a.out)
    if bool(a.reading_map) != bool(a.reading_scores):
        die("--reading-map and --reading-scores go together")
    rt_args = [a.rt_map, a.rt_scores, a.rt_key_p, a.rt_key_e]
    if any(rt_args) and not all(rt_args):
        die("--rt-map, --rt-scores, --rt-key-p and --rt-key-e go together")
    kit = Kit(a.kit)
    issues, notes, inputs = [], [], {}
    plan_path = os.path.join(a.results, "ANALYSIS_PLAN.md")
    ctx = dict(kit=kit, partial=a.partial, boot=a.boot, sections=[], issues=issues, judge_note=a.judge_note.strip(),
               tool_sha=hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest(), plan_sha=hashlib.sha256(open(plan_path, "rb").read()).hexdigest() if os.path.exists(plan_path) else None)

    def need_complete(sheets, what):
        inc = [s["code"] for s in sheets if not s["complete"]]
        if inc and not a.partial:
            die("%s: %d judged sheets are incomplete (%s); finish the judging or use --partial for a look that is not a result" % (what, len(inc), " ".join(inc)))

    if a.reading_map:
        sheets = load_judged(a.reading_map, a.reading_scores, kit, False, notes)
        need_complete(sheets, "reading")
        bad = [s for s in sheets if s["arm"] not in ("R", "N")]
        if bad:
            die("reading map: sheet %s has the arm %r" % (bad[0]["code"], bad[0]["arm"]))
        runs = assemble(kit, sheets, lambda s: (s["arm"], s["model"], int(s["run"])), False, issues)
        ctx["reading"] = reading_block(kit, runs, a.boot)
        ctx["reading_sheets"] = sheets
        ctx["sections"].append("reading")
        inputs["reading_map"] = sha16(a.reading_map)
    vdirs = a.validity
    if not vdirs:
        vdirs = [d for d in (os.path.join(a.results, "validity_P"), os.path.join(a.results, "validity_P_high")) if os.path.exists(os.path.join(d, "items.csv"))]
    by = None
    if vdirs:
        by = load_validity(vdirs)
        check_validity_summaries(vdirs, by, issues)
        ctx["writing"] = writing_block(kit, by, a.boot)
        ctx["sections"].append("writing")
        for d in vdirs:
            inputs["validity:" + os.path.basename(d.rstrip("/"))] = sha16(os.path.join(d, "items.csv"))
        eng = load_english(a.results, kit, issues)
        ctx["length"] = length_block(kit, by, eng)
        ctx["sections"].append("length")
    if a.rt_map:
        cw_p, cw_e, runs_p, nonmsg = load_rt_keys(a.rt_key_p, a.rt_key_e)
        sheets = load_judged(a.rt_map, a.rt_scores, kit, True, notes)
        need_complete(sheets, "round trip")
        for s in sheets:
            cw = cw_p if s["arm"] == "RTP" else cw_e if s["arm"] == "RTE" else None
            if cw is None:
                die("round-trip map: sheet %s has the arm %r" % (s["code"], s["arm"]))
            if int(s["run"]) not in cw:
                die("round-trip map: sheet %s reads chat %s, which is not in the key" % (s["code"], s["run"]))
            s["writer"] = cw[int(s["run"])]
        readers = sorted({s["model"] for s in sheets})
        if len(readers) != 1:
            die("round trip: more than one reader model in the map: %s" % readers)
        runs = assemble(kit, sheets, lambda s: (s["arm"], s["writer"]), True, issues)
        valid_masks = {}
        if by:
            for w, run in runs_p.items():
                if (w, run) in by and sorted(by[(w, run)]) == ITEMS:
                    valid_masks[w] = np.array([by[(w, run)][i]["valid"] == "1" for i in ITEMS])
                else:
                    issues.append("sensitivity check (a) for %s: the validity rows of run %d are missing" % (w, run))
        ctx["rt"] = rt_block(kit, runs, readers[0], valid_masks, nonmsg, a.boot)
        ctx["rt_src"] = runs_p
        ctx["rt_sheets"] = sheets
        ctx["sections"].append("roundtrip")
        inputs["rt_map"], inputs["rt_key_p"], inputs["rt_key_e"] = sha16(a.rt_map), sha16(a.rt_key_p), sha16(a.rt_key_e)
    if not ctx["sections"]:
        die("nothing to do: no reading map, no validity folder")
    for n in notes:
        issues.append(n)
    ep = os.path.join(a.results, "errata.txt")
    ctx["errata"] = open(ep, encoding="utf-8").read().strip() if os.path.exists(ep) else "None."
    ctx["settings"] = settings_text(a.results)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_report(ctx))
    for name, (hdr, rows) in tables(ctx).items():
        write_csv(os.path.join(a.out, "tables", name + ".csv"), hdr, rows)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(jsonable(summary_json(ctx)), f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    # the judged facts, one row each, for the audit trail
    lrows = []
    for key, sheets in (("reading", ctx.get("reading_sheets")), ("roundtrip", ctx.get("rt_sheets"))):
        for s in sheets or []:
            if not s["complete"]:
                continue
            for item in s["order"]:
                v = s["items"][item]
                for k in sorted(v["scores"]):
                    f_ = kit.facts[kit.fidx[(item, k)]]
                    lrows.append([key, s["arm"], s["model"], s.get("writer", ""), s["run"], s["batch"], s["code"], item, f_["id"], f_["type"], f_["tier"], v["scores"][k], v["false"] if k == min(v["scores"]) else ""])
    lrows.sort(key=lambda r: (r[0], r[1], r[2], r[3], int(r[4]), r[6], r[7], r[8]))
    write_csv(os.path.join(a.out, "scores_long.csv"), ["domain", "arm", "model_or_reader", "writer", "run_or_chat", "batch", "sheet", "item", "fact", "type", "tier", "score", "false_count_of_item"], lrows)
    info = dict(made=datetime.datetime.now().isoformat(timespec="seconds"), tool_sha16=sha16(os.path.abspath(__file__)), plan_sha16=sha16(os.path.join(a.results, "ANALYSIS_PLAN.md")) if os.path.exists(os.path.join(a.results, "ANALYSIS_PLAN.md")) else None,
                kit_facts=sha16(os.path.join(a.kit, "facts.csv")), kit_order=sha16(os.path.join(a.kit, "order.csv")), inputs=inputs, seed=SEED, boot=a.boot, partial=a.partial,
                python=platform.python_version(), numpy=np.__version__, score_files=sorted(os.path.basename(p) for d in (a.reading_scores, a.rt_scores) if d for p in glob.glob(os.path.join(d, "*.json"))))
    with open(os.path.join(a.out, "aggregate_info.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=1, sort_keys=True)
        f.write("\n")
    print("written: %s (sections: %s%s)" % (a.out, ", ".join(ctx["sections"]), "; PARTIAL" if a.partial else ""))
    for n in issues:
        print("  list: " + n)


if __name__ == "__main__":
    main()
