# Test F (find the fault): handling rules added after the freeze

Test F's own rules are in README_F.txt (frozen 2026-11-13 23:22 IST, before any F chat). The notes below are decisions the user made after the freeze.
Each note is dated, was made before any F reply was scored or compared with the key, never changes the items or the key, and says which tool change it needed.

## Note 1: run-on lines (decided by the user, 2026-11-14 18:26 IST)

What happened. ChatGPT (Astra 6, medium, as stated 18:21) wrote the 20 answers of FR run 1 batch 1 (recv98, message of 18:18 IST) and of batch 2 (recv99, 18:21 IST)
on ONE line each, after the app line "Worked for N s", instead of one answer per line as the packet asks. The user confirmed at 18:23 that this is ChatGPT's own output and not a fault of the copy:
"ChatGPT replied in that form, one under another, no separate lines. It's not a copy paste fault."

The choice put to the user at 18:24, for every model alike and before anything was scored: (1) read by item code, or (2) strict, that is the rule of README_F.txt
"an item with no answer line counts as no answer" applied literally. The user answered "1." at 18:26.

The rule. A line that holds more than one item code followed by a bar ("F21 | ... F22 | ...") is read as several answers: it is cut before the second and later codes.
No word of the reply is changed or removed; only where the line breaks fall. The reply file itself is never changed (it is saved byte for byte).
The use is a form note in the parse and in the log ("RUN-ON LINE(S)"). A reply with one answer per line is read exactly as before.
The rule applies to every model and both arms, and to later replies as they arrive.
It repairs nothing else: a reply that is missing an answer, answers an item twice, holds a correction note, has search or code-run words, or names a place that cannot be read is held as before.

Not covered (held as before and settled with the user if it happens): a run-on line that starts with a preamble sentence before its first item code;
item codes written with a colon or a dash instead of a bar on a run-on line.

Strict side note. The primary result reads run-on lines by item code. For the report the strict reading (README_F.txt applied literally: of a run-on line only its first answer counts,
the others count as no answer) is computed beside it for the replies concerned: a copy of parsed_f in which, for every line number that holds several answers, only the first answer is kept,
and score_f.py is run on that copy. Both numbers are reported; the primary one is the one by item code.

Limit for the report. A model that writes its answers on one line has not followed the packet's format instruction (one line per item). The result by item code measures
finding faults, not format; the format failure is stated next to it.

Tool changes (working copies in silex_results/tools; the frozen copies in the kit are unchanged and still verify with MANIFEST.sha256, 22 of 22 OK):
- parse_f_reply.py: new functions split_run_on and expand_run_on and the form note. sha256, first 16: 3578b9fb5d355b6b (frozen) -> 73c493211c8114d4.
- reparse_f.py: new. Re-reads a held reply with the current parser (same checks as intake_f.py, tested to agree), keeps the first parse as parsed_f/recvNN.before_note1.json. 0f0784e3ac50383d.
- test_f_tools.py: 15 new tests, 65 in all, all pass. 5e5c49688386fcc2 (frozen) -> 0e447c9da1447ca8.
- intake_f.py, score_f.py, intake.py, parse_reply.py: unchanged (1a735a2fc818c56c, fe01189f2c43d6d4, 34a09a99561957f5, c1b64f2a58895391).

Effect so far: recv98 and recv99 (ChatGPT, FR run 1) were re-read at 2026-11-14 18:31 IST: held (status review) -> data, 20 of 20 answers each.
