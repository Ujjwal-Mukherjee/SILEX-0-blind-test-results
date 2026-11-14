# English baseline (arm E): handling rules

Written on 2026-11-14 at about 05:20 IST (the file hash and the exact time of the hash are in received_log.md). No English-baseline chat had been run when this was written, and no reply of arm E had been received or opened.
The rules are the same for every model. No frozen file changes. The predictions are untouched (prediction 4: no prediction for length or for the round trip against English; both are reported as found).
They follow the rules of the writing test (P_handling_rules.md) wherever English allows it, so that the two arms are filed, measured and shown to readers in the same way.

**Principle.** A case these rules do not cover is held for review, settled with the user, added at the end of this file as a dated rule, and applied to every reply of that kind.
Filing never opens a key and never scores. Arm E has no checker and no validity run: its measures are the length (section F) and the round trip (section E).

## A. Running the chats
1. 4 chats: 4 models x 1 run (run 1). Order: Claude, ChatGPT, Grok, Gemini. Each chat is a new temporary chat with memory, personalisation, custom instructions, web search, browsing and code tools off; never a chat of another test.
   No guide, no STEP 1 and no STEP 2 (the leak check was done once per model before its first session). In a chat: E_batch1 -> reply, then E_batch2 -> reply.
2. Settings. ChatGPT at its highest thinking setting (rule 27 of P_handling_rules.md: every new test from now on). Claude with "Extra" and Grok with "heavy" as in every chat so far. For Gemini the user names the model in the first message.
   The user states the model name and the setting name in the first message of each chat (Gemini: the model; ChatGPT: the model and the highest setting by its name); they are written into model_settings.md.
3. The user sends each reply with a label (arm, model, run, batch). A reply the app cut off is continued with the one word "continue", and both parts are sent. Nothing else is said to the model.

## B. Filing (form only)
4. Each reply is saved byte for byte as recvNN (the counter is shared with the other tests), read-only, hashed and compared with every earlier file.
   A byte-identical re-send is kept once and not counted. Cell = arm E, model, run, batch. A second reply for a filled cell is a conflict and is held.
5. The batch comes from the item numbers (#01 to #20 is batch 1, #21 to #40 is batch 2), not from the label. A mismatch is noted.
6. Line endings are changed to \n before parsing (the saved file is not touched). Trailing blanks of a line are dropped.
   Nothing else is changed: no repair of spelling, spaces, quotes or symbols. A # inside the English text is ordinary text (arm E has no comment rule).
7. Held for review (status review), not counted until settled with the user:
   no item heading found; headings from both batches or outside #01 to #40; a fenced block before any heading; a block that holds several item headings;
   fewer than 20 items, or a reply that ends inside an open fence (it may be cut off: the user is asked whether it was, and to send the continuation if so;
   if the user says that is all there is, it counts as it stands, with the missing items as missing);
   a word that shows searching or running code in the text before the first heading or after the last item (searched, browsed, looked up, a web address, "I ran", code interpreter, sandbox);
   inside an item such words are the writer's English and are not looked at;
   a line that starts like an item number but holds more text (for example "#01 (first)": a heading must be alone on its line);
   a cell that is already filled.
   A held reply is settled with the user (tools/settle_e.py): it becomes data (it counts as it stands) or excluded, with the reason written in the log. Nothing is dropped silently.
   Only noted, still counted: a label mismatch; text before the first heading or after the last item (app status lines such as "Worked for 19s" included);
   items out of order; an item with two headings; an item with a fence (English is normally unfenced; a fence is accepted); an item with no message line (see rule 13).

## C. What counts as an item
8. An item starts at a heading: #NN alone on its line, outside any fence (a markdown heading mark, bold marks, the word Item before it or a colon after it are accepted).
   It runs to the next heading. A heading may also stand inside a fenced block: if the first non-blank line of a block is #NN and no other line of that block is an item heading,
   that line is read as the item's heading and removed from the block (noted "heading inside the block"). A block with two or more item headings inside it is held.
9. The item's text. If the heading is followed by one or more fenced blocks, the text is the block(s) in order (fence lines excluded, joined by one newline); text outside the blocks is not part of the item and is noted.
   Otherwise the text is the non-blank lines under the heading up to the next heading. In both cases a line that holds only a horizontal rule (three or more hyphens, asterisks or underscores) is not text.
   Blank lines and trailing blanks are dropped. Everything else stays as written: bullet and number marks, bold marks, "Message 1" labels, the writer's own wording.
10. A heading with no text and no block is a missing item. A text whose first non-blank line starts with NONE (any case) is a NONE item. Neither has a length.
11. A heading with several blocks: the blocks are joined in order by one newline (noted "split").
12. One number with two headings: the first counts, unless a word of correction (corrected, correction, revised, replaces, replacing, updated, fixed, amended, instead) stands in the text
    between the two headings; then the later one counts. A fenced block that was never closed (cut off) never counts while a closed block exists for the same number. Each case is listed.
13. Message lines (information only, never a hold and never a score): a non-blank line whose part before its first colon holds the word "to" between two short names (up to 40 characters each),
    after any leading bullet, number or bold marks. The count per item and the items with none are reported. The packet asked for one message per line starting with its sender and receivers.

## D. A cut-off reply
14. The parts of a cut-off reply are joined line by line in order; each part is filed as its own recvNN, and the continuation's row names the part it continues.
    I look at the junction and write down what it shows. If the junction cuts a line or a sentence in the middle, the item is held and settled with the user; nothing is repaired.

## E. Round trip (built from each writer's reply once both of its batches are filed)
15. A packet opens with the English reader text of reader_prompts.txt (the text after the line "ROUND TRIP, English reader ..." and its dashes, up to and including ITEMS) and lists 20 items.
    Each item is the writer's text of rule 9, in a fence, with its number, in the same seeded order as the SILEX packets of the same batch (same seed, same order). The two arms are shown to the reader in the same way.
    An item with no text (NONE, missing, empty) is shown as a block holding the single line NONE, so that the opening text ("20 short conversations") stays true; its facts score 0 unless the judge finds them in the reader's restatement.
16. The writer is not named and no model, run or arm appears in a packet. The reader model is the same as for the SILEX round trip (the user chooses it once, before the first reader chat, and it is recorded).
    No guide, no STEP 2. One fresh chat per writer: packet 1, then packet 2. The numbers of the four reader chats come from a seeded shuffle of the writers, separate from the SILEX round trip, and the key is kept from the judge.

## F. Length
17. Characters per item of the writer's English: the characters of the item's text of rule 9, lines joined by one newline, no final newline. Words per item (split on white space) are reported beside it.
    Compared with the same model's SILEX (arm P, characters per item as in rule 19 of P_handling_rules.md) and with the gold SILEX (order.csv, silex_chars), on the items where both exist. Descriptive only.
    Marks that the writer adds (bold, bullets, "Message 1" labels) count as written; that is a limit of the measure and is stated in the report.

## G. Changes
18. Nothing above may be changed after the first E reply is filed. A later addition is a dated note below this line.

### Note 1 (2026-11-14 08:46 IST). Written after the first E replies were filed (recv74 to recv79). It settles, with the user, a case that rule 7 held.
Case. The two ChatGPT replies (recv76, recv77) have each item on one line ("#01 A to B: ... B to A: ..."), so no line holds only #NN and rule 7 held both. The user sent the same text again (recv78 and recv79, byte-identical to the first, kept once and not counted) and said at 08:36 that the Copy button gives it too, with the app line "Worked for 8s" or "Worked for 10s". So it is the form of the reply as the app gives it, not a copying slip. I put the choice to the user after their 08:36 and 08:37 messages, and the user decided (08:42 IST, verbatim): "It's difficult to select only the texts. Yes keep in note."
19. A line that starts with #NN followed by a message line begins an item. A message line is as in rule 13: the rest of the line holds a colon, and before the first colon the word "to" stands between two short names. The item's text is the rest of that line and the lines below it, up to the next item line (a heading alone on its line, or another such line). Rules 9 and 10 apply to that text as before: nothing is repaired and the line breaks between the messages are not put back. A line like "#05 (fifth)", whose rest is not a message line, is still held by rule 7. The note applies to every reply of every model, and to recv76 and recv77, which are re-read under it (tools/reparse_e.py); the first parse of each stays on file as parsed_e/recvNN.before_note1.json. The form check lists such items under "NUMBER AND FIRST MESSAGE ON ONE LINE".
20. Limits, stated in the report. The message lines of rule 13 are counted per line, so an item written on one line counts 1 whatever it holds; that count is not comparable with the other items and is not used as a measure. The length of rule 17 is the text after the number (the number is not counted), as for the other items; the break between two messages is one character either way (a newline or a space). App status lines such as "Worked for 8s" stay in the saved file and are noted, not part of the reply.
21. Tools. parse_e_reply.py reads such lines as items and returns them in "inline_first"; intake_e.py lists them as a note; reparse_e.py is new; test_e_tools.py has the new checks (132 pass). The file hashes and the repo commit are in received_log_E.md (Handling decisions) and, at the next milestone, in the decisions table of the protocol document. Rule 18 holds: nothing above this note was changed.
