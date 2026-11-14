#!/usr/bin/env python3
"""One-pass intake of a reply to a writing-test packet (arm P), or of a STEP 2 answer in a P chat.
FORM ONLY: this tool never runs the checker, never opens a key and never scores. The validity run is a separate step after the last P reply (check_p.py).
Rules: P_handling_rules.md (same folder as the results).

Reply:
  python3 -I intake_p.py --results DIR --src FILE --model gemini --run 2 [--given-batch 1] \
      --label "Gemini run 2 P batch 1" --received "2026-11-14 10:05" --how attached|inline --guide attached|pasted|unknown [--note "model version ..."] [--dry-run]
  Saves the file as recvNN_label-<label>.txt (read-only; NN comes from the same counter as the other tests), hashes it, compares it with every earlier recv file (duplicates),
  parses it (tools/parse_p_reply.py), runs the form checks, writes parsed_p/recvNN.json, adds a row to cells_P.csv and a table row and a paragraph to received_log_P.md.
A reply that was cut off and continued:
  python3 -I intake_p.py ... --src PART2.txt --continues recvNN     (recvNN = the first part, or any earlier part)
  Files the second part as its own recvMM, joins all the parts of that reply by the rule of section D, parses them again, rewrites parsed_p/ of the FIRST part,
  and re-evaluates the first part's row (a hold that came from the cut-off is lifted if nothing else is wrong).
STEP 2 answer (every P chat):
  python3 -I intake_p.py --results DIR --step2 "104 roots, section 7" --model gemini --run 2 --received "10:01" [--guide attached|pasted|unknown] [--note ...] [--dry-run]
The item numbers decide the batch, not the label. A conflict, a hold or a mismatch is reported and left for a person to settle.
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_p_reply as pp   # noqa: E402
import intake as rin         # noqa: E402  (helpers shared with the reading-test intake)

MODEL_NAMES = rin.MODEL_NAMES
HEADER = ["recv", "arm", "model", "run", "batch", "status", "run_assumed", "file", "sha256_16", "parts", "guide", "note"]
LOG_TEMPLATE = """# Writing test (arm P): received log

Created {today}. One row per file received, in the order received. The recvNN counter is shared with the other tests (same folder, same counter), so a number is never used twice.
The cells are in cells_P.csv; parsed replies are in parsed_p/. The handling rules are in P_handling_rules.md (sha256 {rules} when this log was created) and are the same for every model and run.
Nothing in this log runs the checker or scores a reply: the validity run is done once, after the last P reply (check_p.py). intake_p.py never opens a key.

| recv | received | label as the user wrote it | file | sha256 (16) | items | batch | cell | form check |
|---|---|---|---|---|---|---|---|---|

## Form-check notes (one paragraph per file)

## Metadata the protocol asks for

## Handling decisions
"""


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def add_row(lines, row):
    last = max((i for i, l in enumerate(lines) if re.match(r"^\| recv\d+ \|", l)), default=None)
    if last is None:
        last = next((i for i, l in enumerate(lines) if re.match(r"^\|[-| ]+\|\s*$", l)), None)
    if last is None:
        sys.exit("no table found in received_log_P.md")
    return lines[:last + 1] + [row] + lines[last + 1:]


def ensure_files(results, dry):
    lp = os.path.join(results, "received_log_P.md")
    cp = os.path.join(results, "cells_P.csv")
    if not dry:
        if not os.path.exists(lp):
            rules = os.path.join(results, "P_handling_rules.md")
            open(lp, "w", encoding="utf-8").write(LOG_TEMPLATE.format(
                today=datetime.date.today().isoformat(), rules=(sha_file(rules) if os.path.exists(rules) else "NOT FOUND")))
        if not os.path.exists(cp):
            with open(cp, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(HEADER)
        os.makedirs(os.path.join(results, "parsed_p"), exist_ok=True)
    return lp, cp


def read_cells(cp):
    if not os.path.exists(cp):
        return []
    return list(csv.DictReader(open(cp, newline="", encoding="utf-8")))


def write_cells(cp, rows):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cp), prefix=".cells_P_", suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})
    os.replace(tmp, cp)


def do_step2(a):
    txt = a.step2.strip()
    ok = bool(re.search(r"\b104\b", txt)) and bool(re.search(r"(?i)(section|sec\.|§)\s*7\b", txt))
    model = MODEL_NAMES.get(a.model, a.model)
    extra = f" Guide given: {a.guide}." + (f" Note: {a.note}." if a.note else "")
    line = (f"{model} P run {a.run}: STEP 2 answer given {a.received}, {'correct' if ok else 'WRONG'}: \"{txt}\"{extra}"
            + ("" if a.guide != "unknown" else " How the guide was given not stated."))
    print(f"STEP 2 {model} P run {a.run}: {'CORRECT (104 roots, section 7)' if ok else 'WRONG'}")
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
    print("  logged in received_log_P.md (Metadata)")


def evaluate(r, a, cell_clash, dup_of=None):
    """-> (severe, notes) from a parse result r. Rule 7 of P_handling_rules.md."""
    severe, notes = [], []
    if dup_of:
        return severe, [f"DUPLICATE: byte-identical to {dup_of}; kept on file, not counted"]
    ids = r["order"]
    if not r["headings"]:
        severe.append("NO ITEM HEADING FOUND (no line holds only #NN)")
    if r["unknown"] or r["strays"]:
        severe.append(f"HEADINGS OUTSIDE ONE BATCH: not in batch {r['derived_batch']}: {r['strays'] or 'none'}; outside #01-#40: {r['unknown'] or 'none'}")
    if r["orphans"]:
        severe.append(f"{len(r['orphans'])} BLOCK(S) BEFORE ANY HEADING (first has {r['orphans'][0]['raw_lines']} lines)")
    multi_orphans = [o for o in r["orphans"] if o["heading_lines"] >= 2]
    if r["multi_item_blocks"] or multi_orphans:
        severe.append(f"A BLOCK HOLDS SEVERAL ITEM HEADINGS: in {r['multi_item_blocks'] or 'a block before any heading'} "
                      f"({multi_orphans[0]['heading_lines'] if multi_orphans else ''} heading lines inside)")
    if r["inline_heads"]:
        severe.append(f"LINES THAT START LIKE AN ITEM NUMBER BUT HOLD MORE TEXT (a heading must be alone on its line): {r['inline_heads'][:3]}")
    found = [i for i in r["expect"] if i in r["items"] and r["items"][i]["status"] != "missing"]
    if r["headings"] and len(found) < 20:
        severe.append(f"FEWER THAN 20 ITEMS: {len(found)} of the 20 of batch {r['derived_batch']}, missing {r['missing'] or 'none'} (cut off? ask the user)")
    if r["open_at_end"]:
        severe.append("THE REPLY ENDS INSIDE AN OPEN BLOCK (cut off? ask the user for the continuation)")
    if r["tool_words"]:
        severe.append(f"SEARCH OR CODE-RUN WORDS: {r['tool_words'][:6]}")
    if cell_clash:
        severe.append(f"CELL ALREADY FILLED by {cell_clash}: P-{a.model}-{a.run}-b{r['derived_batch']}. Not added as data; ask the user (re-run? mislabel?)")
    given = getattr(a, "given_batch", None)
    if given and given != r["derived_batch"]:
        notes.append(f"LABEL MISMATCH: label says batch {given}, the item numbers say batch {r['derived_batch']} (item numbers rule)")
    pre_plain = [p for p in r["pre"] if p["text"] not in r["status_lines"]]
    if r["status_lines"]:
        notes.append(f"app status line(s) before item 1 (not part of the reply): {r['status_lines'][:2]}")
    if pre_plain:
        notes.append(f"TEXT BEFORE ITEM 1: {[p['text'][:60] for p in pre_plain[:3]]}")
    if r["trailing"]:
        notes.append(f"TEXT AFTER THE LAST ITEM'S BLOCK ({len(r['trailing'])} lines): {[o['text'].strip()[:60] for o in r['trailing'][:2]]}")
    if r["outside_count"] and not r["trailing"]:
        notes.append(f"{r['outside_count']} line(s) of text outside the blocks (not SILEX; not checked)")
    if ids and not r["in_order"]:
        notes.append("items are not in packet order (counts the same)")
    for d in r["dups"]:
        notes.append(f"ITEM {d['id']} HAS {d['headings']} HEADINGS: heading {d['kept_heading']} kept ({d['reason']})")
    if r["inner_heads"]:
        ih = sorted(set(r["inner_heads"]))
        notes.append(f"HEADING INSIDE THE BLOCK in {len(r['inner_heads'])} block(s) {ih[:6]}{'...' if len(ih) > 6 else ''} (read as the heading, not as a comment)")
    unf = [i for i in ids if r["items"][i]["status"] == "unfenced"]
    if unf:
        notes.append(f"NO FENCE in {unf} (text under the heading is taken as the item)")
    split = [i for i in ids if len(r["items"][i]["blocks"]) > 1 and r["items"][i]["status"] == "block"]
    if split:
        notes.append(f"SPLIT ITEMS (several blocks under one heading, each checked on its own): {split}")
    for j in r["joins"]:
        notes.append(f"PART {j['part']} JOINED ({j['kind']}); first line {j['first_line']!r}")
    return severe, notes


def counts(r):
    blocks = [b for i in r["order"] for b in r["items"][i]["blocks"]]
    return {
        "items_found": sum(1 for i in r["order"] if r["items"][i]["status"] != "missing"),
        "none": sum(1 for b in blocks if b["none"]),
        "empty": sum(1 for b in blocks if b["empty"] and not b["none"]),
        "comment_lines": sum(len(b["comments"]) for b in blocks),
        "blocks_with_comments": sum(1 for b in blocks if b["comments"]),
        "chars": [b["chars"] for b in blocks if not b["none"] and not b["empty"]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--src")
    ap.add_argument("--step2")
    ap.add_argument("--arm", choices=["P"], default="P")
    ap.add_argument("--model", required=True, choices=list(MODEL_NAMES))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--given-batch", type=int, choices=[1, 2])
    ap.add_argument("--label", default="")
    ap.add_argument("--received", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--how", choices=["attached", "inline"], default="attached")
    ap.add_argument("--guide", choices=["attached", "pasted", "unknown"], default="unknown")
    ap.add_argument("--note", default="")
    ap.add_argument("--continues")
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
    fname = f"{rid}_label-{rin.slug(a.label or f'{model}_P_run_{a.run}')}.txt"
    cp = os.path.join(a.results, "cells_P.csv")
    cells = read_cells(cp)
    dup_of = next((os.path.basename(p)[:6] for p in existing if open(p, "rb").read() == data), None)

    # ---- which parts make up this reply
    root = None
    texts = [text]
    if a.continues and not dup_of:
        row = next((c for c in cells if c["recv"] == a.continues), None)
        if row is None:
            sys.exit(f"--continues {a.continues}: no such row in cells_P.csv")
        if row["status"].startswith("continuation-of-"):
            row = next(c for c in cells if c["recv"] == row["status"].split("-of-")[1])
        if row["status"].startswith("duplicate-of-") or row["status"] == "conflict":
            sys.exit(f"--continues {a.continues}: that row is a {row['status']}, not a first part")
        if (row["model"], row["run"]) != (a.model, str(a.run)):
            sys.exit(f"--continues {row['recv']}: that reply is {row['model']} run {row['run']}, not {a.model} run {a.run}")
        root = row
        texts = [open(os.path.join(a.results, root["file"]), encoding="utf-8").read()]
        for c in cells:
            if c["status"] == f"continuation-of-{root['recv']}":
                texts.append(open(os.path.join(a.results, c["file"]), encoding="utf-8").read())
        texts.append(text)
    r = pp.parse_parts(texts)
    derived = r["derived_batch"]
    cell = f"P-{a.model}-{a.run}-b{derived}"
    clash = None
    if not root and not dup_of:
        clash = next((c["recv"] for c in cells if c["status"] == "data" and (c["arm"], c["model"], c["run"], c["batch"]) ==
                      ("P", a.model, str(a.run), str(derived))), None)
    if root and (root["batch"] != str(derived)) and r["headings"]:
        print(f"WARNING: the joined reply says batch {derived}, the first part was filed as batch {root['batch']}")
    severe, notes = evaluate(r, a, clash, dup_of)
    ct = counts(r)
    ids = r["order"]

    # ---- report
    print(f"{rid} <- {a.label or fname}   sha256 {s16}   {len(data)} bytes" + (f"   (continues {root['recv']})" if root else ""))
    print(f"cell: {cell}   derived batch: {derived}   headings: {len(r['headings'])} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   "
          f"items with SILEX text: {ct['items_found']} of 20   packet order: {r['in_order']}")
    print(f"NONE blocks: {ct['none']}   empty: {ct['empty']}   comment lines: {ct['comment_lines']} in {ct['blocks_with_comments']} block(s)   "
          + (f"chars per item: min {min(ct['chars'])} max {max(ct['chars'])}" if ct["chars"] else "chars: -"))
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
    parser_sha = sha_file(os.path.join(HERE, "parse_p_reply.py"))[:16]
    first = root["recv"] if root else rid
    if dup_of:
        status = f"duplicate-of-{dup_of}"
    elif root:
        status = f"continuation-of-{first}"
    else:
        status = "conflict" if clash else ("review" if severe else "data")
    parts_list = [first] + [c["recv"] for c in cells if c["status"] == f"continuation-of-{first}"] + ([rid] if root else [])
    part_files = ([root["file"]] + [c["file"] for c in cells if c["status"] == f"continuation-of-{first}"] + [fname]) if root else [fname]
    meta = {"files": part_files, "sha256_of_this_file": sha, "parser_sha16": parser_sha, "label": a.label, "received": a.received, "how": a.how,
            "guide": a.guide, "note": a.note, "parts": parts_list if root else [rid], "cell": cell}
    if not dup_of:
        out = dict(meta)
        out.update({"parse": r, "severe": severe, "notes": notes})
        json.dump(out, open(os.path.join(a.results, "parsed_p", f"{first}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = read_cells(cp)
    if root:
        for rw in rows:
            if rw["recv"] == first:
                rw["parts"] = "+".join(parts_list)
                if rw["status"] in ("review", "data"):
                    rw["status"] = "review" if severe else "data"
                rw["batch"] = str(derived)
    rows.append({"recv": rid, "arm": "P" if not dup_of else "", "model": a.model if not dup_of else "", "run": a.run if not dup_of else "",
                 "batch": derived if not dup_of else "", "status": status, "run_assumed": "no" if not dup_of else "", "file": fname, "sha256_16": s16,
                 "parts": rid if not root else "", "guide": a.guide, "note": a.note})
    write_cells(cp, rows)
    lines = open(lp, encoding="utf-8").read().split("\n")
    how = "Attached as a file." if a.how == "attached" else "Pasted inline; saved by me from the message text."
    if dup_of:
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | same as {dup_of} | - | same cell as {dup_of} | "
               f"DUPLICATE: byte-identical to {dup_of}. Not new data. |")
        para = None
    else:
        span = (f"{ids[0]}-{ids[-1]}, {ct['items_found']} of 20 with text, " + ("in order" if r["in_order"] else "NOT in order")) if ids else "no headings"
        tag = ("HELD FOR REVIEW: " + "; ".join(x.split(":")[0] for x in severe) + "." if severe
               else ("OK, with notes: " + "; ".join(x.split(":")[0] for x in notes) + "." if notes else "OK."))
        if root:
            tag = f"CONTINUATION of {first} (joined; {first} now {'HELD' if severe else 'data'}). " + tag
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | {span} | {derived} | {cell} | {tag} {how} Guide given: {a.guide}."
               f"{(' ' + a.note + '.') if a.note else ''} Not a duplicate of any earlier file (checked against all {len(existing)}). |")
        para = [f"{rid} (arm P, {model}, run {a.run}{', continuation of ' + first if root else ''}): "
                f"{len(r['headings'])} heading(s) ({ids[0] + '-' + ids[-1] if ids else 'none'}), {ct['items_found']} of 20 items with SILEX text, "
                f"{'packet order' if r['in_order'] else 'NOT in packet order'}. "
                f"NONE blocks {ct['none']}, empty blocks {ct['empty']}, comment lines {ct['comment_lines']} in {ct['blocks_with_comments']} block(s), "
                f"{sum(1 for i in ids if r['items'][i]['status'] == 'unfenced')} unfenced, "
                f"{sum(1 for i in ids if len(r['items'][i]['blocks']) > 1)} split, "
                f"{'no repeated heading' if not r['dups'] else str(len(r['dups'])) + ' repeated heading(s)'}. "
                f"{'No search or code-run words.' if not r['tool_words'] else 'Search or code-run words: ' + str(r['tool_words'][:6]) + '.'} "
                f"{('Flags: ' + '; '.join(severe + notes) + '. ') if (severe or notes) else ''}Parsed to parsed_p/{first}.json (parser {parser_sha}). "
                f"The checker has not been run on it."]
    lines = add_row(lines, row)
    if para:
        lines = rin.insert_before_heading(lines, "## Metadata the protocol asks for", para, blank_before=True)
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"written: {fname} (read-only), " + ("" if dup_of else f"parsed_p/{first}.json, ") + f"cells_P.csv row ({status}), received_log_P.md row"
          + (" and form-check paragraph" if para else ""))


if __name__ == "__main__":
    main()
