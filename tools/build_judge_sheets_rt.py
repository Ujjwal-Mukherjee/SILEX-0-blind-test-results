#!/usr/bin/env python3
"""Build blind judge sheets for the round trip (arms RTP and RTE). Rules: RT_handling_rules.md, section C.

FORM ONLY: this script formats text. It never scores anything and never looks at what an explanation says, except to warn when it names a model.
Built on build_judge_sheets.py (same sheet layout, same shuffling, same private map). Differences:
  - the judge prompt is judge_roundtrip.txt (verbatim);
  - only the scenario's C facts are shown (S facts are not used in the round trip); they keep their numbers from facts.csv, so a skipped S fact leaves a gap in the numbering;
  - the rows are the RTP and RTE reader replies of cells.csv (status data); the chat number is in the run column.
One sheet = one reader reply (20 items of one packet). No writer, chat, arm, reader model, packet label or file name appears on a sheet.

Usage:
  python3 -I build_judge_sheets_rt.py --results /home/claude/silex_results --kit /home/claude/silex_blind_test --out OUTDIR [--seed N] [--arms RTP,RTE]
"""
import argparse, csv, datetime, hashlib, json, os, random, secrets, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_judge_sheets as bj   # noqa: E402


def c_facts(kit):
    """item id -> list of (k, 'C', fact text) for the C facts only, with the original fact numbers."""
    allf = bj.load_facts(kit)
    out = {}
    for it, lst in allf.items():
        cs = [(k, t, f) for k, t, f in lst if t == "C"]
        if not cs:
            sys.exit(f"{it} has no C fact")
        out[it] = cs
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--arms", default="RTP,RTE")
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else secrets.randbits(32)
    rng = random.Random(seed)
    arms = set(a.arms.split(","))
    prompt_bytes = open(os.path.join(a.kit, "judge_roundtrip.txt"), "rb").read()
    prompt = prompt_bytes.decode("utf-8")
    facts = c_facts(a.kit)
    corr = {}
    cpth = os.path.join(a.results, "corrections.json")
    if os.path.exists(cpth):
        corr = json.load(open(cpth, encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(os.path.join(a.results, "cells.csv"), newline="", encoding="utf-8"))
            if r["status"] == "data" and r["arm"] in arms]
    if not rows:
        sys.exit("no data rows for those arms in cells.csv")

    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    used, sheets, warns = set(), [], []
    for r in rows:
        rid, batch = r["recv"], int(r["batch"])
        raw_sha = bj.sha16_bytes(open(os.path.join(a.results, r["file"]), "rb").read())
        if raw_sha != r["sha256_16"]:
            sys.exit(f"{rid}: raw file hash {raw_sha} does not match cells.csv {r['sha256_16']}")
        parsed = json.load(open(os.path.join(a.results, "parsed", f"{rid}.json"), encoding="utf-8"))
        if parsed.get("sha256", "")[:16] != raw_sha:
            sys.exit(f"{rid}: parsed JSON was made from a different file")
        items = parsed["items"]
        if parsed.get("trailer") and rid not in corr:
            sys.exit(f"{rid}: the reply has text after its last item (a trailer) but corrections.json has no entry for it; "
                     f"add one (an empty items map if the text names no item) before building sheets")
        if sorted(items) != bj.BATCH_ITEMS[batch]:
            sys.exit(f"{rid}: items {sorted(items)[:3]}... do not match batch {batch}")
        notes = {k: [v] for k, v in corr.get(rid, {}).get("items", {}).items()}
        for it, text in items.items():
            for m in bj.IDENTITY.finditer(text):
                warns.append(f"{rid} {it}: names '{m.group(0)}' in the explanation")
        for it, ns in notes.items():
            for n_ in ns:
                for m in bj.IDENTITY.finditer(n_):
                    warns.append(f"{rid} {it}: names '{m.group(0)}' in a correction note")
        while True:
            code = "".join(rng.choice(bj.ALPHABET) for _ in range(4))
            if code not in used:
                used.add(code)
                break
        order = list(bj.BATCH_ITEMS[batch])
        rng.shuffle(order)
        txt = bj.sheet_text(prompt, code, order, facts, items, notes)
        p = os.path.join(a.out, "sheets", f"sheet_{code}.txt")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        sheets.append(dict(code=code, recv=rid, arm=r["arm"], model=r["model"], run=r["run"], batch=batch,
                           n_items=len(order), raw_sha16=raw_sha, sheet_sha16=bj.sha16_bytes(txt.encode("utf-8")),
                           order=" ".join(order), corrected_items=" ".join(sorted(notes))))

    present = [s["code"] for s in sheets]
    rng.shuffle(present)
    with open(os.path.join(a.out, "sheets_map_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sheets[0].keys()))
        w.writeheader()
        w.writerows(sorted(sheets, key=lambda s: present.index(s["code"])))
    with open(os.path.join(a.out, "judge_order_PRIVATE.txt"), "w", encoding="utf-8") as f:
        f.write("Give the sheets to the judge in this order (codes only):\n" + "\n".join(present) + "\n")
    info = dict(built=datetime.datetime.now().isoformat(timespec="seconds"), seed=seed, arms=sorted(arms), n_sheets=len(sheets),
                judge_prompt_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
                facts_csv_sha256=hashlib.sha256(open(os.path.join(a.kit, "facts.csv"), "rb").read()).hexdigest(),
                script_sha16=bj.sha16_bytes(open(__file__, "rb").read()))
    json.dump(info, open(os.path.join(a.out, "build_info_PRIVATE.json"), "w"), indent=2)

    print(f"sheets built: {len(sheets)}  seed: {seed}  out: {a.out}")
    by = {}
    for s in sheets:
        by.setdefault((s["arm"], s["model"], s["run"]), []).append(s["batch"])
    for k in sorted(by):
        print(f"  {k[0]} reader {k[1]} chat {k[2]}: packets {sorted(by[k])}")
    print(f"corrected items: {sum(len(s['corrected_items'].split()) for s in sheets if s['corrected_items'])}")
    print("identity warnings:" if warns else "identity warnings: none")
    for w_ in warns:
        print("  " + w_)


if __name__ == "__main__":
    main()
