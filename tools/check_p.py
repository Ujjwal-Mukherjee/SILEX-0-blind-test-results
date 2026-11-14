#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validity run for the writing test (arm P): runs the checker on every written item and decides valid / invalid by P_handling_rules.md (rules 15 to 19).
Run it ONCE, after the last P reply is filed. It needs no key. It reads the saved reply files (not the parsed copies) and parses them again with parse_p_reply.py.

  python3 -I check_p.py --results DIR --kit KIT [--out DIR/validity_P] [--only P-claude-1-b1,...] [--include-review]

Per item (its own process for every block):  python3 silex_check.py GUIDE --messages FILE   on the comment-free text of the block.
PRIMARY validity (rule 15): present, not NONE, not empty, no comment, the checker says ok to every message (0 problems, 0 retracted failing lines), every block of the item ok.
Also reported beside it: checker_ok (the same without the comment rule) and joined_ok (a split item with its blocks joined into one conversation).
Before running, the guide and the checker are compared with the hashes in KIT/MANIFEST.sha256; a difference stops the run.
Outputs in --out: items.csv, raw/<cell>__<item>.txt (the checker's full output), summary.json, summary.md.
"""
import argparse, csv, hashlib, json, os, re, statistics, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_p_reply as pp   # noqa: E402

SUMMARY_RE = re.compile(r"== (\d+) message\(s\), (\d+) line\(s\), (\d+) problem\(s\)(?:, (\d+) retracted)?(?:, (\d+) line\(s\) not checked)?")
VERDICT_RE = re.compile(r"^\s+(\S+)\s+(?:header\s+)?(E-[A-Z]+)\b(.*)$")
MODELS = ["claude", "chatgpt", "grok", "gemini"]


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def verify_kit(kit):
    man = {}
    for ln in open(os.path.join(kit, "MANIFEST.sha256"), encoding="utf-8"):
        parts = ln.strip().split(None, 1)
        if len(parts) == 2:
            man[parts[1].lstrip("*")] = parts[0]
    for f in ("SILEX-0-GRAMMAR.md", "silex_check.py"):
        if f not in man:
            sys.exit(f"{f} is not listed in {kit}/MANIFEST.sha256")
        if sha_file(os.path.join(kit, f)) != man[f]:
            sys.exit(f"HASH MISMATCH for {f}: the run is stopped (the guide and the checker must be the frozen files)")
    return man["SILEX-0-GRAMMAR.md"], man["silex_check.py"]


def run_checker(kit, text, tmp):
    """-> dict with the checker's counts, verdict lines, notes and full output; error set if it did not run properly."""
    path = os.path.join(tmp, "item.txt")
    open(path, "w", encoding="utf-8").write(text + "\n")
    try:
        p = subprocess.run([sys.executable, "-I", os.path.join(kit, "silex_check.py"), os.path.join(kit, "SILEX-0-GRAMMAR.md"), "--messages", path],
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"error": "checker timed out (30 s)", "raw": ""}
    out = p.stdout + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
    m = None
    for m_ in SUMMARY_RE.finditer(p.stdout):
        m = m_
    if p.returncode not in (0, 1) or m is None:
        return {"error": f"checker did not run properly (exit {p.returncode}): {(p.stderr or p.stdout)[-200:].strip()}", "raw": out}
    verdicts, notes = [], []
    for ln in p.stdout.split("\n"):
        v = VERDICT_RE.match(ln)
        if v and ("<-- problem" in ln or "(retracted by" in ln):
            verdicts.append({"place": v.group(1), "code": v.group(2), "retracted": "(retracted by" in ln})
        elif ln.startswith("  note "):
            notes.append(ln.strip())
    return {"error": None, "messages": int(m.group(1)), "lines": int(m.group(2)), "problems": int(m.group(3)),
            "retracted": int(m.group(4) or 0), "not_checked": int(m.group(5) or 0), "verdicts": verdicts, "notes": notes, "raw": out}


def block_ok(res):
    return res is not None and res["error"] is None and res["problems"] == 0 and res["retracted"] == 0 and res["messages"] > 0


def load_replies(results, include_review):
    """-> list of dicts (cell, recv, model, run, batch, texts, files, status) for every first-part row that counts."""
    rows = list(csv.DictReader(open(os.path.join(results, "cells_P.csv"), newline="", encoding="utf-8")))
    cont = {}
    for r in rows:
        if r["status"].startswith("continuation-of-"):
            cont.setdefault(r["status"].split("-of-")[1], []).append(r)
    out, skipped = [], []
    for r in rows:
        if r["status"] == "data" or (include_review and r["status"] == "review"):
            files = [r["file"]] + [c["file"] for c in sorted(cont.get(r["recv"], []), key=lambda x: x["recv"])]
            texts = [open(os.path.join(results, f), encoding="utf-8").read() for f in files]
            out.append({"cell": f"P-{r['model']}-{r['run']}-b{r['batch']}", "recv": r["recv"], "model": r["model"], "run": int(r["run"]),
                        "batch": int(r["batch"]), "texts": texts, "files": files, "status": r["status"]})
        elif not r["status"].startswith("duplicate-of-") and not r["status"].startswith("continuation-of-"):
            skipped.append((r["recv"], r["status"]))
    return out, skipped


def evaluate_item(kit, tmp, item_id, item):
    """-> (row dict, list of raw outputs). item = parse_parts()['items'][id] or None."""
    row = {"valid": 0, "checker_ok": 0, "joined_ok": 0, "reasons": [], "blocks": 0, "messages": 0, "lines": 0, "problems": 0, "retracted": 0,
           "not_checked": 0, "verdicts": [], "comment_lines": 0, "chars": "", "checker_notes": 0}
    raws = []
    if item is None or item["status"] == "missing":
        row["reasons"].append("missing")
        return row, raws
    blocks = item["blocks"]
    row["blocks"] = len(blocks)
    results = []
    for k, b in enumerate(blocks, 1):
        row["comment_lines"] += len(b["comments"])
        if b["none"]:
            row["reasons"].append("NONE")
            results.append(None)
            continue
        if b["empty"]:
            row["reasons"].append("empty")
            results.append(None)
            continue
        res = run_checker(kit, b["text"], tmp)
        raws.append(f"--- block {k} ---\n{b['text']}\n--- checker ---\n{res['raw']}")
        results.append(res)
        if res["error"]:
            row["reasons"].append("checker-error: " + res["error"])
            continue
        row["messages"] += res["messages"]
        row["lines"] += res["lines"]
        row["problems"] += res["problems"]
        row["retracted"] += res["retracted"]
        row["not_checked"] += res["not_checked"]
        row["checker_notes"] += len(res["notes"])
        row["verdicts"] += [v["code"] for v in res["verdicts"]]
        if res["problems"] or res["retracted"]:
            row["reasons"].append("verdict")
    if any(b["comments"] for b in blocks):
        row["reasons"].append("comment")
    if len(blocks) > 1:
        row["reasons"].append("split")
    if any(not b["closed"] for b in blocks):
        row["reasons"].append("unclosed")
    texts = [b["chars"] for b in blocks if not b["none"] and not b["empty"]]
    row["chars"] = sum(texts) if texts else ""
    all_ok = all(block_ok(r) for r in results) and len(results) > 0
    row["checker_ok"] = int(all_ok)
    row["valid"] = int(all_ok and not any(b["comments"] for b in blocks))
    if len(blocks) > 1 and not all_ok:
        usable = [b["text"] for b in blocks if not b["none"] and not b["empty"]]
        if usable and len(usable) == len(blocks):
            res = run_checker(kit, "\n---\n".join(usable), tmp)
            raws.append(f"--- joined variant ---\n{res['raw']}")
            row["joined_ok"] = int(block_ok(res))
    else:
        row["joined_ok"] = row["checker_ok"]
    return row, raws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", default="/home/claude/silex_blind_test")
    ap.add_argument("--out")
    ap.add_argument("--only")
    ap.add_argument("--include-review", action="store_true")
    a = ap.parse_args()
    out = a.out or os.path.join(a.results, "validity_P")
    guide_sha, checker_sha = verify_kit(a.kit)
    replies, skipped = load_replies(a.results, a.include_review)
    if a.only:
        keep = set(a.only.split(","))
        replies = [r for r in replies if r["cell"] in keep]
    if not replies:
        sys.exit("no P reply with status data to check")
    os.makedirs(os.path.join(out, "raw"), exist_ok=True)
    order = {}
    op = os.path.join(a.kit, "order.csv")
    if os.path.exists(op):
        for r in csv.DictReader(open(op, newline="", encoding="utf-8")):
            order[r["id"]] = {"tier": int(r["tier"]), "gold_chars": int(r["silex_chars"])}
    rules = os.path.join(a.results, "P_handling_rules.md")
    rows = []
    with tempfile.TemporaryDirectory(prefix="check_p_") as tmp:
        for rp in sorted(replies, key=lambda r: (r["model"], r["run"], r["batch"])):
            parsed = pp.parse_parts(rp["texts"])
            if parsed["derived_batch"] != rp["batch"]:
                print(f"WARNING {rp['cell']}: the item numbers say batch {parsed['derived_batch']}")
            for iid in ["#%02d" % k for k in (range(1, 21) if rp["batch"] == 1 else range(21, 41))]:
                row, raws = evaluate_item(a.kit, tmp, iid, parsed["items"].get(iid))
                row.update({"cell": rp["cell"], "recv": rp["recv"], "model": rp["model"], "run": rp["run"], "batch": rp["batch"], "item": iid,
                            "tier": order.get(iid, {}).get("tier", ""), "gold_chars": order.get(iid, {}).get("gold_chars", "")})
                rows.append(row)
                open(os.path.join(out, "raw", f"{rp['cell']}__{iid[1:]}.txt"), "w", encoding="utf-8").write("\n".join(raws) if raws else "(no checker run: " + "; ".join(row["reasons"]) + ")\n")
    cols = ["cell", "recv", "model", "run", "batch", "item", "tier", "valid", "checker_ok", "joined_ok", "reasons", "blocks", "messages", "lines", "problems",
            "retracted", "not_checked", "verdicts", "comment_lines", "chars", "gold_chars", "checker_notes"]
    with open(os.path.join(out, "items.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([";".join(r[c]) if isinstance(r[c], list) else r[c] for c in cols])

    # ---- summary
    S = {"guide_sha256": guide_sha, "checker_sha256": checker_sha, "rules_sha256": sha_file(rules) if os.path.exists(rules) else None,
         "cells_checked": sorted({r["cell"] for r in rows}), "rows_not_included": skipped, "per_run": {}, "per_model": {}, "verdict_codes": {}, "reasons": {}}
    for m in MODELS:
        for run in sorted({r["run"] for r in rows if r["model"] == m}):
            rr = [r for r in rows if r["model"] == m and r["run"] == run]
            if rr:
                S["per_run"][f"{m}-{run}"] = {"items": len(rr), "valid": sum(r["valid"] for r in rr), "checker_ok": sum(r["checker_ok"] for r in rr),
                                              "joined_ok": sum(r["joined_ok"] for r in rr), "batches": sorted({r["batch"] for r in rr})}
        rm = [r for r in rows if r["model"] == m]
        if rm:
            shares = [S["per_run"][k]["valid"] / S["per_run"][k]["items"] for k in S["per_run"] if k.startswith(m + "-")]
            ch = [r["chars"] for r in rm if r["chars"] != ""]
            gold = [r["gold_chars"] for r in rm if r["chars"] != "" and r["gold_chars"] != ""]
            S["per_model"][m] = {"items": len(rm), "valid": sum(r["valid"] for r in rm), "valid_share": sum(r["valid"] for r in rm) / len(rm),
                                 "checker_ok_share": sum(r["checker_ok"] for r in rm) / len(rm), "joined_ok_share": sum(r["joined_ok"] for r in rm) / len(rm),
                                 "run_shares": shares, "run_min": min(shares), "run_max": max(shares),
                                 "median_chars": statistics.median(ch) if ch else None, "median_gold_chars_same_items": statistics.median(gold) if gold else None,
                                 "prediction_3_at_least_half_valid": sum(r["valid"] for r in rm) / len(rm) >= 0.5,
                                 "by_tier": {str(t): {"items": sum(1 for r in rm if r["tier"] == t), "valid": sum(r["valid"] for r in rm if r["tier"] == t)} for t in range(1, 6)}}
    for r in rows:
        for c in r["verdicts"]:
            S["verdict_codes"][c] = S["verdict_codes"].get(c, 0) + 1
        for c in r["reasons"]:
            key = c.split(":")[0]
            S["reasons"][key] = S["reasons"].get(key, 0) + 1
    json.dump(S, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = ["# Writing test (arm P): validity run", "",
          f"Guide sha256 {guide_sha[:16]}, checker sha256 {checker_sha[:16]}, rules sha256 {(S['rules_sha256'] or 'none')[:16]}. Cells checked: {len(S['cells_checked'])}. "
          f"Rows not included: {skipped or 'none'}.", "",
          "Primary validity = present, not NONE, no comment, checker ok on every message (rules 15 to 17 of P_handling_rules.md).", "",
          "| model | run | items | valid | checker-ok (comments allowed) | joined-ok |", "|---|---|---|---|---|---|"]
    for k, v in S["per_run"].items():
        md.append(f"| {k.split('-')[0]} | {k.split('-')[1]} | {v['items']} | {v['valid']} | {v['checker_ok']} | {v['joined_ok']} |")
    md += ["", "| model | items | valid share (mean of runs) | lowest run | highest run | checker-ok share | prediction 3 (at least half valid) | median chars (writer) | median chars (gold, same items) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m, v in S["per_model"].items():
        md.append(f"| {m} | {v['items']} | {v['valid_share']:.3f} | {v['run_min']:.3f} | {v['run_max']:.3f} | {v['checker_ok_share']:.3f} | "
                  f"{'yes' if v['prediction_3_at_least_half_valid'] else 'no'} | {v['median_chars']} | {v['median_gold_chars_same_items']} |")
    md += ["", "Verdict lines by code (all items): " + (", ".join(f"{k} {v}" for k, v in sorted(S["verdict_codes"].items())) or "none"),
           "Reasons (items): " + (", ".join(f"{k} {v}" for k, v in sorted(S["reasons"].items())) or "none"), ""]
    open(os.path.join(out, "summary.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md))
    print(f"written: {out}/items.csv, summary.json, summary.md, raw/ ({len(rows)} items)")


if __name__ == "__main__":
    main()
