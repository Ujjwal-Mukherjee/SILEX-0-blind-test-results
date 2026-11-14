ROUND TRIP (arms RTP = SILEX reader, RTE = English reader): tools. Same rules as the other arms: python3 -I, form only, none of it is part of a frozen kit. Rules: RT_handling_rules.md (in RES).
KIT = the frozen reading kit folder (facts.csv, judge_roundtrip.txt, reader_prompts.txt, MANIFEST).
Packets: build_roundtrip_p.py (README: tools/test_roundtrip_p.py) and build_roundtrip_e.py (tools/README_E.txt). The keys (rt_key_PRIVATE.csv, rt_key_E_PRIVATE.csv) say which writer each chat reads; no tool below opens them.
intake_rt.py - files one reader reply or a STEP 2 answer (RTP chats only). Built on intake.py: same parse (parse_reply.py), same files (cells.csv, parsed/, received_log.md).
    python3 -I RES/tools/intake_rt.py --results RES --src FILE --arm RTP|RTE --model grok --chat 2 [--given-batch 1|2] --label "RT P chat 2 packet 1" \
        --received "YYYY-MM-DD HH:MM" --how attached|inline [--seed TEXT] [--dry-run]
    python3 -I RES/tools/intake_rt.py --results RES --step2 "104 roots, section 7" --arm RTP --model grok --chat 2 --received "HH:MM" [--dry-run]
    --model is the READER model; --chat is the packet file's chat number (stored in the run column of cells.csv). The packet order it compares with is computed from the seed of the build
    (default = the build's seed), a different order is only a note. Held for review: not 20 items of one batch, over 120 words, search-like words, cell already filled, 3+ items identical to an earlier reply,
    guide words in an RTE reply. Settle a held reply as in the reading tests (cells.csv status edited with a dated line in received_log.md, with the user).
build_judge_sheets_rt.py - blind judge sheets for the round trip:
    python3 -I RES/tools/build_judge_sheets_rt.py --results RES --kit KIT --out OUTDIR [--seed N] [--arms RTP,RTE]
    judge_roundtrip.txt verbatim, C facts only (own numbers from facts.csv), items and sheets shuffled, no writer/chat/arm/reader on a sheet; sheets_map_PRIVATE.csv, judge_order_PRIVATE.txt, build_info_PRIVATE.json.
check_judge_reply_rt.py - form check of a judge reply to one round-trip sheet (C facts only):
    python3 -I RES/tools/check_judge_reply_rt.py --map OUTDIR/sheets_map_PRIVATE.csv --kit KIT --code CODE --reply FILE [--json OUT]
test_rt_tools.py - 46 checks on SYNTHETIC reader and judge replies in temporary folders; nothing real is touched.  python3 -I RES/tools/test_rt_tools.py [KIT]   Re-run after any change.
