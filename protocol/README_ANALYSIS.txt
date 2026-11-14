ANALYSIS PLAN AND AGGREGATOR (written and committed before any judging)
ANALYSIS_PLAN.md          how every number of the report is computed (fixed before any judge sheet exists)
tools/aggregate.py        makes the tables from the checked judge files, the sheet maps, the round-trip keys, the validity files and the parsed English replies; it scores nothing
tools/test_aggregate.py   281 checks on made-up data in temporary folders (the real kit files are only read); the judge replies go through the real form checkers and the English replies through the real parser
tools/check_judge_reply.py, tools/build_judge_sheets.py, tools/test_judging_tools.py, tools/test_intake.py
                          the reading-test judge tools (written 2026-11-13, unchanged); they were not in the repository before this commit. README_tools_reading_and_P.txt is the README of the results tools folder.
The tests import and run check_judge_reply.py (this folder), check_judge_reply_rt.py (silex_blind_test_roundtrip_RT/tools) and parse_e_reply.py (silex_blind_test_E_tools/tools): put the tools of the folders you need into ONE folder, then
  python3 -I test_aggregate.py [KIT]
Run the aggregator:
  python3 -I aggregate.py --results RES --kit KIT --out OUTDIR --reading-map MAP --reading-scores DIR [--rt-map MAP --rt-scores DIR --rt-key-p FILE --rt-key-e FILE] [--validity DIR ...] [--judge-note TEXT] [--boot N] [--partial]
The aggregator opens the private sheet maps and keys, so it runs only after the last judge reply is checked.

JUDGING_PROCEDURE.md      how the judge agents are run and how the reliability checks are done (fixed before any judge sheet exists; seeds fixed in it)
tools/stage_judging.py    copies sheets into an inbox (read-only), groups them (at most 6 per agent, random order), writes the exact text to give each agent
tools/collect_judge_replies.py  copies each reply file byte for byte (read-only), logs its sha256, checks only the FORM and writes the JSON for the aggregator; prints no score
tools/audit_agent_transcript.py lists every tool call of a judge agent from its transcript (names and paths only) and flags anything outside its own sheets and reply files
tools/make_redo_sheet.py  cuts a redo sheet (only the items with a form problem) out of an existing sheet; the redo reply is collected with --suffix _redo1
tools/reliability.py      second-judge draw and comparison (random 20 percent of the judged explanations), audit draw and comparison (30 judged facts for the user)
tools/test_reliability.py (61 checks) and tools/test_judging_stage.py (67 checks): made-up data in temporary folders; the real sheet builders and form checkers are run on it
The new tests also import build_judge_sheets_rt.py and check_judge_reply_rt.py (folder silex_blind_test_roundtrip_RT/tools): put the tools of both folders into ONE folder, then
  python3 -I test_reliability.py [KIT]     python3 -I test_judging_stage.py [KIT]
