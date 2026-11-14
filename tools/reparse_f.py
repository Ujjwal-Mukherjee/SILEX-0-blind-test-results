#!/usr/bin/env python3
"""Re-read a held Test F reply (status review) with the current parser (Note 1 of Test F, 2026-11-14 18:26) and lift the hold if nothing else is wrong.
FORM ONLY. Never opens the key and never scores. The saved reply file is never touched.

  python3 -I reparse_f.py --results DIR --recv recvNN [--when "2026-11-14 18:40"] [--dry-run]

Only a row that is held (status review) can be re-read. The old parse is kept as parsed_f/recvNN.before_note1.json (read-only),
parsed_f/recvNN.json is rewritten with the current parser, the row becomes data (its batch is the one the item numbers give) when no hold remains,
and a form-check paragraph and a dated line in "Handling decisions" are added to received_log_F.md. If a hold remains, nothing is changed.
The checks are those of intake_f.py (same constants, same conditions); test_f_tools.py checks that the two agree.
"""
import argparse, csv, datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import intake_f as inf      # noqa: E402
import intake as rin        # noqa: E402
import parse_f_reply as pf  # noqa: E402
import parse_reply as pr    # noqa: E402


def evaluate(text, arm, model, run, given_batch, cells, results, exclude):
    """The form checks of intake_f.py on a reply that is already on file (exclude = its own recv number). -> dict."""
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
    over = [i for i, w in pw.items() if w > inf.PHRASE_LIMIT]
    other = r["pre"] + r["post"]
    names_in_other = [(ln, s[:80]) for ln, s in other if inf.names_item(s)]
    tool = sorted({m.group(0).lower() for m in pr.SEARCHY.finditer(text)} | {m.group(0).lower() for m in inf.TOOL_EXTRA.finditer(text)})
    fn_strong = sorted({m.group(0) for m in inf.FN_STRONG.finditer(text)}) if arm == "FN" else []
    fn_ordinary = sorted({m.group(0).lower() for m in inf.FN_ORDINARY.finditer(text)}) if arm == "FN" else []
    cell = f"{arm}-{model}-{run}-b{derived}"
    clash = next((c["recv"] for c in cells if c["recv"] != exclude and c["status"] == "data" and
                  (c["arm"], c["model"], c["run"], c["batch"]) == (arm, model, str(run), str(derived))), None)
    same = {}
    for c in cells:
        if c["recv"] == exclude or c["status"] != "data" or c["batch"] != str(derived):
            continue
        pj = os.path.join(results, "parsed_f", f"{c['recv']}.json")
        if os.path.exists(pj):
            old = json.load(open(pj, encoding="utf-8"))["answers"]
            k = sum(1 for i, v in ans.items() if v["phrase"] and i in old and (old[i]["place"], old[i]["phrase"]) == (v["place"], v["phrase"]))
            if k:
                same[c["recv"]] = k
    severe, notes = [], []
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
    if arm == "FN" and fn_ordinary:
        notes.append(f"ordinary word(s) that the guide also uses, in an FN reply: {fn_ordinary} (read them in context)")
    if given_batch and given_batch != derived:
        notes.append(f"LABEL MISMATCH: label says batch {given_batch}, the item numbers say batch {derived} (item numbers rule)")
    if not in_order and ids:
        notes.append("answers are not in packet order (counts the same)")
    if over:
        notes.append(f"phrase over {inf.PHRASE_LIMIT} words on {over} (cut after word {inf.PHRASE_LIMIT} before judging; the place still counts)")
    if r["pre"]:
        notes.append(f"TEXT BEFORE ITEM 1: {[s[:60] for _, s in r['pre'][:3]]}")
    if r["post"] and not names_in_other:
        notes.append(f"TEXT AFTER THE FIRST ANSWER THAT IS NOT AN ANSWER: {[s[:60] for _, s in r['post'][:3]]}")
    for nt in r["notes"]:
        notes.append("form: " + nt)
    return dict(r=r, derived=derived, cell=cell, ids=ids, ans=ans, severe=severe, notes=notes, in_order=in_order, none_n=none_n,
                named=named, unread=unread, pw=pw, over=over, other=other, dups=dups, tool=tool)


def write_cells(cp, rows):
    with open(cp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(inf.HEADER)
        for row in rows:
            w.writerow([row[h] for h in inf.HEADER])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--recv", required=True)
    ap.add_argument("--when", default=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cp = os.path.join(a.results, "cells_F.csv")
    rows = inf.read_cells(cp)
    row = next((x for x in rows if x["recv"] == a.recv), None)
    if row is None:
        sys.exit(f"no such row: {a.recv}")
    if row["status"] != "review":
        sys.exit(f"{a.recv} is {row['status']}: only a held reply (status review) can be re-read")
    jp = os.path.join(a.results, "parsed_f", f"{a.recv}.json")
    old = json.load(open(jp, encoding="utf-8"))
    path = os.path.join(a.results, row["file"])
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != old["sha256"]:
        sys.exit(f"{row['file']} no longer has the hash recorded in {jp}: stop")
    text = data.decode("utf-8")
    mb = re.search(r"batch\D{0,3}(\d)", row["file"], re.I)
    given = int(mb.group(1)) if mb else None
    ev = evaluate(text, row["arm"], row["model"], int(row["run"]), given, rows, a.results, a.recv)
    r, ids, ans, severe, notes, derived, cell = ev["r"], ev["ids"], ev["ans"], ev["severe"], ev["notes"], ev["derived"], ev["cell"]
    pw = ev["pw"]
    print(f"{a.recv} <- {row['file']}   cell {cell}   derived batch {derived} (was {row['batch']})   answers: {len(ids)} ({ids[0] if ids else '-'}..{ids[-1] if ids else '-'})   packet order: {ev['in_order']}")
    print(f"places named: {len(ev['named'])}   none: {ev['none_n']}   unreadable: {len(ev['unread'])}   phrase words: "
          + (f"min {min(pw.values())} max {max(pw.values())}" if pw else "-") + f"   over {inf.PHRASE_LIMIT}: {len(ev['over'])}")
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
    lp = os.path.join(a.results, "received_log_F.md")
    parser_sha = hashlib.sha256(open(os.path.join(HERE, "parse_f_reply.py"), "rb").read()).hexdigest()[:16]
    keep = os.path.join(a.results, "parsed_f", f"{a.recv}.before_note1.json")
    if os.path.exists(keep):
        sys.exit(f"{keep} exists: this reply was already re-read")
    os.replace(jp, keep)
    os.chmod(keep, 0o444)
    new = {"source": old.get("source", path), "sha256": old["sha256"], "preamble": r["pre"], "other_lines_after_first_answer": r["post"],
           "duplicates": ev["dups"], "form_notes": r["notes"], "order": ids, "answers": ans,
           "parser_sha16": parser_sha,
           "reread": {"when": a.when, "under": "Note 1 of Test F (2026-11-14 18:26)", "old_parse_kept_as": os.path.basename(keep)}}
    json.dump(new, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    was = row["status"], row["batch"]
    row["status"], row["batch"] = "data", str(derived)
    write_cells(cp, rows)
    model = inf.MODEL_NAMES[row["model"]]
    other = ev["other"]
    flags = notes
    lines = open(lp, encoding="utf-8").read().split("\n")
    para = (f"{a.recv} re-read under Note 1 of Test F ({a.when}; arm {row['arm']}, {model}, run {row['run']}): {len(ids)} of 20 answers ({ids[0]}-{ids[-1]}), "
            f"{'no item answered twice' if not ev['dups'] else 'ITEMS ANSWERED TWICE ' + str(ev['dups'])}, {'packet order' if ev['in_order'] else 'NOT in packet order'}. "
            f"Places named {len(ev['named'])}, none {ev['none_n']}, unreadable {len(ev['unread'])}"
            f"{' ' + str([(i, ans[i]['place_raw'][:30]) for i in ev['unread']]) if ev['unread'] else ''}. "
            f"{'Nothing before the first answer or after it.' if not other else 'Other lines: ' + str(len(r['pre'])) + ' before the first answer, ' + str(len(r['post'])) + ' after it.'} "
            f"Phrase words {min(pw.values()) if pw else 0} to {max(pw.values()) if pw else 0}"
            f"{'' if not ev['over'] else ', OVER ' + str(inf.PHRASE_LIMIT) + ': ' + str(ev['over'])}. "
            f"{'No search or code-run words.' if not ev['tool'] else 'Search or code-run words: ' + str(ev['tool'][:6]) + '.'} "
            f"{('Flags: ' + '; '.join(flags) + '. ') if flags else ''}Answers parsed to parsed_f/{a.recv}.json (parser {parser_sha}); "
            f"the first parse (the parser frozen with the kit) is kept as parsed_f/{os.path.basename(keep)}.")
    lines = rin.insert_before_heading(lines, "## Metadata the protocol asks for", [para], blank_before=True)
    i = lines.index("## Handling decisions")
    j = i + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1
    e = j
    while e > i + 1 and lines[e - 1] == "":
        e -= 1
    dec = (f"- {a.when}: {a.recv} ({cell}) re-read under Note 1 of Test F (the user chose it 2026-11-14 18:26): {was[0]} -> data, "
           f"batch {was[1]} -> {derived}. {len(ids)} of 20 answers; the first parse is kept as parsed_f/{os.path.basename(keep)}.")
    lines[e:e] = [dec]
    open(lp, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{a.recv}: review -> data, batch {was[1]} -> {derived}; parsed_f/{a.recv}.json rewritten, old parse kept; logged in received_log_F.md")


if __name__ == "__main__":
    main()
