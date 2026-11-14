#!/usr/bin/env python3
"""Form parser for a reply to a Test F packet (find the fault). FORM ONLY: it never scores and never reads a phrase for meaning.

A reply is one line per item:   F07 | B1.2 | what is wrong      or      F07 | none
Tolerated (and noted when used): markdown bold, bullets, numbering, table bars, backticks, a colon or a dash instead of a bar,
"B1 line 2", "line 2 of B1", "B1.0" / "B1 header" for a header, a short preamble, a short closing sentence.
Run-on lines (Note 1 of Test F, the user's choice of 2026-11-14 18:26): a line that holds more than one item code followed by a bar
("F21 | ... F22 | ...") is cut before the second and later codes, so that each code starts an answer. No word of the reply is changed, only where
the line breaks fall; the use is noted. A reply with one answer per line is read exactly as before.
Usage:  python3 -I parse_f_reply.py REPLY.txt [--json OUT.json]
"""
import json, re, sys, hashlib

ID_AT_START = re.compile(r"^\W*?(?:\d+[.)]\s+)?\W*?[Ff](\d{2})\b\W*?(?P<rest>.*)$")
NONE_RE = re.compile(r"(?i)^\W*(none|no\s+faults?(\s+found)?|no\s+problems?|nothing(\s+wrong)?|clean|fault[- ]?free)\b")
P_STRICT = re.compile(r"\b([A-Za-z])\s?(\d+)\s?\.\s?(\d+)\b")
P_HEAD1 = re.compile(r"\b([A-Za-z])\s?(\d+)\s?\.\s?(?:h|header|0)\b", re.I)
P_HEAD2 = re.compile(r"\b([A-Za-z])\s?(\d+)\b[\s,;:()\-]*(?:the\s+)?header\b", re.I)
P_HEAD3 = re.compile(r"\bheader\s+(?:of|in|for)\s+(?:message\s+)?([A-Za-z])\s?(\d+)\b", re.I)
P_LINE1 = re.compile(r"\b([A-Za-z])\s?(\d+)\b[\s,;:()\-]*(?:line|ln|l)\.?\s?(\d+)\b", re.I)
P_LINE2 = re.compile(r"\bline\s?(\d+)\s+(?:of|in)\s+(?:message\s+)?([A-Za-z])\s?(\d+)\b", re.I)


def norm_places(s):
    """-> list of normalised places found in s, in order of appearance: 'A1.2' or 'A1.h'."""
    found = []
    for rx, kind in ((P_HEAD1, "h1"), (P_HEAD3, "h3"), (P_HEAD2, "h2"), (P_STRICT, "s"), (P_LINE1, "l1"), (P_LINE2, "l2")):
        for m in rx.finditer(s):
            if kind in ("h1", "h2"):
                p = f"{m.group(1).upper()}{m.group(2)}.h"
            elif kind == "h3":
                p = f"{m.group(1).upper()}{m.group(2)}.h"
            elif kind == "s":
                p = f"{m.group(1).upper()}{m.group(2)}.{int(m.group(3))}"
            elif kind == "l1":
                p = f"{m.group(1).upper()}{m.group(2)}.{int(m.group(3))}"
            else:
                p = f"{m.group(2).upper()}{m.group(3)}.{int(m.group(1))}"
            found.append((m.start(), p))
    found.sort()
    out = []
    for _, p in found:
        if p not in out:
            out.append(p)
    return out


def strip_decor(line):
    s = line.strip()
    s = re.sub(r"[`*_]+", "", s)          # markdown bold / code marks
    s = re.sub(r"^[>\-•●]+\s*", "", s)   # quote mark, bullets
    s = s.strip()
    if s.startswith("|"):
        s = s[1:]
    return s.strip()


def split_fields(rest):
    """After the id: -> (place text, phrase, how the fields were separated)."""
    r = rest.strip()
    had_bar = "|" in r
    if r[:1] in ("|", ":", "\u2013", "\u2014", "-"):
        r = r[1:].strip()
    if had_bar:
        parts = [p.strip() for p in r.split("|")]
        if parts and parts[-1] == "":
            parts = parts[:-1]                 # a closing table bar
        place = parts[0] if parts else ""
        phrase = " | ".join(parts[1:]).strip()
        return place, phrase, "bar"
    m = re.match(r"^(.*?)(?:\s[-\u2013\u2014]\s|\s*[:\u2013\u2014]\s*)(.*)$", r)
    if m:
        return m.group(1).strip(), m.group(2).strip(), "other"
    return r, "", "none"


ITEM_CODE_START = re.compile(r"(?:(?<=\s)|^)[Ff]\d{2}\s*\|")     # an item code followed by a bar, at the start of the line or after a space


def split_run_on(s):
    """Note 1 of Test F: cut a (decoration-stripped) line before every item code 'Fnn |' except the first one on it.
    A line with fewer than two such codes is returned as it is."""
    starts = [m.start() for m in ITEM_CODE_START.finditer(s)]
    if len(starts) < 2:
        return [s]
    segs, prev = [], 0
    for c in starts[1:]:
        segs.append(s[prev:c].strip())
        prev = c
    segs.append(s[prev:].strip())
    return segs


def expand_run_on(lines, run_on):
    """Yield (line number, text) for every line of the reply; a run-on line comes out as several pieces, one per item code.
    run_on collects (line number, number of pieces) for each such line."""
    for i, raw in enumerate(lines, 1):
        if not raw.strip():
            yield i, raw
            continue
        segs = split_run_on(strip_decor(raw))
        if len(segs) > 1:
            run_on.append((i, len(segs)))
            for seg in segs:
                yield i, seg
        else:
            yield i, raw


def parse(text):
    lines = text.replace("\r\n", "\n").split("\n")
    answers, order, dups, other, notes = {}, [], [], [], []
    first_answer_line, decorated, run_on = None, 0, []
    for i, raw in expand_run_on(lines, run_on):
        if not raw.strip():
            continue
        s = strip_decor(raw)
        m = ID_AT_START.match(s)
        if not m:
            other.append((i, raw.strip()))
            continue
        iid = "F" + m.group(1)
        place_raw, phrase, sep = split_fields(m.group("rest"))
        if first_answer_line is None:
            first_answer_line = i
        if sep == "other":
            notes.append(f"{iid}: no '|' bars; read with a colon or dash")
        elif sep == "none":
            notes.append(f"{iid}: no separator at all")
        if not re.match(r"^[Ff]\d{2}\b", raw.strip()):
            decorated += 1
        if NONE_RE.match(place_raw):
            place = "none"
        else:
            ps = norm_places(place_raw)
            if not ps and sep != "bar":
                ps = norm_places(m.group("rest"))
            place = ps[0] if ps else None
            if len(ps) > 1:
                notes.append(f"{iid}: more than one place named ({', '.join(ps)}); the first one is taken")
            if place is None:
                notes.append(f"{iid}: place could not be read: {place_raw!r}")
        if iid in answers:
            dups.append(iid)
            continue
        answers[iid] = dict(place_raw=place_raw, place=place, phrase=phrase, line=raw.strip(), line_no=i)
        order.append(iid)
    if decorated:
        notes.append(f"{decorated} answer line(s) had decoration in front of the id (markdown, bullet, number or table bar), stripped")
    if run_on:
        n_run = sum(c for _, c in run_on)
        where = ", ".join(f"line {ln}: {c} answers" for ln, c in run_on[:5])
        notes.append(f"RUN-ON LINE(S): {n_run} answers sat together on {len(run_on)} line(s) ({where}); each item code starts an answer "
                     f"(Note 1 of Test F, 2026-11-14 18:26)")
    pre = [o for o in other if first_answer_line is None or o[0] < first_answer_line]
    post = [o for o in other if first_answer_line is not None and o[0] > first_answer_line]
    return dict(answers=answers, order=order, dups=dups, pre=pre, post=post, notes=notes,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    txt = open(sys.argv[1], encoding="utf-8").read()
    r = parse(txt)
    print(f"answers: {len(r['answers'])}  ids: {r['order'][0] if r['order'] else '-'} .. {r['order'][-1] if r['order'] else '-'}  duplicates: {r['dups']}")
    print(f"unreadable places: {[k for k, v in r['answers'].items() if v['place'] is None]}")
    print(f"before first answer: {len(r['pre'])} line(s); after: {len(r['post'])} line(s)")
    for n in r["notes"]:
        print("  note:", n)
    if "--json" in sys.argv:
        json.dump(r, open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
