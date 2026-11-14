#!/usr/bin/env python3
"""Fill a COPY of the kit's silex_scoring.xlsx with the judged scores and check the workbook's own formulas against the aggregator's tables.

This is a presentation and cross-check step; it scores nothing. The 0/1 values are copied from aggregate.py's scores_long.csv (reading: arms R and N, round trip: arms RTP and RTE)
and from the validity files made by check_p.py (writing). The kit's template is never changed. The filled copy is recalculated with LibreOffice (headless) and the numbers that the
workbook's formulas give on its Summary tab are compared with aggregate.py's tables/*.csv. Any difference larger than 0.0005 (0.05 points) is listed and the exit code is 1.

Layout of the template (read from it, not assumed): Recovery A=Fact ID B=Type C=Tier D..S one column per run (R-claude-1 .. N-gemini-1); Writing A=Item B=Tier C..N one column per run (P-claude-1 .. P-gemini-3);
Round trip A=Fact ID B=Tier C..F SILEX by writer (P-claude .. P-gemini), G..J English by writer (E-claude .. E-gemini). ChatGPT's writing columns hold the HIGH-setting set (runs 4 to 6, the main set of the
comparison); the auto-mode set (runs 1 to 3) is on an extra sheet "Writing (ChatGPT auto)", values only. An extra sheet "Notes" says where every number comes from.

Usage:
  python3 -I fill_scoring_xlsx.py --template silex_scoring.xlsx --scores AGG/scores_long.csv --validity validity_P validity_P_high --tables AGG/tables --out OUTDIR
OUTDIR must not exist or be empty. Output: OUTDIR/silex_scoring_filled.xlsx (formulas and the values LibreOffice calculated), OUTDIR/crosscheck.md.
Exit code: 0 everything agrees, 1 a difference or a structural mismatch, 2 usage / tool missing.
"""
import argparse
import csv
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

import openpyxl

MODELS = ["claude", "chatgpt", "grok", "gemini"]
TOL = 0.0005


def die(msg, code=1):
    print("fill_scoring_xlsx.py: " + msg, file=sys.stderr)
    sys.exit(code)


def read_csv(p):
    return list(csv.DictReader(open(p, newline="", encoding="utf-8")))


def sha16(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def header_map(ws, row=1):
    return {str(c.value).strip(): c.column for c in ws[row] if c.value is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--validity", nargs="+", required=True, help="the main validity folder first (runs of claude, grok, gemini and ChatGPT auto), then the high-setting folder")
    ap.add_argument("--tables", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out) and os.listdir(a.out):
        die("OUT must not exist or must be empty", 2)
    os.makedirs(a.out, exist_ok=True)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        die("LibreOffice (soffice) is not installed", 2)

    wb = openpyxl.load_workbook(a.template)
    rec, wri, rtt, key = wb["Recovery"], wb["Writing"], wb["Round trip"], wb["Key"]
    problems = []

    # ---- reading
    rows = read_csv(a.scores)
    reading = {}
    fact_meta = {}
    for r in rows:
        if r["domain"] == "reading":
            reading[(r["arm"], r["model_or_reader"], int(r["run_or_chat"]), r["fact"])] = int(r["score"])
            fact_meta[r["fact"]] = (r["type"], int(r["tier"]))
    hm = header_map(rec)
    col_of_run = {}
    for name, col in hm.items():
        parts = name.split("-")
        if len(parts) == 3 and parts[0] in ("R", "N") and parts[1] in MODELS:
            col_of_run[(parts[0], parts[1], int(parts[2]))] = col
    n_cells = 0
    for rr in range(2, rec.max_row + 1):
        fid = rec.cell(rr, 1).value
        if fid is None:
            continue
        fid = str(fid).strip()
        meta = fact_meta.get(fid)
        if meta is None:
            problems.append("Recovery: fact %s is not in scores_long.csv" % fid)
            continue
        if (str(rec.cell(rr, 2).value).strip(), int(rec.cell(rr, 3).value)) != meta:
            problems.append("Recovery: type or tier of %s differs between the template and scores_long.csv" % fid)
        for (arm, model, run), col in col_of_run.items():
            v = reading.get((arm, model, run, fid))
            if v is None:
                problems.append("Recovery: no score for %s %s run %d %s" % (arm, model, run, fid))
                continue
            rec.cell(rr, col).value = v
            n_cells += 1
    n_facts_template = sum(1 for rr in range(2, rec.max_row + 1) if rec.cell(rr, 1).value)
    if n_facts_template != len({f for f in fact_meta}):
        problems.append("Recovery: the template has %d facts, scores_long.csv has %d" % (n_facts_template, len(fact_meta)))
    n_reading_expected = len(reading)
    if n_cells != n_reading_expected:
        problems.append("Recovery: %d cells filled but scores_long.csv has %d reading scores" % (n_cells, n_reading_expected))

    # ---- round trip
    rt = {}
    for r in rows:
        if r["domain"] == "roundtrip":
            rt[(r["arm"], r["writer"], r["fact"])] = int(r["score"])
    hm = header_map(rtt)
    n_rt = 0
    for rr in range(2, rtt.max_row + 1):
        fid = rtt.cell(rr, 1).value
        if fid is None:
            continue
        fid = str(fid).strip()
        for w in MODELS:
            for arm, prefix in (("RTP", "P"), ("RTE", "E")):
                col = hm.get("%s-%s" % (prefix, w))
                v = rt.get((arm, w, fid))
                if col is None or v is None:
                    problems.append("Round trip: no place or no score for %s %s %s" % (arm, w, fid))
                    continue
                rtt.cell(rr, col).value = v
                n_rt += 1
    if n_rt != len(rt):
        problems.append("Round trip: %d cells filled but scores_long.csv has %d round-trip scores" % (n_rt, len(rt)))

    # ---- writing
    val_main = {}
    val_high = {}
    for p, store in ((a.validity[0], val_main), (a.validity[-1], val_high)):
        for r in read_csv(os.path.join(p, "items.csv")):
            store[(r["model"], int(r["run"]), r["item"])] = (int(r["valid"]), int(r["tier"]))
    hm = header_map(wri)
    n_w = 0
    for rr in range(2, wri.max_row + 1):
        item = wri.cell(rr, 1).value
        if item is None:
            continue
        item = str(item).strip()
        for m in MODELS:
            for k in (1, 2, 3):
                col = hm.get("P-%s-%d" % (m, k))
                src = val_high.get(("chatgpt", k + 3, item)) if m == "chatgpt" else val_main.get((m, k, item))
                if col is None or src is None:
                    problems.append("Writing: no place or no validity for %s run %d %s" % (m, k, item))
                    continue
                if int(wri.cell(rr, 2).value) != src[1]:
                    problems.append("Writing: tier of %s differs between the template and the validity file" % item)
                wri.cell(rr, col).value = src[0]
                n_w += 1
    # extra sheet: ChatGPT auto-mode set (values only)
    ws_auto = wb.create_sheet("Writing (ChatGPT auto)")
    ws_auto.append(["Item", "Tier", "P-chatgpt-auto-1", "P-chatgpt-auto-2", "P-chatgpt-auto-3"])
    items = sorted({k[2] for k in val_main if k[0] == "chatgpt"})
    for it in items:
        ws_auto.append([it, val_main[("chatgpt", 1, it)][1]] + [val_main[("chatgpt", k, it)][0] for k in (1, 2, 3)])
    ws_auto.append([])
    ws_auto.append(["Valid items", "", *[sum(val_main[("chatgpt", k, it)][0] for it in items) for k in (1, 2, 3)]])
    ws_auto.append(["Auto mode = ChatGPT 6.0 sol with no thinking adjustment (runs 1 to 3 of the writing test). The Writing tab holds the high-setting set (runs 4 to 6), the main set of the comparison."])

    notes = wb.create_sheet("Notes")
    for line in [
        "Where the numbers come from",
        "Filled on %s from the aggregator's scores_long.csv (sha256 first 16: %s) and the validity files (%s)." % (
            datetime.date.today().isoformat(), sha16(a.scores), ", ".join(os.path.basename(os.path.normpath(p)) + "/items.csv " + sha16(os.path.join(p, "items.csv")) for p in a.validity)),
        "Template: %s (sha256 first 16: %s), unchanged; this is a copy." % (os.path.basename(a.template), sha16(a.template)),
        "Reading and round trip: 1 = the judge credited the fact, 0 = not. Judge: first judge (cold-start Claude Fable 5.2 agents), frozen prompts judge_recovery.txt and judge_roundtrip.txt.",
        "Writing: 1 = every message of the item passes the checker (the primary decision of P_handling_rules.md rule 15).",
        "ChatGPT's writing columns hold its high-setting set (runs 4 to 6, the main set); the auto-mode set is on the sheet 'Writing (ChatGPT auto)'.",
        "The Summary tab is the template's own formulas. The aggregator's tables (report.md) were compared with them: see crosscheck.md.",
        "Limits that go with every number: one author who is also a tested model; form not truth; 40 items in one fixed order; thinking mode and tier were not controlled across models; judges are Claude models.",
    ]:
        notes.append([line])
    notes.column_dimensions["A"].width = 160
    if problems:
        print("STRUCTURAL PROBLEMS:\n  " + "\n  ".join(problems[:40]))
        die("the template could not be filled completely; nothing is claimed")
    raw = os.path.join(a.out, "silex_scoring_filled_raw.xlsx")
    wb.save(raw)

    # ---- recalculate with LibreOffice
    prof = tempfile.mkdtemp(prefix="lo_profile_")
    rec_dir = os.path.join(a.out, "recalc")
    os.makedirs(rec_dir)
    cmd = [soffice, "-env:UserInstallation=file://" + prof, "--headless", "--convert-to", "xlsx", "--outdir", rec_dir, raw]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out_x = os.path.join(rec_dir, "silex_scoring_filled_raw.xlsx")
    if p.returncode != 0 or not os.path.exists(out_x):
        die("LibreOffice failed: " + (p.stderr or p.stdout)[:300])
    final = os.path.join(a.out, "silex_scoring_filled.xlsx")
    shutil.move(out_x, final)
    os.rmdir(rec_dir)
    os.remove(raw)
    shutil.rmtree(prof, ignore_errors=True)

    # ---- compare the workbook's formulas with the aggregator's tables
    wv = openpyxl.load_workbook(final, data_only=True)
    S = wv["Summary"]
    diffs, n_cmp = [], 0

    def cmp(label, got, exp):
        nonlocal n_cmp
        n_cmp += 1
        if got is None or got == "":
            diffs.append("%s: the workbook shows nothing, aggregate %.6f" % (label, exp))
        elif abs(float(got) - float(exp)) > TOL:
            diffs.append("%s: workbook %.6f, aggregate %.6f" % (label, float(got), float(exp)))

    by_run = {(r["arm"], r["model"], int(r["run"])): r for r in read_csv(os.path.join(a.tables, "reading_by_run.csv"))}
    cols = ["all", "C", "S", "T1", "T2", "T3", "T4", "T5"]
    for rr in range(6, 22):
        name = str(S.cell(rr, 1).value)
        arm, model, run = name.split("-")[0], name.split("-")[1], int(name.split("-")[2])
        agg = by_run[(arm, model, run)]
        for j, c in enumerate(cols):
            cmp("Summary %s %s" % (name, c), S.cell(rr, 4 + j).value, float(agg[c]))
    by_model = {(r["model"], r["arm"]): r for r in read_csv(os.path.join(a.tables, "reading_by_model.csv"))}
    for rr in range(25, 29):
        m = str(S.cell(rr, 1).value)
        agg_r, agg_n = by_model[(m, "R")], by_model[(m, "N")]
        cmp("Summary %s R all" % m, S.cell(rr, 2).value, float(agg_r["all"]))
        cmp("Summary %s R C" % m, S.cell(rr, 3).value, float(agg_r["C"]))
        cmp("Summary %s R C lowest run" % m, S.cell(rr, 4).value, float(agg_r["C_min"]))
        cmp("Summary %s R C highest run" % m, S.cell(rr, 5).value, float(agg_r["C_max"]))
        cmp("Summary %s N C" % m, S.cell(rr, 6).value, float(agg_n["C"]))
        cmp("Summary %s R minus N (C)" % m, S.cell(rr, 7).value, float(agg_r["C"]) - float(agg_n["C"]))
    wr = {(r["model"], int(r["run"])): r for r in read_csv(os.path.join(a.tables, "writing_by_run.csv"))}
    for rr in range(32, 44):
        name = str(S.cell(rr, 1).value)
        m, k = name.split("-")[1], int(name.split("-")[2])
        agg = wr[(m, k + 3 if m == "chatgpt" else k)]
        cmp("Summary %s valid items" % name, S.cell(rr, 3).value, float(agg["valid"]))
        cmp("Summary %s share valid" % name, S.cell(rr, 4).value, float(agg["valid"]) / float(agg["items"]))
    rtab = {r["writer"]: r for r in read_csv(os.path.join(a.tables, "roundtrip.csv")) if r["items_kept"] == "all items"}
    for rr in range(47, 51):
        w = str(S.cell(rr, 1).value)
        cmp("Summary round trip %s SILEX" % w, S.cell(rr, 2).value, float(rtab[w]["silex"]))
        cmp("Summary round trip %s English" % w, S.cell(rr, 3).value, float(rtab[w]["english"]))
        cmp("Summary round trip %s difference" % w, S.cell(rr, 4).value, float(rtab[w]["diff"]))
    lines = ["# Cross-check: the workbook's own formulas against the aggregator's tables", "",
             "Filled copy: silex_scoring_filled.xlsx (recalculated with LibreOffice). Template %s (sha256 first 16 %s). scores_long.csv %s." % (
                 os.path.basename(a.template), sha16(a.template), sha16(a.scores)),
             "Cells filled: reading %d, round trip %d, writing %d (+ the ChatGPT auto sheet). Numbers compared: %d (tolerance %.4f, that is 0.05 points)." % (n_cells, n_rt, n_w, n_cmp, TOL), ""]
    if diffs:
        lines += ["**%d difference(s):**" % len(diffs)] + ["- " + d for d in diffs]
    else:
        lines += ["**All %d numbers agree.** (the workbook's SUM/COUNT formulas and the aggregator's own code reach the same shares)" % n_cmp]
    open(os.path.join(a.out, "crosscheck.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(1 if diffs else 0)


if __name__ == "__main__":
    main()
