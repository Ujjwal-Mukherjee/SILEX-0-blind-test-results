# Judging procedure (written before any judge sheet exists; no reply has been scored)

Written on 2026-11-14 at about 06:21 IST (the exact time of the hash is in received_log.md). No judge sheet has been built, no explanation has been compared with a fact, no score has been seen.
It settles how the judge agents are run and how the reliability checks of ANALYSIS_PLAN.md (rules 14 to 17) are done, on the user's choice of a separate agent as judge (RT_handling_rules.md, Note 1, rule 13; the user's words: "An agent").
The frozen judge prompts (judge_recovery.txt for the reading arms R and N, judge_roundtrip.txt for the round trips RTP and RTE) are used verbatim. Nothing in the kit, the predictions or ANALYSIS_PLAN.md changes.

## 1. Who judges
1. First judge: separate agents (the Agent tool; each agent starts cold, with no access to this conversation, the work, the keys or the maps), run on the model setting "fable" of the Agent tool (the session lists Claude Fable 5.2 as the current model of that tier). It is not the assistant that built the tools and the packets.
2. Second judge (the reliability sample, rule 16 of the plan): the same kind of agents on the model setting "opus" of the Agent tool (the session lists Claude Opus 5.5), a different model from the first judge. If a model is not available when it is needed, the procedure stops and the user is told; nothing is substituted silently.
   Optional, only if the user wants it: the same sample sheets pasted by the user into a chat of a model from another family; such a run is reported beside the Opus one and replaces nothing.
3. Limit reported with every table: all agent judges are Claude models, and Claude Sonnet 5.5 is the reader of every round-trip chat and one of the four readers in the reading arms. The sheets carry no identity (the sheet builders warn when an explanation names a model), but a preference of a Claude judge for Claude wording cannot be excluded; the user's audit and the second judge are the checks.

## 2. What the agents are given, and how I stay blind
4. Only sheet files (the frozen prompt verbatim, then the sheet) and a fixed wrapper text (the template of tools/stage_judging.py, sha256 41f351920043d0c1abe72c3089889ddab8c2bccd712c5f9a647fded89719c255). tools/stage_judging.py copies the sheets into WORK/inbox (read-only copies) and makes an empty WORK/outbox; WORK holds no map, key, log, arm, model, run or writer. A sheet code is 4 random characters.
5. One pass = one staging. Reading and round-trip sheets are mixed in one pool, put in a random order (fixed seed below) and split into groups of at most 6 sheets, as equal as possible; one agent judges one group, each sheet on its own, and writes one reply file per sheet.
6. After each agent finishes, tools/audit_agent_transcript.py reads its transcript and lists every tool call (names and paths only). The allowed calls are: Read of its own sheets, Read of its own reply files, Write or Edit of its own reply files. Anything else (another file or folder, Bash, Glob, Grep, a web tool) is flagged. The tool also reads the model named in the transcript and flags any model other than the one of the pass (claude-fable-5-2 for the first judge, claude-opus-5-5 for the second); the replies of a flagged group are not used, the group is judged again by a new agent, and the report lists the case.
7. I do not open or print a reply. tools/collect_judge_replies.py copies each reply byte for byte (read-only), writes its sha256 to a log and checks the form with the rules of check_judge_reply.py or check_judge_reply_rt.py (one line per item, exactly the sheet's facts, 0 or 1, a false count); it prints only the form result. A reply item with a form problem is asked again from a new agent with a redo sheet that holds only those items (tools/make_redo_sheet.py cuts it from the original sheet: same prompt, same code, same facts, same explanation text; its reply is collected with collect_judge_replies.py --suffix _redo1); the first usable scoring of an item is kept (plan, rule 4). Nothing is filled in by hand and nothing is re-scored after a first look at results.
8. No score is looked at before tools/aggregate.py is run on the complete set (plan, rule 18).
9. Judging starts only after the last reader reply of both round trips is filed and the user has said that no more chats are coming (RT rules, rule 7). Before the first sheet is given: the hashes of the plan, this procedure and every tool are checked and logged, the tool test suites are run, and the sheet builders' identity warnings are shown to the user.

## 3. Seeds (fixed now, so that no draw can be chosen after seeing anything)
10. Sheet builders: build_judge_sheets.py --seed 20261114301 (arms R and N); build_judge_sheets_rt.py --seed 20261114302 (arms RTP and RTE).
    First-judge staging: stage_judging.py --seed 20261114303 --per-agent 6.
    Second-judge draw: reliability.py second-draw --seed 20261114304 --fraction 0.2 (a random 20 percent of all judged explanations, each item of each reader reply being one explanation; no scenario item twice on a sheet; at most 20 items per sheet).
    Second-judge staging: stage_judging.py --seed 20261114305 --per-agent 6.
    Audit by the user: reliability.py audit-draw --seed 20261114306 --n 30 (30 judged facts drawn at random from all judged facts of the reading and round-trip arms; the user sees only the fact and the explanation, with the scoring rule of the judge prompt, and answers 1 or 0 for each).

## 4. Reliability results
11. Second judge against first judge: the share of facts, over the drawn explanations, where the two scores differ (reliability.py second-compare); above 10 percent when 10 x differing > compared (exactly 10 percent is not above). Also shown: by kind and by arm, the direction of the differences, the false counts, Cohen's kappa (extra).
12. Audit: the share of the 30 entries where the user's score differs from the judge's (reliability.py audit-compare); above 10 percent when 4 or more of the 30 differ (3 of 30 is exactly 10 percent, not above).
13. If either share is above 10 percent, the second model re-judges everything (plan, rule 17): all sheets again by agents on "opus", and both sets of tables are reported side by side; the tables of the first judge stay the primary ones, as pre-registered.

## 5. What the report states about the judging
14. The judge models; the number of agents, groups and sheets per agent; every redo and every flagged agent; the audit and second-judge shares; the rehearsal below; the limit of rule 3.

## 6. Rehearsal (an instrument check, not data)
15. On 2026-11-14 at about 06:12 IST one agent on "fable" judged a made-up sheet (sha256 first 16: af3580bf9a4afa98) built from the pilot reply R-claude-pilot-b1 (not part of the data) with 10 of its 20 explanations left as they were and 10 replaced by the explanations of other items (a cyclic shift among those 10), so that the right answer is known: 0 on every fact of the replaced ones.
    Result, checked with the same form checker and against the known answer: the reply (sha256 first 16: d97d4842af7c4cff) was clean in form; all 10 untouched explanations were credited on all 37 facts (false 0); all 10 replaced ones scored 0 on all 43 facts (false counts 2 to 4). The agent made 2 tool calls (one Read of the sheet, one Write of the reply; checked from its transcript), the transcript names the model claude-fable-5-2, and the run took 33 seconds and about 63 thousand tokens.

## 7. Changes
16. Nothing above may be changed after the first judge sheet is given to an agent. A later addition is a dated note below this line.
