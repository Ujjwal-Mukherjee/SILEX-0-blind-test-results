#!/usr/bin/env python3
"""Phrase judge of Test F (find the fault), README_F.txt, "Secondary: the phrase".

README_F.txt (frozen 2026-11-13 23:22 IST) says: a fresh blind judge scores each faulty item's phrase 1 or 0 against the key (judge_fault.txt, same blind-sheet
method as the reading test), reported for all faulty items and for those where the place was right. This file is the tool for that. It was written on 2026-11-14,
after all Test F replies were filed and before any Test F score or judge reply exists; the frozen kit files are not changed. A judge is started only when the user says yes.

Three commands.

  build    one blind entry for every ANSWER THAT NAMES A FAULT ON A FAULTY ITEM (an answer other than "none"; right place or not; the reader's place and phrase, the phrase
           cut after its 12th word as README_F.txt fixes). Clean items and "none" answers have nothing to judge and get no entry. Each entry shows the item code, the key's kind of
           fault and one-sentence description (key_F_PRIVATE.csv columns kind and description; never the checker's text and never the true place column), the reader's place and phrase.
           The frozen judge prompt (KIT/judge_fault.txt) stands at the top of every sheet, verbatim. No model, arm, run, chat number or batch is on a sheet.
           Entries are shuffled with a seed and spread over sheets of at most 20 entries, one entry per item code on a sheet (the judge's reply line is "F07 | 1 | ...").
           Output OUT/sheets/sheet_CODE.txt, OUT/sheets_map_PRIVATE.csv (code, n_items, order, sheet_sha16), OUT/entries_PRIVATE.csv (what each entry is), OUT/build_info_PRIVATE.json.
  collect  copy each judge reply file byte for byte (read-only) into REPLIES, check its FORM, write SCORES/CODE.json. Prints the sheet code, items usable and a status
           (clean, notes, redo) and the problems; never a score. Same rules as collect_judge_replies.py: an unchanged collected reply is skipped, a different one is not overwritten.
  tables   after score_f.py rules and a complete set of judge replies: adds up the judge's 1/0 per run, model and arm, for all faulty items (an item answered "none" or
           not answered counts 0) and for the items where the place was right; also where the place was wrong, and by verdict (for description). Writes OUT/phrase_f_items.csv
           (WITH the key: private until the last run is scored), OUT/phrase_f_tables.md and OUT/phrase_f_summary.json.

FORM RULES of a judge reply (fixed here, before any reply exists): one line per entry of the sheet, "F07 | 1" or "F07 | 0 | reason" (a "|" before the reason). Every item code of the sheet exactly once.
Leading "-", "*", ">" or backticks are stripped (noted). Other lines (a heading, a "SHEET XXXX" echo, remarks) are ignored (noted). A line that starts with an item code but does not read
"Fnn | 0 or 1 ..." is a problem; so is a missing item, a doubled item, an item that is not on the sheet. A 0 without a reason, a reason over 12 words, or a reason on a 1 is a note only.
An item with a problem is not used and the sheet's status is "redo": a redo is made by hand with a fresh judge and settled with the user; this tool does not fill in anything.

Usage:
  python3 -I phrase_judge_f.py build   --results RES --kit KITF --seed N --out OUT [--per-sheet 20] [--avoid MAP.csv ...] [--include-review]
  python3 -I phrase_judge_f.py collect --outbox WORK/outbox --map OUT/sheets_map_PRIVATE.csv --replies REPLIES --scores SCORES [--codes AB12,CD34]
  python3 -I phrase_judge_f.py tables  --results RES --kit KITF --build OUT --scores SCORES --out TABLES [--include-review] [--partial]
Exit code: 0 done, 1 a problem with the input or a sheet needing a redo (nothing is guessed or filled in), 2 usage.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import random
import re
import stat
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_f as sf  # noqa: E402   (the frozen scorer's own loaders, so that the same answers are read)

ALPHABET = "ABCDEFGHJKMNPQRTUVWXYZ23456789"  # the alphabet of the reading sheets (no 0/O, 1/I/L, S/5 mix-ups)
MAX_PER_SHEET = 20
FIELDS = ["faulty", "named", "judged", "unjudged", "credited", "found", "found_judged", "found_credited", "wrong_judged", "wrong_credited"]
MODEL_WORDS = re.compile(r"(?i)\b(claude|chatgpt|gpt|openai|gemini|grok|anthropic|sonnet|opus|haiku|astra|xai|google)\b")
LINE = re.compile(r"^(F\d{2})\s*\|\s*([01])\s*(?:\|\s*(.*))?$")
WRAP = re.compile(r"^[\s>*`_\-•]+")
ITEM_AT_START = re.compile(r"^F\d{2}\b")


def die(msg, code=1):
    print("phrase_judge_f.py: " + msg, file=sys.stderr)
    sys.exit(code)


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


# ---------------------------------------------------------------- build

def gather(results, kit, include_review):
    """-> (key, runs, entries). One entry per answer that names a fault on a faulty item, in a fixed order."""
    key = sf.load_key(kit)
    runs, _applied = sf.load_runs(results, include_review)
    if not runs:
        die("no data rows in cells_F.csv")
    entries = []
    for k in sorted(runs):
        arm, model, run = k
        for iid in sorted(runs[k]["answers"]):
            kk = key.get(iid)
            ans = runs[k]["answers"][iid]
            if kk is None or not kk["faulty"] or ans["place"] == "none":
                continue
            batch = int(kk["batch"])
            recv = runs[k]["batches"].get(batch)
            if recv is None:
                continue
            place = ans["place"]
            shown = place if place else ((ans.get("place_raw") or "").strip() or "(no readable place)")
            entries.append(dict(recv=recv, arm=arm, model=model, run=run, batch=batch, item=iid, verdict=kk["verdict"], kind=kk["kind"].strip(),
                                description=kk["description"].strip(), place_shown=shown, place_read=("" if place is None else place),
                                phrase=sf.cut_words(ans["phrase"]), words_original=len(ans["phrase"].split())))
    return key, runs, entries


def assign(entries, per_sheet, rng):
    """Spread the entries over sheets of at most per_sheet entries with no item code twice on a sheet. Deterministic for a given rng state."""
    by_item = defaultdict(list)
    for e in entries:
        by_item[e["item"]].append(e)
    k = max(math.ceil(len(entries) / per_sheet), max(len(v) for v in by_item.values()))
    while True:
        sheets = [[] for _ in range(k)]
        ok = True
        groups = sorted(by_item.items(), key=lambda kv: (-len(kv[1]), rng.random()))
        for item, ents in groups:
            ents = ents[:]
            rng.shuffle(ents)
            for e in ents:
                cands = [s for s in sheets if len(s) < per_sheet and all(x["item"] != item for x in s)]
                if not cands:
                    ok = False
                    break
                m = min(len(s) for s in cands)
                rng.choice([s for s in cands if len(s) == m]).append(e)
            if not ok:
                break
        if ok:
            return sheets
        k += 1


def sheet_text(prompt, code, ents):
    lines = [prompt.rstrip("\n"), "", "SHEET " + code, ""]
    for e in ents:
        lines += [e["item"],
                  "Key, kind of fault: " + e["kind"],
                  "Key, planted fault: " + e["description"],
                  "Reader's place: " + e["place_shown"],
                  "Reader's phrase: " + (e["phrase"] if e["phrase"] else "(empty)"),
                  ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def cmd_build(a):
    if os.path.exists(a.out) and os.listdir(a.out):
        die("OUT must not exist or must be empty")
    if a.per_sheet < 1 or a.per_sheet > MAX_PER_SHEET:
        die("--per-sheet must be 1 to %d" % MAX_PER_SHEET, 2)
    pp = os.path.join(a.kit, "judge_fault.txt")
    praw = open(pp, "rb").read()
    prompt = praw.decode("utf-8")
    key, runs, entries = gather(a.results, a.kit, a.include_review)
    if not entries:
        die("no answer names a fault on a faulty item: nothing to judge")
    avoid = set()
    for m in a.avoid or []:
        for r in csv.DictReader(open(m, newline="", encoding="utf-8")):
            avoid.add(r["code"])
    rng = random.Random(a.seed)
    sheets = assign(entries, a.per_sheet, rng)
    codes, used = [], set(avoid)
    while len(codes) < len(sheets):
        c = "".join(rng.choice(ALPHABET) for _ in range(4))
        if c not in used:
            used.add(c)
            codes.append(c)
    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    map_rows, ent_rows, named = [], [], 0
    for code, ents in zip(codes, sheets):
        ents = ents[:]
        rng.shuffle(ents)
        text = sheet_text(prompt, code, ents)
        with open(os.path.join(a.out, "sheets", "sheet_%s.txt" % code), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        map_rows.append(dict(code=code, n_items=len(ents), order=" ".join(e["item"] for e in ents), sheet_sha16=sha16(text.encode("utf-8"))))
        for pos, e in enumerate(ents, 1):
            named += bool(MODEL_WORDS.search(e["phrase"]))
            ent_rows.append(dict(code=code, pos=pos, item=e["item"], recv=e["recv"], arm=e["arm"], model=e["model"], run=e["run"], batch=e["batch"],
                                 verdict=e["verdict"], kind=e["kind"], place_shown=e["place_shown"], place_read=e["place_read"], phrase=e["phrase"],
                                 words_original=e["words_original"]))
    map_rows.sort(key=lambda r: r["code"])
    with open(os.path.join(a.out, "sheets_map_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "n_items", "order", "sheet_sha16"])
        w.writeheader()
        w.writerows(map_rows)
    with open(os.path.join(a.out, "entries_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ent_rows[0].keys()))
        w.writeheader()
        w.writerows(ent_rows)
    info = dict(program_sha256_16=sha16(open(__file__, "rb").read()), judge_prompt_sha256=hashlib.sha256(praw).hexdigest(), seed=a.seed, per_sheet=a.per_sheet,
                entries=len(entries), sheets=len(sheets), max_entries_on_a_sheet=max(len(s) for s in sheets), phrases_naming_a_model=named,
                phrases_cut_after_12_words=sum(1 for e in entries if e["words_original"] > 12), empty_phrases=sum(1 for e in entries if not e["phrase"]),
                faulty_answers_named_by_run={"%s-%s-%s" % k: sum(1 for e in entries if (e["arm"], e["model"], e["run"]) == k) for k in sorted(runs)},
                built=datetime.datetime.now().isoformat(timespec="seconds"))
    json.dump(info, open(os.path.join(a.out, "build_info_PRIVATE.json"), "w", encoding="utf-8"), indent=1)
    print("built %d sheets with %d entries (at most %d on a sheet, no item code twice on a sheet; seed %d); phrases cut after 12 words: %d; empty phrases: %d; "
          "phrases that name a model: %d" % (len(sheets), len(entries), info["max_entries_on_a_sheet"], a.seed, info["phrases_cut_after_12_words"], info["empty_phrases"], named))


# ---------------------------------------------------------------- collect

def check_reply(text, exp_items):
    """-> (got {item: {score, reason}}, problems [(item, msg)], warnings [msg], redo [items])."""
    problems, warnings, got, seen = [], [], {}, {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        stripped = WRAP.sub("", line).rstrip("`* ") if not ITEM_AT_START.match(line) else line.rstrip("`* ")
        if not ITEM_AT_START.match(stripped):
            warnings.append("ignored text: %r" % line[:70])
            continue
        if stripped != line.rstrip():
            warnings.append("decorated line, wrapper stripped: %r" % line[:40])
        item = stripped[:3]
        seen[item] = seen.get(item, 0) + 1
        m = LINE.match(stripped)
        if not m:
            problems.append((item, "malformed line: " + stripped[:70]))
            continue
        if seen[item] > 1:
            problems.append((item, "item appears more than once"))
            continue
        if item not in exp_items:
            problems.append((item, "item is not on this sheet"))
            continue
        score = int(m.group(2))
        reason = (m.group(3) or "").strip().rstrip("|").strip()
        if score == 0 and not reason:
            warnings.append("%s: a 0 without a reason" % item)
        if score == 1 and reason:
            warnings.append("%s: a reason on a 1" % item)
        if len(reason.split()) > 12:
            warnings.append("%s: reason has %d words (limit 12)" % (item, len(reason.split())))
        got[item] = dict(score=score, reason=reason)
    for it in sorted(exp_items):
        if it not in seen:
            problems.append((it, "no line for this item"))
    bad = {it for it, _ in problems}
    for it in list(got):
        if it in bad:
            del got[it]
    return got, problems, warnings, sorted(bad)


def cmd_collect(a):
    rows = list(csv.DictReader(open(a.map, newline="", encoding="utf-8")))
    if a.codes:
        want = set(a.codes.split(","))
        rows = [r for r in rows if r["code"] in want]
        if len(rows) != len(want):
            die("some --codes are not in the map", 2)
    os.makedirs(a.replies, exist_ok=True)
    os.makedirs(a.scores, exist_ok=True)
    log_path = os.path.join(a.replies, "collected_log.csv")
    new_log = not os.path.exists(log_path)
    logf = open(log_path, "a", newline="", encoding="utf-8")
    lw = csv.writer(logf)
    if new_log:
        lw.writerow(["code", "sha256", "bytes", "collected", "status", "items_usable"])
    bad = 0
    for r in sorted(rows, key=lambda x: x["code"]):
        code = r["code"]
        src = os.path.join(a.outbox, "reply_%s.txt" % code)
        dst = os.path.join(a.replies, "reply_%s.txt" % code)
        if not os.path.exists(src):
            print("%s: MISSING (no reply file in the outbox)" % code)
            bad += 1
            continue
        data = open(src, "rb").read()
        if os.path.exists(dst):
            if open(dst, "rb").read() == data:
                print("%s: already collected, unchanged" % code)
            else:
                print("%s: the outbox file differs from the collected reply; NOT collected (a second reply is a redo, handled by hand)" % code)
                bad += 1
            continue
        order = set(r["order"].split())
        got, problems, warnings, redo = check_reply(data.decode("utf-8", errors="replace"), order)
        status = "redo" if redo else ("notes" if warnings else "clean")
        with open(dst, "wb") as f:
            f.write(data)
        os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        json.dump(dict(code=code, status=status, redo_items=redo, problems=["%s: %s" % (i, m) for i, m in problems], warnings=warnings, items=got),
                  open(os.path.join(a.scores, code + ".json"), "w"), indent=1)
        lw.writerow([code, hashlib.sha256(data).hexdigest(), len(data), datetime.datetime.now().isoformat(timespec="seconds"), status, len(got)])
        logf.flush()
        print("%s: %d of %d items usable; status: %s" % (code, len(got), len(order), status))
        for it, msg in problems:
            print("  PROBLEM %s: %s" % (it, msg))
        if redo:
            print("  ask the judge again for: " + " ".join(redo))
            bad += 1
    logf.close()
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- tables

def pct(k, n):
    return "%.0f%%" % (100.0 * k / n) if n else "-"


def cmd_tables(a):
    if os.path.exists(a.out) and os.listdir(a.out):
        die("OUT must not exist or must be empty")
    key = sf.load_key(a.kit)
    runs, _applied = sf.load_runs(a.results, a.include_review)
    if not runs:
        die("no data rows in cells_F.csv")
    ents = list(csv.DictReader(open(os.path.join(a.build, "entries_PRIVATE.csv"), newline="", encoding="utf-8")))
    maprows = list(csv.DictReader(open(os.path.join(a.build, "sheets_map_PRIVATE.csv"), newline="", encoding="utf-8")))
    judged, incomplete, notes = {}, [], []
    for r in maprows:
        code = r["code"]
        p = os.path.join(a.scores, code + ".json")
        if not os.path.exists(p):
            incomplete.append("%s: no judge file" % code)
            continue
        d = json.load(open(p, encoding="utf-8"))
        exp = set(r["order"].split())
        if d["status"] == "redo" or set(d["items"]) != exp:
            incomplete.append("%s: status %s, %d of %d items usable" % (code, d["status"], len(d["items"]), len(exp)))
            continue
        for it, v in d["items"].items():
            judged[(code, it)] = v
    if incomplete and not a.partial:
        die("incomplete judging, nothing is tabulated (use --partial to see a partial table):\n  " + "\n  ".join(incomplete))
    by_recv_item = {}
    for e in ents:
        v = judged.get((e["code"], e["item"]))
        by_recv_item[(e["recv"], e["item"])] = (e, v)
    out_rows, per_run, verdict_rows = [], {}, []
    for k in sorted(runs):
        t, rows, _missing = sf.score_run(key, runs[k])
        agg = defaultdict(int)
        agg["faulty"] = t["faulty"]
        for r in rows:
            if not r["detected"]:
                continue
            recv = runs[k]["batches"][int(r["batch"])]
            e, v = by_recv_item.get((recv, r["id"]), (None, None))
            if e is None:
                die("internal: no entry for %s %s" % (recv, r["id"]))
            agg["named"] += 1
            if v is None:
                agg["unjudged"] += 1
            else:
                agg["judged"] += 1
                agg["credited"] += v["score"]
                if r["found"]:
                    agg["found_judged"] += 1
                    agg["found_credited"] += v["score"]
                else:
                    agg["wrong_judged"] += 1
                    agg["wrong_credited"] += v["score"]
                verdict_rows.append((k[0], r["verdict"], v["score"]))
            out_rows.append(dict(arm=k[0], model=k[1], run=k[2], recv=recv, id=r["id"], verdict=r["verdict"], kind=e["kind"], found=r["found"],
                                 place=e["place_shown"], phrase=e["phrase"], code=e["code"], judge_score=("" if v is None else v["score"]),
                                 judge_reason=("" if v is None else v["reason"])))
        agg["found"] = t["found"]
        per_run[k] = {f: agg.get(f, 0) for f in FIELDS}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "phrase_f_items.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arm", "model", "run", "recv", "id", "verdict", "kind", "found", "place", "phrase", "code", "judge_score", "judge_reason"])
        w.writeheader()
        w.writerows(out_rows)

    def tot(keys):
        t = defaultdict(int)
        for k in keys:
            for f, v in per_run[k].items():
                t[f] += v
        return t

    L = []
    L.append("# Test F, secondary result: the phrase (README_F.txt)\n")
    L.append("A blind judge scored 1 or 0 whether the reader's phrase names the key's fault (judge_fault.txt). Only answers that name a fault on a faulty item have a phrase to judge; "
             "an item answered \"none\" or not answered counts 0 in the 'all faulty items' column. The place is scored by the program (score_f.py), not by the judge.\n")
    if incomplete:
        L.append("**PARTIAL: these sheets are not complete and their entries are left out:** " + "; ".join(incomplete) + "\n")
    L.append("## Per run\n")
    L.append("| arm | model | run | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in sorted(per_run):
        t = per_run[k]
        L.append("| %s | %s | %d | %d | %d | %d/%d (%s) | %d/%d (%s) | %d | %d/%d (%s) | %d/%d (%s) |" % (
            k[0], k[1], k[2], t["faulty"], t["named"], t["credited"], t["judged"], pct(t["credited"], t["judged"]), t["credited"], t["faulty"], pct(t["credited"], t["faulty"]),
            t["found"], t["found_credited"], t["found_judged"], pct(t["found_credited"], t["found_judged"]), t["wrong_credited"], t["wrong_judged"],
            pct(t["wrong_credited"], t["wrong_judged"])))
    L.append("\n## By arm and model (runs added up)\n")
    L.append("| arm | model | runs | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for k in per_run:
        groups[(k[0], k[1])].append(k)
    for g in sorted(groups):
        t = tot(groups[g])
        L.append("| %s | %s | %d | %d | %d | %d/%d (%s) | %d/%d (%s) | %d | %d/%d (%s) | %d/%d (%s) |" % (
            g[0], g[1], len(groups[g]), t["faulty"], t["named"], t["credited"], t["judged"], pct(t["credited"], t["judged"]), t["credited"], t["faulty"],
            pct(t["credited"], t["faulty"]), t["found"], t["found_credited"], t["found_judged"], pct(t["found_credited"], t["found_judged"]),
            t["wrong_credited"], t["wrong_judged"], pct(t["wrong_credited"], t["wrong_judged"])))
    L.append("\n## By arm (all models)\n")
    L.append("| arm | runs | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for arm in sorted({k[0] for k in per_run}):
        ks = [k for k in per_run if k[0] == arm]
        t = tot(ks)
        L.append("| %s | %d | %d | %d | %d/%d (%s) | %d/%d (%s) | %d | %d/%d (%s) | %d/%d (%s) |" % (
            arm, len(ks), t["faulty"], t["named"], t["credited"], t["judged"], pct(t["credited"], t["judged"]), t["credited"], t["faulty"], pct(t["credited"], t["faulty"]),
            t["found"], t["found_credited"], t["found_judged"], pct(t["found_credited"], t["found_judged"]), t["wrong_credited"], t["wrong_judged"],
            pct(t["wrong_credited"], t["wrong_judged"])))
    L.append("\n## By verdict (phrase credited / phrase judged; two items per verdict per run, so for description only)\n")
    arms = sorted({k[0] for k in per_run})
    L.append("| verdict | " + " | ".join(arms) + " |")
    L.append("|---|" + "---|" * len(arms))
    for v in sorted({x[1] for x in verdict_rows}):
        cells = []
        for arm in arms:
            sc = [s for (ar, vd, s) in verdict_rows if ar == arm and vd == v]
            cells.append("%d/%d" % (sum(sc), len(sc)))
        L.append("| %s | %s |" % (v, " | ".join(cells)))
    open(os.path.join(a.out, "phrase_f_tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(dict(program_sha256_16=sha16(open(__file__, "rb").read()), partial=bool(incomplete),
                   per_run={"%s-%s-%d" % k: v for k, v in per_run.items()}), open(os.path.join(a.out, "phrase_f_summary.json"), "w", encoding="utf-8"), indent=1)
    print("tables for %d runs written to %s%s" % (len(per_run), a.out, " (PARTIAL)" if incomplete else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--results", required=True)
    b.add_argument("--kit", required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--per-sheet", type=int, default=MAX_PER_SHEET)
    b.add_argument("--avoid", nargs="*")
    b.add_argument("--include-review", action="store_true")
    c = sub.add_parser("collect")
    c.add_argument("--outbox", required=True)
    c.add_argument("--map", required=True)
    c.add_argument("--replies", required=True)
    c.add_argument("--scores", required=True)
    c.add_argument("--codes")
    t = sub.add_parser("tables")
    t.add_argument("--results", required=True)
    t.add_argument("--kit", required=True)
    t.add_argument("--build", required=True)
    t.add_argument("--scores", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--include-review", action="store_true")
    t.add_argument("--partial", action="store_true")
    a = ap.parse_args()
    {"build": cmd_build, "collect": cmd_collect, "tables": cmd_tables}[a.cmd](a)


if __name__ == "__main__":
    main()
