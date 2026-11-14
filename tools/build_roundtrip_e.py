#!/usr/bin/env python3
"""Build the round-trip reader packets of arm E (English baseline): rules 15 and 16 of E_handling_rules.md.
FORM ONLY: never opens a key, never scores. Built on build_roundtrip_p.py (same seed, same item order, same layout), so the two arms are shown to the reader in the same way.

  python3 -I build_roundtrip_e.py --results DIR --kit KIT --out DIR/roundtrip_E --writers claude:1,chatgpt:1,grok:1,gemini:1 [--seed TEXT]

  --writers   model:run pairs, the run of that writer whose items are read back (arm E has run 1 only).
  Output (in --out): RT-E_chat1_packet1.txt ... (one reader chat per writer, two packets per chat), rt_key_E_PRIVATE.csv, README_RT_E.txt.
  A packet = the English reader text of reader_prompts.txt (with the item range of the batch), then 20 items as "#NN" and a fenced block, in the layout of the SILEX packets.
  The writer's text is the item text of rule 9 (non-blank lines, rule lines dropped, as written). An item with no text (NONE, missing, empty) is a block holding the single line NONE.
  Order: the same as the SILEX packets of the same batch. Chat numbers: the four writers sorted by sha256 of "SEED|chatE|model" (separate from the SILEX round trip).
  Nothing in a packet names a writer, a model, a run or an arm. The key (rt_key_E_PRIVATE.csv) is kept from the judge.
"""
import argparse, csv, hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_e_reply as pe          # noqa: E402
import build_roundtrip_p as brp     # noqa: E402
import check_p as cp                # noqa: E402  (verify_kit only)

DEFAULT_SEED = brp.DEFAULT_SEED
MODELS = brp.MODELS
BANNED = re.compile(r"(?i)\b(claude|chatgpt|gpt|grok|gemini|openai|anthropic|google|xai|sonnet|argon|arm\s+[pe]|run\s+\d|high\s+run)\b")


def chat_numbers(seed):
    order = sorted(MODELS, key=lambda m: brp.h(f"{seed}|chatE|{m}"))
    return {m: i + 1 for i, m in enumerate(order)}


def english_header(kit):
    """The English reader text of reader_prompts.txt: the lines after the SECOND dashed line, up to and including ITEMS."""
    lines = open(os.path.join(kit, "reader_prompts.txt"), encoding="utf-8").read().split("\n")
    dashes = [i for i, l in enumerate(lines) if l.startswith("-----")]
    if len(dashes) < 2:
        sys.exit("reader_prompts.txt: no second dashed line (the English reader text)")
    start = dashes[1] + 1
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "ITEMS")
    text = "\n".join(lines[start:end + 1])
    if text.count(brp.RANGE1) != 1:
        sys.exit("reader_prompts.txt: the English reader text does not hold the item range once")
    return text


def load_replies(results):
    """-> list of dicts (cell, recv, model, run, batch, texts) for every first-part row of status data in cells_E.csv."""
    rows = list(csv.DictReader(open(os.path.join(results, "cells_E.csv"), newline="", encoding="utf-8")))
    cont = {}
    for r in rows:
        if r["status"].startswith("continuation-of-"):
            cont.setdefault(r["status"].split("-of-")[1], []).append(r)
    out = []
    for r in rows:
        if r["status"] == "data":
            files = [r["file"]] + [c["file"] for c in sorted(cont.get(r["recv"], []), key=lambda x: x["recv"])]
            out.append({"cell": f"E-{r['model']}-{r['run']}-b{r['batch']}", "recv": r["recv"], "model": r["model"], "run": int(r["run"]),
                        "batch": int(r["batch"]), "texts": [open(os.path.join(results, f), encoding="utf-8").read() for f in files]})
    return out


def item_text(item):
    if item is None or item["status"] == "missing" or item["state"] in ("none", "empty", "missing"):
        return "NONE"
    if any(l.strip().startswith(("```", "~~~")) for l in item["text"].split("\n")):
        sys.exit("an item text holds a line of backticks or tildes: it would break the fence of the packet; the build is stopped")
    return item["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--writers", required=True)
    ap.add_argument("--seed", default=DEFAULT_SEED)
    a = ap.parse_args()
    guide_sha, check_sha = cp.verify_kit(a.kit)
    writers = []
    for pair in a.writers.split(","):
        m, r = pair.split(":")
        if m not in MODELS:
            sys.exit(f"unknown writer {m}")
        writers.append((m, int(r)))
    if len({m for m, _ in writers}) != len(writers):
        sys.exit("a writer is named twice")
    replies = load_replies(a.results)
    chats = chat_numbers(a.seed)
    header = english_header(a.kit)
    ids1 = [f"#{n:02d}" for n in range(1, 21)]
    ids2 = [f"#{n:02d}" for n in range(21, 41)]
    order = {1: brp.item_order(a.seed, ids1), 2: brp.item_order(a.seed, ids2)}
    os.makedirs(a.out, exist_ok=True)
    key_rows, made = [], []
    for m, run in sorted(writers, key=lambda w: chats[w[0]]):
        for batch in (1, 2):
            rep = [r for r in replies if r["model"] == m and r["run"] == run and r["batch"] == batch]
            if len(rep) != 1:
                sys.exit(f"no single data reply for {m} run {run} batch {batch} (found {len(rep)})")
            rep = rep[0]
            parsed = pe.parse_parts(rep["texts"])
            ids = ids1 if batch == 1 else ids2
            texts = {i: item_text(parsed["items"].get(i)) for i in ids}
            packet = brp.render_packet(brp.header_for(header, batch), order[batch], texts)
            hit = sorted({x.group(0).lower() for x in BANNED.finditer(packet)})
            if hit:
                sys.exit(f"{m} run {run} batch {batch}: the packet holds a word that could name a writer, a model or an arm: {hit}")
            n_none = sum(1 for i in ids if texts[i] == "NONE")
            other = [i for i in ids if parsed["items"].get(i) and parsed["items"][i]["state"] == "text" and parsed["items"][i]["other_lines"] > 0]
            fname = f"RT-E_chat{chats[m]}_packet{batch}.txt"
            path = os.path.join(a.out, fname)
            if os.path.exists(path):
                if open(path, encoding="utf-8").read() != packet:
                    sys.exit(f"{path} exists with other content; it is not overwritten")
            else:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(packet)
                os.chmod(path, 0o444)
            made.append(fname)
            key_rows.append({"chat": chats[m], "packet": batch, "file": fname, "writer": m, "writer_run": run, "source_cell": rep["cell"],
                             "source_recv": rep["recv"], "none_items": n_none, "items_with_non_message_lines": " ".join(other),
                             "sha256_16": hashlib.sha256(packet.encode("utf-8")).hexdigest()[:16], "item_order": " ".join(order[batch])})
    keypath = os.path.join(a.out, "rt_key_E_PRIVATE.csv")
    old = []
    if os.path.exists(keypath):
        old = [r for r in csv.DictReader(open(keypath, newline="", encoding="utf-8")) if r["file"] not in made]
        os.chmod(keypath, 0o644)
    allrows = sorted(old + key_rows, key=lambda r: (int(r["chat"]), int(r["packet"])))
    cols = ["chat", "packet", "file", "writer", "writer_run", "source_cell", "source_recv", "none_items", "items_with_non_message_lines", "sha256_16", "item_order"]
    with open(keypath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(allrows)
    os.chmod(keypath, 0o444)
    readme = os.path.join(a.out, "README_RT_E.txt")
    readme_text = (
        "Round trip, arm E (English reader). Chat numbers and item order are fixed by the seed below and by sha256, so the packets can be rebuilt exactly.\n"
        f"Seed: {a.seed}\nKit guide sha256 {guide_sha[:16]}, checker sha256 {check_sha[:16]} (verified against the kit MANIFEST before the build; the English reader gets no guide).\n"
        "Per reader chat: a NEW temporary chat, NO guide and no STEP 2, packet 1; wait for the reply; then packet 2. The same reader model and the same thinking setting as in the SILEX round trip.\n"
        "A packet shows only the writer's English text for each item (as written; blank lines and horizontal rules dropped).\n"
        "An item with no text from the writer (NONE, missing, empty) appears as a block holding the single line NONE.\n"
        "rt_key_E_PRIVATE.csv says which writer each chat reads; it is kept from the judge.\n")
    if not os.path.exists(readme) or open(readme, encoding="utf-8").read() != readme_text:
        if os.path.exists(readme):
            os.chmod(readme, 0o644)
        with open(readme, "w", encoding="utf-8") as f:
            f.write(readme_text)
    os.chmod(readme, 0o444)
    print("built:", ", ".join(sorted(made)))
    print("chat numbers (fixed for all four writers):", ", ".join(f"chat {n} = {m}" for m, n in sorted(chats.items(), key=lambda x: x[1])))
    for r in key_rows:
        print(f"  chat {r['chat']} packet {r['packet']}: writer {r['writer']} run {r['writer_run']} ({r['source_cell']}, {r['source_recv']}), NONE items {r['none_items']}, "
              f"items with non-message lines {len(r['items_with_non_message_lines'].split())}, sha256 {r['sha256_16']}")


if __name__ == "__main__":
    main()
