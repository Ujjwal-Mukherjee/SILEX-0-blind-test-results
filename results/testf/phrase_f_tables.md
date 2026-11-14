# Test F, secondary result: the phrase (README_F.txt)

A blind judge scored 1 or 0 whether the reader's phrase names the key's fault (judge_fault.txt). Only answers that name a fault on a faulty item have a phrase to judge; an item answered "none" or not answered counts 0 in the 'all faulty items' column. The place is scored by the program (score_f.py), not by the judge.

## Per run

| arm | model | run | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |
|---|---|---|---|---|---|---|---|---|---|
| FN | chatgpt | 1 | 30 | 24 | 20/24 (83%) | 20/30 (67%) | 22 | 20/22 (91%) | 0/2 (0%) |
| FN | claude | 1 | 30 | 22 | 21/22 (95%) | 21/30 (70%) | 22 | 21/22 (95%) | 0/0 (-) |
| FN | gemini | 1 | 30 | 24 | 20/24 (83%) | 20/30 (67%) | 23 | 20/23 (87%) | 0/1 (0%) |
| FN | grok | 1 | 30 | 7 | 7/7 (100%) | 7/30 (23%) | 7 | 7/7 (100%) | 0/0 (-) |
| FR | chatgpt | 1 | 30 | 28 | 26/28 (93%) | 26/30 (87%) | 28 | 26/28 (93%) | 0/0 (-) |
| FR | chatgpt | 2 | 30 | 26 | 25/26 (96%) | 25/30 (83%) | 26 | 25/26 (96%) | 0/0 (-) |
| FR | claude | 1 | 30 | 30 | 30/30 (100%) | 30/30 (100%) | 30 | 30/30 (100%) | 0/0 (-) |
| FR | claude | 2 | 30 | 30 | 30/30 (100%) | 30/30 (100%) | 30 | 30/30 (100%) | 0/0 (-) |
| FR | gemini | 1 | 30 | 30 | 30/30 (100%) | 30/30 (100%) | 30 | 30/30 (100%) | 0/0 (-) |
| FR | gemini | 2 | 30 | 30 | 30/30 (100%) | 30/30 (100%) | 30 | 30/30 (100%) | 0/0 (-) |
| FR | grok | 1 | 30 | 29 | 29/29 (100%) | 29/30 (97%) | 29 | 29/29 (100%) | 0/0 (-) |
| FR | grok | 2 | 30 | 30 | 28/30 (93%) | 28/30 (93%) | 29 | 28/29 (97%) | 0/1 (0%) |

## By arm and model (runs added up)

| arm | model | runs | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |
|---|---|---|---|---|---|---|---|---|---|
| FN | chatgpt | 1 | 30 | 24 | 20/24 (83%) | 20/30 (67%) | 22 | 20/22 (91%) | 0/2 (0%) |
| FN | claude | 1 | 30 | 22 | 21/22 (95%) | 21/30 (70%) | 22 | 21/22 (95%) | 0/0 (-) |
| FN | gemini | 1 | 30 | 24 | 20/24 (83%) | 20/30 (67%) | 23 | 20/23 (87%) | 0/1 (0%) |
| FN | grok | 1 | 30 | 7 | 7/7 (100%) | 7/30 (23%) | 7 | 7/7 (100%) | 0/0 (-) |
| FR | chatgpt | 2 | 60 | 54 | 51/54 (94%) | 51/60 (85%) | 54 | 51/54 (94%) | 0/0 (-) |
| FR | claude | 2 | 60 | 60 | 60/60 (100%) | 60/60 (100%) | 60 | 60/60 (100%) | 0/0 (-) |
| FR | gemini | 2 | 60 | 60 | 60/60 (100%) | 60/60 (100%) | 60 | 60/60 (100%) | 0/0 (-) |
| FR | grok | 2 | 60 | 59 | 57/59 (97%) | 57/60 (95%) | 58 | 57/58 (98%) | 0/1 (0%) |

## By arm (all models)

| arm | runs | faulty items | named a fault | phrase credited, of named | phrase credited, of all faulty | place right | phrase credited, place right | phrase credited, place wrong |
|---|---|---|---|---|---|---|---|---|
| FN | 4 | 120 | 77 | 68/77 (88%) | 68/120 (57%) | 74 | 68/74 (92%) | 0/3 (0%) |
| FR | 8 | 240 | 233 | 228/233 (98%) | 228/240 (95%) | 232 | 228/232 (98%) | 0/1 (0%) |

## By verdict (phrase credited / phrase judged; two items per verdict per run, so for description only)

| verdict | FN | FR |
|---|---|---|
| E-ARITY | 6/6 | 16/16 |
| E-BUDGET | 0/2 | 16/16 |
| E-CODE | 3/4 | 12/13 |
| E-COUNT | 4/5 | 16/16 |
| E-ENGLISH | 0/3 | 12/15 |
| E-HEAD | 8/8 | 16/16 |
| E-KIND | 6/6 | 15/15 |
| E-LEX | 6/6 | 16/16 |
| E-MATH | 3/4 | 14/15 |
| E-NAME | 6/6 | 16/16 |
| E-QUOTE | 0/0 | 16/16 |
| E-REDEF | 5/5 | 15/15 |
| E-REF | 5/6 | 16/16 |
| E-SYN | 8/8 | 16/16 |
| E-TIME | 8/8 | 16/16 |
