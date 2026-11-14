# Round trip (arms RTP and RTE): handling rules for the reader chats, their replies and their judging

Written on 2026-11-14 at about 05:29 IST (the file hash and the exact time of the hash are in received_log.md). No reader chat had been run when this was written, and no reader reply had been received or opened.
RTP = the SILEX round trip (packets RT-P_chatN_packetB.txt, built by build_roundtrip_p.py under rules 20 and 21 of P_handling_rules.md and rule 25 of its Addition 1).
RTE = the English round trip (packets RT-E_chatN_packetB.txt, built by build_roundtrip_e.py under rules 15 and 16 of E_handling_rules.md).
The rules are the same for every chat of both round trips. No frozen file changes. The predictions are untouched (prediction 4: no prediction for the round-trip comparison with English; both are reported as found).

**Principle.** A case these rules do not cover is held for review, settled with the user, added at the end of this file as a dated rule before judging starts, and applied to every reply of that kind.
Filing never opens a key and never scores. Judging starts only after the last reader reply of both round trips is filed.

## A. Running the reader chats
1. 8 reader chats: RTP chats 1 to 4 and RTE chats 1 to 4 (the number is the packet file's chat number; one chat per writer). One reader model for all 8, chosen by the user before the first reader chat and written into model_settings.md in the user's words,
   with the same thinking setting in all 8 (if ChatGPT is the reader: its highest setting). Each chat is a new temporary chat with memory, personalisation, custom instructions, web search, browsing and code tools off; never a chat of another test.
2. RTP chat: the guide first (SILEX-0-GRAMMAR.md, sha256 fd8640fc..., given the same way as in the other chats; the user says attached or pasted), then STEP 2 (right answer: 104 roots and section 7; if it is wrong, a new chat once with the guide
   given the other way, and the replies of the first chat are not used), then packet 1 -> reply, then packet 2 -> reply. RTE chat: no guide and no STEP 2; packet 1 -> reply, packet 2 -> reply.
3. The user sends each reply with a label (arm, chat number, packet): "RT P chat 2 packet 1". A reply the app cut off is continued with the one word "continue"; both parts are sent. Nothing else is said to the reader.
   The chats may be run in any order; each reader chat starts fresh, so no chat sees another.

## B. Filing (form only; the rules of the reading replies, with the changes below)
4. Each reply is saved byte for byte as recvNN (the counter is shared with the other tests), read-only, hashed and compared with every earlier file. A byte-identical re-send is kept once and not counted.
   Cell = arm (RTP or RTE), reader model, chat number, batch; the chat number is stored in the run column of cells.csv. A second reply for a filled cell is a conflict and is held. The batch comes from the item numbers, not from the label.
5. A reply is parsed as the reading replies are (parse_reply.py): "#NN" alone on a line, then the explanation. Held for review, not counted until settled with the user:
   not exactly 20 items of one batch (missing, repeated or unknown numbers); an explanation of more than 120 words (the packet's limit; counted as it stands if the user says so after being asked);
   search-like words; a cell that is already filled; three or more items with the same text as an earlier reply of the same batch (possible re-send or mix-up);
   in an RTE reply: guide words (guide, section N, pinned, rule N), because the English reader has no guide.
   Only noted, still counted: the items are not in the order of the packet (the packets are shuffled with the seed of the build; the order does not matter to the judge); text before item 1; a trailer after the last item; a label mismatch;
   possible dropped text. A correction that names an item replaces the earlier wording for that item (corrections.json, as for the reading replies).
6. The packet order that the filing tool compares with is computed from the seed of the build (build_roundtrip_p.item_order), never from a key file. The tool does not open a key.

## C. Judging
7. The judge sheet is built from the reader's replies with build_judge_sheets_rt.py: the frozen judge_roundtrip.txt verbatim, a random sheet code, and per item the scenario's C facts (never S facts) and the reader's explanation.
   The facts keep their numbers from facts.csv (a skipped S fact leaves a gap in the numbering). Items are shuffled inside a sheet and the sheets are shuffled; no writer, chat, arm, reader model or run is on a sheet.
   The map from sheet code to arm, chat and batch is written to a separate private file.
8. A writer's NONE item (shown to the reader as a block holding the single line NONE) is judged like any other: its facts score 0 unless the judge finds them in the reader's restatement.
9. Judge replies are checked for form only (check_judge_reply_rt.py): one line per item, the sheet's facts, 0 or 1, a false count. A malformed item is asked again with the same prompt; nothing is filled in by me.
10. Figures reported. Per writer: C facts credited / C facts over its 40 items, in its RTP chat (SILEX) and in its RTE chat (English), side by side, with the same scenarios and facts on both sides; by tier; false statements per 20 items.
    Sensitivity checks, reported beside the main figure: (a) RTP restricted to the items that were valid under the checker (arm P, rule 15); (b) RTE restricted to the items with message lines only (rule 13 of E_handling_rules.md);
    (c) the writer from the reader's own model family shown separately, because a reader may read its own family's wording more easily.
    The 30-fact audit by the user and the second-judge pass on 20% of the explanations are as in the protocol. Who judges (me, or a fresh agent that has not seen this work) is decided with the user before judging starts.

## D. Changes
11. Nothing above may be changed after the first reader reply is filed. A later addition is a dated note below this line.

### Note 1 (2026-11-14 06:08 IST). Written before any reader reply was received (the user had sent none when this was written). It records the two choices that rules 1 and 10 leave to the user.
12. Reader model (rule 1). The user chose it on 2026-11-14 at 06:06 IST, verbatim: "1. Claude sonnet Extra". All 8 reader chats (RTP chats 1 to 4 and RTE chats 1 to 4) are run in Claude Sonnet 5.5 at the thinking setting Extra, the model and setting of the user's Claude chats in every earlier test (model_settings.md). The reader is then of the same family as the Claude writer, which is why sensitivity check (c) of rule 10 stays: that writer is shown separately and the means are also shown without it.
13. Who judges (rule 10). The user chose on 2026-11-14 at 06:06 IST, verbatim: "3. An agent". The first judge is therefore a separate agent that has not seen this work, the keys or the maps, and not the assistant that built the tools and the packets (which knows which writer each chat reads). How the agent is run (its model, exactly what it is given, how its replies are taken and checked) is fixed in a further dated note before the first judge sheet is given to any judge, and it applies to the reading arms and to both round trips alike.

### Note 2 (2026-11-14 06:31 IST). Written before any reader reply was received (the user had sent none when this was written). It corrects one sentence of Note 1.
14. and 15. [Not reproduced in this public copy. They withdrew a parenthesis of rule 12 that gave chat numbers for one writer, and they say that no file of the repository names the writer of a reader chat. The parenthesis is also left out of rule 12 here. The original file has sha256 6ad5bbc9728286952552d6c39101be1b2c23d22c67a71fdd78e259458a4abdef.]
