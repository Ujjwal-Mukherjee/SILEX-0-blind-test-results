#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Form parser for a reply to a writing-test packet (arm P). FORM ONLY: it never runs the checker, never opens a key and never reads a block for meaning.
The rules it follows are in P_handling_rules.md (sections B to D, rules 5 to 14). Working script, not part of any frozen kit.

Usage:  python3 -I parse_p_reply.py REPLY.txt [CONTINUATION.txt ...] [--json OUT.json]
        (a reply cut off by the app is followed by the part sent after "continue"; parts are given in order)

An item starts at a heading  #NN  alone on its line (outside any block; heading marks, bold marks, "Item" and a trailing colon are accepted).
Its SILEX is its fenced block(s). Without a fence, the non-blank lines under the heading are its text. Comments are taken out of the block text
(the checker's own rule) and recorded. Nothing else is changed in the text of a block except trailing blanks, which the checker strips anyway.
"""
import hashlib
import json
import re
import sys

HEAD = re.compile(r"^[\s>*_#-]*?(?:item\s+)?(#\d{2})[\s*_:.)-]*$", re.I)
OPEN = re.compile(r"^\s*(?P<f>`{3,}|~{3,})(?P<tag>[^`]*)$")
CLOSE = re.compile(r"^\s*(?P<f>`{3,}|~{3,})\s*$")
SEP = re.compile(r"^---\s*$")
NONE_RE = re.compile(r"(?i)^\s*none\b")
CORR = re.compile(r"(?i)\b(corrected|correction|revised|replaces|replacing|updated|fixed|amended|instead)\b")
TOOLS = re.compile(r"(?i)(?:\b(?:searched|browsed|looked\s+up|code\s+interpreter|sandbox)\b|\bsearching\s+the\s+web\b|\bweb\s+search\s+results?\b"
                   r"|https?://|\bwww\.|\bi\s+(?:ran|executed)\b|\bran\s+the\s+(?:code|checker|script)\b)")
INLINE = re.compile(r"^\W*(#\d{2})\b(?!\s*$)")
STATUS_LINE = re.compile(r"(?i)^(worked|thought|reasoned|searched|analy[sz]ed|browsed)\b.*\b(for|the)\b")


def strip_comment(line):
    """The checker's rule (silex_check.py, strip_comment): a # outside quotation marks and not followed by "(" starts a comment.
    Returns (code, comment) with comment None when there is none; the comment keeps its #."""
    q = None
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            if c == q:
                if q == '"' and line[i + 1:i + 2] == '"':
                    i += 2
                    continue
                q = None
        else:
            if c in '"\'':
                q = c
            elif c == '#' and line[i + 1:i + 2] != '(':
                return line[:i], line[i:]
        i += 1
    return line, None


def clean_block(raw_lines):
    """-> (lines without comments and blank lines, comments). The checker splits messages on raw lines of three hyphens before it strips comments; so does this."""
    out, comments = [], []
    for n, l in enumerate(raw_lines, 1):
        if SEP.match(l):
            out.append("---")
            continue
        code, com = strip_comment(l)
        if com is not None:
            comments.append({"line": n, "text": com.strip()[:200]})
            if code.strip():
                out.append(code.rstrip())
        elif l.strip():
            out.append(l.rstrip())
    return out, comments


def n_messages(clean):
    chunks, cur = [], []
    for l in clean:
        if l == "---":
            chunks.append(cur)
            cur = []
        else:
            cur.append(l)
    chunks.append(cur)
    return sum(1 for c in chunks if c)


def describe_block(raw_lines, closed, tag, part, start_line, unfenced=False):
    clean, comments = clean_block(raw_lines)
    text = "\n".join(clean)
    first = next((l for l in clean if l != "---"), "")
    return {"tag": tag, "closed": closed, "part": part, "start_line": start_line, "unfenced": unfenced,
            "raw_lines": len(raw_lines), "text": text, "chars": len(text), "messages": n_messages(clean),
            "comments": comments, "none": bool(NONE_RE.match(first)), "empty": not clean,
            "heading_lines": sum(1 for l in raw_lines if HEAD.match(l))}


def parse_parts(parts):
    """parts: list of reply texts in order (one text for an ordinary reply). -> dict, see the end of the function."""
    # stage 1: lines -> tokens (text lines and fenced blocks, in order), with the join rule for cut-off parts
    tokens, joins = [], []
    fence, block = None, None
    for pi, text in enumerate(parts):
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if pi > 0 and fence is not None:
            first = next((l for l in lines if l.strip()), None)
            if first is not None:
                if CLOSE.match(first) or not (HEAD.match(first) or OPEN.match(first)):
                    joins.append({"part": pi + 1, "kind": "mid-block", "first_line": first.strip()[:60]})
                else:
                    joins.append({"part": pi + 1, "kind": "restart", "first_line": first.strip()[:60]})
                    fence, block = None, None
        for ln_no, ln in enumerate(lines, 1):
            if fence is not None:
                m = CLOSE.match(ln)
                if m and m.group("f")[0] == fence[0] and len(m.group("f")) >= fence[1]:
                    block["closed"] = True
                    fence, block = None, None
                else:
                    block["raw"].append(ln)
                continue
            m = OPEN.match(ln)
            if m:
                fence = (m.group("f")[0], len(m.group("f")))
                block = {"tag": m.group("tag").strip(), "raw": [], "closed": False, "part": pi + 1, "start_line": ln_no}
                tokens.append(("block", block))
                continue
            tokens.append(("text", pi + 1, ln_no, ln))
    open_at_end = fence is not None

    # stage 2: tokens -> items. A heading alone on a line starts an item. A block whose first non-blank line is a heading and that holds no other
    # heading line has the heading INSIDE the block: the line is read as the heading (not as a comment) and removed from the block.
    items, pre, orphans, inline_heads, inner_heads = [], [], [], [], []
    cur = None
    for tok in tokens:
        if tok[0] == "text":
            _, pn, ln_no, ln = tok
            m = HEAD.match(ln)
            if m:
                cur = {"id": m.group(1), "blocks": [], "outside": [], "part": pn, "line": ln_no}
                items.append(cur)
            else:
                if INLINE.match(ln):
                    inline_heads.append(ln.strip()[:80])
                if cur is None:
                    if ln.strip():
                        pre.append({"part": pn, "line": ln_no, "text": ln.strip()})
                else:
                    cur["outside"].append({"part": pn, "line": ln_no, "text": ln, "after_block": bool(cur["blocks"])})
            continue
        b = tok[1]
        nz = [k for k, l in enumerate(b["raw"]) if l.strip()]
        hl = [k for k, l in enumerate(b["raw"]) if HEAD.match(l)]
        if len(hl) == 1 and nz and nz[0] == hl[0]:
            inner = HEAD.match(b["raw"][hl[0]]).group(1)
            b["raw"] = b["raw"][:hl[0]] + b["raw"][hl[0] + 1:]
            inner_heads.append(inner)
            if cur is None or cur["id"] != inner or cur["blocks"]:
                cur = {"id": inner, "blocks": [], "outside": [], "part": b["part"], "line": b["start_line"]}
                items.append(cur)
        (cur["blocks"] if cur is not None else orphans).append(b)

    for it in items:
        it["described"] = [describe_block(b["raw"], b["closed"], b["tag"], b["part"], b["start_line"]) for b in it["blocks"]]
    orphan_desc = [describe_block(b["raw"], b["closed"], b["tag"], b["part"], b["start_line"]) for b in orphans]

    def complete(c):
        return any(b["closed"] for b in c["described"]) or (not c["described"] and any(o["text"].strip() for o in c["outside"]))

    by_id, order_ids = {}, []
    for it in items:
        if it["id"] not in by_id:
            order_ids.append(it["id"])
        by_id.setdefault(it["id"], []).append(it)
    resolved, dups = {}, []
    for id_ in order_ids:
        cands = by_id[id_]
        comp = [c for c in cands if complete(c)]
        pool = comp if comp else cands
        keep, reason = pool[0], "first"
        for nxt in pool[1:]:
            words = set()
            for o in keep["outside"]:
                words |= {w.lower() for w in CORR.findall(o["text"])}
            for b in keep["described"]:
                for c in b["comments"]:
                    words |= {w.lower() for w in CORR.findall(c["text"])}
            for o in nxt["outside"]:
                if not o["after_block"]:
                    words |= {w.lower() for w in CORR.findall(o["text"])}
            if words:
                keep, reason = nxt, "correction word " + "/".join(sorted(words))
        if len(cands) > 1:
            why = reason + ("; a block that was never closed was dropped" if len(pool) < len(cands) else "")
            dups.append({"id": id_, "headings": len(cands), "kept_heading": cands.index(keep) + 1, "reason": why})
        resolved[id_] = keep

    out_items = {}
    for id_ in order_ids:
        it = resolved[id_]
        if it["described"]:
            blocks, status = it["described"], "block"
        else:
            lines = [o["text"] for o in it["outside"] if o["text"].strip()]
            if lines:
                blocks, status = [describe_block(lines, True, None, it["part"], it["line"], unfenced=True)], "unfenced"
            else:
                blocks, status = [], "missing"
        outside = [o for o in it["outside"] if o["text"].strip()] if status == "block" else []
        out_items[id_] = {"status": status, "blocks": blocks, "outside": outside, "part": it["part"], "line": it["line"]}

    nums = [int(i[1:]) for i in order_ids]
    in1 = [i for i, k in zip(order_ids, nums) if 1 <= k <= 20]
    in2 = [i for i, k in zip(order_ids, nums) if 21 <= k <= 40]
    unknown = [i for i, k in zip(order_ids, nums) if not 1 <= k <= 40]
    derived = 1 if len(in1) >= len(in2) else 2
    expect = ["#%02d" % k for k in (range(1, 21) if derived == 1 else range(21, 41))]
    last = items[-1] if items else None
    trailing = [o for o in (last["outside"] if last else []) if o["after_block"] and o["text"].strip()]
    outside_all = [o for it in items for o in it["outside"] if o["text"].strip() and out_items[it["id"]]["status"] != "unfenced"]
    tool_hits = sorted({m.group(0).lower() for t in ([p["text"] for p in pre] + [o["text"] for o in outside_all]
                                                    + [c["text"] for it in items for b in it["described"] for c in b["comments"]])
                        for m in TOOLS.finditer(t)})
    return {
        "parts": len(parts), "joins": joins, "open_at_end": open_at_end,
        "pre": pre, "orphans": orphan_desc, "headings": [it["id"] for it in items], "order": order_ids, "dups": dups,
        "items": out_items, "derived_batch": derived, "expect": expect, "in_batch1": in1, "in_batch2": in2, "unknown": unknown,
        "missing": [i for i in expect if i not in out_items or out_items[i]["status"] == "missing"],
        "strays": [i for i in order_ids if i not in expect],
        "in_order": [i for i in order_ids if i in expect] == [i for i in expect if i in order_ids],
        "multi_item_blocks": sorted({i for i, it in out_items.items() for b in it["blocks"] if b["heading_lines"] >= 2}),
        "trailing": trailing, "tool_words": tool_hits,
        "outside_count": len(outside_all),
        "status_lines": [p["text"] for p in pre if STATUS_LINE.match(p["text"])],
        "inline_heads": inline_heads, "inner_heads": inner_heads,
    }


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        k = args.index("--json")
        out = args[k + 1]
        del args[k:k + 2]
    if not args:
        sys.exit(__doc__)
    texts = [open(p, encoding="utf-8").read() for p in args]
    r = parse_parts(texts)
    print("files: %d   sha256 %s" % (len(args), ", ".join(hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] for p in args)))
    print("headings: %d (%s .. %s)   resolved items: %d   derived batch: %d   in packet order: %s" % (
        len(r["headings"]), r["headings"][0] if r["headings"] else "-", r["headings"][-1] if r["headings"] else "-",
        len(r["order"]), r["derived_batch"], r["in_order"]))
    print("missing:", r["missing"] or "none", "  strays:", r["strays"] or "none", "  repeated headings:", r["dups"] or "none")
    print("ends inside an open block:", r["open_at_end"], "  joins:", r["joins"] or "none")
    print("text before the first heading:", [p["text"][:50] for p in r["pre"]][:3] or "none")
    print("tool words:", r["tool_words"] or "none")
    for i in r["order"]:
        it = r["items"][i]
        bs = it["blocks"]
        print("  %s %-8s blocks %d  messages %s  chars %s  comments %d%s%s" % (
            i, it["status"], len(bs), "/".join(str(b["messages"]) for b in bs) or "-", "/".join(str(b["chars"]) for b in bs) or "-",
            sum(len(b["comments"]) for b in bs), "  NONE" if any(b["none"] for b in bs) else "", "  UNCLOSED" if any(not b["closed"] for b in bs) else ""))
    if out:
        json.dump(r, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written", out)


if __name__ == "__main__":
    main()
