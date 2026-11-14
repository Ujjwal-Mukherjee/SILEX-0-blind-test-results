#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for build_roundtrip_p.py. Everything is built in a TEMP folder from a COPY of the cells and reply files; nothing real is written.
The key test: the packet renderer reproduces the frozen reading packets R_batch1.txt and R_batch2.txt byte for byte from their own items.
Run:  python3 -I test_roundtrip_p.py [KIT]
"""
import csv, hashlib, os, re, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
KIT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/silex_blind_test"
sys.path.insert(0, HERE)
import build_roundtrip_p as brp  # noqa: E402
import parse_p_reply as pp       # noqa: E402
import check_p as cp              # noqa: E402

TMP = tempfile.mkdtemp(prefix="rt_p_test_")
fails = []
BUILDER = os.path.join(HERE, "build_roundtrip_p.py")


def ok(cond, msg, ctx=None):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        fails.append(msg)
        if ctx is not None:
            print("      context: " + str(ctx)[-700:].replace("\n", "\n      "))


def snapshot(folder):
    out = {}
    for root, _, files in os.walk(folder):
        if "__pycache__" in root:
            continue
        for f in files:
            p = os.path.join(root, f)
            st = os.stat(p)
            out[p] = (st.st_mtime_ns, st.st_size)
    return out


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(args, kit=KIT):
    return subprocess.run([sys.executable, "-I", BUILDER, "--kit", kit] + args, capture_output=True, text=True)


def parse_packet(text):
    """-> (header including ITEMS, [(id, text)]) of a packet in the R layout."""
    i = text.index("\nITEMS\n") + len("\nITEMS")
    head, body = text[:i], text[i:]
    assert body.startswith("\n\n"), "no blank line after ITEMS"
    items = re.findall(r"(#\d\d)\n```\n(.*?)\n```(?:\n\n|\n$)", body[2:], flags=re.S)
    return head, items


real_before = snapshot(REAL)

# ---------- 1. header and renderer against the frozen reading packets
r1 = open(os.path.join(KIT, "R_batch1.txt"), encoding="utf-8").read()
r2 = open(os.path.join(KIT, "R_batch2.txt"), encoding="utf-8").read()
hdr = brp.silex_header(KIT)
h1, items1 = parse_packet(r1)
h2, items2 = parse_packet(r2)
ok(hdr == h1, "the SILEX reader text of reader_prompts.txt equals the opening of R_batch1.txt")
ok(brp.header_for(hdr, 2) == h2, "the batch 2 opening (item range replaced) equals the opening of R_batch2.txt")
ok(len(items1) == 20 and len(items2) == 20, "R_batch1 and R_batch2 each parse into 20 items", (len(items1), len(items2)))
ok(brp.render_packet(h1, [i for i, _ in items1], dict(items1)) == r1, "render_packet reproduces R_batch1.txt byte for byte")
ok(brp.render_packet(h2, [i for i, _ in items2], dict(items2)) == r2, "render_packet reproduces R_batch2.txt byte for byte")
ok(r1.endswith("```\n") and not r1.endswith("\n\n"), "the frozen packets end with one fence line and one newline (what the renderer does)")

# ---------- 2. seeded orders
ids1 = [f"#{n:02d}" for n in range(1, 21)]
ids2 = [f"#{n:02d}" for n in range(21, 41)]
c = brp.chat_numbers(brp.DEFAULT_SEED)
ok(sorted(c.values()) == [1, 2, 3, 4] and set(c) == set(brp.MODELS), "chat numbers are a permutation of 1..4 over the four writers", c)
ok(c == brp.chat_numbers(brp.DEFAULT_SEED), "chat numbers are the same when asked twice")
o1 = brp.item_order(brp.DEFAULT_SEED, ids1)
o2 = brp.item_order(brp.DEFAULT_SEED, ids2)
ok(sorted(o1) == ids1 and sorted(o2) == ids2, "item orders are permutations of the batch's own ids")
ok(o1 == brp.item_order(brp.DEFAULT_SEED, ids1), "item order is the same when asked twice")
ok(o1 != ids1 and o2 != ids2, "the shuffle really changes the order")
others = [brp.item_order(s, ids1) for s in ("a", "b", "c")]
ok(any(x != o1 for x in others), "another seed gives another order")

# ---------- 3. item_text cases
def blk(text="", none=False, empty=False):
    return {"text": text, "none": none, "empty": empty}

ok(brp.item_text(None) == "NONE", "no item at all -> NONE")
ok(brp.item_text({"status": "missing", "blocks": []}) == "NONE", "missing item -> NONE")
ok(brp.item_text({"status": "block", "blocks": [blk("NONE", none=True)]}) == "NONE", "NONE block -> NONE")
ok(brp.item_text({"status": "block", "blocks": [blk("", empty=True)]}) == "NONE", "empty block -> NONE")
ok(brp.item_text({"status": "block", "blocks": [blk("⊨(a,b)")]}) == "⊨(a,b)", "one block -> its text exactly")
ok(brp.item_text({"status": "unfenced", "blocks": [blk("⊨(a,b)\n---\n⊡(A1)")]}) == "⊨(a,b)\n---\n⊡(A1)", "an unfenced item keeps its text and its separators")
try:
    brp.item_text({"status": "block", "blocks": [blk("a"), blk("b")]})
    ok(False, "two blocks stop the build")
except SystemExit:
    ok(True, "two blocks stop the build")
try:
    brp.item_text({"status": "block", "blocks": [blk("```evil")]})
    ok(False, "a text holding a fence line stops the build")
except SystemExit:
    ok(True, "a text holding a fence line stops the build")

# ---------- 4. a temporary results folder: cells_P.csv and the reply files it names (copied)
RES = os.path.join(TMP, "res")
os.makedirs(RES)
rows = list(csv.DictReader(open(os.path.join(REAL, "cells_P.csv"), newline="", encoding="utf-8")))
shutil.copy(os.path.join(REAL, "cells_P.csv"), RES)
for r in rows:
    shutil.copy(os.path.join(REAL, r["file"]), RES)

OUT = os.path.join(TMP, "out")
p = run(["--results", RES, "--out", OUT, "--writers", "claude:1,grok:1,gemini:1"])
ok(p.returncode == 0, "build for claude, grok, gemini (run 1) succeeds", p.stdout + p.stderr)
files = sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []
ok(files == sorted([f"RT-P_chat{n}_packet{b}.txt" for n in c.values() if n in {c[m] for m in ("claude", "grok", "gemini")} for b in (1, 2)] + ["rt_key_PRIVATE.csv", "README_RT_P.txt"]),
   "the output folder holds 6 packets, the key file and the README", files)
allp = {}
for m in ("claude", "grok", "gemini"):
    for b in (1, 2):
        f = os.path.join(OUT, f"RT-P_chat{c[m]}_packet{b}.txt")
        allp[(m, b)] = open(f, encoding="utf-8").read()
        ok(not os.stat(f).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), f"packet of {m} batch {b} is read-only")
ok(os.access(os.path.join(OUT, "rt_key_PRIVATE.csv"), os.R_OK) and not os.stat(os.path.join(OUT, "rt_key_PRIVATE.csv")).st_mode & stat.S_IWUSR, "the key file is read-only")

# every packet: header, 20 items, the batch's own ids, the common order
for (m, b), text in allp.items():
    head, items = parse_packet(text)
    want_ids = o1 if b == 1 else o2
    ok(head == (hdr if b == 1 else brp.header_for(hdr, 2)), f"{m} batch {b}: the opening text is the frozen SILEX reader text")
    ok([i for i, _ in items] == want_ids, f"{m} batch {b}: 20 items in the common seeded order")
    ok(text.endswith("```\n") and not text.endswith("\n\n"), f"{m} batch {b}: the packet ends with one fence line and one newline")

# the item texts equal what the parser reads from the writer's own reply
reps, _ = cp.load_replies(RES, False)
for m in ("claude", "grok", "gemini"):
    for b in (1, 2):
        rep = [r for r in reps if r["model"] == m and r["run"] == 1 and r["batch"] == b]
        parsed = pp.parse_parts(rep[0]["texts"])
        _, items = parse_packet(allp[(m, b)])
        got = dict(items)
        bad = [i for i in got if got[i] != brp.item_text(parsed["items"].get(i))]
        ok(not bad, f"{m} batch {b}: every item's text is the writer's comment-free block text", bad[:3])
        # no comment survives: a '#' that is a comment start (outside quotes, not followed by "(") may not occur in a packet item
        stray = [i for i, t in got.items() if any(pp.strip_comment(l)[1] is not None for l in t.split("\n"))]
        ok(not stray, f"{m} batch {b}: no comment in any item", stray[:3])

# nothing names a writer, a model, a run or an arm
for (m, b), text in allp.items():
    low = text.lower()
    ok(not any(w in low for w in brp.BANNED), f"{m} batch {b}: no writer, model, run or arm word in the packet")

# the key
key = list(csv.DictReader(open(os.path.join(OUT, "rt_key_PRIVATE.csv"), newline="", encoding="utf-8")))
ok(len(key) == 6, "the key holds 6 rows", len(key))
ok(all(sha_row == hashlib.sha256(open(os.path.join(OUT, r["file"]), "rb").read()).hexdigest()[:16] for r in key for sha_row in [r["sha256_16"]]), "the key's hashes match the packet files")
ok({(r["writer"], r["packet"]) for r in key} == {(m, str(b)) for m in ("claude", "grok", "gemini") for b in (1, 2)}, "the key names each writer for each packet")
ok(all(int(r["chat"]) == c[r["writer"]] for r in key), "the key's chat numbers are the fixed ones")
ok(all(r["source_cell"] == f"P-{r['writer']}-1-b{r['packet']}" for r in key), "the key points to run 1 of each writer")
ok(all(r["item_order"].split() == (o1 if r["packet"] == "1" else o2) for r in key), "the key records the item order")
readme = open(os.path.join(OUT, "README_RT_P.txt"), encoding="utf-8").read()
ok(all(m not in readme.lower() for m in ("claude", "grok", "gemini", "chatgpt")), "the README names no writer")
ok(not os.stat(os.path.join(OUT, "README_RT_P.txt")).st_mode & stat.S_IWUSR, "the README is read-only")

# ---------- 5. rebuild is idempotent, a partial build can be completed without changing earlier packets
before = {f: sha(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.startswith("RT-P_")}
p = run(["--results", RES, "--out", OUT, "--writers", "claude:1,grok:1,gemini:1"])
ok(p.returncode == 0, "a second identical build succeeds", p.stdout + p.stderr)
ok(before == {f: sha(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.startswith("RT-P_")}, "a second build leaves every packet unchanged")
OUT2 = os.path.join(TMP, "out2")
p1 = run(["--results", RES, "--out", OUT2, "--writers", "grok:1"])
first = {f: sha(os.path.join(OUT2, f)) for f in os.listdir(OUT2) if f.startswith("RT-P_")}
p2 = run(["--results", RES, "--out", OUT2, "--writers", "gemini:1,claude:1"])
ok(p1.returncode == 0 and p2.returncode == 0, "a later build adds more writers to the same folder", p1.stderr + p2.stderr)
after = {f: sha(os.path.join(OUT2, f)) for f in os.listdir(OUT2) if f.startswith("RT-P_")}
ok(all(after[f] == first[f] for f in first), "the earlier packets are unchanged by the later build")
ok({f: after[f] for f in after} == before, "the two-step build gives the same packets as the one-step build")
key2 = list(csv.DictReader(open(os.path.join(OUT2, "rt_key_PRIVATE.csv"), newline="", encoding="utf-8")))
ok(len(key2) == 6 and [(r["chat"], r["packet"]) for r in key2] == sorted([(r["chat"], r["packet"]) for r in key2], key=lambda x: (int(x[0]), int(x[1]))), "the key holds all 6 rows in chat order after the two-step build")

# ---------- 6. refusals
p = run(["--results", RES, "--out", os.path.join(TMP, "o3"), "--writers", "chatgpt:4"])
ok(p.returncode != 0 and "no single data reply" in (p.stdout + p.stderr), "a writer run with no data reply stops the build", p.stdout + p.stderr)
p = run(["--results", RES, "--out", os.path.join(TMP, "o4"), "--writers", "claude:1,claude:2"])
ok(p.returncode != 0 and "twice" in (p.stdout + p.stderr), "a writer named twice stops the build")
p = run(["--results", RES, "--out", os.path.join(TMP, "o5"), "--writers", "llama:1"])
ok(p.returncode != 0 and "unknown writer" in (p.stdout + p.stderr), "an unknown writer stops the build")
# an existing packet with other content is not overwritten
victim = os.path.join(OUT, f"RT-P_chat{c['claude']}_packet1.txt")
os.chmod(victim, 0o644)
open(victim, "a", encoding="utf-8").write("tamper\n")
p = run(["--results", RES, "--out", OUT, "--writers", "claude:1"])
ok(p.returncode != 0 and "not overwritten" in (p.stdout + p.stderr), "a packet that exists with other content is not overwritten", p.stdout + p.stderr)
ok(open(victim, encoding="utf-8").read().endswith("tamper\n"), "and the tampered file is left as it was (the builder does not hide it)")
# a changed kit stops the build
BADKIT = os.path.join(TMP, "badkit")
os.makedirs(BADKIT)
for f in ("MANIFEST.sha256", "SILEX-0-GRAMMAR.md", "silex_check.py", "reader_prompts.txt"):
    shutil.copy(os.path.join(KIT, f), BADKIT)
open(os.path.join(BADKIT, "SILEX-0-GRAMMAR.md"), "a", encoding="utf-8").write("\nchanged\n")
p = run(["--results", RES, "--out", os.path.join(TMP, "o6"), "--writers", "claude:1"], kit=BADKIT)
ok(p.returncode != 0 and "HASH MISMATCH" in (p.stdout + p.stderr), "a changed guide stops the build")
# a word that could name a writer inside an item text stops the build
RES2 = os.path.join(TMP, "res2")
shutil.copytree(RES, RES2)
rep = [r for r in cp.load_replies(RES2, False)[0] if r["model"] == "claude" and r["run"] == 1 and r["batch"] == 1][0]
f0 = os.path.join(RES2, rep["files"][0])
txt = open(f0, encoding="utf-8").read()
m = re.search(r"(#01\s*\n```[a-z]*\n)(.*?\n)", txt, flags=re.S)
ok(m is not None, "found item #01 of claude run 1 batch 1 in the copy (test set-up)")
open(f0, "w", encoding="utf-8").write(txt[:m.end(1)] + '"Gemini" ' + txt[m.end(1):])
p = run(["--results", RES2, "--out", os.path.join(TMP, "o7"), "--writers", "claude:1"])
ok(p.returncode != 0 and "could name a writer" in (p.stdout + p.stderr), "a model name inside an item stops the build", p.stdout + p.stderr)

# ---------- 7. the real results folder is untouched
real_after = snapshot(REAL)
changed = [k for k in set(real_before) | set(real_after) if real_before.get(k) != real_after.get(k)]
ok(not changed, "the real results folder is unchanged by the tests", changed[:5])

shutil.rmtree(TMP, ignore_errors=True)
print()
print("ALL %s" % ("PASS" if not fails else f"DONE, {len(fails)} FAIL"))
sys.exit(1 if fails else 0)
