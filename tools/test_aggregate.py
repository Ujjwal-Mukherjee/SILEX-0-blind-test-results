#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of aggregate.py on SYNTHETIC data in temporary folders. Nothing real is touched: the real kit files are only read (facts.csv, order.csv).
The judge replies are run through the real form checkers (check_judge_reply.py, check_judge_reply_rt.py) and the English replies through the real
parser (parse_e_reply.py), so the formats the aggregator reads are the formats the tools write. Every number is also computed here again in plain loops.

  python3 -I test_aggregate.py [KIT]
"""
import csv, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aggregate as ag          # noqa: E402
import parse_e_reply as pe      # noqa: E402

KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
MODELS = ag.MODELS
ITEMS = ag.ITEMS
B = 300
FAILS, OK = [], [0]


def check(cond, msg):
    if cond:
        OK[0] += 1
    else:
        FAILS.append(msg)
        print("FAIL:", msg)


def close(a, b, tol=1e-9):
    return a is not None and b is not None and abs(a - b) <= tol


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


FACTS = [dict(id=r["fact_id"], item=r["id"], k=int(r["fact_id"].split(".F")[1]), type=r["type"], tier=int(r["tier"])) for r in read_csv(os.path.join(KIT, "facts.csv"))]
ORDER = {r["id"]: dict(batch=int(r["batch"]), tier=int(r["tier"]), gold=int(r["silex_chars"])) for r in read_csv(os.path.join(KIT, "order.csv"))}
BATCH_ITEMS = {b: [i for i in ITEMS if ORDER[i]["batch"] == b] for b in (1, 2)}
FACTS_OF = {}
for f in FACTS:
    FACTS_OF.setdefault(f["item"], []).append(f)
ALPH = "ABCDEFGHJKMNPQRTUVWXYZ23456789"


def run_py(script, *args):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *args], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def run_ag(*args):
    return run_py("aggregate.py", *args)


# ------------------------------------------------------------------ the synthetic world
class World:
    pass


def build_world(root, seed=7, drop=(), cut=None, no_high=False, summary_lie=False, reader="grok", p3_special=True, with_rt=True, with_english=True, dup_conflict=False):
    rng = random.Random(seed)
    w = World()
    w.root, w.res = root, os.path.join(root, "res")
    os.makedirs(w.res)
    put(os.path.join(w.res, "model_settings.md"), "# Models and settings\nSynthetic settings line.\n")
    put(os.path.join(w.res, "ANALYSIS_PLAN.md"), "synthetic plan\n")
    used = set()

    def code():
        while True:
            c = "".join(rng.choice(ALPH) for _ in range(4))
            if c not in used:
                used.add(c)
                return c

    # ---------- reading truth and sheets
    w.rtruth, w.rfalse = {}, {}
    for m in MODELS:
        for arm, runs in (("R", (1, 2, 3)), ("N", (1,))):
            for run in runs:
                base = {"R": 0.85, "N": 0.30}[arm] + 0.03 * MODELS.index(m)
                if m == "chatgpt" and arm == "N":
                    base = 0.80                      # a small R minus N gap
                sc, fl = {}, {}
                for f in FACTS:
                    p = base - 0.05 * (f["tier"] - 1) - (0.05 if f["type"] == "S" else 0)
                    sc[f["id"]] = 1 if (m == "grok" and arm == "R") else int(rng.random() < p)      # grok R: every fact credited -> tier 1 equals tier 5
                for i in ITEMS:
                    fl[i] = rng.choice([0, 0, 0, 1, 2])
                w.rtruth[(arm, m, run)], w.rfalse[(arm, m, run)] = sc, fl
    rmap, w.rcodes = [], {}
    for (arm, m, run) in sorted(w.rtruth):
        for b in (1, 2):
            c = code()
            order = list(BATCH_ITEMS[b])
            rng.shuffle(order)
            w.rcodes[(arm, m, run, b)] = c
            rmap.append(dict(code=c, recv="recv%02d" % (len(rmap) + 1), arm=arm, model=m, run=str(run), batch=str(b), n_items="20", raw_sha16="0" * 16, sheet_sha16="1" * 16, order=" ".join(order), corrected_items=""))
    w.rmap_path = os.path.join(root, "judge_reading", "sheets_map_PRIVATE.csv")
    os.makedirs(os.path.dirname(w.rmap_path))
    write_map(w.rmap_path, rmap)
    w.rscores = os.path.join(root, "judge_reading", "scores")
    os.makedirs(w.rscores)
    for r in rmap:
        key = (r["arm"], r["model"], int(r["run"]))
        if r["code"] in drop:
            continue
        lines = []
        for it in r["order"].split():
            sc = {f["k"]: w.rtruth[key][f["id"]] for f in FACTS_OF[it]}
            lines.append("%s | %s | false=%d | %s" % (it, " ".join("F%d=%d" % (k, v) for k, v in sorted(sc.items())), w.rfalse[key][it], "missing" if 0 in sc.values() else ""))
        if cut and r["code"] == cut[0]:
            lines = lines[:cut[1]]
        rp = os.path.join(root, "judge_reading", "reply_%s.txt" % r["code"])
        put(rp, "\n".join(lines) + "\n")
        rc, out, err = run_py("check_judge_reply.py", "--map", w.rmap_path, "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(w.rscores, "%s_1.json" % r["code"]))
        assert rc in (0, 1), (out, err)
        if dup_conflict and r["code"] == w.rcodes[("R", "claude", 1, 1)]:
            # a second scoring of the same sheet with other values for the first item: the first scoring must stay
            first = r["order"].split()[0]
            alt = [l for l in lines]
            alt[0] = "%s | %s | false=9 | changed" % (first, " ".join("F%d=%d" % (f["k"], 1 - w.rtruth[key][f["id"]]) for f in FACTS_OF[first]))
            put(rp + "2", "\n".join(alt) + "\n")
            run_py("check_judge_reply.py", "--map", w.rmap_path, "--kit", KIT, "--code", r["code"], "--reply", rp + "2", "--json", os.path.join(w.rscores, "%s_2.json" % r["code"]))

    # ---------- writing: validity folders
    w.vtruth = {}
    runs_all = [(m, r) for m in MODELS for r in (1, 2, 3)] + [("chatgpt", r) for r in (4, 5, 6)]
    for (m, run) in runs_all:
        p = {"claude": 0.97, "chatgpt": 0.5, "grok": 0.8, "gemini": 0.9}[m] + (0.15 if run >= 4 else 0)
        rows = {}
        for i in ITEMS:
            valid = int(rng.random() < p)
            reason = ""
            verd = ""
            if not valid:
                if rng.random() < 0.15:
                    reason = "NONE"
                else:
                    reason = "verdict"
                    verd = rng.choice(["E-LEX", "E-LEX;E-ARITY", "E-SYNTAX"])
            chars = "" if reason == "NONE" else str(rng.randint(30, 140))
            rows[i] = dict(cell="P-%s-%d-b%d" % (m, run, ORDER[i]["batch"]), recv="recv99", model=m, run=str(run), batch=str(ORDER[i]["batch"]), item=i, tier=str(ORDER[i]["tier"]),
                           valid=str(valid), checker_ok=str(valid), joined_ok=str(valid), reasons=reason, blocks="1", messages="1", lines="2", problems="0", retracted="0", not_checked="0",
                           verdicts=verd, comment_lines="0", chars=chars, gold_chars=str(ORDER[i]["gold"]), checker_notes="0")
        w.vtruth[(m, run)] = rows
    if p3_special:
        # exactly 60 of 120 valid for grok (holds), exactly 59 of 120 for gemini (does not hold)
        for m, target in (("grok", 60), ("gemini", 59)):
            cells = [(run, i) for run in (1, 2, 3) for i in ITEMS]
            rng.shuffle(cells)
            ok = set(cells[:target])
            for run in (1, 2, 3):
                for i in ITEMS:
                    r = w.vtruth[(m, run)][i]
                    v = (run, i) in ok
                    r["valid"] = r["checker_ok"] = r["joined_ok"] = "1" if v else "0"
                    r["reasons"], r["verdicts"] = ("", "") if v else ("verdict", "E-LEX")
                    if r["chars"] == "":
                        r["chars"] = "50"
    cols = list(next(iter(w.vtruth[("claude", 1)].values())).keys())
    for folder, sel in (("validity_P", [x for x in runs_all if x[1] <= 3]), ("validity_P_high", [] if no_high else [x for x in runs_all if x[1] >= 4])):
        if not sel:
            continue
        d = os.path.join(w.res, folder)
        os.makedirs(d)
        with open(os.path.join(d, "items.csv"), "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(cols)
            for key in sel:
                for i in ITEMS:
                    wr.writerow([w.vtruth[key][i][c] for c in cols])
        per_run = {"%s-%d" % key: dict(items=40, valid=sum(int(w.vtruth[key][i]["valid"]) for i in ITEMS) + (1 if (summary_lie and key == ("claude", 1)) else 0), checker_ok=0, joined_ok=0, batches=[1, 2]) for key in sel}
        put(os.path.join(d, "summary.json"), json.dumps(dict(per_run=per_run)))

    # ---------- English (arm E): real parser on synthetic replies
    w.eng = {}
    if with_english:
        cells = ["recv,arm,model,run,batch,status,run_assumed,file,sha256_16,parts,guide,note"]
        n = 100
        for m in MODELS:
            texts = {1: [], 2: []}
            info = {}
            for i in ITEMS:
                b = ORDER[i]["batch"]
                kind = rng.choice(["text"] * 9 + ["none", "missing", "note"])
                if kind == "missing":
                    info[i] = dict(state="missing", chars=0, words=0, other=0)
                    continue
                if kind == "none":
                    texts[b].append("%s\n\nNONE\n" % i)
                    info[i] = dict(state="none", chars=len("NONE"), words=1, other=0)
                    continue
                lines = ["A to B: " + " ".join("word" for _ in range(rng.randint(2, 9))) for _ in range(rng.randint(1, 3))]
                if kind == "note":
                    lines.append("Note: explaining explaining")
                txt = "\n".join(lines)
                texts[b].append("%s\n\n%s\n" % (i, txt))
                info[i] = dict(state="text", chars=len(txt), words=len(txt.split()), other=1 if kind == "note" else 0)
            w.eng[m] = info
            for b in (1, 2):
                n += 1
                rid = "recv%d" % n
                parsed = pe.parse_parts(["\n".join(texts[b])])
                put(os.path.join(w.res, "parsed_e", rid + ".json"), json.dumps({"parse": parsed}))
                cells.append("%s,E,%s,1,%d,data,no,x.txt,0000000000000000,%s,,\n" % (rid, m, b, rid))
        put(os.path.join(w.res, "cells_E.csv"), cells[0] + "\n" + "".join(cells[1:]))
        # the parser's own view must equal what was intended
        for m in MODELS:
            for i in ITEMS:
                pj = [json.load(open(os.path.join(w.res, "parsed_e", x))) for x in sorted(os.listdir(os.path.join(w.res, "parsed_e")))]
        for r in read_csv(os.path.join(w.res, "cells_E.csv")):
            d = json.load(open(os.path.join(w.res, "parsed_e", r["recv"] + ".json")))["parse"]["items"]
            for i, it in d.items():
                if ORDER[i]["batch"] == int(r["batch"]):
                    exp = w.eng[r["model"]][i]
                    assert (it["state"], it["chars"], it["words"]) == (exp["state"], exp["chars"], exp["words"]), (r["model"], i, it["state"], it["chars"], exp)
                    if exp["state"] == "text":
                        assert (it["other_lines"] > 0) == (exp["other"] > 0), (r["model"], i, it["other_lines"], exp)

    # ---------- round trip
    w.rt = None
    if with_rt:
        w.rt = build_rt(w, rng, code, reader, drop)
    return w


def write_map(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)


def build_rt(w, rng, code, reader, drop):
    root = w.root
    chats_p = {"claude": 1, "gemini": 2, "chatgpt": 3, "grok": 4}
    chats_e = {"grok": 1, "claude": 2, "gemini": 3, "chatgpt": 4}
    src_run = ag.RT_SOURCE_RUN
    t = {}
    t["truth"], t["false"] = {}, {}
    for arm in ("RTP", "RTE"):
        for m in MODELS:
            base = 0.55 if arm == "RTP" else 0.7
            base += 0.04 * MODELS.index(m)
            sc, fl = {}, {}
            for f in FACTS:
                if f["type"] != "C":
                    continue
                sc[f["id"]] = int(rng.random() < base - 0.04 * (f["tier"] - 1))
            for i in ITEMS:
                fl[i] = rng.choice([0, 0, 1, 3])
            t["truth"][(arm, m)], t["false"][(arm, m)] = sc, fl
    t["nonmsg"] = {m: sorted(i for i in ITEMS if w.eng.get(m, {}).get(i, {}).get("state") == "text" and w.eng[m][i]["other"] > 0) for m in MODELS} if w.eng else {m: [] for m in MODELS}
    kp, ke = [], []
    for m in MODELS:
        for b in (1, 2):
            kp.append(dict(chat=chats_p[m], packet=b, file="RT-P_chat%d_packet%d.txt" % (chats_p[m], b), writer=m, writer_run=src_run[m], source_cell="x", source_recv="recv00", none_items=0, sha256_16="0" * 16, item_order=""))
            ke.append(dict(chat=chats_e[m], packet=b, file="RT-E_chat%d_packet%d.txt" % (chats_e[m], b), writer=m, writer_run=1, source_cell="x", source_recv="recv00", none_items=0,
                           items_with_non_message_lines=" ".join(i for i in t["nonmsg"][m] if ORDER[i]["batch"] == b), sha256_16="0" * 16, item_order=""))
    w.key_p, w.key_e = os.path.join(root, "rt_key_PRIVATE.csv"), os.path.join(root, "rt_key_E_PRIVATE.csv")
    write_map(w.key_p, kp)
    write_map(w.key_e, ke)
    rmap, t["codes"] = [], {}
    for arm, chats in (("RTP", chats_p), ("RTE", chats_e)):
        for m in MODELS:
            for b in (1, 2):
                c = code()
                order = list(BATCH_ITEMS[b])
                rng.shuffle(order)
                t["codes"][(arm, m, b)] = c
                rmap.append(dict(code=c, recv="recv%02d" % (200 + len(rmap)), arm=arm, model=reader, run=str(chats[m]), batch=str(b), n_items="20", raw_sha16="0" * 16, sheet_sha16="1" * 16, order=" ".join(order), corrected_items=""))
    w.rtmap = os.path.join(root, "judge_rt", "sheets_map_PRIVATE.csv")
    os.makedirs(os.path.dirname(w.rtmap))
    write_map(w.rtmap, rmap)
    w.rtscores = os.path.join(root, "judge_rt", "scores")
    os.makedirs(w.rtscores)
    inv = {(arm, str(chats[m])): m for arm, chats in (("RTP", chats_p), ("RTE", chats_e)) for m in MODELS}
    for r in rmap:
        if r["code"] in drop:
            continue
        m = inv[(r["arm"], r["run"])]
        lines = []
        for it in r["order"].split():
            sc = {f["k"]: t["truth"][(r["arm"], m)][f["id"]] for f in FACTS_OF[it] if f["type"] == "C"}
            lines.append("%s | %s | false=%d | %s" % (it, " ".join("F%d=%d" % (k, v) for k, v in sorted(sc.items())), t["false"][(r["arm"], m)][it], "missing" if 0 in sc.values() else ""))
        rp = os.path.join(root, "judge_rt", "reply_%s.txt" % r["code"])
        put(rp, "\n".join(lines) + "\n")
        rc, out, err = run_py("check_judge_reply_rt.py", "--map", w.rtmap, "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(w.rtscores, "%s_1.json" % r["code"]))
        assert rc in (0, 1), (out, err)
    return t


def rewrite_model(w, model, fn):
    """Replace the judge files of one model's reading sheets by scores fn(arm, run, fact) -> 0/1 (through the real form checker)."""
    for r in read_csv(w.rmap_path):
        if r["model"] != model:
            continue
        lines = ["%s | %s | false=0 | x" % (it, " ".join("F%d=%d" % (f["k"], fn(r["arm"], int(r["run"]), f)) for f in FACTS_OF[it])) for it in r["order"].split()]
        rp = os.path.join(w.root, "rw_%s.txt" % r["code"])
        put(rp, "\n".join(lines) + "\n")
        run_py("check_judge_reply.py", "--map", w.rmap_path, "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(w.rscores, "%s_1.json" % r["code"]))


def naive_boot(sel, B, tag, f):
    """f(items_drawn: list of item indices) -> statistic; the same draws as aggregate.make_weights."""
    rng = np.random.default_rng([ag.SEED, tag])
    idx = rng.integers(0, len(sel), size=(B, len(sel)))
    return np.array([f([sel[j] for j in row]) for row in idx])


def per_item(truth, ctype=None):
    num, den = [0.0] * 40, [0.0] * 40
    for f in FACTS:
        if ctype and f["type"] != ctype:
            continue
        i = ITEMS.index(f["item"])
        num[i] += truth[f["id"]]
        den[i] += 1
    return num, den


def run_all(w, out, *extra, rt=True):
    args = ["--results", w.res, "--kit", KIT, "--out", out, "--reading-map", w.rmap_path, "--reading-scores", w.rscores, "--boot", str(B), "--judge-note", "Synthetic judge note."]
    if rt and w.rt is not None:
        args += ["--rt-map", w.rtmap, "--rt-scores", w.rtscores, "--rt-key-p", w.key_p, "--rt-key-e", w.key_e]
    return run_ag(*args, *extra)


def main():
    tmp = tempfile.mkdtemp(prefix="agtest_")
    try:
        w = build_world(os.path.join(tmp, "w1"))
        out1 = os.path.join(tmp, "out1")
        rc, so, se = run_all(w, out1)
        check(rc == 0, "full run exits 0: " + se[-400:])
        S = json.load(open(os.path.join(out1, "summary.json")))
        rep = open(os.path.join(out1, "report.md"), encoding="utf-8").read()
        check(S["sections"] == ["reading", "writing", "length", "roundtrip"], "sections: %s" % S["sections"])
        check("PARTIAL" not in rep.split("\n")[2], "report is not marked partial")
        check("Synthetic settings line." in rep, "settings text is in the report")
        check(len(FACTS) == 146 and sum(f["type"] == "C" for f in FACTS) == 127, "kit has 146 facts, 127 C")

        # ---- reading by run and by model
        nC = 127
        for m in MODELS:
            md = S["reading"]["models"][m]
            Rs = [w.rtruth[("R", m, r)] for r in (1, 2, 3)]
            N = w.rtruth[("N", m, 1)]
            cshare = lambda tr: sum(tr[f["id"]] for f in FACTS if f["type"] == "C") / nC
            check(close(md["R"]["C"], np.mean([cshare(t) for t in Rs])), "%s R C mean" % m)
            check(close(md["N"]["C"], cshare(N)), "%s N C" % m)
            check(close(md["R_min_C"], min(cshare(t) for t in Rs)) and close(md["R_max_C"], max(cshare(t) for t in Rs)), "%s R lowest/highest C" % m)
            allsh = lambda tr: sum(tr.values()) / 146
            check(close(md["R"]["all"], np.mean([allsh(t) for t in Rs])), "%s R all mean" % m)
            ssh = lambda tr: sum(tr[f["id"]] for f in FACTS if f["type"] == "S") / 19
            check(close(md["R"]["S"], np.mean([ssh(t) for t in Rs])), "%s R S mean" % m)
            for tier in range(1, 6):
                fs = [f for f in FACTS if f["tier"] == tier]
                check(close(md["R"]["T%d" % tier], np.mean([sum(t[f["id"]] for f in fs) / len(fs) for t in Rs])), "%s R tier %d" % (m, tier))
                fc = [f for f in fs if f["type"] == "C"]
                check(close(md["N"]["T%d_C" % tier], sum(N[f["id"]] for f in fc) / len(fc)), "%s N tier %d C" % (m, tier))
            check(close(md["R"]["false20"], np.mean([sum(w.rfalse[("R", m, r)].values()) / 2 for r in (1, 2, 3)])), "%s R false per 20" % m)
            # prediction 1
            numR = [np.mean([per_item(t, "C")[0][i] for t in Rs]) for i in range(40)]
            denC = per_item(Rs[0], "C")[1]
            numN = per_item(N, "C")[0]
            gap = sum(numR) / sum(denC) - sum(numN) / sum(denC)
            p1 = md["p1"]
            check(close(p1["gap"], gap), "%s gap" % m)
            vals = naive_boot(list(range(40)), B, 0, lambda dr: sum(numR[i] for i in dr) / sum(denC[i] for i in dr) - sum(numN[i] for i in dr) / sum(denC[i] for i in dr))
            lo, hi = np.percentile(vals, [2.5, 97.5])
            check(close(p1["lo"], lo) and close(p1["hi"], hi), "%s gap interval" % m)
            check(p1["holds"] == (round(gap * 1e9) >= 0.2 * 1e9 or gap >= 0.2 - 1e-12) and p1["robust"] == (lo >= 0.2), "%s gap verdicts (%s, %s)" % (m, p1["holds"], gap))
            d_i = [numR[i] / denC[i] - numN[i] / denC[i] for i in range(40)]
            check(close(p1["mean_item_gap"], np.mean(d_i)), "%s mean per-item gap" % m)
            vals2 = naive_boot(list(range(40)), B, 0, lambda dr: sum(d_i[i] for i in dr) / 40)
            lo2, hi2 = np.percentile(vals2, [2.5, 97.5])
            check(close(p1["item_lo"], lo2) and close(p1["item_hi"], hi2), "%s per-item gap interval" % m)
            cs = [cshare(t) for t in Rs]
            check(close(p1["gap_lowest_run"], min(cs) - cshare(N)) and close(p1["gap_highest_run"], max(cs) - cshare(N)), "%s gap with lowest/highest run" % m)
            # prediction 2
            allR = [np.mean([per_item(t)[0][i] for t in Rs]) for i in range(40)]
            denA = per_item(Rs[0])[1]
            tier_items = {t: [i for i in range(40) if ORDER[ITEMS[i]]["tier"] == t] for t in range(1, 6)}
            t1 = sum(allR[i] for i in tier_items[1]) / sum(denA[i] for i in tier_items[1])
            t5 = sum(allR[i] for i in tier_items[5]) / sum(denA[i] for i in tier_items[5])
            p2 = md["p2"]
            check(close(p2["t1"], t1) and close(p2["t5"], t5), "%s tier 1 and 5" % m)
            v1 = naive_boot(tier_items[1], B, 1, lambda dr: sum(allR[i] for i in dr) / sum(denA[i] for i in dr))
            v5 = naive_boot(tier_items[5], B, 5, lambda dr: sum(allR[i] for i in dr) / sum(denA[i] for i in dr))
            lo, hi = np.percentile(v1 - v5, [2.5, 97.5])
            check(close(p2["lo"], lo) and close(p2["hi"], hi), "%s tier difference interval" % m)
            if m == "grok":
                check(p2["tie"] is True and p2["holds"] is False and close(p2["t1"], 1.0) and close(p2["t5"], 1.0), "grok: a tie at 100% is not 'higher'")
            else:
                check(p2["holds"] == (t1 > t5) and p2["tie"] == (abs(t1 - t5) < 1e-12), "%s tier verdict" % m)
        chat = S["reading"]["models"]["chatgpt"]["p1"]
        check(chat["holds"] is False, "chatgpt: a small gap does not hold")
        check(S["reading"]["models"]["claude"]["p1"]["holds"] is True, "claude: a large gap holds")
        # exact boundary: a gap of exactly 20 points holds (checked in the unit section below)
        # per-run rows and items table
        runs_csv = read_csv(os.path.join(out1, "tables", "reading_by_run.csv"))
        check(len(runs_csv) == 16, "16 reading runs in the table, got %d" % len(runs_csv))
        items_csv = read_csv(os.path.join(out1, "tables", "reading_items.csv"))
        check(len(items_csv) == 40, "40 items in the item table")
        r0 = items_csv[0]
        check(close(float(r0["claude_R_C"]), np.mean([per_item(w.rtruth[("R", "claude", r)], "C")[0][0] for r in (1, 2, 3)]) / per_item(w.rtruth[("R", "claude", 1)], "C")[1][0], 1e-6), "item table: claude R share of #01")

        # ---- the scores_long audit file
        sl = read_csv(os.path.join(out1, "scores_long.csv"))
        check(len([r for r in sl if r["domain"] == "reading"]) == 16 * 146, "scores_long: 16 runs x 146 facts")
        check(len([r for r in sl if r["domain"] == "roundtrip"]) == 8 * 127, "scores_long: 8 chats x 127 C facts")
        row = [r for r in sl if r["domain"] == "reading" and r["arm"] == "R" and r["model_or_reader"] == "gemini" and r["run_or_chat"] == "2" and r["fact"] == "#05.F1"][0]
        check(int(row["score"]) == w.rtruth[("R", "gemini", 2)]["#05.F1"], "scores_long: a fact's score")

        # ---- writing
        WR = S["writing"]
        sets = {(s["model"], s["label"]): s for s in WR["sets"]}
        check(set(sets) == {("claude", ""), ("chatgpt", "high setting"), ("chatgpt", "auto mode"), ("grok", ""), ("gemini", "")}, "five writing sets")
        for (m, label), runs in (("claude", ""), (1, 2, 3)), (("chatgpt", "high setting"), (4, 5, 6)), (("chatgpt", "auto mode"), (1, 2, 3)), (("grok", ""), (1, 2, 3)), (("gemini", ""), (1, 2, 3)):
            pass
        for (m, label, runs) in ag.WRITING_SETS:
            s = sets[(m, label)]
            V = [[int(w.vtruth[(m, r)][i]["valid"]) for i in ITEMS] for r in runs]
            check(s["items"] == 40 * len(runs) and s["valid"] == sum(map(sum, V)), "%s %s valid count" % (m, label))
            check(close(s["share"], sum(map(sum, V)) / (40 * len(runs))), "%s %s share" % (m, label))
            check(s["holds"] == (2 * s["valid"] >= s["items"]), "%s %s holds" % (m, label))
            check(close(s["run_min"], min(sum(v) / 40 for v in V)) and close(s["run_max"], max(sum(v) / 40 for v in V)), "%s %s run min/max" % (m, label))
            numv = [sum(v[i] for v in V) for i in range(40)]
            vals = naive_boot(list(range(40)), B, 0, lambda dr: sum(numv[i] for i in dr) / (len(runs) * len(dr)))
            lo, hi = np.percentile(vals, [2.5, 97.5])
            check(close(s["lo"], lo) and close(s["hi"], hi), "%s %s interval" % (m, label))
            for t in range(1, 6):
                cols = [i for i in range(40) if ORDER[ITEMS[i]]["tier"] == t]
                check(s["tiers"][str(t)]["valid"] == sum(v[i] for v in V for i in cols) and s["tiers"][str(t)]["items"] == len(runs) * len(cols), "%s %s tier %d" % (m, label, t))
        check(sets[("grok", "")]["valid"] == 60 and sets[("grok", "")]["holds"] is True, "exactly 60 of 120 valid holds")
        check(sets[("gemini", "")]["valid"] == 59 and sets[("gemini", "")]["holds"] is False, "59 of 120 valid does not hold")
        check(WR["main"]["chatgpt"]["label"] == "high setting" and WR["main"]["chatgpt"]["provisional"] is False, "chatgpt main set is the high set")
        codes = {}
        for key, rows in w.vtruth.items():
            for i, r in rows.items():
                if r["valid"] == "0":
                    for c in [x for x in r["verdicts"].split(";") if x]:
                        codes[c] = codes.get(c, 0) + 1
        check(WR["codes"] == codes, "verdict codes counted over the invalid items: %s vs %s" % (WR["codes"], codes))
        main_runs = [(m, r) for m, (lab, rs) in {"claude": ("", (1, 2, 3)), "chatgpt": ("high", (4, 5, 6)), "grok": ("", (1, 2, 3)), "gemini": ("", (1, 2, 3))}.items() for r in rs]
        hard = [(ITEMS[i], sum(1 - int(w.vtruth[k][ITEMS[i]]["valid"]) for k in main_runs)) for i in range(40)]
        hard = [(a, b) for a, b in hard if b >= 4]
        check([tuple(x) for x in WR["hard"]] == hard, "items invalid in 4 or more main-set runs: %s vs %s" % (WR["hard"], hard))
        check("Items invalid in 4 or more of the 12 runs" in rep, "report names the 12 main-set runs")

        # ---- length
        LN = S["length"]
        for s in LN["silex"]:
            runs = s["runs"]
            vals = [(int(w.vtruth[(s["model"], r)][i]["chars"]), ORDER[i]["gold"]) for r in runs for i in ITEMS if w.vtruth[(s["model"], r)][i]["chars"] != ""]
            check(s["n"] == len(vals) and close(s["median_chars"], float(np.median([a for a, b in vals]))) and close(s["median_gold"], float(np.median([b for a, b in vals]))) and
                  close(s["median_ratio"], float(np.median([a / b for a, b in vals]))), "%s %s SILEX length" % (s["model"], s["label"]))
        for e in LN["english"]:
            m = e["model"]
            info = w.eng[m]
            pres = [i for i in ITEMS if info[i]["state"] == "text"]
            check(e["n"] == len(pres) and close(e["median_chars"], float(np.median([info[i]["chars"] for i in pres]))) and close(e["median_words"], float(np.median([info[i]["words"] for i in pres]))), "%s English length" % m)
            src = ag.RT_SOURCE_RUN[m]
            both = [int(w.vtruth[(m, src)][i]["chars"]) / info[i]["chars"] for i in pres if w.vtruth[(m, src)][i]["chars"] != ""]
            check(e["n_both"] == len(both) and close(e["median_silex_per_english"], float(np.median(both))), "%s SILEX per English character" % m)
            check(e["none_items"] == sum(1 for i in ITEMS if info[i]["state"] == "none") and e["missing_items"] == sum(1 for i in ITEMS if info[i]["state"] == "missing"), "%s none and missing counts" % m)

        # ---- round trip
        RT = S["roundtrip"]
        T = w.rt
        check(RT["reader"] == "grok", "reader recorded")
        inv_all = {}
        for m in MODELS:
            P = T["truth"][("RTP", m)]
            E = T["truth"][("RTE", m)]
            numP, den = per_item(P, "C")
            numE, _ = per_item(E, "C")
            d = RT["writers"][m]
            mk = d["masks"]["all items"]
            check(mk["cred_P"] == sum(numP) and mk["cred_E"] == sum(numE) and mk["n_facts"] == 127, "%s round trip credited" % m)
            check(close(mk["shareP"], sum(numP) / 127) and close(mk["shareE"], sum(numE) / 127) and close(mk["diff"], (sum(numP) - sum(numE)) / 127), "%s round trip shares" % m)
            vals = naive_boot(list(range(40)), B, 0, lambda dr: (sum(numP[i] for i in dr) - sum(numE[i] for i in dr)) / sum(den[i] for i in dr))
            lo, hi = np.percentile(vals, [2.5, 97.5])
            check(close(mk["lo"], lo) and close(mk["hi"], hi), "%s round trip paired interval" % m)
            check(d["own"] == (m == "grok"), "%s own-family flag" % m)
            check(close(d["false20_P"], sum(T["false"][("RTP", m)].values()) / 2) and close(d["false20_E"], sum(T["false"][("RTE", m)].values()) / 2), "%s round trip false per 20" % m)
            for t in range(1, 6):
                cols = [i for i in range(40) if ORDER[ITEMS[i]]["tier"] == t]
                check(close(d["tiers"][str(t)]["shareP"], sum(numP[i] for i in cols) / sum(den[i] for i in cols)) and close(d["tiers"][str(t)]["shareE"], sum(numE[i] for i in cols) / sum(den[i] for i in cols)), "%s round trip tier %d" % (m, t))
            # sensitivity (a): items valid in the source run
            src = ag.RT_SOURCE_RUN[m]
            va = [i for i in range(40) if w.vtruth[(m, src)][ITEMS[i]]["valid"] == "1"]
            ma = d["masks"]["items valid in the SILEX source run"]
            check(ma["n_items"] == len(va) and close(ma["shareP"], sum(numP[i] for i in va) / sum(den[i] for i in va)) and close(ma["shareE"], sum(numE[i] for i in va) / sum(den[i] for i in va)), "%s sensitivity (a)" % m)
            vals = naive_boot(va, B, 0, lambda dr: (sum(numP[i] for i in dr) - sum(numE[i] for i in dr)) / sum(den[i] for i in dr))
            lo, hi = np.percentile(vals, [2.5, 97.5])
            check(close(ma["lo"], lo) and close(ma["hi"], hi), "%s sensitivity (a) interval (resampled inside the kept items)" % m)
            # sensitivity (b): items whose English has message lines only
            keep = [i for i in range(40) if ITEMS[i] not in T["nonmsg"][m]]
            mb = d["masks"]["items whose English has message lines only"]
            check(mb["n_items"] == len(keep) and close(mb["shareP"], sum(numP[i] for i in keep) / sum(den[i] for i in keep)) and close(mb["shareE"], sum(numE[i] for i in keep) / sum(den[i] for i in keep)), "%s sensitivity (b)" % m)
        shares = {m: (RT["writers"][m]["masks"]["all items"]["shareP"], RT["writers"][m]["masks"]["all items"]["shareE"]) for m in MODELS}
        check(close(RT["mean_all"]["P"], np.mean([v[0] for v in shares.values()])) and close(RT["mean_all"]["diff"], np.mean([v[0] - v[1] for v in shares.values()])), "mean over writers")
        wo = [m for m in MODELS if m != "grok"]
        check(RT["mean_without_own"]["n"] == 3 and close(RT["mean_without_own"]["E"], np.mean([shares[m][1] for m in wo])), "mean over writers without the reader's family")
        check(any(len(read_csv(os.path.join(out1, "tables", "roundtrip.csv"))) > 8 for _ in [0]), "round-trip table has a row per mask")

        # ---- report sanity
        check("| 1 | Claude |" in rep and "| 2 | Grok |" in rep and "no (tie)" in rep, "predictions table in the report")
        check("Grok*" in rep, "own-family writer is marked in the report")

        # ---- determinism and no writes outside the output folder
        out2 = os.path.join(tmp, "out2")
        rc, so, se = run_all(w, out2)
        check(rc == 0, "second run exits 0")
        same = True
        for dp, _, fs in os.walk(out1):
            for fn in fs:
                if fn == "aggregate_info.json":
                    continue
                p1 = os.path.join(dp, fn)
                p2 = os.path.join(out2, os.path.relpath(p1, out1))
                if not os.path.exists(p2) or open(p1, "rb").read() != open(p2, "rb").read():
                    same = False
                    print("  differs:", os.path.relpath(p1, out1))
        check(same, "two runs give byte-identical files (except aggregate_info.json)")
        info = json.load(open(os.path.join(out1, "aggregate_info.json")))
        check(info["seed"] == ag.SEED and info["boot"] == B and info["tool_sha16"] == ag.sha16(os.path.join(HERE, "aggregate.py")) and info["plan_sha16"] == ag.sha16(os.path.join(w.res, "ANALYSIS_PLAN.md")), "info file holds seed, boot, hashes")
        rc, so, se = run_all(w, out1)
        check(rc != 0 and "not empty" in se, "a non-empty output folder is refused")

        # ---- no ChatGPT high set yet: the auto set is the main one, marked provisional
        w2 = build_world(os.path.join(tmp, "w2"), no_high=True, with_rt=False, with_english=False)
        o3 = os.path.join(tmp, "out3")
        rc, so, se = run_all(w2, o3)
        check(rc == 0, "run without the high set: " + se[-300:])
        S3 = json.load(open(os.path.join(o3, "summary.json")))
        check(S3["writing"]["main"]["chatgpt"]["label"] == "auto mode" and S3["writing"]["main"]["chatgpt"]["provisional"] is True, "auto set is the provisional main set")
        check("provisional" in open(os.path.join(o3, "report.md"), encoding="utf-8").read(), "report says provisional")
        check("roundtrip" not in S3["sections"] and "length" in S3["sections"], "sections without round trip")

        # ---- an incomplete sheet
        first = None
        w3 = build_world(os.path.join(tmp, "w3"), drop=set(), with_rt=False, with_english=False)
        code_drop = w3.rcodes[("R", "gemini", 3, 2)]
        os.remove(os.path.join(w3.rscores, "%s_1.json" % code_drop))
        rc, so, se = run_all(w3, os.path.join(tmp, "o4"))
        check(rc != 0 and "incomplete" in se and code_drop in se, "an unjudged sheet stops the run: " + se[-200:])
        check(not os.path.exists(os.path.join(tmp, "o4", "report.md")), "nothing is written when the run stops")
        rc, so, se = run_all(w3, os.path.join(tmp, "o5"), "--partial")
        check(rc == 0, "--partial runs: " + se[-200:])
        S5 = json.load(open(os.path.join(tmp, "o5", "summary.json")))
        rep5 = open(os.path.join(tmp, "o5", "report.md"), encoding="utf-8").read()
        check(S5["partial"] is True and "PARTIAL RUN" in rep5, "partial run is marked")
        check(S5["reading"]["models"]["gemini"]["R_runs"] == [1, 2] and "run R gemini 3 is not complete" in rep5, "the incomplete run is left out and listed")
        Rs = [w3.rtruth[("R", "gemini", r)] for r in (1, 2)]
        check(close(S5["reading"]["models"]["gemini"]["R"]["C"], np.mean([sum(t[f["id"]] for f in FACTS if f["type"] == "C") / 127 for t in Rs])), "mean of the two complete runs")
        # a sheet judged on only part of its items is incomplete too
        w4 = build_world(os.path.join(tmp, "w4"), with_rt=False, with_english=False, cut=(None, 0))
        w4b = build_world(os.path.join(tmp, "w4b"), with_rt=False, with_english=False)
        cc = w4b.rcodes[("N", "claude", 1, 1)]
        j = json.load(open(os.path.join(w4b.rscores, "%s_1.json" % cc)))
        j["items"] = dict(list(j["items"].items())[:10])
        json.dump(j, open(os.path.join(w4b.rscores, "%s_1.json" % cc), "w"))
        rc, so, se = run_all(w4b, os.path.join(tmp, "o6"))
        check(rc != 0 and "incomplete" in se, "a sheet with 10 of 20 items scored stops the run")
        rc, so, se = run_all(w4b, os.path.join(tmp, "o7"), "--partial")
        S7 = json.load(open(os.path.join(tmp, "o7", "summary.json")))
        check(rc == 0 and "p1" not in S7["reading"]["models"]["claude"] and S7["reading"]["models"]["claude"]["N_runs"] == [], "without a complete N run there is no R minus N")

        # ---- a second, different scoring of an item: the first stays and the difference is listed
        w5 = build_world(os.path.join(tmp, "w5"), with_rt=False, with_english=False, dup_conflict=True)
        rc, so, se = run_all(w5, os.path.join(tmp, "o8"))
        check(rc == 0, "duplicate scoring run: " + se[-200:])
        rep8 = open(os.path.join(tmp, "o8", "report.md"), encoding="utf-8").read()
        check("scored again" in rep8 and "the first scoring" in rep8, "differing second scoring is listed")
        S8 = json.load(open(os.path.join(tmp, "o8", "summary.json")))
        S1 = json.load(open(os.path.join(out1, "summary.json")))
        check(S8["reading"]["models"]["claude"]["R"]["C"] == S1["reading"]["models"]["claude"]["R"]["C"], "the first scoring was kept")

        # ---- inconsistent inputs are refused
        w6 = build_world(os.path.join(tmp, "w6"), with_rt=False, with_english=False, summary_lie=True)
        rc, so, se = run_all(w6, os.path.join(tmp, "o9"))
        check(rc != 0 and "summary.json says" in se, "validity summary.json that disagrees with items.csv is refused: " + se[-200:])
        w7 = build_world(os.path.join(tmp, "w7"), with_rt=False, with_english=False)
        cc = w7.rcodes[("R", "grok", 2, 1)]
        j = json.load(open(os.path.join(w7.rscores, "%s_1.json" % cc)))
        it = next(iter(j["items"]))
        j["items"][it]["scores"]["F9"] = 1
        json.dump(j, open(os.path.join(w7.rscores, "%s_1.json" % cc), "w"))
        rc, so, se = run_all(w7, os.path.join(tmp, "o10"))
        check(rc != 0 and "needs" in se, "a score on a fact that the sheet does not have is refused: " + se[-200:])
        w8 = build_world(os.path.join(tmp, "w8"), with_rt=True, with_english=False)
        cc = w8.rt["codes"][("RTP", "claude", 1)]
        j = json.load(open(os.path.join(w8.rtscores, "%s_1.json" % cc)))
        it = next(iter(j["items"]))
        s_fact = [f for f in FACTS if f["item"] == it and f["type"] == "S"]
        if s_fact:
            j["items"][it]["scores"]["F%d" % s_fact[0]["k"]] = 1
        else:
            j["items"][it]["scores"]["F99"] = 1
        json.dump(j, open(os.path.join(w8.rtscores, "%s_1.json" % cc), "w"))
        rc, so, se = run_all(w8, os.path.join(tmp, "o11"))
        check(rc != 0 and "needs" in se, "an S-fact score on a round-trip sheet is refused: " + se[-200:])
        w9 = build_world(os.path.join(tmp, "w9"), with_rt=True, with_english=False, reader="grok")
        mp = read_csv(w9.rtmap)
        mp[0]["model"] = "claude"
        write_map(w9.rtmap, mp)
        rc, so, se = run_all(w9, os.path.join(tmp, "o12"))
        check(rc != 0 and "more than one reader" in se, "two reader models in the round trip are refused: " + se[-200:])
        w10 = build_world(os.path.join(tmp, "w10"), with_rt=True, with_english=False)
        kp = read_csv(w10.key_p)
        for r in kp:
            if r["writer"] == "chatgpt":
                r["writer_run"] = "1"
        write_map(w10.key_p, kp)
        rc, so, se = run_all(w10, os.path.join(tmp, "o13"))
        check(rc != 0 and "plan says run" in se, "a round-trip key that reads another run than the plan is refused: " + se[-200:])

        # ---- hand-computable fixed points (no randomness)
        w11 = build_world(os.path.join(tmp, "w11"), with_rt=False, with_english=False)
        # rewrite the reading judge files: every R fact 1, every N fact 0 for claude; everything 1 for all arms of gemini
        for r in read_csv(w11.rmap_path):
            if r["model"] not in ("claude", "gemini"):
                continue
            val = 1 if (r["arm"] == "R" or r["model"] == "gemini") else 0
            lines = ["%s | %s | false=0 | %s" % (it, " ".join("F%d=%d" % (f["k"], val) for f in FACTS_OF[it]), "" if val else "no") for it in r["order"].split()]
            rp = os.path.join(w11.root, "fixed_%s.txt" % r["code"])
            put(rp, "\n".join(lines) + "\n")
            run_py("check_judge_reply.py", "--map", w11.rmap_path, "--kit", KIT, "--code", r["code"], "--reply", rp, "--json", os.path.join(w11.rscores, "%s_1.json" % r["code"]))
        rc, so, se = run_all(w11, os.path.join(tmp, "o14"))
        check(rc == 0, "fixed-point run: " + se[-200:])
        S11 = json.load(open(os.path.join(tmp, "o14", "summary.json")))["reading"]["models"]
        c1 = S11["claude"]["p1"]
        check(c1["gap"] == 1.0 and c1["lo"] == 1.0 and c1["hi"] == 1.0 and c1["holds"] and c1["robust"] and c1["mean_item_gap"] == 1.0, "R all 1, N all 0: gap exactly 100 points with a zero-width interval")
        g1 = S11["gemini"]["p1"]
        check(g1["gap"] == 0.0 and g1["lo"] == 0.0 and g1["hi"] == 0.0 and not g1["holds"] and S11["gemini"]["p2"]["tie"], "everything 1: gap 0 and tier tie")
        check(S11["claude"]["R"]["false20"] == 0.0, "no false statements")

        # ---- units
        W = ag.make_weights(np.random.default_rng([1, 2]), np.array([3, 5, 9]), 50)
        check(W.shape == (50, 40) and (W.sum(axis=1) == 3).all() and W[:, [0, 1, 2]].sum() == 0, "make_weights: 3 draws per row, only from the allowed items")
        check(ag.pct(0.123456) == "12.3" and ag.spct(-0.0004) == "+0.0" and ag.spct(0.2) == "+20.0" and ag.pct(float("nan")) == "n/a", "number formats")
        # ---- the 20-point rule at the boundary: with 127 C facts, 3 R runs and 1 N run a gap is a multiple of 1/381; 76/381 = 19.95 points fails, 77/381 = 20.21 holds
        cfacts = [f["id"] for f in FACTS if f["type"] == "C"]
        for k, expect in ((76, False), (77, True)):
            wb = build_world(os.path.join(tmp, "wb%d" % k), with_rt=False, with_english=False)
            credited = set(cfacts[:k])
            rewrite_model(wb, "claude", lambda arm, run, f: 1 if (arm == "R" and run == 1 and f["id"] in credited) else 0)
            rc, so, se = run_all(wb, os.path.join(tmp, "ob%d" % k))
            check(rc == 0, "boundary run %d: %s" % (k, se[-200:]))
            pb = json.load(open(os.path.join(tmp, "ob%d" % k, "summary.json")))["reading"]["models"]["claude"]["p1"]
            check(close(pb["gap"], k / 381) and pb["holds"] is expect, "gap %d/381 = %.4f: holds is %s (expected %s)" % (k, k / 381, pb["holds"], expect))
        check("Synthetic judge note." in rep and "Notes that go with every table" in rep, "report carries the judge note and the notes")
        check(hashlib.sha256(open(os.path.join(HERE, "aggregate.py"), "rb").read()).hexdigest()[:16] in rep and "The SILEX the reader saw was written in run: Claude 1, ChatGPT 4, Grok 1, Gemini 1" in rep, "report carries the tool hash and the source runs")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAILS:
        print("%d FAILED, %d passed" % (len(FAILS), OK[0]))
        sys.exit(1)
    print("ALL PASS (%d checks)" % OK[0])


if __name__ == "__main__":
    main()
