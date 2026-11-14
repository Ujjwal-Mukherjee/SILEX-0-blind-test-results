SILEX blind test: TEST F (find the fault)
FROZEN on 2026-11-13 (IST), on the user's go-ahead, before any F chat. Not part of the reading kit (silex_blind_test), which is unchanged.
Every file of this kit is listed with its sha256 in MANIFEST.sha256 (made at the freeze; check with: sha256sum -c MANIFEST.sha256).
A change after the freeze is made only as a dated entry in received_log_F.md and a new hash; nothing is changed silently.

WHAT IT TESTS
Whether a model can find one planted fault in a short SILEX-0 conversation and say where it is, using the line numbers of the numbered form
(guide section 1.3), which exist so that a fault can be pointed at. Two arms:
  FR  the model has the guide (same file as the reading test, consolidated edition 0.14s, sha256 fd8640fc...).
  FN  the model has no guide.

ITEMS
40 conversations, F01 to F40 (batch 1 = F01-F20, batch 2 = F21-F40). 30 have exactly one planted fault, 10 have none.
The 30 faults are two for each of the 15 verdicts of guide section 9: E-SYN E-LEX E-ARITY E-KIND E-NAME E-REDEF E-HEAD E-TIME E-QUOTE E-ENGLISH E-BUDGET E-REF E-COUNT E-CODE E-MATH.
Each batch holds one item of every verdict and five clean items, in a random order (seed in the private build info).
Every item is a conversation of the reading test with one planted fault (25 faulty items; in 6 of them the fault is one added line), or a new short message with one planted fault (5 items),
or a conversation of the reading test left as it was (the 10 clean items). All are in the numbered form.
Two of the faults are faults of the numbered form itself: a header with a number in front of it (E-HEAD) and a line with no number (E-COUNT).

TRUTH
The truth for every item is the guide's own checker, silex_check.py (same file as in the reading kit, sha256 485065d4...), not the author's opinion:
each faulty item gives exactly one verdict at exactly one place, each clean item gives none. verify_items_F.py repeats this from the packets and the key:
    python3 -I verify_items_F.py        (expected last line: ALL OK)
Places are named as the checker names them: A1.2 = line 2 of message A1 (by position, which in the numbered form is also the number shown); A1.h = the header of A1.
The checker judges form only. It does not say whether a statement is true or wise, and neither does this test.

WHAT THE MODEL DOES
For each item it replies with one line:  F07 | B1.2 | what is wrong in at most 12 words    or    F07 | none.

SCORING (fixed before any reply is read)
Primary, per model and arm and run, reported as two numbers:
  1. Place found: of the 30 faulty items, how many have exactly the checker's place (a program scores this).
  2. False alarms: of the 10 clean items, how many got any answer other than "none".
Also reported: detection (any answer other than "none" on a faulty item, right place or not); a lenient place score where, for the two E-REDEF items, the first definition also counts;
a table by verdict (two items each, so for description only).
Form rules, fixed now: an answer whose place cannot be read counts as an answer other than none (a false alarm on a clean item; detected but not found on a faulty one);
an item with no answer line counts as no answer; a phrase over 12 words is cut after the 12th word before judging (the place is not affected).
A reply that answers an item twice or adds a correction note is held and settled with the user before any score is looked at; a correction the model itself gives
in the same reply for an item replaces its earlier answer (the rule of the reading test). A reply with search or code-run words, or (FN only) with words that only the guide uses, is held too.
Secondary: the phrase. A fresh blind judge scores each faulty item's phrase 1 or 0 against the key (judge_fault.txt, same blind-sheet method as the reading test);
reported for all faulty items and for those where the place was right. The key text is key_F_PRIVATE.csv (private until the last run is scored).
Baselines: a random place among all the places of an item (every line and every header) hits the fault about 26 % of the time (7.7 of 30);
always answering "none" gets the 10 clean items right and finds no fault.

RUNS
FR: 2 runs per model (run 1 in the order Claude, ChatGPT, Grok, Gemini; run 2 in reverse). FN: 1 run per model (order Grok, Gemini, Claude, ChatGPT).
That is 12 new temporary chats, memory off, never the same chat as a reading-test run (a reader who has just read the valid versions would remember them).
Steps are in start_prompts_F.txt.

LIMITS (to be stated in the report)
Small samples: 40 items, 12 chats, 4 models, versions not recorded. The items are derived from the reading-test items, so the two tests are not independent.
The test is form only. The two faults per verdict are not a sample of all faults of that kind. A model may recognise the notation from training (the leak checks passed for all four).
The author of the items is an AI that is also one of the tested models; the checker, not the author, decides the key, and a blind judge scores the phrases.

FILES
FR_batch1.txt FR_batch2.txt   packets with the guide        FN_batch1.txt FN_batch2.txt   packets without the guide
start_prompts_F.txt           steps and the reading check    judge_fault.txt               prompt of the blind judge for the phrases
key_F_PRIVATE.csv items_F_PRIVATE.json   private key and the items with their build notes (do not publish before the last run is scored)
verify_items_F.py             re-checks every item with the checker    SILEX-0-GRAMMAR.md silex_check.py   the guide and the checker (same bytes as in the reading kit)
tools_private/                the scripts that made the items and the key
tools/                        the programs that file and score the replies (intake_f.py parse_f_reply.py score_f.py test_f_tools.py, and intake.py parse_reply.py that intake_f.py imports),
                              frozen with the kit so that the scoring is fixed before any reply. Their tests: python3 -B -I tools/test_f_tools.py   (README_F_tools.txt says how they are used)
