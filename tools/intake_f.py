#!/usr/bin/env python3
"""One-pass intake of a reply to a Test F packet (arm FR or FN), or of a STEP 2 answer (FR chats only).
FORM ONLY: this tool never opens the key and never scores. Scoring is a separate step after the last run (score_f.py).

Reply:
  python3 -I intake_f.py --results DIR --src FILE --arm FR --model gemini --run 2 [--given-batch 1] \
      --label "FR gemini run 2 batch 1" --received "2026-11-14 10:05" --how attached [--dry-run]
  Saves the file as recvNN_label-<label>.txt (read-only; NN comes from the same counter as the reading test, so a number is never used twice),
  hashes it, compares it with every earlier recv file (duplicates), parses it (tools/parse_f_reply.py), runs the form checks,
  writes parsed_f/recvNN.json, adds a row to cells_F.csv (not to cells.csv), and adds a table row and a form-check paragraph to received_log_F.md.
STEP 2 answer (FR chats only; same check as the reading test):
  python3 -I intake_f.py --results DIR --step2 "104 roots, section 7" --arm FR --model gemini --run 2 --received "10:01" [--dry-run]
The item numbers decide the batch, not the label. A conflict, a hold or a mismatch is reported and left for a person to settle.
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_f_reply as pf   # noqa: E402
import parse_reply as pr     # noqa: E402  (only its SEARCHY pattern is reused)
import intake as rin         # noqa: E402  (helpers shared with the reading-test intake)

MODEL_NAMES = rin.MODEL_NAMES
PHRASE_LIMIT = 12                      # words, as the packet says
RANGE = re.compile(r"(?i)\bF\d{2}\s*(?:-|\u2013|\u2014|to|through|thru)\s*F\d{2}\b")
TOOL_EXTRA = re.compile(r"(?i)\b(?:i\s+(?:ran|executed)\b|ran\s+the\s+(?:code|checker|script)\b|code\s+interpreter\b|sandbox\b)")
# words that only the guide (or its checker) uses; in an FN reply they hold the reply for review
FN_STRONG = re.compile(r"\bE-(?:SYN|LEX|ARITY|KIND|NAME|REDEF|HEAD|TIME|QUOTE|ENGLISH|BUDGET|REF|COUNT|CODE|MATH)\b"
                       r"|(?i:\bsection\s+\d+(?:\.\d+)*\b|\bsilex\b|\b(?:nbrl|lnrl|cv1|aw1)\b)")
FN_ORDINARY = re.compile(r"(?i)\bguide\b|\brules?\b|\bchecker\b")      # ordinary words: counted and shown, not held
HEADER = ["recv", "arm", "model", "run", "batch", "status", "run_assumed", "file", "sha256_16"]
LOG_TEMPLATE = """# Test F (find the fault): received log

Created {today}. One row per file received, in the order received. The recvNN counter is shared with the reading test (same folder, same counter), so a number is never used twice.
The cells are in cells_F.csv (not in cells.csv); parsed replies are in parsed_f/. Nothing in this log scores a reply: scoring is done once, after the last run, with score_f.py.
intake_f.py never opens the key (key_F_PRIVATE.csv).

| recv | received | label as the user wrote it | file | sha256 (16) | items | batch | cell | form check |
|---|---|---|---|---|---|---|---|---|

## Form-check notes (one paragraph per file)

## Metadata the protocol asks for

## Handling decisions
"""


def names_item(s):
    return bool(re.search(r"\bF\d{2}\b", RANGE.sub("", s)))


def add_row(lines, row):
    last = max((i for i, l in enumerate(lines) if re.match(r"^\| recv\d+ \|", l)), default=None)
    if last is None:
        last = next((i for i, l in enumerate(lines) if re.match(r"^\|[-| ]+\|\s*$", l)), None)
    if last is None:
        sys.exit("no table found in received_log_F.md")
    return lines[:last + 1] + [row] + lines[last + 1:]


def ensure_files(results, dry):
    lp = os.path.join(results, "received_log_F.md")
    cp = os.path.join(results, "cells_F.csv")
    if not dry:
        if not os.path.exists(lp):
            open(lp, "w", encoding="utf-8").write(LOG_TEMPLATE.format(today=datetime.date.today().isoformat()))
        if not os.path.exists(cp):
            with open(cp, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(HEADER)
        os.makedirs(os.path.join(results, "parsed_f"), exist_ok=True)
    return lp, cp


def read_cells(cp):
    if not os.path.exists(cp):
        return []
    return list(csv.DictReader(open(cp, newline="", encoding="utf-8")))


def do_step2(a):
    if a.arm != "FR":
        sys.exit("STEP 2 belongs to FR chats only (an FN chat has no guide and no STEP 2).")
    txt = a.step2.strip()
    ok = bool(re.search(r"\b104\b", txt)) and bool(re.search(r"(?i)(section|sec\.|\u00a7)\s*7\b", txt))
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
    lp, _ = ensure_files(a.results, False)
    lines = open(lp, encoding="utf-8").read().split("\n")
    lines = rin.insert_before_heading(lines, "## Handling decisions", [line])
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print("  logged in received_log_F.md (Metadata)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--src")
    ap.add_argument("--step2")
    ap.add_argument("--arm", required=True, choices=["FR", "FN"])
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
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        sys.exit(f"the reply file is not valid UTF-8 ({e}); save it again exactly as received")
    sha = hashlib.sha256(data).hexdigest()
    s16 = sha[:16]
    model = MODEL_NAMES[a.model]
    existing = sorted(glob.glob(os.path.join(a.results, "recv*_*.txt")))
    n = rin.next_recv(a.results)
    rid = f"recv{n:02d}"
    fname = f"{rid}_label-{rin.slug(a.label or f'{model}_{a.arm}_run_{a.run}')}.txt"
    severe, notes = [], []   # severe: held for review (status "review"); notes: told to the user, the reply still counts

    dup_of = next((os.path.basename(p)[:6] for p in existing if open(p, "rb").read() == data), None)
    r = pf.parse(text)
    ans, ids = r["answers"], r["order"]
    nums = [int(i[1:]) for i in ids]
    in1 = [i for i, k in zip(ids, nums) if 1 <= k <= 20]
    in2 = [i for i, k in zip(ids, nums) if 21 <= k <= 40]
    unknown = [i for i, k in zip(ids, nums) if not 1 <= k <= 40]
    derived = 1 if len(in1) >= len(in2) else 2
    expect = [f"F{k:02d}" for k in (range(1, 21) if derived == 1 else range(21, 41))]
    missing = [i for i in expect if i not in ids]
    strays = [i for i in ids if i not in expect]
    dups = sorted(set(r["dups"]))
    in_order = [i for i in ids if i in expect] == [i for i in expect if i in ids]
    none_n = sum(1 for v in ans.values() if v["place"] == "none")
    named = [i for i, v in ans.items() if v["place"] not in (None, "none")]
    unread = [i for i, v in ans.items() if v["place"] is None]
    pw = {i: len(v["phrase"].split()) for i, v in ans.items()}
    over = [i for i, w in pw.items() if w > PHRASE_LIMIT]
    other = r["pre"] + r["post"]
    names_in_other = [(ln, s[:80]) for ln, s in other if names_item(s)]
    tool = sorted({m.group(0).lower() for m in pr.SEARCHY.finditer(text)} | {m.group(0).lower() for m in TOOL_EXTRA.finditer(text)})
    fn_strong = sorted({m.group(0) for m in FN_STRONG.finditer(text)}) if a.arm == "FN" else []
    fn_ordinary = sorted({m.group(0).lower() for m in FN_ORDINARY.finditer(text)}) if a.arm == "FN" else []

    cp = os.path.join(a.results, "cells_F.csv")
    cells = read_cells(cp)
    cell = f"{a.arm}-{a.model}-{a.run}-b{derived}"
    clash = next((c["recv"] for c in cells if c["status"] == "data" and (c["arm"], c["model"], c["run"], c["batch"]) ==
                  (a.arm, a.model, str(a.run), str(derived))), None)
    same = {}
    for c in cells:
        if c["status"] != "data" or c["batch"] != str(derived):
            continue
        pj = os.path.join(a.results, "parsed_f", f"{c['recv']}.json")
        if os.path.exists(pj):
            old = json.load(open(pj, encoding="utf-8"))["answers"]
            k = sum(1 for i, v in ans.items() if v["phrase"] and i in old and (old[i]["place"], old[i]["phrase"]) == (v["place"], v["phrase"]))
            if k:
                same[c["recv"]] = k

    if dup_of:
        notes.append(f"DUPLICATE: byte-identical to {dup_of}; kept on file, not counted")
    else:
        if not ids:
            severe.append("NO ANSWER LINES FOUND (no line starts with an item number F01-F40)")
        elif len(ids) != 20 or missing or strays or unknown:
            severe.append(f"ITEMS: found {len(ids)} of the 20 of batch {derived}, missing {missing or 'none'}, "
                          f"not in this batch {strays or 'none'}")
        if dups:
            severe.append(f"ITEM ANSWERED MORE THAN ONCE: {dups} (the first line is kept in parsed_f; a person decides)")
        if len(unread) >= 4:
            severe.append(f"{len(unread)} PLACES COULD NOT BE READ: {[(i, ans[i]['place_raw'][:30]) for i in unread]}")
        if names_in_other:
            severe.append(f"A LINE THAT IS NOT AN ANSWER NAMES AN ITEM (a correction note?): {names_in_other[:3]}")
        if tool:
            severe.append(f"SEARCH OR CODE-RUN WORDS: {tool[:6]}")
        if fn_strong:
            severe.append(f"GUIDE WORDS IN AN FN REPLY: {fn_strong[:6]} (check for exposure)")
        if clash:
            severe.append(f"CELL ALREADY FILLED by {clash}: {cell}. Not added as data; ask the user (re-run? mislabel?)")
        big = {k: v for k, v in same.items() if v >= 8}
        if big:
            severe.append(f"SAME PLACE AND PHRASE AS AN EARLIER REPLY on {big} items (possible re-send or mix-up)")
        if 1 <= len(unread) <= 3:
            notes.append(f"unreadable place(s), counted as no place named: {[(i, ans[i]['place_raw'][:30]) for i in unread]}")
        if a.arm == "FN" and fn_ordinary:
            notes.append(f"ordinary word(s) that the guide also uses, in an FN reply: {fn_ordinary} (read them in context)")
        if a.given_batch and a.given_batch != derived:
            notes.append(f"LABEL MISMATCH: label says batch {a.given_batch}, the item numbers say batch {derived} (item numbers rule)")
        if not in_order and ids:
            notes.append("answers are not in packet order (counts the same)")
        if over:
            notes.append(f"phrase over {PHRASE_LIMIT} words on {over} (cut after word {PHRASE_LIMIT} before judging; the place still counts)")
        if r["pre"]:
            notes.append(f"TEXT BEFORE ITEM 1: {[s[:60] for _, s in r['pre'][:3]]}")
        if r["post"] and not names_in_other:
            notes.append(f"TEXT AFTER THE FIRST ANSWER THAT IS NOT AN ANSWER: {[s[:60] for _, s in r['post'][:3]]}")
        for nt in r["notes"]:
            notes.append("form: " + nt)
    flags = severe + notes

    # ---- report
    print(f"{rid} <- {a.label or fname}   sha256 {s16}   {len(data)} bytes")
    print(f"cell: {cell}   derived batch: {derived}   answers: {len(ids)} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   packet order: {in_order}")
    print(f"places named: {len(named)}   none: {none_n}   unreadable: {len(unread)}   phrase words: "
          + (f"min {min(pw.values())} max {max(pw.values())}" if pw else "-") + f"   over {PHRASE_LIMIT}: {len(over)}")
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
    lp, cp = ensure_files(a.results, False)
    dst = os.path.join(a.results, fname)
    with open(dst, "xb") as f:
        f.write(data)
    os.chmod(dst, 0o444)
    status = f"duplicate-of-{dup_of}" if dup_of else ("conflict" if clash else ("review" if severe else "data"))
    if not dup_of:
        json.dump({"source": dst, "sha256": sha, "preamble": r["pre"], "other_lines_after_first_answer": r["post"], "duplicates": dups,
                   "form_notes": r["notes"], "order": ids, "answers": ans},
                  open(os.path.join(a.results, "parsed_f", f"{rid}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(cp, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([rid, a.arm if not dup_of else "", a.model if not dup_of else "", a.run if not dup_of else "",
                                derived if not dup_of else "", status, "no" if not dup_of else "", fname, s16])
    lines = open(lp, encoding="utf-8").read().split("\n")
    how = "Attached as a file." if a.how == "attached" else "Pasted inline; saved by me from the message text."
    if dup_of:
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | same as {dup_of} | - | same cell as {dup_of} | "
               f"DUPLICATE: byte-identical to {dup_of}. Not new data. |")
        para = None
    else:
        span = (f"{ids[0]}-{ids[-1]}, {len(ids)} of 20, " + ("in order" if in_order else "NOT in order")) if ids else "no answer lines"
        ok = ("HELD FOR REVIEW: " + "; ".join(f.split(":")[0] for f in severe) + "." if severe
              else ("OK, with notes: " + "; ".join(f.split(":")[0] for f in notes) + "." if notes else "OK."))
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | {span} | {derived} | {cell} | {ok} {how} "
               f"Not a duplicate of any earlier file (checked against all {len(existing)}). |")
        para = [f"{rid} (arm {a.arm}, {model}, run {a.run}): {len(ids)} of 20 answers ({ids[0] + '-' + ids[-1] if ids else 'none'}), "
                f"{'no item answered twice' if not dups else 'ITEMS ANSWERED TWICE ' + str(dups)}, {'packet order' if in_order else 'NOT in packet order'}. "
                f"Places named {len(named)}, none {none_n}, unreadable {len(unread)}"
                f"{' ' + str([(i, ans[i]['place_raw'][:30]) for i in unread]) if unread else ''}. "
                f"{'Nothing before the first answer or after it.' if not other else 'Other lines: ' + str(len(r['pre'])) + ' before the first answer, ' + str(len(r['post'])) + ' after it.'} "
                f"Phrase words {min(pw.values()) if pw else 0} to {max(pw.values()) if pw else 0}"
                f"{'' if not over else ', OVER ' + str(PHRASE_LIMIT) + ': ' + str(over)}. "
                f"{'No search or code-run words.' if not tool else 'Search or code-run words: ' + str(tool[:6]) + '.'} "
                f"{('Flags: ' + '; '.join(flags) + '. ') if flags else ''}Answers parsed to parsed_f/{rid}.json."]
    lines = add_row(lines, row)
    if para:
        lines = rin.insert_before_heading(lines, "## Metadata the protocol asks for", para, blank_before=True)
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"written: {fname} (read-only), " + ("" if dup_of else f"parsed_f/{rid}.json, ") + f"cells_F.csv row ({status}), received_log_F.md row"
          + (" and form-check paragraph" if para else ""))


if __name__ == "__main__":
    main()
