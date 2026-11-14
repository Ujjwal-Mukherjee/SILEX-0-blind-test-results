# Writing test (arm P): handling rules

Written on 2026-11-14 shortly before 03:03 IST (the file hash and the exact time of the hash are in received_log.md). No writing chat had been run when this was written, and no reply of arm P had been received or opened.
The rules are the same for every model and every run. No frozen file changes. The predictions are untouched.

**Principle.** A case these rules do not cover is held for review, settled with the user, added at the end of this file as a dated rule before any validity run,
and applied to every reply of that kind. Filing never runs the checker and never opens the key. The checker is run on the written items once, after the last P reply is filed.

## A. Running the chats
1. 12 chats: 4 models x 3 runs. Order: run 1 Claude, ChatGPT, Grok, Gemini; run 2 Gemini, Grok, ChatGPT, Claude; run 3 Grok, Gemini, Claude, ChatGPT.
   Each chat is a new temporary chat with memory, personalisation, custom instructions, web search, browsing and code tools off; never a chat of another test.
2. In a chat: the guide first (SILEX-0-GRAMMAR.md, sha256 fd8640fc..., given the same way to all four models; the user says attached or pasted), then STEP 2
   (right answer: 104 roots and section 7; if it is wrong, a new chat once with the guide given the other way, and the replies of the first chat are not used),
   then P_batch1 -> reply, then P_batch2 -> reply.
3. The user sends each reply with a label (arm, model, run, batch). A reply the app cut off is continued with the one word "continue", and both parts are sent.
   Nothing else is said to the model.

## B. Filing (form only)
4. Each reply is saved byte for byte as recvNN (the counter is shared with the other tests), read-only, hashed and compared with every earlier file.
   A byte-identical re-send is kept once and not counted. Cell = arm P, model, run, batch. A second reply for a filled cell is a conflict and is held.
5. The batch comes from the item numbers (#01 to #20 is batch 1, #21 to #40 is batch 2), not from the label. A mismatch is noted.
6. Line endings are changed to \n before parsing (the saved file is not touched). Trailing blanks of a line are dropped (the checker strips them anyway).
   Nothing else is changed: no repair of quotes, spaces or symbols.
7. Held for review (status review), not counted until settled with the user:
   no item heading found; headings from both batches or outside #01 to #40; a block before any heading; a block that holds several item headings;
   fewer than 20 items, or a reply that ends inside an open block (it may be cut off: the user is asked whether it was, and to send the continuation if so;
   if the user says that is all there is, it counts as it stands, with the missing items invalid);
   a word that shows searching or running code outside the blocks (searched, browsed, looked up, a web address, "I ran", code interpreter, sandbox);
   a line outside the blocks that starts like an item number but holds more text (for example "#01 (first)": a heading must be alone on its line);
   a cell that is already filled.
   A held reply is settled with the user (tools/settle_p.py): it becomes data (it counts as it stands) or excluded, with the reason written in the log. Nothing is dropped silently.
   Only noted, still counted: a label mismatch; text before the first heading or after the last item (app status lines such as "Worked for 19s" included);
   items out of order; an item with two headings; an item without a fence.

## C. What counts as an item
8. An item starts at a heading: #NN alone on its line, outside any block (a markdown heading mark, bold marks, the word Item before it or a colon after it are accepted).
   It runs to the next heading. A heading may also stand inside the block: if the first non-blank line of a block is #NN and no other line of that block is an item heading,
   that line is read as the item's heading and removed from the block; it is not counted as a comment (noted "heading inside the block"). A block with two or more item headings
   inside it is held.
9. The item's SILEX is its fenced block: from an opening line of three or more backticks (or tildes), any tag allowed, to the closing line that holds only backticks (or tildes).
   The fence lines are not part of the text. Text outside the blocks (intro, remarks, the reason line of a NONE item) is not SILEX: it is not checked,
   never shown to a reader, and noted.
10. A heading with no fenced block: the non-blank lines under it, up to the next heading, are the item's text and are checked as they stand (noted "no fence").
    A heading with no block and no text is a missing item.
11. A heading with several blocks: each block is checked on its own as a conversation (protocol: every block is its own conversation), and the item is valid only if every block is ok
    (noted "split"). Rule 17(b) reports the other reading.
12. One number with two headings: the first counts, unless a word of correction (corrected, correction, revised, replaces, replacing, updated, fixed, amended, instead) stands in the text
    between the two headings; then the later one counts. A block that was never closed (cut off) never counts while a closed block exists for the same number. Each case is listed.
13. A comment is what the checker reads as one: a # outside quotation marks that is not followed by "(", and everything after it on that line. Comments are removed from the block text
    before the check, and each one is recorded. Blank lines are ignored.

## D. A cut-off reply
14. A part that ends inside an open block is incomplete. The next part (sent after "continue") is joined to it when its first non-blank line is neither a heading nor an opening fence line
    (the block goes on). Otherwise the earlier block stays as it stands and the later part is read as a new text, and rule 12 decides between two blocks of one number.
    Both parts are filed as their own recvNN; the continuation's row names the part it continues. The parser does the joining; I look only at the junction.

## E. Validity (the primary score of the written items)
15. Each item gets one decision. An item is **valid** only if all of these hold: it is present; its block is not NONE; its block has no comment; the checker says ok to every message
    (zero problems; a failing line that its own sender takes back with the retraction root still counts as a verdict, although the checker does not count it);
    and, if the item has several blocks, every block is ok. NONE, a missing item, an empty block, a comment or any verdict makes the item invalid, as the protocol says.
    English outside a gloss is the checker's verdict E-ENGLISH. If the checker itself fails to run on an item (a crash, or more than 30 seconds), the item is invalid and listed with the error.
16. How: per item, in its own process, python3 silex_check.py GUIDE --messages FILE, on the comment-free text (the messages of a block are separated by a line of three hyphens).
    The full output is stored. Before the run, the guide (fd8640fc...) and the checker (485065d4...) are checked against their hashes.
17. Also reported, never instead of the primary: (a) "checker-ok": the same decision without the comment rule; (b) "joined": for a split item, its blocks joined in order into one conversation;
    (c) the verdicts counted by code (E-SYN, E-LEX, ...). Notes the checker prints (for example "serial 2 is the sender's message number 1") are stored; they are not verdicts.
18. The validity run happens once, after the last P reply is filed, over every cell of status data (held cells only after they are settled).
    The program is tested beforehand on made-up replies, the pilot reply and the gold items only.

## F. Length
19. Characters per item of the writer's SILEX: the characters of the comment-free text, fences excluded, lines joined by one newline, blank lines removed, trailing blanks removed, no final newline.
    This is the gold measure (order.csv, silex_chars). A NONE or missing item has no length. Descriptive only.

## G. Round trip (built after the last P reply; one reader packet per writer and batch, from each writer's run 1)
20. A packet opens with the text of reader_prompts.txt (SILEX reader) and lists 20 items. Each item is the writer's comment-free block text exactly as written, in a fence, with its number,
    shuffled in order with a fixed seed. Invalid items go in as they are, with their verdicts. An item with no SILEX text (NONE, missing, empty) is shown as a block holding the single line NONE,
    so that the frozen opening text ("20 short conversations") stays true; its facts score 0 unless the judge finds them in the reader's restatement.
21. The writer is not named and no model, run or arm appears in a packet. The reader model is the same for every writer (the user chooses it before the first reader chat and it is recorded).
    One fresh chat per writer: guide first, STEP 2, then the two packets.

## H. Changes
22. Nothing above may be changed after the first validity run. A later addition is a dated note below this line.

### Addition 1 (2026-11-14 05:05 IST). Written before any high-setting reply was received. Decided after the first validity run was seen.
23. Reason. In every chat of the study so far ChatGPT ran in auto mode (the user had no thinking setting for it). Claude ran with "Extra" and Grok with "heavy" (both in every chat), and Gemini ran on named models that differed between chats (reading: 4 Argon; writing run 1: 3.1 Pro, run 2: 4 Argon, run 3: 3.5 Flash-lite). On 2026-11-14 at 05:02 the user said that ChatGPT's thinking can now be set. The details are in model_settings.md.
24. What is added. The writing test is run again for ChatGPT: 3 new chats at the highest thinking setting the app offers (the user names the model and the setting in the first message), each with the same steps and the same packets (guide attached, STEP 2, P_batch1, P_batch2), called "ChatGPT high run 1, 2 and 3". They are filed under model chatgpt with run numbers 4, 5 and 6 (high run k = run 3 + k). The six earlier ChatGPT cells (runs 1 to 3, auto) stay in the data; nothing is replaced, dropped or re-scored. Both sets are reported in full whatever the results are.
25. Main set. For comparisons between models in the writing test and for the round trip, ChatGPT's main set is the high-setting set (runs 4 to 6), because it is the one that matches the settings of the other models; the auto set is shown beside it. The round trip uses ChatGPT's high run 1 (run 4). This is fixed before any high-setting reply exists.
26. Validity of the new cells: one more validity run, python3 check_p.py with --only the six cells P-chatgpt-4-b1 to P-chatgpt-6-b2 and --out validity_P_high, after the last of them is filed. Same measure (rules 15 to 17), same hash checks. The outputs of the first run (validity_P) are not touched.
27. From now on ChatGPT is run at the highest thinking setting in every new test (English arms, round-trip readers, Test F). Its reading chats already run (R runs 1 to 3, N run 1) stay in auto mode and are reported as such; its R against N contrast is within auto mode.
28. The decision to repeat the ChatGPT writing test was made after the auto-set results were seen (64 of 120 items valid); the report says so.
29. Gemini's writing runs are not repeated unless the user asks; they are reported per run with the model of each run, and pooled as pre-registered. Any later addition gets its own dated note before its data arrives.
