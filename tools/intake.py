#!/usr/bin/env python3
"""One-pass intake of a reply to an R or N packet, or of a STEP 2 answer. FORM ONLY: never scores.

Reply:
  python3 -I intake.py --results DIR --src FILE --arm R --model gemini --run 2 --given-batch 1 \
      --label "Gemini R run 2 batch 1" --received "2026-11-13 22:05" --how attached [--dry-run]
  Saves the file as recvNN_label-<label>.txt (read-only), hashes it, checks it against every earlier file,
  parses it (tools/parse_reply.py), runs the form checks, writes parsed/recvNN.json, adds a row to cells.csv,
  and adds a table row and a form-check paragraph to received_log.md.
STEP 2 answer:
  python3 -I intake.py --results DIR --step2 "SILEX-0 has 104 roots ... section 7." --arm R --model gemini --run 2 \
      --received "22:01" [--dry-run]
  Judges the answer (104 roots and section 7) and adds a line to the Metadata part of received_log.md.
Nothing here reads a reply for meaning. A conflict or a mismatch is reported and left for a person to settle.
"""
import argparse, csv, glob, hashlib, json, os, re, shutil, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_reply as pr  # noqa: E402

HEDGE = re.compile(r"(?i)cannot tell|cannot be determined|cannot be established|unknown|uncertain|unclear|unsure")
GUIDEW = re.compile(r"(?i)\bguide\b|\bsection [0-9.]+|\bpinned\b|\brules?\b")  # counted and reported for every reply
GUIDE_STRONG = re.compile(r"(?i)\bguide\b|\bsection [0-9.]+|\bpinned\b|\brule [0-9]+")  # only these hold an N reply for review ("rule" alone is an ordinary word)
GAPS = [re.compile(r" [,.](?: |$)"), re.compile(r"\(\)"), re.compile(r"(?i)\bfrom and\b"), re.compile(r"(?i)\bof as approaches\b"),
        re.compile(r"(?i)\binfer \.")]
MODEL_NAMES = {"claude": "Claude", "chatgpt": "ChatGPT", "grok": "Grok", "gemini": "Gemini"}


def slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s.strip()).strip("_") or "reply"


def insert_before_heading(lines, heading_prefix, new_lines, blank_before=False):
    idx = next((i for i, l in enumerate(lines) if l.startswith(heading_prefix)), None)
    if idx is None:
        sys.exit(f"log heading not found: {heading_prefix!r}")
    pos = idx
    while pos > 0 and lines[pos - 1].strip() == "":
        pos -= 1
    ins = ([""] if blank_before else []) + new_lines
    return lines[:pos] + ins + lines[pos:]


def insert_after_last_row(lines, new_row):
    last = max((i for i, l in enumerate(lines) if re.match(r"^\| recv\d+ \|", l)), default=None)
    if last is None:
        sys.exit("no table rows found in the log")
    return lines[:last + 1] + [new_row] + lines[last + 1:]


def next_recv(results):
    nums = [int(re.match(r"recv(\d+)_", os.path.basename(p)).group(1)) for p in glob.glob(os.path.join(results, "recv*_*.txt"))]
    return max(nums, default=0) + 1


def do_step2(a):
    txt = a.step2.strip()
    ok = bool(re.search(r"\b104\b", txt)) and bool(re.search(r"(?i)(section|sec\.|§)\s*7\b", txt))
    model = MODEL_NAMES.get(a.model, a.model)
    line = (f"{model} {a.arm} run {a.run}: STEP 2 answer given {a.received}, {'correct' if ok else 'WRONG'}: \"{txt}\" "
            f"Model version and how the guide was given not stated.")
    print(f"STEP 2 {model} {a.arm} run {a.run}: {'CORRECT (104 roots, section 7)' if ok else 'WRONG'}")
    if not ok:
        print("  Protocol: if wrong, start a new chat once and give the guide the other way (pasted vs attached). "
              "Replies from this chat must not be used. Ask the user which way the guide went the first time.")
    if a.dry_run:
        print("  (dry run, nothing written)")
        return
    lp = os.path.join(a.results, "received_log.md")
    lines = open(lp, encoding="utf-8").read().split("\n")
    lines = insert_before_heading(lines, "## Handling decisions", [line])
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print("  logged in received_log.md (Metadata)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--src")
    ap.add_argument("--step2")
    ap.add_argument("--arm", required=True, choices=["R", "N"])
    ap.add_argument("--model", required=True, choices=list(MODEL_NAMES))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--given-batch", type=int, choices=[1, 2])
    ap.add_argument("--label", default="")
    ap.add_argument("--received", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--how", choices=["attached", "inline"], default="attached")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.step2 is not None:
        return do_step2(a)
    if not a.src:
        sys.exit("--src is required for a reply")

    data = open(a.src, "rb").read()
    text = data.decode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    s16 = sha[:16]
    model = MODEL_NAMES[a.model]
    existing = sorted(glob.glob(os.path.join(a.results, "recv*_*.txt")))
    n = next_recv(a.results)
    rid = f"recv{n:02d}"
    fname = f"{rid}_label-{slug(a.label or f'{model}_{a.arm}_run_{a.run}')}.txt"
    severe, notes = [], []  # severe: the reply is held for review (status "review"); notes: told to the user, reply still counts

    dup_of = next((os.path.basename(p)[:6] for p in existing if open(p, "rb").read() == data), None)
    pre, items, inline, trailer = pr.parse(text)
    ids = [i["id"] for i in items]
    b1, b2 = pr.packet_ids(1), pr.packet_ids(2)
    in1, in2 = [i for i in ids if i in b1], [i for i in ids if i in b2]
    derived = 1 if len(in1) >= len(in2) else 2
    expect = b1 if derived == 1 else b2
    missing = [i for i in expect if i not in ids]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    unknown = [i for i in ids if i not in b1 and i not in b2]
    in_order = ids == [i for i in expect if i in ids]
    words = [i["words"] for i in items]
    over = [i["id"] for i in items if i["words"] > pr.LIMIT]
    ui = [l for l in pre if pr.UILINE.match(l.strip())]
    search = [(i["id"], m.group(0)) for i in items for m in pr.SEARCHY.finditer(i["text"])]
    gaps = [(i["id"], g.pattern) for i in items for g in GAPS if g.search(i["text"])]
    hedge = {}
    for i in items:
        for m in HEDGE.finditer(i["text"]):
            hedge[m.group(0).lower()] = hedge.get(m.group(0).lower(), 0) + 1
    guidew = {}
    for i in items:
        for m in GUIDEW.finditer(i["text"]):
            guidew[m.group(0).lower()] = guidew.get(m.group(0).lower(), 0) + 1
    strong = {}
    for i in items:
        for m in GUIDE_STRONG.finditer(i["text"]):
            strong[m.group(0).lower()] = strong.get(m.group(0).lower(), 0) + 1
    multi = [i["id"] for i in items if "\n" in i["text"]]

    cells = list(csv.DictReader(open(os.path.join(a.results, "cells.csv"), newline="", encoding="utf-8")))
    cell = f"{a.arm}-{a.model}-{a.run}-b{derived}"
    clash = next((r["recv"] for r in cells if r["status"] == "data" and (r["arm"], r["model"], r["run"], r["batch"]) ==
                  (a.arm, a.model, str(a.run), str(derived))), None)
    same_items = {}
    for r in cells:
        if r["status"] != "data" or int(r["batch"]) != derived:
            continue
        pj = os.path.join(a.results, "parsed", f"{r['recv']}.json")
        if os.path.exists(pj):
            old = json.load(open(pj, encoding="utf-8"))["items"]
            k = sum(1 for i in items if old.get(i["id"]) == i["text"])
            if k:
                same_items[r["recv"]] = k

    if dup_of:
        notes.append(f"DUPLICATE: byte-identical to {dup_of}; kept on file, not counted")
    else:
        if len(ids) != 20 or missing or dups or unknown:
            severe.append(f"ITEMS: found {len(ids)}, missing {missing or 'none'}, duplicates {dups or 'none'}, unknown {unknown or 'none'}")
        if not in_order:
            severe.append("ITEMS NOT IN PACKET ORDER")
        if over:
            severe.append(f"OVER {pr.LIMIT} WORDS: {over}")
        if search:
            severe.append(f"SEARCH-LIKE WORDS: {search[:5]}")
        if clash:
            severe.append(f"CELL ALREADY FILLED by {clash}: {cell}. Not added as data; ask the user (re-run? mislabel?)")
        big = {k: v for k, v in same_items.items() if v >= 3}
        if big:
            severe.append(f"SAME ITEM TEXT AS EARLIER REPLIES: {big} (possible re-send or mix-up)")
        if a.arm == "N" and strong:
            severe.append(f"GUIDE WORDS IN AN N REPLY: {strong} (check for exposure)")
        elif a.arm == "N" and guidew:
            notes.append(f"ordinary word(s) that the guide also uses, in an N reply: {guidew} (read them in context)")
        if a.given_batch and a.given_batch != derived:
            notes.append(f"LABEL MISMATCH: label says batch {a.given_batch}, the item numbers say batch {derived} (item numbers rule)")
        if gaps:
            notes.append(f"POSSIBLE DROPPED TEXT: {gaps[:6]}")
        if trailer:
            notes.append("TRAILER after the last item (correction rule: add it to corrections.json before building sheets): " + trailer[:160])
        if pre:
            notes.append(f"TEXT BEFORE ITEM 1: {pre[:3]}")
    flags = severe + notes

    # ---- report
    print(f"{rid} <- {a.label or fname}   sha256 {s16}   {len(data)} bytes")
    print(f"cell: {cell}   derived batch: {derived}   items: {len(ids)} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   packet order: {in_order}")
    if items:
        print(f"words per item: min {min(words)} max {max(words)} mean {sum(words) / len(words):.1f} total {sum(words)}; over limit: {len(over)}")
    print(f"hedging words: {sum(hedge.values())} {hedge or ''}   guide words: {guidew or 'none'}   multi-line items: {len(multi)}")
    print("HELD FOR REVIEW (status review):" if severe else "held for review: nothing")
    for f in severe:
        print("  - " + f)
    print("notes:" if notes else "notes: none")
    for f in notes:
        print("  - " + f)
    if a.dry_run:
        print("(dry run, nothing written)")
        return

    # ---- write
    dst = os.path.join(a.results, fname)
    with open(dst, "xb") as f:
        f.write(data)
    os.chmod(dst, 0o444)
    status = f"duplicate-of-{dup_of}" if dup_of else ("conflict" if clash else ("review" if severe else "data"))
    if not dup_of:
        json.dump({"source": dst, "sha256": sha, "preamble": pre, "trailer": trailer,
                   "items": {i["id"]: i["text"] for i in items}}, open(os.path.join(a.results, "parsed", f"{rid}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    with open(os.path.join(a.results, "cells.csv"), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([rid, a.arm if not dup_of else "", a.model if not dup_of else "", a.run if not dup_of else "",
                                derived if not dup_of else "", status, "no" if not dup_of else "", fname, s16])
    lp = os.path.join(a.results, "received_log.md")
    lines = open(lp, encoding="utf-8").read().split("\n")
    how = "Attached as a file." if a.how == "attached" else "Pasted inline; saved by me from the message text."
    if dup_of:
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | same as {dup_of} | - | same cell as {dup_of} | "
               f"DUPLICATE: byte-identical to {dup_of}. Not new data. |")
        para = None
    else:
        span = f"{ids[0]}-{ids[-1]}, {len(ids)} of 20, " + ("in order" if in_order else "NOT in order")
        ok = ("HELD FOR REVIEW: " + "; ".join(f.split(":")[0] for f in severe) + "." if severe
              else ("OK, with notes: " + "; ".join(f.split(":")[0] for f in notes) + "." if notes else "OK."))
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | {span} | {derived} | {cell} | {ok} {how} "
               f"Not a duplicate of any earlier file (checked against all {len(existing)}). |")
        para = [f"{rid} (arm {a.arm}, {model}, run {a.run}): {len(ids)} of 20 items ({ids[0]}-{ids[-1]}), "
                f"{'no duplicates' if not dups else 'DUPLICATES ' + str(dups)}, {'packet order' if in_order else 'NOT in packet order'}. "
                f"{'Nothing before the first item or after the last.' if not pre and not trailer else 'Text before item 1: ' + str(len(pre)) + ' line(s); trailer: ' + str(len(trailer)) + ' chars.'} "
                f"Words per item {min(words)} to {max(words)} (mean {sum(words) / len(words):.1f}, total {sum(words)}; "
                f"{'none over 120' if not over else 'OVER 120: ' + str(over)}). "
                f"{'No search-like words.' if not search else 'Search-like words: ' + str(search[:5]) + '.'} "
                f"{'No dropped-text gaps.' if not gaps else 'Possible dropped text: ' + str(gaps[:6]) + '.'} "
                f"{len(multi)} item(s) span several lines (kept as one item each). "
                f"Hedging words: {sum(hedge.values())}{' ' + str(hedge) if hedge else ''}. "
                f"Guide words: {guidew if guidew else 'none'}. "
                f"{('Flags: ' + '; '.join(flags) + '. ') if flags else ''}Items parsed to parsed/{rid}.json."]
    lines = insert_after_last_row(lines, row)
    if para:
        lines = insert_before_heading(lines, "## Metadata the protocol asks for", para, blank_before=True)
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"written: {fname} (read-only), parsed/{rid}.json, cells.csv row ({status}), received_log.md row" + (" and form-check paragraph" if para else ""))


if __name__ == "__main__":
    main()
