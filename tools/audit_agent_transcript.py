#!/usr/bin/env python3
"""Check that a judge agent stayed inside its task (JUDGING_PROCEDURE.md rule 6). It reads the agent's transcript file (JSONL) and lists every tool call;
it prints only the tool names and the paths they used, never the contents of a sheet or a reply.

Allowed for an agent whose group prompt is PROMPT (the text made by stage_judging.py): Read of its own sheet files and of its own reply files (to check what it wrote),
Write or Edit of its own reply files. Anything else is flagged: another file or folder, Bash, Glob, Grep, a web tool, a second agent, ...
Also reported: for every sheet of the group whether it was read and whether its reply file was written, the number of tool calls, and the model named in the transcript's assistant messages;
with --expect-model (for example claude-fable-5-2 for the first judge, claude-opus-5-5 for the second) any other model, or none, is flagged.

Usage:
  python3 -I audit_agent_transcript.py --transcript FILE.output --prompt GROUPS/group_NN_prompt.txt [--expect-model claude-fable-5-2]
Exit code: 0 no flag and every sheet read and answered, 1 something flagged or missing, 2 usage or file problem.
"""
import argparse
import json
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--expect-model")
    a = ap.parse_args()
    prompt = open(a.prompt, encoding="utf-8").read()
    pairs = re.findall(r"^\d+\.\s+(\S+/sheet_[A-Z0-9]{4}\.txt)\s+->\s+(\S+/reply_[A-Z0-9]{4}\.txt)\s*$", prompt, re.M)
    if not pairs:
        print("no task lines found in the prompt file", file=sys.stderr)
        sys.exit(2)
    sheets = {s for s, _ in pairs}
    replies = {r for _, r in pairs}
    calls = []
    models = {}
    try:
        lines = open(a.transcript, encoding="utf-8").read().splitlines()
    except OSError as e:
        print("cannot read the transcript: %s" % e, file=sys.stderr)
        sys.exit(2)
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message")
        if d.get("type") != "assistant" or not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
            continue
        if msg.get("model"):
            models[msg["model"]] = models.get(msg["model"], 0) + 1
        for x in msg["content"]:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                calls.append((x.get("name"), x.get("input") or {}))
    flagged, read, written = [], set(), set()
    for name, inp in calls:
        path = inp.get("file_path") if isinstance(inp, dict) else None
        if name == "Read" and path in sheets:
            read.add(path)
        elif name == "Read" and path in replies:
            pass
        elif name in ("Write", "Edit") and path in replies:
            written.add(path)
        else:
            flagged.append((name, path if path else "(no file path; input keys: %s)" % ",".join(sorted(inp)) if isinstance(inp, dict) else "(?)"))
    if a.expect_model and set(models) != {a.expect_model}:
        flagged.append(("model", "the transcript names %s, expected only %s" % (", ".join(sorted(models)) or "no model", a.expect_model)))
    unread = sorted(sheets - read)
    unwritten = sorted(replies - written)
    print("tool calls: %d (reads of own sheets %d of %d, writes of own replies %d of %d)" % (len(calls), len(read), len(sheets), len(written), len(replies)))
    print("models named in the transcript: %s" % (", ".join("%s x%d" % (m, n) for m, n in sorted(models.items())) or "none"))
    for name, path in flagged:
        print("  FLAGGED: %s %s" % (name, path))
    for s in unread:
        print("  sheet never read: %s" % s)
    for r in unwritten:
        print("  reply never written: %s" % r)
    sys.exit(1 if (flagged or unread or unwritten) else 0)


if __name__ == "__main__":
    main()
