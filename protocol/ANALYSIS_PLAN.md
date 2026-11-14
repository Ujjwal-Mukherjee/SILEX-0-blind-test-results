# Analysis plan (written before any judging; no reply has been scored)

Written on 2026-11-14 at about 05:55 IST (the exact time of the hash is in received_log.md). Nothing has been judged or scored when this is written: no judge sheet exists, no explanation has been compared with a fact.
It fixes how the numbers of the protocol (section "Predictions and analysis") are computed, so that the code (tools/aggregate.py, tested by tools/test_aggregate.py on made-up data) and the report follow it and nothing is chosen after the results are seen.
The predictions are the ones of the protocol and are not changed. Where this plan says "descriptive", no test is run and no claim beyond the numbers is made.

## 1. Units and scores
1. A fact is scored 1 or 0 by the judge (frozen prompts judge_recovery.txt and judge_roundtrip.txt). The kit has 146 facts: 127 C facts and 19 S facts (facts.csv). A run of arm R or N covers both batches (all 146 facts).
   A run with a batch missing, a sheet not fully judged or an item excluded is left out of every mean and listed. Facts keep the tier of their item (1 to 5; eight items per tier).
2. Share = facts credited / facts judged, shown in points (0 to 100) with one decimal. "C", "S" and "all" mean the C facts, the S facts and all facts. False statements = the sum of the judge's false counts over a run's 40 items divided by 2 (per 20 items).
3. Model level, reading: the mean of the model's R runs (three) with the lowest and the highest run; N has one run per model. ChatGPT's reading chats (R runs 1 to 3, N run 1) all ran in auto mode and Gemini's all on 4 Argon (model_settings.md), so the contrast R minus N is within one setting for every model.
4. Item scoring: a judge reply is checked for form only. An item scored twice keeps the first scoring (a differing second one is listed in the report); a malformed item is asked again with the same prompt. Nothing is re-scored after the first look at the results.

## 2. The predictions
5. Prediction 1 (R minus N). For each model: gap = (mean of its R runs, C facts) minus (its N run, C facts). Holds if the gap is 20.0 points or more, compared exactly as fractions: with 127 C facts, 3 R runs and 1 N run a gap is a multiple of 1/381, so 76/381 = 19.95 points fails and 77/381 = 20.21 points holds.
   Beside it: the gap with the lowest and with the highest R run; the mean of the per-item gaps (the "gap per item" of the protocol) with its own interval; the interval of the pooled gap from 10,000 bootstrap resamples of the 40 items (an item brings all its C facts):
   numpy default_rng([20261114, k]) with k = 0 for resamples over all items or over a subset of items and k = the tier number for resamples within one tier; percentile 2.5 and 97.5 (numpy percentile, linear interpolation). "Robust" = the lower bound is also 20 or more. Both the point verdict and "robust" are reported.
6. Prediction 2 (tier 1 above tier 5). For each model, with the guide: the R-mean share of all facts in tier 1 and in tier 5. Holds if tier 1 is strictly higher than tier 5, compared exactly as integer counts; a tie, including 100 and 100, counts as not higher and is shown as a tie.
   Interval of the difference: independent bootstrap resamples of the items within tier 1 and within tier 5 (eight items each). Descriptive beside the point rule.
7. Prediction 3 (writing). For each model: valid items / written items over the runs of its main set (valid = the primary decision of rule 15 of P_handling_rules.md). Holds if the share is 50 percent or more (60 of 120 holds, 59 of 120 does not).
   Main set: Claude, Grok and Gemini: runs 1 to 3 (Gemini pooled over its three models, as pre-registered, and shown run by run). ChatGPT: the high-setting set, runs 4 to 6 (run 4 is Astra 6 at "medium", the highest on the user's subscription; runs 5 and 6 as the user states them), by rule 25 of Addition 1.
   ChatGPT's auto set (runs 1 to 3) is reported in the same table with its own verdict. If the high set does not exist yet, the auto set is shown as the provisional main set. Interval: bootstrap of the 40 items, all runs of a set resampled together.
   Also shown: the valid share by run (lowest and highest), the checker-ok and joined shares, the share by tier, the verdict codes and reasons of the invalid items, and the items invalid in 4 or more of the 12 runs of the main sets.
8. Prediction 4 has no prediction; length and the round-trip comparison with English are reported as found.
9. Every prediction is reported in one table, with the result whichever way it goes (the protocol: a result that goes against a prediction goes in the same table as the rest).

## 3. Length (descriptive only)
10. Characters per item of the writer's SILEX (rule 19 of P_handling_rules.md), the gold SILEX (order.csv silex_chars) and the writer's English (rule 17 of E_handling_rules.md; words beside it). Per set: the median over the items that have text, the median gold length on the same items, and the median of the item-wise ratio writer / gold.
    SILEX against English: for each writer, the median over the items that have text in both of (the SILEX characters of the round-trip source run) divided by (the English characters of the writer's run 1 of arm E). NONE and missing items have no length.

## 4. Round trip
11. Per writer and arm (RTP = SILEX, RTE = English): the C facts credited by the judge from the reader's restatement over the writer's 40 items (127 C facts). NONE items count as they are. SILEX minus English per writer with a paired bootstrap interval (the same resampled items in both arms, 10,000 resamples, percentiles 2.5 and 97.5);
    by tier (no interval); false statements per 20 items. The mean over the writers, with and without the reader's own family.
12. Sensitivity checks, shown beside the main figure and never instead of it: (a) the items that were checker-valid in the writer's SILEX round-trip source run; (b) the items whose English has message lines only (rule 13 of E_handling_rules.md: the items that the E key lists as having other lines are dropped);
    (c) the writer from the reader's own model family is marked in every table and the means are also shown without it. In (a) and (b) both arms use the same kept items and the bootstrap draws inside the kept items.
13. The round-trip source runs are fixed: Claude run 1, ChatGPT run 4 (high run 1), Grok run 1, Gemini run 1 (3.1 Pro). The reader model is the one the user chose (RT_handling_rules.md rule 1), the same in all eight chats; one reader makes the comparison between writers fair but not the comparison with other readers.

## 5. Judging reliability
14. First judge: decided with the user before any judge sheet is built (RT_handling_rules.md rule 10); the report names who judged.
15. Audit by the user: 30 judged facts drawn at random with a seed written in the log before the draw, from all judged facts of the reading and round-trip arms. The user sees only the fact and the explanation and scores it 1 or 0. Disagreement = the share of the 30 where the user's score differs from the judge's.
16. Second judge: a different model re-judges a random 20 percent of the explanations (items of reader replies; the sample is drawn with a seed written in the log before the draw) with the same frozen prompts, shuffled and blind. Disagreement = the share of the facts of those explanations where the two scores differ.
17. If either disagreement is above 10 percent, the second model re-judges everything and both sets of results are reported side by side (the tables of the first judge stay the primary ones, as pre-registered).

## 6. How the tables are made and reported
18. tools/aggregate.py makes every table from the checked judge files (JSON), the sheet maps, the round-trip keys, the validity files (validity_P*/items.csv) and the parsed English replies. It scores nothing. It opens the private maps and keys, so it runs only after the last judge reply is checked, and it stops while any judged sheet is incomplete
    (--partial exists for a look that is not a result and marks the report). Its report names the hash of the tool and of this plan.
19. Each table shows n (runs, items, facts) beside the percentages. Model names appear only after all scores are entered. Cross-model comparisons are descriptive: the thinking mode and the model tier were not controlled by the protocol (model_settings.md), so a difference between two models is not a statement about the models alone; contrasts within one model are fair.
20. Items dropped by the errata rule are listed (errata.txt). The limits of the protocol (one author, forty items in one fixed order, form not truth) stay with every table.

## 7. Changes
21. Nothing above may be changed after the first judge sheet is given to a judge. A later addition is a dated note below this line.
