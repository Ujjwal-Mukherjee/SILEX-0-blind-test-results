#!/usr/bin/env python3
"""Build the round-trip reader packets of arm P (rules 20 and 21 of P_handling_rules.md; Addition 1, rule 25).
FORM ONLY: never runs the checker, never opens a key, never scores.

  python3 -I build_roundtrip_p.py --results DIR --kit KIT --out DIR/roundtrip_P --writers claude:1,grok:1,gemini:1 [--seed TEXT]

  --writers   model:run pairs, the run of that writer whose items are read back (rule 20: run 1; rule 25: ChatGPT's high run 1 is run 4).
              Only the writers named are built; the chat numbers are fixed for all four writers, so a later build adds the missing chat
              without changing the others.
  Output (in --out): RT-P_chat1_packet1.txt ... (one reader chat per writer, two packets per chat), rt_key_PRIVATE.csv, README_RT_P.txt.
  A packet = the SILEX reader text of reader_prompts.txt (with the item range of the batch), then 20 items as "#NN" and a fenced block,
  in the same layout as the frozen R packets (R_batch1.txt, R_batch2.txt). The writer's block text is used exactly as the checker saw it
  (comments removed, blank lines removed). An item with no SILEX text (NONE, missing, empty) is a block holding the single line NONE.
  An item whose reply holds several blocks stops the build (the rules have no layout for it).
  Order: the same for every writer (so a position effect cannot favour one writer): the items of a batch sorted by sha256 of "SEED|items|#NN".
  Chat numbers: the four writers sorted by sha256 of "SEED|chat|model". Nothing in a packet names a writer, a model, a run or an arm.
"""
import argparse, csv, hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse_p_reply as pp   # noqa: E402
import check_p as cp          # noqa: E402

DEFAULT_SEED = "SILEX round trip P 2026-11-14"
MODELS = ["claude", "chatgpt", "grok", "gemini"]
RANGE1 = "(items #01 to #20)"
RANGE2 = "(items #21 to #40)"
BANNED = ["claude", "chatgpt", "grok", "gemini", "openai", "anthropic", "google", "xai", "sonnet", "argon", "flash", "arm p", "run 1", "high run"]


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def chat_numbers(seed):
    order = sorted(MODELS, key=lambda m: h(f"{seed}|chat|{m}"))
    return {m: i + 1 for i, m in enumerate(order)}


def item_order(seed, ids):
    return sorted(ids, key=lambda i: h(f"{seed}|items|{i}"))


def silex_header(kit):
    """The SILEX reader text of reader_prompts.txt: the lines after the first dashed line, up to and including ITEMS."""
    lines = open(os.path.join(kit, "reader_prompts.txt"), encoding="utf-8").read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("-----")) + 1
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "ITEMS")
    text = "\n".join(lines[start:end + 1])
    if text.count(RANGE1) != 1:
        sys.exit("reader_prompts.txt: the SILEX reader text does not hold the item range once")
    return text


def header_for(header, batch):
    return header if batch == 1 else header.replace(RANGE1, RANGE2)


def render_packet(header, ids, texts):
    """header (ends with ITEMS) + blank line + the items, each '#NN', a fence line, the text, a fence line; one blank line between items; final newline."""
    blocks = [f"{i}\n```\n{texts[i]}\n```" for i in ids]
    return header + "\n\n" + "\n\n".join(blocks) + "\n"


def item_text(item):
    if item is None or item["status"] == "missing":
        return "NONE"
    blocks = item["blocks"]
    if len(blocks) != 1:
        sys.exit(f"an item with {len(blocks)} blocks: no layout for it in the rules; the build is stopped")
    b = blocks[0]
    if b["none"] or b["empty"] or not b["text"].strip():
        return "NONE"
    if any(l.strip().startswith("```") for l in b["text"].split("\n")):
        sys.exit("an item text holds a line of backticks: it would break the fence of the packet; the build is stopped")
    return b["text"]


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
    replies, _ = cp.load_replies(a.results, False)
    chats = chat_numbers(a.seed)
    header = silex_header(a.kit)
    ids1 = [f"#{n:02d}" for n in range(1, 21)]
    ids2 = [f"#{n:02d}" for n in range(21, 41)]
    order = {1: item_order(a.seed, ids1), 2: item_order(a.seed, ids2)}
    os.makedirs(a.out, exist_ok=True)
    key_rows, made = [], []
    for m, run in sorted(writers, key=lambda w: chats[w[0]]):
        for batch in (1, 2):
            rep = [r for r in replies if r["model"] == m and r["run"] == run and r["batch"] == batch]
            if len(rep) != 1:
                sys.exit(f"no single data reply for {m} run {run} batch {batch} (found {len(rep)})")
            rep = rep[0]
            parsed = pp.parse_parts(rep["texts"])
            ids = ids1 if batch == 1 else ids2
            texts = {i: item_text(parsed["items"].get(i)) for i in ids}
            packet = render_packet(header_for(header, batch), order[batch], texts)
            low = packet.lower()
            hit = [w for w in BANNED if w in low]
            if hit:
                sys.exit(f"{m} run {run} batch {batch}: the packet holds a word that could name a writer, a model or an arm: {hit}")
            n_none = sum(1 for i in ids if texts[i] == "NONE")
            fname = f"RT-P_chat{chats[m]}_packet{batch}.txt"
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
                             "source_recv": rep["recv"], "none_items": n_none, "sha256_16": hashlib.sha256(packet.encode("utf-8")).hexdigest()[:16],
                             "item_order": " ".join(order[batch])})
    keypath = os.path.join(a.out, "rt_key_PRIVATE.csv")
    old = []
    if os.path.exists(keypath):
        old = [r for r in csv.DictReader(open(keypath, newline="", encoding="utf-8")) if r["file"] not in made]
        os.chmod(keypath, 0o644)
    allrows = sorted(old + key_rows, key=lambda r: (int(r["chat"]), int(r["packet"])))
    cols = ["chat", "packet", "file", "writer", "writer_run", "source_cell", "source_recv", "none_items", "sha256_16", "item_order"]
    with open(keypath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(allrows)
    os.chmod(keypath, 0o444)
    readme = os.path.join(a.out, "README_RT_P.txt")
    readme_text = (
        "Round trip, arm P (SILEX reader). Chat numbers and item order are fixed by the seed below and by sha256, so the packets can be rebuilt exactly.\n"
        f"Seed: {a.seed}\nGuide sha256 {guide_sha[:16]}, checker sha256 {check_sha[:16]} (verified against the kit MANIFEST before the build).\n"
        "Per reader chat: a NEW temporary chat, the guide (SILEX-0-GRAMMAR.md) attached first, then the STEP 2 reading check (text in start_prompts.txt),\n"
        "then packet 1; wait for the reply; then packet 2. The same reader model and the same thinking setting in all reader chats.\n"
        "A packet shows only the writer's SILEX text for each item (comments removed, as the checker reads it); checker verdicts are not shown to the reader.\n"
        "An item with no SILEX text from the writer (NONE, missing, empty) appears as a block holding the single line NONE.\n"
        "rt_key_PRIVATE.csv says which writer each chat reads; it is kept from the judge.\n")
    if not os.path.exists(readme) or open(readme, encoding="utf-8").read() != readme_text:
        if os.path.exists(readme):
            os.chmod(readme, 0o644)
        with open(readme, "w", encoding="utf-8") as f:
            f.write(readme_text)
    os.chmod(readme, 0o444)
    print("built:", ", ".join(sorted(made)))
    print("chat numbers (fixed for all four writers):", ", ".join(f"chat {n} = {m}" for m, n in sorted(chats.items(), key=lambda x: x[1])))
    for r in key_rows:
        print(f"  chat {r['chat']} packet {r['packet']}: writer {r['writer']} run {r['writer_run']} ({r['source_cell']}, {r['source_recv']}), NONE items {r['none_items']}, sha256 {r['sha256_16']}")


if __name__ == "__main__":
    main()
