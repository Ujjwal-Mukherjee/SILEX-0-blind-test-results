SILEX blind test: working tools (not part of the frozen kit). Run everything with python3 -I.
RES = /home/claude/silex_results (data and logs)   KIT = /home/claude/silex_blind_test (frozen, read-only, never write there)
None of these tools scores or reads a reply for meaning.

intake.py  - files one reply or one STEP 2 answer.
  Reply:
    python3 -I RES/tools/intake.py --results RES --src FILE --arm R|N --model claude|chatgpt|grok|gemini --run N \
        --given-batch 1|2 --label "label exactly as the user wrote it" --received "YYYY-MM-DD HH:MM" --how attached|inline [--dry-run]
    Saves recvNN_label-....txt read-only, hashes it, compares it with every earlier file (duplicates), parses it, runs the form checks,
    writes parsed/recvNN.json, adds a row to cells.csv and a table row + form-check paragraph to received_log.md.
    The item numbers decide the batch, not the label. An inline paste is first written to a file exactly as received (plus a final newline) and passed with --how inline.
    cells.csv status: data (counts) | review (held: fix by hand, then set to data) | conflict (that cell is already filled) | duplicate-of-recvNN.
    Held for review: wrong item count, order, over 120 words, search-like words, same item text as an earlier reply (3 or more items),
    guide words in an N reply, cell already filled. Notes only: label mismatch, possible dropped text, text before item 1, trailer after the last item.
    A trailer needs an entry in corrections.json before sheets can be built (the sheet builder refuses otherwise).
  STEP 2:
    python3 -I RES/tools/intake.py --results RES --step2 "answer text" --arm R --model gemini --run 2 --received "HH:MM"
    Right = 104 roots and section 7. Wrong = start a new chat once and give the guide the other way; do not use replies from that chat.

parse_reply.py - the form check intake.py uses (can be run alone: python3 -I parse_reply.py REPLY.txt [--compare OTHER.txt] [--json OUT.json]).

build_judge_sheets.py - one blind sheet per data reply (frozen judge prompt verbatim, random code, shuffled item order, fact list with S marked,
    explanation plus any correction note from corrections.json). Private map, presentation order and seed go to --out (use RES/judging).
    python3 -I RES/tools/build_judge_sheets.py --results RES --kit KIT --out RES/judging [--seed N] [--arms R,N]
    Build once, when all runs are in and the user has agreed how the judge is run. Never show a sheet's map to the judge.

check_judge_reply.py - checks the FORM of a judge's reply to one sheet; items with a problem are listed for a redo of those items only.
    python3 -I RES/tools/check_judge_reply.py --map RES/judging/sheets_map_PRIVATE.csv --kit KIT --code CODE --reply FILE [--json OUT]

test_intake.py, test_judging_tools.py - tests on temp copies and made-up judge replies (nothing real is touched). Re-run after any change.
  test_intake.py was changed 2026-11-14 02:07 IST: it now takes the next recv number from its temp copy and uses run 9, because the first version hard-coded recv20 and run 2
  and failed 8 of 21 checks once the real folder had grown. No change to intake.py or any other tool.

Files in RES: cells.csv (reply -> arm/model/run/batch; add a row per new data reply, intake.py does it), corrections.json (correction notes by reply and item),
received_log.md (master log), leak_checks.md, parsed/ (items as JSON), recvNN_*.txt (raw replies, byte for byte).
Rules decided during the run are in the protocol doc, section "Handling rules added during the main run".

TEST F (find the fault): tools. Same rules: python3 -I, form only, none of it is part of any frozen kit. KITF = the Test F kit folder.
intake_f.py   - files one Test F reply or one STEP 2 answer (arm FR or FN). Same steps as intake.py, except: the cell table is cells_F.csv (not cells.csv),
    parsed answers go to parsed_f/, the log is received_log_F.md (made on the first reply), and the recvNN counter is shared with the reading test (a number is never used twice).
    python3 -I RES/tools/intake_f.py --results RES --src FILE --arm FR|FN --model claude|chatgpt|grok|gemini --run N [--given-batch 1|2] \
        --label "label exactly as the user wrote it" --received "YYYY-MM-DD HH:MM" --how attached|inline [--dry-run]
    python3 -I RES/tools/intake_f.py --results RES --step2 "answer text" --arm FR --model gemini --run 2 --received "HH:MM"     (FR chats only)
    Held for review: not exactly the 20 items of one batch, an item answered twice, 4 or more unreadable places, a line that is not an answer but names an item (a correction note),
    search or code-run words, guide words or verdict codes in an FN reply, a cell already filled (status conflict), the same places and phrases as an earlier reply on 8 or more items.
    Notes only: label mismatch, 1 to 3 unreadable places, answers out of order, a phrase over 12 words, text before or after the answers, form notes (no bars, decoration, two places named).
    It never opens the key and never scores.
parse_f_reply.py - the form parser of intake_f.py (alone: python3 -I parse_f_reply.py REPLY.txt [--json OUT.json]).
score_f.py    - the program score, run once after the last run:  python3 -I RES/tools/score_f.py --results RES --kit KITF [--out RES/scores_F] [--include-review]
    Needs the key, so its --out files (items csv, summary json) are private until the last run is scored. Definitions are in its docstring and in README_F.txt.
test_f_tools.py - 50 tests on made-up replies in temporary folders; nothing real is touched.  python3 -I RES/tools/test_f_tools.py [KITF]   Re-run after any change.
WRITING TEST (arm P): tools. Same rules: python3 -I, form only until the validity run, none of it is part of a frozen kit. Rules: P_handling_rules.md (in RES).
KIT = the frozen reading kit folder (guide, checker, order.csv). The private-kit zip is read only by test_p_tools.py (gold items for the tests).
intake_p.py   - files one P reply, a cut-off continuation, or a STEP 2 answer. Like intake_f.py: the cell table is cells_P.csv, parsed replies go to parsed_p/, the log is received_log_P.md
    (made on the first reply, with the hash of the rules file), and the recvNN counter is shared with the other tests.
    python3 -I RES/tools/intake_p.py --results RES --src FILE --model claude|chatgpt|grok|gemini --run N [--given-batch 1|2] --label "label exactly as the user wrote it" \
        --received "YYYY-MM-DD HH:MM" --how attached|inline --guide attached|pasted|unknown [--note "model version, anything the user said"] [--dry-run]
    Cut-off reply, second part:  same call with  --src PART2 --continues recvNN  (the first part); the parts are joined by the rule of section D and the first part's row is re-evaluated.
    STEP 2:  python3 -I RES/tools/intake_p.py --results RES --step2 "answer text" --model gemini --run 2 --received "HH:MM" [--guide ...] [--note ...]
    Held for review (status review): no heading; headings outside one batch; a block before any heading; one block with several headings; a heading with more text on its line; fewer than 20 items;
    a reply that ends inside an open block; search or code-run words; a cell already filled (status conflict). Notes only: label mismatch, text before/after, out of order, repeated heading,
    no fence, split item, heading inside the block, joined parts. It never runs the checker and never opens a key.
parse_p_reply.py - the form parser (alone: python3 -I parse_p_reply.py REPLY.txt [PART2.txt ...] [--json OUT.json]).
settle_p.py   - settle a held reply:  python3 -I RES/tools/settle_p.py --results RES --recv recvNN --status data|excluded --why "reason" [--when "YYYY-MM-DD HH:MM"]   (dated line in the log)
                the grid of what is filed:  python3 -I RES/tools/settle_p.py --results RES --grid
check_p.py    - the validity run, ONCE, after the last P reply:  python3 -I RES/tools/check_p.py --results RES --kit KIT [--out RES/validity_P] [--include-review]
    Verifies the guide and the checker against KIT/MANIFEST.sha256 first, parses the saved reply files again, runs silex_check.py --messages on every item (own process per block),
    writes items.csv, raw/ (the checker's full output per item), summary.json and summary.md. Primary validity, checker-ok and joined-ok are defined in the rules (15 to 17).
test_p_tools.py - 74 checks on made-up replies (gold items, the pilot reply, mutations) in temporary folders; nothing real is touched.  python3 -I RES/tools/test_p_tools.py [KIT]   Re-run after any change.

