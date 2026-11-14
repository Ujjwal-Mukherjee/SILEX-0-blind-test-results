#!/usr/bin/env python3
"""One-pass intake of a reply to an English-baseline packet (arm E).
FORM ONLY: this tool never opens a key and never scores. Arm E has no checker and no validity run.
Rules: E_handling_rules.md (same folder as the results). Built on intake_p.py; the differences are the item text (rules 9 to 13) and the hold list (rule 7).

Reply:
  python3 -I intake_e.py --results DIR --src FILE --model gemini --run 1 [--given-batch 1] \
      --label "Gemini E batch 1" --received "2026-11-14 10:05" --how attached|inline [--note "model version, setting ..."] [--dry-run]
  Saves the file as recvNN_label-<label>.txt (read-only; NN comes from the same counter as the other tests), hashes it, compares it with every earlier recv file (duplicates),
  parses it (tools/parse_e_reply.py), runs the form checks, writes parsed_e/recvNN.json, adds a row to cells_E.csv and a table row and a paragraph to received_log_E.md.
A reply that was cut off and continued:
  python3 -I intake_e.py ... --src PART2.txt --continues recvNN     (recvNN = the first part, or any earlier part)
  Files the second part as its own recvMM, joins all the parts of that reply by rule 14, parses them again, rewrites parsed_e/ of the FIRST part,
  and re-evaluates the first part's row (a hold that came from the cut-off is lifted if nothing else is wrong).
The item numbers decide the batch, not the label. A conflict, a hold or a mismatch is reported and left for a person to settle (tools/settle_e.py).
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_e_reply as pe   # noqa: E402
import intake as rin         # noqa: E402  (helpers shared with the other intake tools)

MODEL_NAMES = rin.MODEL_NAMES
HEADER = ["recv", "arm", "model", "run", "batch", "status", "run_assumed", "file", "sha256_16", "parts", "guide", "note"]
LOG_TEMPLATE = """# English baseline (arm E): received log

Created {today}. One row per file received, in the order received. The recvNN counter is shared with the other tests (same folder, same counter), so a number is never used twice.
The cells are in cells_E.csv; parsed replies are in parsed_e/. The handling rules are in E_handling_rules.md (sha256 {rules} when this log was created) and are the same for every model.
Arm E has no checker and no validity run: the measures are the length and the round trip. intake_e.py never opens a key.

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
        sys.exit("no table found in received_log_E.md")
    return lines[:last + 1] + [row] + lines[last + 1:]


def ensure_files(results, dry):
    lp = os.path.join(results, "received_log_E.md")
    cp = os.path.join(results, "cells_E.csv")
    if not dry:
        if not os.path.exists(lp):
            rules = os.path.join(results, "E_handling_rules.md")
            open(lp, "w", encoding="utf-8").write(LOG_TEMPLATE.format(
                today=datetime.date.today().isoformat(), rules=(sha_file(rules) if os.path.exists(rules) else "NOT FOUND")))
        if not os.path.exists(cp):
            with open(cp, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(HEADER)
        os.makedirs(os.path.join(results, "parsed_e"), exist_ok=True)
    return lp, cp


def read_cells(cp):
    if not os.path.exists(cp):
        return []
    return list(csv.DictReader(open(cp, newline="", encoding="utf-8")))


def write_cells(cp, rows):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cp), prefix=".cells_E_", suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})
    os.replace(tmp, cp)


def evaluate(r, a, cell_clash, dup_of=None):
    """-> (severe, notes) from a parse result r. Rule 7 of E_handling_rules.md."""
    severe, notes = [], []
    if dup_of:
        return severe, [f"DUPLICATE: byte-identical to {dup_of}; kept on file, not counted"]
    ids = r["order"]
    if not r["headings"]:
        severe.append("NO ITEM HEADING FOUND (no line holds only #NN)")
    if r["unknown"] or r["strays"]:
        severe.append(f"HEADINGS OUTSIDE ONE BATCH: not in batch {r['derived_batch']}: {r['strays'] or 'none'}; outside #01-#40: {r['unknown'] or 'none'}")
    if r["orphans"]:
        severe.append(f"{len(r['orphans'])} FENCED BLOCK(S) BEFORE ANY HEADING (first has {r['orphans'][0]['raw_lines']} lines)")
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
        severe.append("THE REPLY ENDS INSIDE AN OPEN FENCE (cut off? ask the user for the continuation)")
    if r["tool_words"]:
        severe.append(f"SEARCH OR CODE-RUN WORDS (outside the items): {r['tool_words'][:6]}")
    if cell_clash:
        severe.append(f"CELL ALREADY FILLED by {cell_clash}: E-{a.model}-{a.run}-b{r['derived_batch']}. Not added as data; ask the user (re-run? mislabel?)")
    given = getattr(a, "given_batch", None)
    if given and given != r["derived_batch"]:
        notes.append(f"LABEL MISMATCH: label says batch {given}, the item numbers say batch {r['derived_batch']} (item numbers rule)")
    if r.get("inline_first"):
        notes.append(f"NUMBER AND FIRST MESSAGE ON ONE LINE (Note 1 of the E rules, counted as they stand): {len(r['inline_first'])} item(s), first {r['inline_first'][:3]}; "
                     "message lines are counted per line, so these items count 1")
    pre_plain = [p for p in r["pre"] if p["text"] not in r["status_lines"]]
    if r["status_lines"]:
        notes.append(f"app status line(s) before item 1 (not part of the reply): {r['status_lines'][:2]}")
    if pre_plain:
        notes.append(f"TEXT BEFORE ITEM 1: {[p['text'][:60] for p in pre_plain[:3]]}")
    if r["trailing"]:
        notes.append(f"TEXT AFTER THE LAST ITEM ({len(r['trailing'])} lines, not part of the item): {[t['text'].strip()[:60] for t in r['trailing'][:2]]}")
    if r["outside_count"]:
        notes.append(f"{r['outside_count']} line(s) of text outside the fenced blocks (not part of any item)")
    if ids and not r["in_order"]:
        notes.append("items are not in packet order (counts the same)")
    for d in r["dups"]:
        notes.append(f"ITEM {d['id']} HAS {d['headings']} HEADINGS: heading {d['kept_heading']} kept ({d['reason']})")
    if r["inner_heads"]:
        ih = sorted(set(r["inner_heads"]))
        notes.append(f"HEADING INSIDE THE BLOCK in {len(r['inner_heads'])} block(s) {ih[:6]}{'...' if len(ih) > 6 else ''}")
    fenced = [i for i in ids if r["items"][i]["status"] == "block"]
    if fenced:
        notes.append(f"FENCED ITEMS (English is normally unfenced; the fenced text is the item): {fenced}")
    split = [i for i in ids if len(r["items"][i]["blocks"]) > 1 and r["items"][i]["status"] == "block"]
    if split:
        notes.append(f"SPLIT ITEMS (several fenced blocks under one heading, joined in order): {split}")
    for j in r["joins"]:
        notes.append(f"PART {j['part']} JOINED ({j['kind']}); first line {j['first_line']!r}; look at the junction (rule 14)")
    nomsg = [i for i in ids if r["items"][i]["state"] == "text" and r["items"][i]["messages"] == 0]
    if nomsg:
        notes.append(f"NO MESSAGE LINE (no 'X to Y:' line) in {nomsg}")
    other = [i for i in ids if r["items"][i]["state"] == "text" and r["items"][i]["messages"] > 0 and r["items"][i]["other_lines"] > 0]
    if other:
        notes.append(f"LINES THAT ARE NOT MESSAGE LINES inside {other} (kept as written; listed for the sensitivity check of rule 13)")
    nn = [i for i in ids if r["items"][i]["state"] in ("none", "empty")]
    if nn:
        notes.append(f"NONE OR EMPTY ITEMS: {nn}")
    return severe, notes


def counts(r):
    its = [r["items"][i] for i in r["order"]]
    return {
        "items_found": sum(1 for it in its if it["status"] != "missing"),
        "with_text": sum(1 for it in its if it["state"] == "text"),
        "none": sum(1 for it in its if it["state"] == "none"),
        "empty": sum(1 for it in its if it["state"] == "empty"),
        "chars": [it["chars"] for it in its if it["state"] == "text"],
        "words": [it["words"] for it in its if it["state"] == "text"],
        "msg_lines": sum(it["messages"] for it in its),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--arm", choices=["E"], default="E")
    ap.add_argument("--model", required=True, choices=list(MODEL_NAMES))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--given-batch", type=int, choices=[1, 2])
    ap.add_argument("--label", default="")
    ap.add_argument("--received", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--how", choices=["attached", "inline"], default="attached")
    ap.add_argument("--note", default="")
    ap.add_argument("--continues")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

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
    fname = f"{rid}_label-{rin.slug(a.label or f'{model}_E_run_{a.run}')}.txt"
    cp = os.path.join(a.results, "cells_E.csv")
    cells = read_cells(cp)
    dup_of = next((os.path.basename(p)[:6] for p in existing if open(p, "rb").read() == data), None)

    # ---- which parts make up this reply
    root = None
    texts = [text]
    if a.continues and not dup_of:
        row = next((c for c in cells if c["recv"] == a.continues), None)
        if row is None:
            sys.exit(f"--continues {a.continues}: no such row in cells_E.csv")
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
    r = pe.parse_parts(texts)
    derived = r["derived_batch"]
    cell = f"E-{a.model}-{a.run}-b{derived}"
    clash = None
    if not root and not dup_of:
        clash = next((c["recv"] for c in cells if c["status"] == "data" and (c["arm"], c["model"], c["run"], c["batch"]) ==
                      ("E", a.model, str(a.run), str(derived))), None)
    if root and (root["batch"] != str(derived)) and r["headings"]:
        print(f"WARNING: the joined reply says batch {derived}, the first part was filed as batch {root['batch']}")
    severe, notes = evaluate(r, a, clash, dup_of)
    ct = counts(r)
    ids = r["order"]

    # ---- report
    print(f"{rid} <- {a.label or fname}   sha256 {s16}   {len(data)} bytes" + (f"   (continues {root['recv']})" if root else ""))
    print(f"cell: {cell}   derived batch: {derived}   headings: {len(r['headings'])} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   "
          f"items with text: {ct['with_text']} of 20   packet order: {r['in_order']}")
    print(f"NONE items: {ct['none']}   empty: {ct['empty']}   message lines: {ct['msg_lines']}   "
          + (f"chars per item: min {min(ct['chars'])} max {max(ct['chars'])}, words per item: min {min(ct['words'])} max {max(ct['words'])}" if ct["chars"] else "chars: -"))
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
    parser_sha = sha_file(os.path.join(HERE, "parse_e_reply.py"))[:16]
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
            "note": a.note, "parts": parts_list if root else [rid], "cell": cell}
    if not dup_of:
        out = dict(meta)
        out.update({"parse": r, "severe": severe, "notes": notes})
        json.dump(out, open(os.path.join(a.results, "parsed_e", f"{first}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = read_cells(cp)
    if root:
        for rw in rows:
            if rw["recv"] == first:
                rw["parts"] = "+".join(parts_list)
                if rw["status"] in ("review", "data"):
                    rw["status"] = "review" if severe else "data"
                rw["batch"] = str(derived)
    rows.append({"recv": rid, "arm": "E" if not dup_of else "", "model": a.model if not dup_of else "", "run": a.run if not dup_of else "",
                 "batch": derived if not dup_of else "", "status": status, "run_assumed": "no" if not dup_of else "", "file": fname, "sha256_16": s16,
                 "parts": rid if not root else "", "guide": "none", "note": a.note})
    write_cells(cp, rows)
    lines = open(lp, encoding="utf-8").read().split("\n")
    how = "Attached as a file." if a.how == "attached" else "Pasted inline; saved by me from the message text."
    if dup_of:
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | same as {dup_of} | - | same cell as {dup_of} | "
               f"DUPLICATE: byte-identical to {dup_of}. Not new data. |")
        para = None
    else:
        span = (f"{ids[0]}-{ids[-1]}, {ct['with_text']} of 20 with text, " + ("in order" if r["in_order"] else "NOT in order")) if ids else "no headings"
        tag = ("HELD FOR REVIEW: " + "; ".join(x.split(":")[0] for x in severe) + "." if severe
               else ("OK, with notes: " + "; ".join(x.split(":")[0] for x in notes) + "." if notes else "OK."))
        if root:
            tag = f"CONTINUATION of {first} (joined; {first} now {'HELD' if severe else 'data'}). " + tag
        row = (f"| {rid} | {a.received} | {a.label or fname} | {fname} | {s16} | {span} | {derived} | {cell} | {tag} {how} No guide (arm E)."
               f"{(' ' + a.note + '.') if a.note else ''} Not a duplicate of any earlier file (checked against all {len(existing)}). |")
        para = [f"{rid} (arm E, {model}, run {a.run}{', continuation of ' + first if root else ''}): "
                f"{len(r['headings'])} heading(s) ({ids[0] + '-' + ids[-1] if ids else 'none'}), {ct['with_text']} of 20 items with text, "
                f"{'packet order' if r['in_order'] else 'NOT in packet order'}. "
                f"NONE items {ct['none']}, empty items {ct['empty']}, message lines {ct['msg_lines']}, "
                f"{sum(1 for i in ids if r['items'][i]['status'] == 'block')} fenced, "
                f"{sum(1 for i in ids if len(r['items'][i]['blocks']) > 1)} split, "
                f"{'no repeated heading' if not r['dups'] else str(len(r['dups'])) + ' repeated heading(s)'}. "
                f"{'No search or code-run words outside the items.' if not r['tool_words'] else 'Search or code-run words: ' + str(r['tool_words'][:6]) + '.'} "
                f"{('Flags: ' + '; '.join(severe + notes) + '. ') if (severe or notes) else ''}Parsed to parsed_e/{first}.json (parser {parser_sha})."]
    lines = add_row(lines, row)
    if para:
        lines = rin.insert_before_heading(lines, "## Metadata the protocol asks for", para, blank_before=True)
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"written: {fname} (read-only), " + ("" if dup_of else f"parsed_e/{first}.json, ") + f"cells_E.csv row ({status}), received_log_E.md row"
          + (" and form-check paragraph" if para else ""))


if __name__ == "__main__":
    main()
