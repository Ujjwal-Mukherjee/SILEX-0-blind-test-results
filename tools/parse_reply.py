# -*- coding: utf-8 -*-
"""Parse one pasted reply to an R or N packet ('#NN' heading, then the explanation).
Working script, not part of the frozen kit.
Usage: python3 -I parse_reply.py REPLY.txt [--compare OTHER.txt] [--json OUT.json]
Only reports form (items, order, length, search words, preamble, trailer). It never scores content.
The item id may stand alone, be a markdown heading ("### #01") or be in bold.
A closing paragraph after the last item that starts with Correction/Note/Summary/... is split off as a trailer.
Word counts: "words" = tokens holding at least one letter or digit (bullet marks and lone symbols are not counted);
"raw" = every whitespace-separated token. The limit is checked on "words" (the lenient count).
"""
import argparse
import difflib
import hashlib
import json
import re

PACKETS = "/home/claude/silex_blind_test"
LIMIT = 120
STRICT = re.compile(r"^[\s>*_#-]*?(#\d{2})[\s*_:.)-]*$")
INLINE = re.compile(r"^\W*(#\d{2})\b(?!\s*$)")
TRAILER = re.compile(r"(?i)^(corrections?|notes?|summary|overall|caveats?|final)\b")
UILINE = re.compile(r"(?i)^(worked|thought|reasoned|searched|analy[sz]ed|browsed)\b.*\b(for|the)\b")
SEARCHY = re.compile(r"(?i)\b(search(?:ed|es|ing)?|web|google|browse[sd]?|internet|https?://|www\.|look(?:ed)? up|wikipedia|online)\b")


def packet_ids(b):
    with open("%s/R_batch%d.txt" % (PACKETS, b), encoding="utf-8") as f:
        return re.findall(r"(?m)^(#\d{2})$", f.read())


def parse(text):
    pre, items, inline, cur = [], [], [], None
    for ln in text.splitlines():
        m = STRICT.match(ln)
        if m:
            cur = {"id": m.group(1), "text": []}
            items.append(cur)
            continue
        if cur is None:
            if ln.strip():
                pre.append(ln)
            continue
        if INLINE.match(ln):
            inline.append(ln[:80])
        cur["text"].append(ln)
    for it in items:
        it["text"] = "\n".join(it["text"]).strip()
    trailer = ""
    if items:
        paras = re.split(r"\n\s*\n", items[-1]["text"])
        for k, para in enumerate(paras):
            if k >= 1 and TRAILER.match(para.strip()):
                trailer = "\n\n".join(paras[k:]).strip()
                items[-1]["text"] = "\n\n".join(paras[:k]).strip()
                break
    for it in items:
        toks = it["text"].split()
        it["raw"] = len(toks)
        it["words"] = len([t for t in toks if re.search(r"\w", t)])
    return pre, items, inline, trailer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reply")
    ap.add_argument("--compare")
    ap.add_argument("--json")
    a = ap.parse_args()
    raw = open(a.reply, encoding="utf-8").read()
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    pre, items, inline, trailer = parse(raw)
    ids = [it["id"] for it in items]
    b1, b2 = packet_ids(1), packet_ids(2)
    print("sha256 %s  bytes %d  lines %d" % (digest[:16], len(raw.encode("utf-8")), len(raw.splitlines())))
    print("packet ids: batch1 %s..%s (%d)  batch2 %s..%s (%d)" % (b1[0], b1[-1], len(b1), b2[0], b2[-1], len(b2)))
    print("items found: %d  (%s .. %s)" % (len(ids), ids[0] if ids else "-", ids[-1] if ids else "-"))
    dup = sorted({i for i in ids if ids.count(i) > 1})
    in1 = [i for i in ids if i in b1]
    in2 = [i for i in ids if i in b2]
    other = [i for i in ids if i not in b1 and i not in b2]
    print("duplicates: %s" % (dup or "none"))
    print("in batch 1: %d   in batch 2: %d   unknown ids: %s" % (len(in1), len(in2), other or "none"))
    expect = b1 if len(in1) >= len(in2) else b2
    print("derived batch: %d" % (1 if expect is b1 else 2))
    print("missing from derived batch: %s" % ([i for i in expect if i not in ids] or "none"))
    print("in packet order: %s" % (ids == [i for i in expect if i in ids]))
    print("text before first item (%d lines): %s" % (len(pre), pre or "none"))
    ui = [l for l in pre if UILINE.match(l.strip())]
    print("  of which look like app status lines (not model text): %s" % (ui or "none"))
    print("lines that start like an item id but are not alone: %s" % (inline or "none"))
    print("text after the last item, split off as trailer (%d chars): %s" % (len(trailer), trailer[:700] or "none"))
    print("\nwords per item, shown as words/raw (limit %d on words):" % LIMIT)
    row = []
    for it in items:
        row.append("%s:%d/%d%s" % (it["id"], it["words"], it["raw"], "*OVER*" if it["words"] > LIMIT else ""))
    print("  " + "  ".join(row))
    tot = sum(it["words"] for it in items)
    if items:
        print("total words %d  mean %.1f  min %d  max %d  over limit (words): %d  over limit (raw): %d" % (
            tot, tot / len(items), min(i["words"] for i in items), max(i["words"] for i in items),
            sum(1 for i in items if i["words"] > LIMIT), sum(1 for i in items if i["raw"] > LIMIT)))
    hits = []
    for it in items:
        for m in SEARCHY.finditer(it["text"]):
            s, e = max(0, m.start() - 30), min(len(it["text"]), m.end() + 30)
            hits.append((it["id"], it["text"][s:e].replace("\n", " ")))
    print("\nsearch-like words: %s" % (hits or "none"))
    print("bold or heading marks inside items: %s" % bool(re.search(r"(?m)(\*\*|^#{2,}\s)", "\n".join(i["text"] for i in items))))
    if a.compare:
        o_raw = open(a.compare, encoding="utf-8").read()
        _, o_items, _, _ = parse(o_raw)
        om = {it["id"]: it["text"] for it in o_items}
        print("\nsimilarity to %s (1.00 = identical text)" % a.compare)
        same, rs = 0, []
        for it in items:
            if it["id"] in om:
                r = difflib.SequenceMatcher(None, it["text"], om[it["id"]], autojunk=False).ratio()
                same += int(it["text"] == om[it["id"]])
                rs.append("%s:%.2f" % (it["id"], r))
        print("  " + "  ".join(rs))
        print("  identical items: %d of %d   whole files identical: %s" % (same, len(items), raw == o_raw))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"source": a.reply, "sha256": digest, "preamble": pre, "trailer": trailer,
                       "items": {it["id"]: it["text"] for it in items}}, f, ensure_ascii=False, indent=1)
        print("\nparsed items written to %s" % a.json)


if __name__ == "__main__":
    main()
