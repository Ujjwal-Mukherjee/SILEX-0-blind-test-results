#!/usr/bin/env python3
"""Re-read a held English-baseline (arm E) reply with the current parser (Note 1 of E_handling_rules.md, 2026-11-14) and lift the hold if nothing else is wrong.
FORM ONLY. Never opens a key and never scores. The saved reply file is never touched.

  python3 -I reparse_e.py --results DIR --recv recvNN [--when "2026-11-14 09:05"] [--dry-run]

Only a row that is held (status review), a single-part reply, can be re-read. The old parse is kept as parsed_e/recvNN.before_note1.json (read-only),
parsed_e/recvNN.json is rewritten with the current parser, the row becomes data (and its batch is the one the item numbers give) when no hold remains,
and a form-check paragraph and a dated line in "Handling decisions" are added to received_log_E.md. If a hold remains, nothing is changed.
"""
import argparse, datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import intake_e as ie     # noqa: E402
import intake as rin      # noqa: E402
import parse_e_reply as pe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--recv", required=True)
    ap.add_argument("--when", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cp = os.path.join(a.results, "cells_E.csv")
    rows = ie.read_cells(cp)
    row = next((r for r in rows if r["recv"] == a.recv), None)
    if row is None:
        sys.exit(f"no such row: {a.recv}")
    if row["status"] != "review":
        sys.exit(f"{a.recv} is {row['status']}: only a held reply (status review) can be re-read")
    if row["parts"] not in ("", a.recv):
        sys.exit(f"{a.recv} is made of several parts ({row['parts']}): not supported here, settle it with settle_e.py")
    jp = os.path.join(a.results, "parsed_e", f"{a.recv}.json")
    old = json.load(open(jp, encoding="utf-8"))
    path = os.path.join(a.results, row["file"])
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != old["sha256_of_this_file"]:
        sys.exit(f"{row['file']} no longer has the hash recorded in {jp}: stop")
    r = pe.parse_parts([data.decode("utf-8")])
    derived = r["derived_batch"]
    mb = re.search(r"batch\D{0,3}(\d)", old.get("label", ""), re.I)

    class A:   # what intake_e.evaluate reads
        model, run = row["model"], int(row["run"])
        given_batch = int(mb.group(1)) if mb else None
        continues = None

    clash = next((c["recv"] for c in rows if c["recv"] != a.recv and c["status"] == "data" and (c["arm"], c["model"], c["run"], c["batch"]) ==
                  ("E", row["model"], row["run"], str(derived))), None)
    severe, notes = ie.evaluate(r, A, clash, None)
    ct = ie.counts(r)
    ids = r["order"]
    cell = f"E-{row['model']}-{row['run']}-b{derived}"
    print(f"{a.recv} <- {old.get('label', row['file'])}   cell {cell}   derived batch {derived} (was {row['batch']})   headings {len(r['headings'])} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   "
          f"items with text {ct['with_text']} of 20   packet order {r['in_order']}")
    print(f"NONE items {ct['none']}   empty {ct['empty']}   message lines {ct['msg_lines']}   "
          + (f"chars per item: min {min(ct['chars'])} max {max(ct['chars'])}, words per item: min {min(ct['words'])} max {max(ct['words'])}" if ct["chars"] else "chars: -"))
    print("STILL HELD:" if severe else "no hold remains")
    for f in severe:
        print("  - " + f)
    print("notes:" if notes else "notes: none")
    for f in notes:
        print("  - " + f)
    if severe:
        print("nothing changed")
        sys.exit(1)
    if a.dry_run:
        print("(dry run, nothing written)")
        return
    lp = os.path.join(a.results, "received_log_E.md")
    parser_sha = ie.sha_file(os.path.join(HERE, "parse_e_reply.py"))[:16]
    keep = os.path.join(a.results, "parsed_e", f"{a.recv}.before_note1.json")
    if os.path.exists(keep):
        sys.exit(f"{keep} exists: this reply was already re-read")
    os.replace(jp, keep)
    os.chmod(keep, 0o444)
    new = dict(old)
    new.update({"parser_sha16": parser_sha, "cell": cell, "parse": r, "severe": severe, "notes": notes,
                "reread": {"when": a.when, "under": "Note 1 of E_handling_rules.md", "old_parser_sha16": old.get("parser_sha16"), "old_parse_kept_as": os.path.basename(keep)}})
    json.dump(new, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    was = row["status"], row["batch"]
    row["status"], row["batch"] = "data", str(derived)
    ie.write_cells(cp, rows)
    model = ie.MODEL_NAMES[row["model"]]
    lines = open(lp, encoding="utf-8").read().split("\n")
    para = (f"{a.recv} re-read under Note 1 of the E rules ({a.when}; arm E, {model}, run {row['run']}): {len(r['headings'])} heading(s) ({ids[0]}-{ids[-1]}), "
            f"{ct['with_text']} of 20 items with text, {'packet order' if r['in_order'] else 'NOT in packet order'}. NONE items {ct['none']}, empty items {ct['empty']}, "
            f"message lines {ct['msg_lines']} (counted per line: an item written on one line counts 1), "
            f"{sum(1 for i in ids if r['items'][i]['status'] == 'block')} fenced, {sum(1 for i in ids if len(r['items'][i]['blocks']) > 1)} split, "
            f"{'no repeated heading' if not r['dups'] else str(len(r['dups'])) + ' repeated heading(s)'}. "
            f"{'No search or code-run words outside the items.' if not r['tool_words'] else 'Search or code-run words: ' + str(r['tool_words'][:6]) + '.'} "
            f"Flags: {'; '.join(notes) if notes else 'none'}. Parsed to parsed_e/{a.recv}.json (parser {parser_sha}); the first parse (parser {old.get('parser_sha16')}) is kept as "
            f"parsed_e/{os.path.basename(keep)}.")
    lines = rin.insert_before_heading(lines, "## Metadata the protocol asks for", [para], blank_before=True)
    i = lines.index("## Handling decisions")
    j = i + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1
    e = j
    while e > i + 1 and lines[e - 1] == "":
        e -= 1
    dec = (f"- {a.when}: {a.recv} (E-{row['model']}-{row['run']}-b{derived}) re-read under Note 1 of the E rules (the user agreed 2026-11-14 08:42): {was[0]} -> data, "
           f"batch {was[1]} -> {derived}. {ct['with_text']} of 20 items; the first parse is kept as parsed_e/{os.path.basename(keep)}.")
    lines[e:e] = [dec]
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{a.recv}: review -> data, batch {was[1]} -> {derived}; parsed_e/{a.recv}.json rewritten, old parse kept; logged in received_log_E.md")


if __name__ == "__main__":
    main()
