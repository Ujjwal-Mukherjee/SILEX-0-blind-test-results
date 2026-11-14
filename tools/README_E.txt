ENGLISH BASELINE (arm E): tools. Same rules as the other arms: python3 -I, form only, none of it is part of a frozen kit. Rules: E_handling_rules.md (in RES).
KIT = the frozen reading kit folder (reader_prompts.txt, E_batch1/2, MANIFEST). Arm E has no checker and no validity run: its measures are length and the round trip.
parse_e_reply.py - the form parser (alone: python3 -I parse_e_reply.py REPLY.txt [PART2.txt ...] [--json OUT.json]). Built on parse_p_reply.py: same headings, fences, repeated headings, joins.
    Differences: the item text is the non-blank lines under the heading (or the fenced block), horizontal-rule lines dropped, nothing else changed (a # is text);
    the LAST item of a reply is cut after its last message line at the first blank line or rule (what follows is text after the last item); message lines counted for information;
    search/code words are looked for only outside the items.
    Note 1 of the E rules (2026-11-14): a line "#NN <message line>" (the rest holds 'X to Y:' before its first colon) starts an item; the rest of that line is its first line.
intake_e.py   - files one E reply or a cut-off continuation:
    python3 -I RES/tools/intake_e.py --results RES --src FILE --model claude|chatgpt|grok|gemini --run 1 [--given-batch 1|2] --label "label exactly as the user wrote it" \
        --received "YYYY-MM-DD HH:MM" --how attached|inline [--note "model version, setting"] [--dry-run]
    Cut-off reply, second part:  same call with  --src PART2 --continues recvNN.
    Writes recvNN (read-only, shared counter), parsed_e/, cells_E.csv, received_log_E.md (made on the first reply, with the hash of the rules file). Never opens a key.
reparse_e.py  - re-read a held single-part reply with the current parser (Note 1 of the E rules) and lift the hold if nothing else is wrong:
    python3 -I RES/tools/reparse_e.py --results RES --recv recvNN [--when "YYYY-MM-DD HH:MM"] [--dry-run]
    Keeps the first parse as parsed_e/recvNN.before_note1.json (read-only), rewrites parsed_e/recvNN.json, sets the row to data, logs a paragraph and a dated line. Never touches the saved reply.
settle_e.py   - settle a held reply:  python3 -I RES/tools/settle_e.py --results RES --recv recvNN --status data|excluded --why "reason" [--when "YYYY-MM-DD HH:MM"]
                the grid of what is filed:  python3 -I RES/tools/settle_e.py --results RES --grid
build_roundtrip_e.py - the English reader packets (rules 15 and 16), after the writer's two batches are filed:
    python3 -I RES/tools/build_roundtrip_e.py --results RES --kit KIT --out RES/roundtrip_E --writers claude:1,chatgpt:1,grok:1,gemini:1
    Same seed and the same item order as the SILEX packets (build_roundtrip_p.py), its own chat numbers; writes RT-E_chatN_packetB.txt (read-only), rt_key_E_PRIVATE.csv, README_RT_E.txt.
    Verifies the guide and checker hashes in KIT/MANIFEST.sha256 first; stops on a model/arm word in a packet, on a fence line inside an item, on a packet that exists with other content.
test_e_tools.py - 132 checks on made-up replies (the scenario text of the E batches turned into "A to B: ..." lines, plus mutations) in temporary folders; nothing real is touched.
    python3 -I RES/tools/test_e_tools.py [KIT]   Re-run after any change.
