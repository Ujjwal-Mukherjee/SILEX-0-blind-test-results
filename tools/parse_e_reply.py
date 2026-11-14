#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Form parser for a reply to an English-baseline packet (arm E). FORM ONLY: it never opens a key and never reads a message for meaning.
The rules it follows are in E_handling_rules.md (sections B to D). Working script, not part of any frozen kit.
It is built on parse_p_reply.py (same heading, fence, repeated-heading and join logic); what differs is the item text (rules 9 to 13) and the search-word check (rule 7).

Usage:  python3 -I parse_e_reply.py REPLY.txt [CONTINUATION.txt ...] [--json OUT.json]
        (a reply cut off by the app is followed by the part sent after "continue"; parts are given in order)

An item starts at a heading  #NN  alone on its line (outside any fence; heading marks, bold marks, "Item" and a trailing colon are accepted).
Its text is its fenced block(s) if it has any, otherwise the non-blank lines under the heading. Horizontal-rule lines are not text. Nothing else is changed
(a # inside the English is ordinary text). In the LAST item of a reply, text that follows the last message line after a blank line or a rule is text after the last item.
"""
import hashlib
import json
import re
import sys

HEAD = re.compile(r"^[\s>*_#-]*?(?:item\s+)?(#\d{2})[\s*_:.)-]*$", re.I)
OPEN = re.compile(r"^\s*(?P<f>`{3,}|~{3,})(?P<tag>[^`]*)$")
CLOSE = re.compile(r"^\s*(?P<f>`{3,}|~{3,})\s*$")
RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
NONE_E = re.compile(r"(?i)^[\s*_`>-]*none\b[\s*_`.!]*(?:[:–—-].*)?$")
CORR = re.compile(r"(?i)\b(corrected|correction|revised|replaces|replacing|updated|fixed|amended|instead)\b")
TOOLS = re.compile(r"(?i)(?:\b(?:searched|browsed|looked\s+up|code\s+interpreter|sandbox)\b|\bsearching\s+the\s+web\b|\bweb\s+search\s+results?\b"
                   r"|https?://|\bwww\.|\bi\s+(?:ran|executed)\b|\bran\s+the\s+(?:code|checker|script)\b)")
INLINE = re.compile(r"^\W*(#\d{2})\b(?!\s*$)")
INLINE_NUM = re.compile(r"^\W*#(\d{2})\b")
INLINE_MSG = re.compile(r"^[\s>*_#-]*?(?:item\s+)?(#\d{2})[\s*_:.)-]+(?P<rest>\S.*)$", re.I)   # "#NN <message line>" (Note 1 of the E rules, 2026-11-14)
STATUS_LINE = re.compile(r"(?i)^(worked|thought|reasoned|searched|analy[sz]ed|browsed)\b.*\b(for|the)\b")
LEAD = re.compile(r"^[\s>*_`•-]*(?:\d+[.)]\s*)?[\s*_`]*")
TO = re.compile(r"^(.{1,40}?)\s+to\s+(.{1,40})$", re.I)


def is_message_line(line):
    """Rule 13: the part before the first colon holds the word 'to' between two short names (after leading bullet, number or bold marks)."""
    s = LEAD.sub("", line, count=1)
    head, sep, _ = s.partition(":")
    if not sep:
        return False
    return bool(TO.match(head.strip().strip("*_` ").strip()))


def clean_text(raw_lines):
    """Rule 9: blank lines and horizontal-rule lines are not text; trailing blanks of a line are dropped; nothing else changes."""
    return [l.rstrip() for l in raw_lines if l.strip() and not RULE.match(l)]


def describe_block(raw_lines, closed, tag, part, start_line, unfenced=False):
    clean = clean_text(raw_lines)
    text = "\n".join(clean)
    first = clean[0] if clean else ""
    msg = sum(1 for l in clean if is_message_line(l))
    return {"tag": tag, "closed": closed, "part": part, "start_line": start_line, "unfenced": unfenced,
            "raw_lines": len(raw_lines), "text": text, "chars": len(text), "words": len(text.split()),
            "messages": msg, "other_lines": len(clean) - msg, "comments": [], "none": bool(NONE_E.match(first)), "empty": not clean,
            "heading_lines": sum(1 for l in raw_lines if HEAD.match(l))}


def cut_closing(lines):
    """Rule 9, last item only. lines: the raw lines under the last heading (blank lines included).
    -> (lines that stay in the item, lines after the last item). Text after the last message line, after a blank line or a rule, is text after the last item."""
    last_msg = max((k for k, l in enumerate(lines) if is_message_line(l)), default=None)
    if last_msg is None:
        return lines, []
    for k in range(last_msg + 1, len(lines)):
        if not lines[k].strip() or RULE.match(lines[k]):
            rest = lines[k:]
            return lines[:k], [l for l in rest if l.strip() and not RULE.match(l)]
    return lines, []


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
        elif pi > 0:
            first = next((l for l in lines if l.strip()), None)
            if first is not None:
                joins.append({"part": pi + 1, "kind": "text", "first_line": first.strip()[:60]})
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

    # stage 2: tokens -> items (same logic as the writing test)
    items, pre, orphans, inline_heads, inner_heads, inline_first = [], [], [], [], [], []
    cur = None
    for tok in tokens:
        if tok[0] == "text":
            _, pn, ln_no, ln = tok
            m = HEAD.match(ln)
            mi = None if m else INLINE_MSG.match(ln)
            if m:
                cur = {"id": m.group(1), "blocks": [], "outside": [], "part": pn, "line": ln_no}
                items.append(cur)
            elif mi and is_message_line(mi.group("rest")):
                # Note 1 of the E rules (2026-11-14): "#NN <message line>" starts an item; its first line is the rest of this line
                cur = {"id": mi.group(1), "blocks": [], "outside": [{"part": pn, "line": ln_no, "text": mi.group("rest"), "after_block": False}],
                       "part": pn, "line": ln_no}
                items.append(cur)
                inline_first.append(mi.group(1))
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
            for o in nxt["outside"]:
                if not o["after_block"]:
                    words |= {w.lower() for w in CORR.findall(o["text"])}
            if words:
                keep, reason = nxt, "correction word " + "/".join(sorted(words))
        if len(cands) > 1:
            why = reason + ("; a block that was never closed was dropped" if len(pool) < len(cands) else "")
            dups.append({"id": id_, "headings": len(cands), "kept_heading": cands.index(keep) + 1, "reason": why})
        resolved[id_] = keep

    last = items[-1] if items else None
    trailing = []
    out_items = {}
    for id_ in order_ids:
        it = resolved[id_]
        if it["described"]:
            blocks, status = it["described"], "block"
            outside = [o for o in it["outside"] if o["text"].strip()]
            if it is last:
                trailing += [{"part": o["part"], "line": o["line"], "text": o["text"]} for o in it["outside"] if o["after_block"] and o["text"].strip()]
        else:
            lines = [o["text"] for o in it["outside"]]
            cut = []
            if it is last:
                kept, cut = cut_closing(lines)
                lines = kept
                trailing += [{"part": it["part"], "line": it["line"], "text": t} for t in cut]
            body = [l for l in lines if l.strip()]
            if body:
                blocks, status = [describe_block(body, True, None, it["part"], it["line"], unfenced=True)], "unfenced"
            else:
                blocks, status = [], "missing"
            outside = []
        texts = [b["text"] for b in blocks if b["text"]]
        text = "\n".join(texts)
        first = text.split("\n")[0] if text else ""
        is_none = bool(NONE_E.match(first))
        state = "missing" if status == "missing" else ("none" if is_none else ("empty" if not text else "text"))
        out_items[id_] = {"status": status, "blocks": blocks, "outside": outside, "part": it["part"], "line": it["line"],
                          "text": text, "chars": len(text), "words": len(text.split()), "state": state,
                          "messages": sum(b["messages"] for b in blocks), "other_lines": sum(b["other_lines"] for b in blocks)}

    nums = [int(i[1:]) for i in order_ids]
    in1 = [i for i, k in zip(order_ids, nums) if 1 <= k <= 20]
    in2 = [i for i, k in zip(order_ids, nums) if 21 <= k <= 40]
    unknown = [i for i, k in zip(order_ids, nums) if not 1 <= k <= 40]
    derived = 1 if len(in1) >= len(in2) else 2
    if not in1 and not in2:
        # held case: no line holds only #NN, but lines start like item numbers ("#21 A to B: ..."). The item numbers still decide the batch (rule 5).
        inl = [int(m.group(1)) for m in (INLINE_NUM.match(h) for h in inline_heads) if m]
        derived = 1 if sum(1 for k in inl if 1 <= k <= 20) >= sum(1 for k in inl if 21 <= k <= 40) else 2
    expect = ["#%02d" % k for k in (range(1, 21) if derived == 1 else range(21, 41))]
    outside_fenced = [o for it in out_items.values() for o in it["outside"] if o["text"].strip()]
    tool_hits = sorted({m.group(0).lower() for t in ([p["text"] for p in pre] + [o["text"] for o in outside_fenced] + [t_["text"] for t_ in trailing])
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
        "outside_count": len(outside_fenced),
        "status_lines": [p["text"] for p in pre if STATUS_LINE.match(p["text"])],
        "inline_heads": inline_heads, "inner_heads": inner_heads, "inline_first": inline_first,
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
    print("ends inside an open fence:", r["open_at_end"], "  joins:", r["joins"] or "none")
    print("text before the first heading:", [p["text"][:50] for p in r["pre"]][:3] or "none")
    print("text after the last item:", [t["text"][:50] for t in r["trailing"]][:3] or "none")
    print("tool words:", r["tool_words"] or "none")
    for i in r["order"]:
        it = r["items"][i]
        print("  %s %-8s %-7s message lines %d  other lines %d  chars %d  words %d" % (i, it["status"], it["state"], it["messages"], it["other_lines"], it["chars"], it["words"]))
    if out:
        json.dump(r, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written", out)


if __name__ == "__main__":
    main()
