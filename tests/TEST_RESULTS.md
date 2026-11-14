# Tool test suites

The tools in `tools/` come with test suites (`tools/test_*.py`). They were run on 14 November 2026 at about 19:00 IST, after the runner said all chats were done and before the first judge sheet was built. The counts below are the ones in the report (Reproducibility and Appendix) and in the study's log.

Most suites run against the frozen kit, which holds the answer keys, so they cannot be run from this package alone. They are here so that what each tool was tested for can be read.

| Suite | Checks passed | Checks failed |
| --- | --- | --- |
| test_f_tools | 65 | 0 |
| test_e_tools | 132 | 0 |
| test_rt_tools | 46 | 0 |
| test_judging_stage | 67 | 0 |
| test_judging_tools | 16 | 0 |
| test_reliability | 61 | 0 |
| test_aggregate | 281 | 0 |
| test_phrase_judge_f | 55 | 0 |
| test_p_tools | 73 | 1 |
| test_roundtrip_p | 87 | 1 |
| test_intake | 20 | 1 |

`test_phrase_judge_f` was written and run later the same day (the phrase judge came after the first judging), and its count is the one in the report.

The three failures are stale expectations of the tests, not faults of the tools:

| Suite | Why the failing check is stale |
| --- | --- |
| test_p_tools | It expects the results folder to hold no writing-test files such as cells_P.csv; they exist now. |
| test_roundtrip_p | It expects a writer run without a data reply to stop the build; every writer run has one now. |
| test_intake | It expects one reading sheet per row of cells.csv; the file now also holds 16 round-trip rows, and the builder builds only arms R and N. |

The kit's scoring workbook (withheld, because it holds the fact lists), filled from the aggregator's scores and recalculated by LibreOffice, matched the aggregator's tables on all 188 numbers (report, Reproducibility).
