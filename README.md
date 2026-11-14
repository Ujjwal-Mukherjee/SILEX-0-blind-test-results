# SILEX-0 blind test: results package

Run by Moonbeam · results of 14 November 2026

This package holds the report and the supporting files of a blind test of SILEX-0, a constructed language for messages between AI agents, whose predictions were written down before the first main run (what can and cannot be checked about that is below). Four AI models that had never seen SILEX-0 (Claude, ChatGPT, Grok and Gemini) were asked to read it, to write it, and to find a planted fault in it, with and without the language guide. The tests used 40 fixed items and 146 key facts. The rules, plans and scoring tools were hashed before the steps that used them (the report's Reproducibility section gives the times); the decisions made after the freeze are listed in its appendix.

**Read first:** [`report/SILEX-0_blind_test_results_report.pdf`](report/SILEX-0_blind_test_results_report.pdf) (14 pages). The same text is in [`report/SILEX-0_blind_test_results_report.md`](report/SILEX-0_blind_test_results_report.md).

## Headline results

From the report's Summary, unchanged:

With the guide, all four models recovered 90 to 99% of the content facts in 40 SILEX-0 items; without it they recovered 29 to 85%. On the 19 status facts that only the guide's rules give, the gap is larger: 81 to 96% with the guide, 0 to 21% without. The predictions fixed before any chat held as follows: predictions 2 and 3 for every model, prediction 1 (a gain of at least 20 points from the guide) for ChatGPT and Grok only.

| Model | Prediction 1: gain from the guide on content facts (needs 20 points or more) | Prediction 2: tier 1 minus tier 5, with the guide (needs above 0) | Prediction 3: written items that pass the checker (needs 50% or more) |
| --- | --- | --- | --- |
| Claude | +18.6 points: no | +3.3 points: yes | 99.2%: yes |
| ChatGPT | +61.2 points: yes | +5.9 points: yes | 100.0% at its high setting, 53.3% in auto mode: yes |
| Grok | +40.7 points: yes | +6.7 points: yes | 86.7%: yes |
| Gemini | +12.9 points: no | +6.6 points: yes | 94.2%: yes |

No prediction was made for the rest, which is reported as found:

- Round trip: a Claude reader recovered 97.0% of the content facts from SILEX written by the four models, against 99.2% from their English (minus 2.2 points).
- Length: the models' SILEX is as long as the gold SILEX, and 31 to 41% shorter than their own English for the same scenarios.
- Find the fault: with the guide the models located the planted fault in 232 of 240 faulty conversations (97%) and raised no false alarm; without it they found 74 of 120 (62%).

Three things not to over-read:

1. Differences between models are descriptive. Thinking mode and model tier were not controlled, and Gemini's three writing runs used three different models.
2. The 20-point threshold of prediction 1 could not be reached by a model that already scored above 80% without the guide (Claude 80.3%, Gemini 85.0%). Each model had one no-guide run.
3. Claude wrote the items and is one of the four tested models; Claude also read every round-trip chat, and every judge is a Claude model. The first judge credited slightly more than the second judge and than the runner's audit.

The runner's own readings of these results, and what the data say about them, have a section of their own; none of them was tested directly.

## What is in this package

| Path | What it holds |
| --- | --- |
| `report/` | The report (PDF and Markdown), its six charts (PNG and SVG) and the data of the charts (`figures/chart_data.json`). |
| `results/` | The aggregate tables behind the report (`tables/*.csv`), the Test F summaries (`testf/`), and the aggregator's summary and run information. The tables hold scores by item number, but no item text, fact text or reply. |
| `protocol/` | The protocol document (current version, and the versions of revisions 20, 25 and 28), the analysis plan, the judging procedure, the handling rules decided during the runs, the leak checks, and the two design notes. |
| `guide/` | The SILEX-0 guide that the guided chats received (edition 0.14s) and its checker. |
| `prompts/` | The frozen prompts given to the models and to the judges. |
| `tools/` | The working tools of the study and their tests. See `tools/NOTE_PUBLIC_COPY.txt`. |
| `tests/` | The results of the tools' test suites. |
| `hashes/` | The kit manifests and key-hash notes that fixed the files, including files that are not published. |
| `HASHES.md`, `SHA256SUMS` | Fingerprints of this package and of the files named in the report, the commits, and the withheld files. |

## What is not published, and why

- **The 40 items, the answer key and the fact list, and the Test F items and key.** They are the material of the test. A later blind test on new models needs items that no model has seen, so publishing them would use them up. They can be released later; their fingerprints are in `HASHES.md`, so a later release can be checked against them.
- **The models' replies, the judge sheets and replies, the sheet maps, and the round-trip keys.** The replies restate the items, and the judge sheets hold the fact lists, so publishing them would publish the items and the key. They are kept in the runner's results and judging folders (an archive of 1,507 files, SHA-256 in `HASHES.md`).
- **The private repository.** The report's word "the repository" means the private repository that holds the frozen kits and the answer keys. Opening it would also publish the keys.

Two exceptions to keep in mind:

1. Line 138 of each protocol file (a revision-log entry) quotes the wording of one key fact of item #04. The protocol files are published unedited so that their hashes hold.
2. The protocol, the guide and its checker name the runner by the handle Moonbeam, and the protocol names the private repository.

`protocol/rules/RT_handling_rules_redacted.md` is the round-trip rules file with one parenthesis (in rule 12) and rules 14 and 15 removed, because they quoted a reader chat number next to a writer; the note in the file gives the SHA-256 of the original.

## What you can check, and what you cannot

You can check:

- **The files.** `python3 hashes/check_hashes.py` (or `sha256sum -c SHA256SUMS`) confirms that every file is as published, and that the eight files named in the report's Reproducibility table have the fingerprints recorded there.
- **The checker.** `python3 guide/silex_check.py guide/SILEX-0-GRAMMAR.md` checks the guide against its own rules (it reports 0 example disagreements and 0 document problems); `--messages FILE` checks a SILEX-0 conversation. It judges form only.
- **The numbers.** `results/tables/` holds the aggregate tables the report is built from; `report/figures/chart_data.json` holds the data of each chart.
- **The design, step by step.** The protocol, the analysis plan, the judging procedure and the handling rules say what was decided and when.

You cannot check, from this package alone:

- **The scoring.** Re-making the tables with `tools/aggregate.py` needs the judge replies, the sheet maps and the keys; re-scoring Test F with `tools/score_f.py` needs the Test F key. These are withheld.
- **The timing.** The commits in `HASHES.md` belong to a private repository, so they cannot be looked up until it, or a bundle of it, is shown. The commit that timestamps the predictions came after the reading chats (all 32 reading replies were filed by 02:05 on 14 November) and before the writing, English, round-trip and Test F chats. That the predictions preceded the first chat rests on the runner's account.
- **The test suites.** Most need the frozen kit, so they cannot be run here; their results are in `tests/TEST_RESULTS.md`.

## Who did what

- **The runner (Moonbeam)** pasted every packet into the apps and every reply back as given, stated the models and settings, and made the decisions that the report's appendix lists.
- **Claude** (Anthropic's AI model) wrote the 40 items and the answer key, built the packets, tools and tests, filed and parsed the replies with those tools, and wrote the report. Claude is also one of the four tested models, and Claude Sonnet 5.5 was the reader in every round-trip chat.
- **The judges** were Claude models: eight cold-start agents on Claude Fable 5.2 (first judge), three agents on Claude Opus 5.5 (second judge, a random 20% of the explanations), and three Claude Fable 5.2 agents for the Test F phrase scores. The runner audited 30 facts. The report says how the scoring was kept honest and where it could not be.
- **SILEX-0** and its guide were made by the runner together with several AI models; the guide records who made each part.

## Main limits

The report has a full section; in short:

- One author: Claude wrote the items and the key, is one of the four models tested, and every judge is a Claude model. The second judge and the audit guard against a Claude preference but cannot rule it out.
- Forty items in one fixed order; few runs per model; one unguided reading run per model.
- Thinking mode and model tier were not controlled, so differences between models are descriptive. Contrasts within one model are fair.
- The first judge credited slightly more than the second judge and the runner's audit, so the guide's gain in reading could be a little overstated.
- The Test F phrase scores have no reliability check, by the runner's decision.
- The leak checks are self-reports by the models.

## Licence

Code (`tools/*.py`, `guide/silex_check.py`, `hashes/check_hashes.py`): MIT, see `LICENSE`. Everything else: CC BY 4.0, see `LICENSE-DATA.md`.

Cite as: Moonbeam (2026), *SILEX-0 blind test: results report*, 14 November 2026.
