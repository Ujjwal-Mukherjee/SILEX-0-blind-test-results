#!/usr/bin/env python3
"""One-pass intake of a reader reply of the round trip (arms RTP and RTE), or of a STEP 2 answer in an RTP reader chat.
FORM ONLY: never scores, never opens a key. Rules: RT_handling_rules.md (same folder as the results).
Built on intake.py (same parse, same checks, same files cells.csv / parsed/ / received_log.md); the differences are the cell, the packet order and the guide-word check:
  - the cell is (arm, reader model, chat number, batch); the chat number is stored in the run column of cells.csv;
  - the packet order is the seeded shuffle of the build (build_roundtrip_p.item_order with the build's seed, never read from a key); a different order is a note, not a hold;
  - guide words are held only in an RTE reply (the English reader has no guide).

Reply:
  python3 -I intake_rt.py --results DIR --src FILE --arm RTP|RTE --model grok --chat 2 [--given-batch 1] \
      --label "RT P chat 2 packet 1" --received "2026-11-14 22:05" --how attached|inline [--seed TEXT] [--dry-run]
STEP 2 answer (RTP chats only):
  python3 -I intake_rt.py --results DIR --step2 "104 roots, section 7" --arm RTP --model grok --chat 2 --received "22:01" [--dry-run]
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_reply as pr           # noqa: E402
import intake as ik                # noqa: E402
import build_roundtrip_p as brp    # noqa: E402

MODEL_NAMES = ik.MODEL_NAMES


def do_step2(a):
    if a.arm != "RTP":
        sys.exit("STEP 2 belongs to RTP chats only (the English reader has no guide)")
    txt = a.step2.strip()
    ok = bool(re.search(r"\b104\b", txt)) and bool(re.search(r"(?i)(section|sec\.|§)\s*7\b", txt))
    model = MODEL_NAMES.get(a.model, a.model)
    line = (f"Reader {model}, arm RTP, chat {a.chat}: STEP 2 answer given {a.received}, {'correct' if ok else 'WRONG'}: \"{txt}\" "
            f"Model version and how the guide was given not stated.")
    print(f"STEP 2 reader {model} RTP chat {a.chat}: {'CORRECT (104 roots, section 7)' if ok else 'WRONG'}")
    if not ok:
        print("  Rule 2: if wrong, start a new chat once and give the guide the other way (pasted vs attached). "
              "Replies from this chat must not be used. Ask the user which way the guide went the first time.")
    if a.dry_run:
        print("  (dry run, nothing written)")
        return
    lp = os.path.join(a.results, "received_log.md")
    lines = open(lp, encoding="utf-8").read().split("\n")
    lines = ik.insert_before_heading(lines, "## Handling decisions", [line])
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print("  logged in received_log.md (Metadata)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--src")
    ap.add_argument("--step2")
    ap.add_argument("--arm", required=True, choices=["RTP", "RTE"])
    ap.add_argument("--model", required=True, choices=list(MODEL_NAMES), help="the READER model")
    ap.add_argument("--chat", type=int, required=True, choices=[1, 2, 3, 4])
    ap.add_argument("--given-batch", type=int, choices=[1, 2])
    ap.add_argument("--label", default="")
    ap.add_argument("--received", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--how", choices=["attached", "inline"], default="attached")
    ap.add_argument("--seed", default=brp.DEFAULT_SEED)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.step2 is not None:
        return do_step2(a)
    if not a.src:
        sys.exit("--src is required for a reply")

    data = open(a.src, "rb").read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        sys.exit(f"the reply file is not valid UTF-8 ({e}); save it again exactly as received")
    sha = hashlib.sha256(data).hexdigest()
    s16 = sha[:16]
    model = MODEL_NAMES[a.model]
    existing = sorted(glob.glob(os.path.join(a.results, "recv*_*.txt")))
    n = ik.next_recv(a.results)
    rid = f"recv{n:02d}"
    fname = f"{rid}_label-{ik.slug(a.label or f'RT_{a.arm}_chat_{a.chat}')}.txt"
    severe, notes = [], []

    dup_of = next((os.path.basename(p)[:6] for p in existing if open(p, "rb").read() == data), None)
    pre, items, inline, trailer = pr.parse(text)
    ids = [i["id"] for i in items]
    b1, b2 = pr.packet_ids(1), pr.packet_ids(2)
    in1, in2 = [i for i in ids if i in b1], [i for i in ids if i in b2]
    derived = 1 if len(in1) >= len(in2) else 2
    expect = b1 if derived == 1 else b2
    packet_order = brp.item_order(a.seed, expect)
    missing = [i for i in expect if i not in ids]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    unknown = [i for i in ids if i not in b1 and i not in b2]
    in_order = ids == [i for i in packet_order if i in ids]
    in_numeric_order = ids == [i for i in expect if i in ids]
    words = [i["words"] for i in items]
    over = [i["id"] for i in items if i["words"] > pr.LIMIT]
    search = [(i["id"], m.group(0)) for i in items for m in pr.SEARCHY.finditer(i["text"])]
    gaps = [(i["id"], g.pattern) for i in items for g in ik.GAPS if g.search(i["text"])]
    hedge, guidew, strong = {}, {}, {}
    for i in items:
        for m in ik.HEDGE.finditer(i["text"]):
            hedge[m.group(0).lower()] = hedge.get(m.group(0).lower(), 0) + 1
        for m in ik.GUIDEW.finditer(i["text"]):
            guidew[m.group(0).lower()] = guidew.get(m.group(0).lower(), 0) + 1
        for m in ik.GUIDE_STRONG.finditer(i["text"]):
            strong[m.group(0).lower()] = strong.get(m.group(0).lower(), 0) + 1
    multi = [i["id"] for i in items if "\n" in i["text"]]

    cells = list(csv.DictReader(open(os.path.join(a.results, "cells.csv"), newline="", encoding="utf-8")))
    cell = f"{a.arm}-{a.model}-chat{a.chat}-b{derived}"
    clash = next((r["recv"] for r in cells if r["status"] == "data" and (r["arm"], r["model"], r["run"], r["batch"]) ==
                  (a.arm, a.model, str(a.chat), str(derived))), None)
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
        if over:
            severe.append(f"OVER {pr.LIMIT} WORDS: {over}")
        if search:
            severe.append(f"SEARCH-LIKE WORDS: {search[:5]}")
        if clash:
            severe.append(f"CELL ALREADY FILLED by {clash}: {cell}. Not added as data; ask the user (re-run? mislabel?)")
        big = {k: v for k, v in same_items.items() if v >= 3}
        if big:
            severe.append(f"SAME ITEM TEXT AS EARLIER REPLIES: {big} (possible re-send or mix-up)")
        if a.arm == "RTE" and strong:
            severe.append(f"GUIDE WORDS IN AN RTE REPLY: {strong} (the English reader has no guide; check for exposure)")
        elif a.arm == "RTE" and guidew:
            notes.append(f"ordinary word(s) that the guide also uses, in an RTE reply: {guidew} (read them in context)")
        if not in_order:
            notes.append("items are not in the order of the packet" + (" (they are in numeric order)" if in_numeric_order else "") + "; the order does not matter to the judge")
        if a.given_batch and a.given_batch != derived:
            notes.append(f"LABEL MISMATCH: label says packet {a.given_batch}, the item numbers say batch {derived} (item numbers rule)")
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
        csv.writer(f).writerow([rid, a.arm if not dup_of else "", a.model if not dup_of else "", a.chat if not dup_of else "",
                                derived if not dup_of else "", status, "no" if not dup_of else "", fname, s16])
    lp = os.path.join(a.results, "received_log.md")
    lines = open(lp, encoding="utf-8").read().split("\n")
    how = "Attached as a file." if a.how == "attached" else "Pasted inline; saved by me from the message text."
    if dup_of:
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | same as {dup_of} | - | same cell as {dup_of} | "
               f"DUPLICATE: byte-identical to {dup_of}. Not new data. |")
        para = None
    else:
        span = f"{ids[0]}-{ids[-1]}, {len(ids)} of 20, " + ("in packet order" if in_order else "NOT in packet order")
        okx = ("HELD FOR REVIEW: " + "; ".join(f.split(":")[0] for f in severe) + "." if severe
               else ("OK, with notes: " + "; ".join(f.split(":")[0] for f in notes) + "." if notes else "OK."))
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | {span} | {derived} | {cell} | {okx} {how} "
               f"Not a duplicate of any earlier file (checked against all {len(existing)}). |")
        para = [f"{rid} (arm {a.arm}, reader {model}, chat {a.chat}): {len(ids)} of 20 items ({ids[0] if ids else '-'}-{ids[-1] if ids else '-'}), "
                f"{'no duplicates' if not dups else 'DUPLICATES ' + str(dups)}, {'packet order' if in_order else 'NOT in packet order'}. "
                f"{'Nothing before the first item or after the last.' if not pre and not trailer else 'Text before item 1: ' + str(len(pre)) + ' line(s); trailer: ' + str(len(trailer)) + ' chars.'} "
                f"Words per item {min(words) if words else 0} to {max(words) if words else 0} (mean {(sum(words) / len(words)) if words else 0:.1f}, total {sum(words)}; "
                f"{'none over 120' if not over else 'OVER 120: ' + str(over)}). "
                f"{'No search-like words.' if not search else 'Search-like words: ' + str(search[:5]) + '.'} "
                f"{'No dropped-text gaps.' if not gaps else 'Possible dropped text: ' + str(gaps[:6]) + '.'} "
                f"{len(multi)} item(s) span several lines (kept as one item each). "
                f"Hedging words: {sum(hedge.values())}{' ' + str(hedge) if hedge else ''}. "
                f"Guide words: {guidew if guidew else 'none'}. "
                f"{('Flags: ' + '; '.join(flags) + '. ') if flags else ''}Items parsed to parsed/{rid}.json."]
    lines = ik.insert_after_last_row(lines, row)
    if para:
        lines = ik.insert_before_heading(lines, "## Metadata the protocol asks for", para, blank_before=True)
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"written: {fname} (read-only), parsed/{rid}.json, cells.csv row ({status}), received_log.md row" + (" and form-check paragraph" if para else ""))


if __name__ == "__main__":
    main()
