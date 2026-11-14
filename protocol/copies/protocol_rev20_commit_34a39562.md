# SILEX blind test protocol

Nov 13, 2026 · @Moonbeam

Forty fixed items, four AI models that have never seen SILEX-0, a fresh chat for every run: the test measures how much the models recover when they read SILEX-0 and how well they write it, with every prompt and scoring rule fixed before the first run.

## What this test can show

It answers two questions about SILEX-0 (edition 0.14s, roots from r6.6): can an AI that has never seen it read it, and can it write it, using only the guide?

- **Reading with the guide (arm R):** the share of 146 key facts a model recovers from 40 SILEX items. 127 are content facts (C). 19 are status facts (S) that only the guide's rules give, such as whether a word is pinned.
- **Reading without the guide (arm N):** the same items, no guide. The gap between R and N is what the guide adds.
- **Writing (arm P):** the model gets 40 scenarios in English and writes SILEX. Your checker gives every message a verdict. A second model then reads what was written (the round trip) and the content facts are scored again.
- **Plain-English baseline (arm E):** the same scenarios written as short plain English and read back the same way. It shows what the round trip costs in English, and how long the messages are.

It cannot show that SILEX beats English in general, that results would hold on other items, or that any message is true. The checker judges form only: it does not run programs or formulas.

## Before the first run

1. **Pilot first** (phase 0 below). Fix any problem in an item or a prompt once, and list each change.
2. **Freeze.** After the pilot changes, nothing in the file table at the end of this document may change. Its SHA-256 values prove it.
3. **Record the date.** Create a private repository on GitHub, upload every frozen file and this document, and commit. The commit time is the pre-registration. Keep the repository private until the last run is scored, because models with web search could otherwise find the key.
4. **Name the edition** in the paper: SILEX-0 0.14s. The guide says its roots are those of r6.6, not r6.4.
5. **Errata rule.** If an item proves wrong after the first main run, drop it for every model and every arm, and list it. Never fix it and rerun only some sessions.

## Rules for every session

Each run is a new temporary chat with memory, personalisation, custom instructions, web search, browsing and code tools all off. Nothing is attached or pasted except what the steps say. If an app has no switch for web search (as in the Claude app used here), the line "No web search" in the packet is the control: write "search: prompt only" on the label line, and look in each reply for signs of searching.

1. **Leak check, once per model,** in its own separate temporary chat before any other session of that model: paste STEP 1 from start\_prompts.txt. If the model says it knows SILEX, mark that model "exposed" in every result. Never paste it inside a test session, because it would hint at what the notation is.
2. **Reading and writing with the guide (arms R and P):** give SILEX-0-GRAMMAR.md the same way for every model and record the way (attached or pasted). Then paste STEP 2, the reading check. The right answer is 104 roots and section 7. If it is wrong, start a new chat once and give the guide the other way.
3. **Reading without the guide (arm N) and the English baseline (arm E):** no guide and no checks. Go straight to the packet.
4. Paste the whole packet file and nothing else. Wait for the full reply. If the app cuts it off, write "continue" and note that you did.
5. In the same chat, paste the second batch of the same arm. Two batches make one run.
6. Copy each reply exactly as given. Do not correct, shorten or comment on it.

## Phases and run order

Do phase A first: it gives the headline result on its own. Change the order of the models between runs (run 1: Claude, ChatGPT, Grok, Gemini; run 2 in reverse; run 3: Grok, Gemini, Claude, ChatGPT) so no model always goes first.

| Phase | What you run | Files to paste | Guide | Pastes |
| --- | --- | --- | --- | --- |
| 0 Pilot | one model, one run, batch 1 only | R\_batch1, P\_batch1 | yes | 2 |
| A Reading | R: 4 models x 3 runs | R\_batch1, R\_batch2 | yes | 24 |
| A Reading | N: 4 models x 1 run | N\_batch1, N\_batch2 | no | 8 |
| B Writing | P: 4 models x 3 runs | P\_batch1, P\_batch2 | yes | 24 |
| B Round trip | one reader model reads each writer's run 1 | reader packets built by Claude | yes | 8 |
| C English | E: 4 models x 1 run | E\_batch1, E\_batch2 | no | 8 |
| C Round trip | the same reader reads each writer's English | reader packets built by Claude | no | 8 |

About 80 packet pastes after the pilot: 16 into each of the four models and 16 into the reader model. Use one reader model for every round trip, record which, and do not change it. Every reader packet opens with the text in reader\_prompts.txt; the SILEX reader gets the guide first.

## Collecting the outputs

Send each reply to Claude in this chat, with a label line first: the arm, the model, the run and the batch, for example `R-grok-2-b1`. Arms are R, N, P and E. Add what matters on the same line: model version, how the guide was given, "exposed", "cut off, continued". Paste the text; a screenshot is not enough.

Claude then:

1. saves each reply as a file and splits it by item number;
2. runs your checker on every SILEX block the writers produced;
3. builds the reader packets, with the writer's identity removed and the items shuffled;
4. builds the judge sheets, scores them blind, and fills the scoring sheet.

Your part afterwards: audit 30 judged facts picked at random, and run the second-judge pass on 20% of the outputs.

## Scoring

| Measure | How it is scored |
| --- | --- |
| Recovery (R, N) | Each key fact is scored 1 or 0 by the judge. Score = facts credited / facts, reported for C facts, S facts and all facts, overall and by tier. |
| False statements | The judge counts things a reading says that contradict the item. Reported per 20 items. |
| Validity (P) | Every SILEX block goes through your checker as its own conversation. An item is valid only when all its messages are ok. NONE, a missing item or any verdict makes it invalid. A comment, or English outside a gloss, counts as a broken rule, and the block is checked with comments removed. |
| Round trip (P, E) | A reader who never saw the scenario restates the writer's messages. The judge scores the scenario's C facts against that restatement. S facts are not used here. |
| Length | Characters per item: the writer's SILEX, the gold SILEX, and the writer's English. Descriptive only. |

**Judging.** One fixed judge scores everything with the frozen prompts judge\_recovery.txt and judge\_roundtrip.txt. It sees fact lists and explanations only, shuffled, with no model name, run or arm. Scores are 1 or 0. In the writing arm the names of newly defined words are free: the judge checks what a word means, not how it is spelled.

**Audit.** You check 30 judged facts chosen at random, reading only the fact and the explanation. A different model re-judges 20% of the explanations. If either disagrees with the first judge on more than 10% of facts, the second model re-judges everything and both sets are reported.

## Predictions and analysis

Written before any run. They may not be changed afterwards; add a note instead.

1. With the guide, each model recovers at least 20 points more of the C facts than without it (R minus N).
2. With the guide, each model scores higher on tier 1 than on tier 5.
3. At least half of each model's written items pass the checker.
4. No prediction for length, or for the round-trip comparison with English: both are reported as found.

Analysis: per model, the mean of its three runs with the lowest and highest run; the same by tier; the R minus N gap per item with a bootstrap 95% interval over items; the share of valid items; round-trip scores for SILEX and English side by side; median length. Items dropped by the errata rule are listed. A result that goes against a prediction goes in the same table as the rest.

## Limits and safeguards

- **One author.** Claude wrote the items and the key, is one of the four models tested, and is the first judge. Safeguards: all 40 gold items passed your checker before any run, the rubric is frozen, judging is blind and shuffled, you audit 30 facts, and a second model re-judges 20%. A stronger version has a second model write 10 more items.
- **Forty items, one fixed order.** Order effects are the same for every model but are not removed.
- **Guide delivery.** Apps may read a 181 KB attachment in parts. The reading check and the recorded delivery method exist for that reason.
- **Moving targets.** Apps change models without notice. Record the model version and date of every session.
- **Form, not truth.** The checker does not run programs or formulas. The computed answers inside the items (such as 120, 36 and 17) were verified separately in Python and are not scored as facts.
- **Four models, one month.** The results describe these models in November 2026.
- **The English baseline** is written by the same kind of models. It is a reference point, not a ceiling.
- **Prior exposure** is checked only through the leak check, which covers what a model says it knows.
- **Status cue.** The reading prompt asks the model to say whether things are asserted, agreed, adopted, pinned or shared, which cues the status (S) facts. This is deliberate: S facts measure whether the guide's rules are applied, not whether the model thinks to mention status. The no-guide prompt gives no such cue.
- **Ceiling.** In the pilot, Claude with the guide earned credit on every fact and wrote every item validly. If the other models do the same, reading with the guide and the validity score cannot separate them; the no-guide arm, the round trip and the length comparison carry the contrast.

## File hashes

SHA-256 of every file as rebuilt on 2026-11-13 after the pilot fixes listed in the last section. If anything else changes before the first main run, rebuild, replace this table and list what changed; the table in force at the first main run is the frozen one. The first 16 characters are shown here and the full values are in `MANIFEST.sha256`. Check them with `sha256sum -c MANIFEST.sha256` in the folder that holds the files, or attach the files and ask Claude to check.

| File | What it is | SHA-256 (first 16) |
| --- | --- | --- |
| `SILEX-0-GRAMMAR.md` | The guide, edition 0.14s; given to arms R and P | `fd8640fcec49787e` |
| `silex_check.py` | Your checker, used for the validity score | `485065d4fae66e72` |
| `R_batch1.txt` | Reading with the guide, items 1 to 20 | `b222bd8b91ce78f7` |
| `R_batch2.txt` | Reading with the guide, items 21 to 40 | `76f9a197a4dc9d39` |
| `N_batch1.txt` | Reading without the guide, items 1 to 20 | `0f31d11e66227072` |
| `N_batch2.txt` | Reading without the guide, items 21 to 40 | `2115c9a60f3a16b9` |
| `P_batch1.txt` | Writing from English scenarios, items 1 to 20 | `7e75be1d30cfcc72` |
| `P_batch2.txt` | Writing from English scenarios, items 21 to 40 | `dc2c3c2ffc1db891` |
| `E_batch1.txt` | Plain-English baseline, items 1 to 20 | `89df79f2789ab558` |
| `E_batch2.txt` | Plain-English baseline, items 21 to 40 | `7312693b1b5979e1` |
| `start_prompts.txt` | Leak check and reading check | `78c95d76109aa124` |
| `reader_prompts.txt` | Opening text of the round-trip reader packets | `0e5701613e523136` |
| `judge_recovery.txt` | Judge prompt for reading | `eb9a91da7eaffb78` |
| `judge_roundtrip.txt` | Judge prompt for the round trip | `4a42fcefdd04e37a` |
| `answer_key.md` | Private. Items, scenarios and key facts | `ff08196b7ccbc042` |
| `facts.csv` | Private. The 146 key facts | `75a352ac83133078` |
| `order.csv` | Private. Item number, batch and tier | `921671500e36ad19` |
| `silex_scoring.xlsx` | The blank scoring workbook | `1807ed17b39285c3` |
| `silex_kit_PRIVATE.zip` | Private. The scripts that rebuild everything | `92068da312e1f085` |

Private files never go into a test session. They go into the repository only while it is private.

## Changes before the freeze

- 2026-11-13, leak check. The first check on Claude ran with web search on, and the model searched (it found nothing). The Claude app has no switch for search, so the control for every model is a line in the prompt. STEP 1 now ends with "Do not search the web or use any tool; answer only from what you already know."
- 2026-11-13, pilot on Claude, batch 1. With the guide, Claude's reading earned credit for all 80 key facts (judged by Claude, not blind) and its 20 written items all passed the checker. The pilot is not part of the main data. It exposed the four wording faults below, each fixed once.
- Item #08 (reading key and writing scenario) said the best job is "the one with the highest priority". The guide only says "the best member by a criterion". Both now say "best by priority".
- Item #27 (reading key) asked for a computed date. The clause "that is by 2026-11-16 10:00" is removed.
- Item #04 (writing scenario) said "either … or", and the writer chose an exclusive or. It now says the job is ready and nothing blocks it, or the job is done, "at least one of the two holds". Its key fact says the same.
- The reading prompts said "one to three messages", but item #18 has four. They now say "one to four".
- New file `reader_prompts.txt` freezes the opening text of the round-trip reader packets.

## Handling rules added during the main run

Made on 2026-11-13, after the first replies arrived and before any reply was scored. Each rule is the same for every model and arm. No frozen file changed, and the predictions are untouched.

- **Labels.** The batch of a reply is read from its item numbers (#01 to #20 is batch 1, #21 to #40 is batch 2), not from its label. The first labels carried batch numbers where run numbers belong, so each model's first guided reply is filed as run 1 by assumption. From the second round on, every label carries the run number.
- **Re-sends.** A reply sent twice is kept once. Byte-identical re-sends stay on file and are not counted (three so far).
- **What counts as the reply.** Replies are split by item number. App status lines such as "Worked for 27s", a title, and an intro before item 1 are not part of any item, and the judge does not see them. Item numbers written as headings or in bold are accepted.
- **Corrections inside a reply.** A correction note that names an item replaces the earlier wording for that item. The judge sheet shows the item followed by "\[Correction later in the same reply: …\]". It applies to ChatGPT's first guided reply (#02, #05, #09 and #13).
- **Word limit.** The limit of 120 words is counted on words that hold a letter or a digit. No reply has gone over it. An item that does is judged as written and listed.
- **Lost text.** Two no-guide ChatGPT items lost their formulas in the text the app hands over (#13 in batch 1, #25 in batch 2). Copying again gave identical text. They are judged as they stand, with no re-run, and listed as a limit. They touch two facts, #13.F3 and #25.F4, both tier 5.
- **Judge sheets.** One sheet per reply batch, with a random code, shuffled item order, the frozen judge prompt and the fact list (status facts marked S). A private map links each code to model, arm, run and batch. A judge line that is missing, malformed or lists the wrong facts is asked for again, for those items only, with the same prompt. Nothing is filled in by Claude.
- **Not recorded.** Model versions, and whether the guide and the packets were pasted or attached, were not recorded for the first runs. They stay "unknown" unless the user supplies them. A status line in one ChatGPT reply ("Worked for 27s") could mean the app used a tool; this cannot be checked.
- **Blinding limit.** The judge never sees model, run or arm, but style can give the arm away: guided readers use the guide's words (such as "pinned"), unguided readers hedge. The judge prompt says identity must not matter. This is a limit, not a fix.
- **Leak check.** All four models said they do not know SILEX. Claude was asked three times (the first with web search on, which found nothing); the second is the official check.

## Test F: find the fault

Test F asks whether a model can find one planted fault in a short SILEX-0 conversation and name the line, using the line numbers of the numbered form. It was added on 2026-11-13 at 23:22 IST on your go-ahead, before any F chat. The reading kit, its hashes and the predictions are untouched.

- **Items.** 40 conversations, F01 to F40, all in the numbered form (batch 1 is F01 to F20, batch 2 is F21 to F40). 30 hold exactly one planted fault, two for each of the 15 verdicts of guide section 9. 10 are clean. Each batch has one item of every verdict and five clean items, in a random order.
- **Truth.** The guide's own checker decides, not the author: each faulty item gives exactly one verdict at exactly one place, each clean item gives none. A script repeats this from the packets and the key: 40 of 40 agree. The key stays private until the last run is scored.
- **Arms.** FR: the model has the guide (the same single-R file as arm R). FN: no guide. No search, no code and no other tools in either arm.
- **Reply.** One line per item: `F07 | B1.2 | what is wrong, in at most 12 words`, or `F07 | none`. B1.2 is line 2 of message B1; B1.h is the header of B1.
- **Runs.** FR: 2 runs per model (run 1 in the order Claude, ChatGPT, Grok, Gemini; run 2 reversed). FN: 1 run per model (Grok, Gemini, Claude, ChatGPT). That is 12 new temporary chats with memory off, never the chat of a reading-test run. An FR chat starts with the guide and STEP 2 (104 roots, section 7); an FN chat has neither. Labels carry arm, model, run and batch, for example "FR claude run 1 batch 1".
- **Primary score, by a program.** Place found: of the 30 faulty items, how many have exactly the checker's place. False alarms: of the 10 clean items, how many got any answer other than "none". No judge is involved.
- **Also reported.** Detection (any answer other than "none" on a faulty item, right place or not); a lenient place score where, for the two E-REDEF items, the first definition also counts; a table by verdict (two items each, so description only); a Wilson 95% interval, read as orientation because the runs of one model are not independent.
- **Secondary: the phrase.** A fresh blind judge scores each faulty item's phrase 1 or 0 against the key, with the frozen prompt `judge_fault.txt` and the same blind-sheet method as the reading test. A phrase over 12 words is cut after the 12th word first. You are asked before a separate judge is started.
- **Baselines.** A random place among all the places of an item (every line and every header) finds the fault about 26% of the time (7.7 of 30). Always answering "none" finds nothing and raises no false alarm.
- **Form rules, fixed now.** An unreadable place counts as an answer other than "none": a false alarm on a clean item, detected but not found on a faulty one. An item with no answer line counts as no answer. A reply that answers an item twice or adds a correction note is held and settled with you before any score is looked at; a correction the model gives itself in the same reply replaces its earlier answer. A reply with search or code-run words, or (FN only) with words only the guide uses, is held too. Filing never opens the key, and scoring runs once, after the last run.
- **Changes at the freeze.** No item and no key changed. The packet intros said "one to four messages"; the most any item has is three, so they now say "one to three". The batch-2 packets use F21 in the reply example. The scoring wording above was tightened, and the filing and scoring programs were added to the kit.
- **Limits.** 40 items, 12 chats, 4 models, versions not recorded. The items are derived from reading-test items, so the two tests are not independent. The test is form only: the checker does not say whether a statement is true or wise, and two faults per verdict are not a sample of all faults of that kind. A model may recognise the notation from training (the leak checks passed for all four). The author of the items is an AI that is also one of the tested models; the checker, not the author, decides the key, and a blind judge scores the phrases.

**Test F file hashes.** SHA-256 of the files of the Test F kit, made at the freeze. The guide and the checker are the same files as in the table above (`fd8640fcec49787e` and `485065d4fae66e72`).

| File | What it is | SHA-256 (first 16) |
| --- | --- | --- |
| `FR_batch1.txt` | Fault finding with the guide, items F01 to F20 | `3c054f37b1e131ec` |
| `FR_batch2.txt` | Fault finding with the guide, items F21 to F40 | `6c900bc1bf16a6d1` |
| `FN_batch1.txt` | Fault finding without the guide, items F01 to F20 | `f834f9c6d3e72694` |
| `FN_batch2.txt` | Fault finding without the guide, items F21 to F40 | `d795bb57218c23e0` |
| `start_prompts_F.txt` | Steps, STEP 2 reading check and label examples | `fa157bb783aa9d29` |
| `judge_fault.txt` | Judge prompt for the phrases | `7a3956027cca8c6d` |
| `README_F.txt` | Design, scoring and form rules | `d96d7a5e96cfa9a7` |
| `key_F_PRIVATE.csv` | Private. Fault, place and description of every item | `681b7832b4f12424` |
| `items_F_PRIVATE.json` | Private. The 40 items with their build notes | `3315944a031c7429` |
| `tools/` (6 programs) | Filing and scoring programs, frozen with the kit | listed in the manifest |

The whole kit (22 files, with the key and the programs) is listed in `MANIFEST.sha256`; check it with `sha256sum -c MANIFEST.sha256` in the kit folder. The manifest's own SHA-256 is `3e39765f047b077cf8f5c01cb354f3d616c6257ffc0c546bc4cedcf4198da1dc`. The private files are not published before the last run is scored.
