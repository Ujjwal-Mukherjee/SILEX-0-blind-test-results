#!/usr/bin/env python3
"""Build blind judge sheets for the reading test (arms R and N).

FORM ONLY: this script formats text. It never scores anything and never looks at what an
explanation says, except to warn when it names a model or an arm.

One sheet = one reply batch (20 items of one reader chat). The sheet shows:
  the frozen judge prompt (judge_recovery.txt, verbatim), a random sheet code, and for each
  item: its fact list (F1.., S facts marked) and the reader's explanation (with any correction
  note the same reply gave for that item). No model, run, arm, batch label or file name.
Item order inside a sheet is shuffled; so is the order in which sheets are to be given.
The map from sheet code to model/arm/run/batch is written to a separate PRIVATE file.

Usage:
  python3 -I build_judge_sheets.py --results /home/claude/silex_results \
      --kit /home/claude/silex_blind_test --out OUTDIR [--seed N] [--arms R,N]
"""
import argparse, csv, hashlib, json, os, random, re, secrets, sys, datetime

BATCH_ITEMS = {1: [f"#{i:02d}" for i in range(1, 21)], 2: [f"#{i:02d}" for i in range(21, 41)]}
ALPHABET = "ABCDEFGHJKMNPQRTUVWXYZ23456789"  # no 0/O, 1/I/L, S/5 mix-ups
IDENTITY = re.compile(
    r"(?i)\b(gemini|chatgpt|gpt|openai|grok|xai|claude|anthropic|google|bard|sonnet|opus|haiku|"
    r"llama|mistral|deepseek|copilot)\b")


def sha16_bytes(b):
    return hashlib.sha256(b).hexdigest()[:16]


def load_facts(kit):
    """item id -> list of (k, type, fact text), in fact order. Tier and key are NOT loaded for display."""
    facts = {}
    with open(os.path.join(kit, "facts.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = re.match(r"^(#\d{2})\.F(\d+)$", r["fact_id"])
            if not m or m.group(1) != r["id"]:
                sys.exit(f"bad fact_id {r['fact_id']!r}")
            facts.setdefault(r["id"], []).append((int(m.group(2)), r["type"], r["fact"].strip()))
    for k in facts:
        facts[k].sort()
        ks = [x[0] for x in facts[k]]
        if ks != list(range(1, len(ks) + 1)):
            sys.exit(f"fact numbers for {k} are not 1..n: {ks}")
    return facts


def sheet_text(prompt, code, order, facts, items, notes):
    out = [prompt.rstrip("\n"), "", "=" * 60, f"SHEET {code}", f"{len(order)} items follow.", "=" * 60, ""]
    for it in order:
        out.append(it)
        out.append("Facts:")
        for k, typ, fact in facts[it]:
            out.append(f"F{k}. " + ("(S) " if typ == "S" else "") + fact)
        out.append("Explanation:")
        out.append(items[it].strip("\n"))
        for n in notes.get(it, []):
            out.append(f"[Correction later in the same reply: {n}]")
        out.append("")
        out.append("-" * 60)
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--arms", default="R,N")
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else secrets.randbits(32)
    rng = random.Random(seed)
    arms = set(a.arms.split(","))

    prompt_path = os.path.join(a.kit, "judge_recovery.txt")
    prompt_bytes = open(prompt_path, "rb").read()
    prompt = prompt_bytes.decode("utf-8")
    facts = load_facts(a.kit)
    corr = {}
    cp = os.path.join(a.results, "corrections.json")
    if os.path.exists(cp):
        corr = json.load(open(cp, encoding="utf-8"))

    rows = [r for r in csv.DictReader(open(os.path.join(a.results, "cells.csv"), newline="", encoding="utf-8"))
            if r["status"] == "data" and r["arm"] in arms]
    if not rows:
        sys.exit("no data rows for those arms in cells.csv")

    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    used, sheets, warns = set(), [], []
    for r in rows:
        rid, batch = r["recv"], int(r["batch"])
        raw_path = os.path.join(a.results, r["file"])
        raw_sha = sha16_bytes(open(raw_path, "rb").read())
        if raw_sha != r["sha256_16"]:
            sys.exit(f"{rid}: raw file hash {raw_sha} does not match cells.csv {r['sha256_16']}")
        parsed = json.load(open(os.path.join(a.results, "parsed", f"{rid}.json"), encoding="utf-8"))
        if parsed.get("sha256", "")[:16] != raw_sha:
            sys.exit(f"{rid}: parsed JSON was made from a different file")
        items = parsed["items"]
        if parsed.get("trailer") and rid not in corr:
            sys.exit(f"{rid}: the reply has text after its last item (a trailer) but corrections.json has no entry for it; "
                     f"add one (an empty items map if the text names no item) before building sheets")
        if sorted(items) != BATCH_ITEMS[batch]:
            sys.exit(f"{rid}: items {sorted(items)[:3]}... do not match batch {batch}")
        notes = {k: [v] for k, v in corr.get(rid, {}).get("items", {}).items()}
        for it, text in items.items():
            for m in IDENTITY.finditer(text):
                warns.append(f"{rid} {it}: names '{m.group(0)}' in the explanation")
        for it, ns in notes.items():
            for n in ns:
                for m in IDENTITY.finditer(n):
                    warns.append(f"{rid} {it}: names '{m.group(0)}' in a correction note")
        while True:
            code = "".join(rng.choice(ALPHABET) for _ in range(4))
            if code not in used:
                used.add(code)
                break
        order = list(BATCH_ITEMS[batch])
        rng.shuffle(order)
        txt = sheet_text(prompt, code, order, facts, items, notes)
        p = os.path.join(a.out, "sheets", f"sheet_{code}.txt")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        sheets.append(dict(code=code, recv=rid, arm=r["arm"], model=r["model"], run=r["run"], batch=batch,
                           n_items=len(order), raw_sha16=raw_sha, sheet_sha16=sha16_bytes(txt.encode("utf-8")),
                           order=" ".join(order), corrected_items=" ".join(sorted(notes))))

    # presentation order of the sheets: a second shuffle, independent of the codes
    present = [s["code"] for s in sheets]
    rng.shuffle(present)

    with open(os.path.join(a.out, "sheets_map_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sheets[0].keys()))
        w.writeheader()
        w.writerows(sorted(sheets, key=lambda s: present.index(s["code"])))
    with open(os.path.join(a.out, "judge_order_PRIVATE.txt"), "w", encoding="utf-8") as f:
        f.write("Give the sheets to the judge in this order (codes only):\n" + "\n".join(present) + "\n")
    info = dict(built=datetime.datetime.now().isoformat(timespec="seconds"), seed=seed, arms=sorted(arms),
                n_sheets=len(sheets), judge_prompt_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
                facts_csv_sha256=hashlib.sha256(open(os.path.join(a.kit, "facts.csv"), "rb").read()).hexdigest(),
                script_sha16=sha16_bytes(open(__file__, "rb").read()))
    json.dump(info, open(os.path.join(a.out, "build_info_PRIVATE.json"), "w"), indent=2)

    print(f"sheets built: {len(sheets)}  seed: {seed}  out: {a.out}")
    by = {}
    for s in sheets:
        by.setdefault((s["arm"], s["model"]), []).append(s["batch"])
    for k in sorted(by):
        print(f"  {k[0]}-{k[1]}: batches {sorted(by[k])}")
    print(f"corrected items: {sum(len(s['corrected_items'].split()) for s in sheets if s['corrected_items'])}")
    print("identity warnings:" if warns else "identity warnings: none")
    for w_ in warns:
        print("  " + w_)


if __name__ == "__main__":
    main()
