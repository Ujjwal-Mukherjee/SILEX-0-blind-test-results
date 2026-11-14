# Hashes and fingerprints

Every hash here is SHA-256. Times are Asia/Kolkata (IST), 14 November 2026 unless stated.

## Check this package

```
python3 hashes/check_hashes.py        # needs only Python 3
# or, with GNU coreutils:
sha256sum -c SHA256SUMS
```

`SHA256SUMS` lists every file of the package except itself. `check_hashes.py` also checks the fingerprints that the report's Reproducibility table gives for eight files (the first 16 characters of their SHA-256).

`.gitattributes` turns off line-ending conversion, so a checkout on any system keeps the bytes that the hashes cover.

## Files named in the report

| File | Fixed | SHA-256 | Path here |
| --- | --- | --- | --- |
| Guide SILEX-0-GRAMMAR.md, edition 0.14s | in the frozen reading kit | `fd8640fcec49787ec875b7bbfbac89a45479598dc4ec706d682d06bb1b9d68eb` | `guide/SILEX-0-GRAMMAR.md` |
| Checker silex_check.py | in the frozen reading kit | `485065d4fae66e724a2983dc653cb3656b92693e04cc54702827b4fb56afd2ad` | `guide/silex_check.py` |
| ANALYSIS_PLAN.md | 14 Nov 05:59 | `25e27eeac34a1f4acfea84db8c5f3eb404650769c9cf829869d017fa25c9cc8e` | `protocol/ANALYSIS_PLAN.md` |
| tools/aggregate.py | 14 Nov 05:59 | `0c2ec37a4cfee7b68669badb28f43f108dfb5057d4123d26d8053f43fd31a092` | `tools/aggregate.py` |
| JUDGING_PROCEDURE.md | 14 Nov 06:24 | `bf56e21fe4f0a6b4387bb39fa519a25059846a99a3b8ee61e033a62ef30a1340` | `protocol/JUDGING_PROCEDURE.md` |
| tools/score_f.py | frozen in the Test F kit | `fe01189f2c43d6d42e634b4df9992b2a9d778c39a17450637b93682d8941ae7b` | `tools/score_f.py` |
| tools/make_strict_copy_f.py | 14 Nov 19:05 | `4c2da5a40c99c415fa009bb9c9927f4e09b57652531f658a3427e8ea69ba48ce` | `tools/make_strict_copy_f.py` |
| tools/phrase_judge_f.py | 14 Nov 19:16 | `7fff8c2c82adef894f09a4a055aafaa4ef25d9fd54a114ba6795f271336f8140` | `tools/phrase_judge_f.py` |
| tools/fill_scoring_xlsx.py | 14 Nov 19:39, logged when it ran | `dfdc0e6f79592b2a300c658d287ff2c03a2a733c046a94c53cf9bfdf71dab5ec` | `tools/fill_scoring_xlsx.py` |

## The protocol document, as committed

The protocol was committed several times as the study went on; each file here is byte for byte the version of that commit. The current version is the last one.

| Revision | Commit | SHA-256 | Path here |
| --- | --- | --- | --- |
| rev 20 | `34a39562aa9abebba4accb443038402ed3535510` | `e71d126519a4ea66b77d11ca79a38de65b15eeeb93c2a1b1c5fd2dcf22f0baab` | `protocol/copies/protocol_rev20_commit_34a39562.md` |
| rev 25 | `0f7a41dfd11af95bccd8f9a8c4407ba650f79db3` | `c5e3030b033693317695870e63208ea18e02294802a75247126ad81187c3b00b` | `protocol/copies/protocol_rev25_commit_0f7a41df.md` |
| rev 28 | `c1ef8c6558fef80ee94930fd5927b499ed7b76c5` | `47c25094f9fd85c938cccfd7cc48409edade43b86855bcbeb78df9a3e67be220` | `protocol/copies/protocol_rev28_commit_c1ef8c65.md` |
| rev 33 (current) | `95b16297524f97b4f9efc19766df7469f9d5f323` | `ffa7129a068aab1d0db2c539e1718b3a6bcbffc809a7234b47302dcc9d0fd44c` | `protocol/SILEX_blind_test_protocol.md` |

The protocol files are published unedited, so that these hashes hold. They carry the runner's handle and the name of the private repository (see README.md, "What is not published").

## Commits of the private repository

The repository is private. These are the commits that the report and this package refer to. They can be checked only once the repository, or a bundle of it, is shown. Commit dates are set by the committer; that the predictions came before the first chat rests on the runner's account, as the report says.

| Commit | When | What it holds |
| --- | --- | --- |
| `f0e608b084e4dfc6712c01b16f947c1717fe2021` | 14 Nov 02:38 | The frozen reading kit and the frozen Test F kit (guide, checker, packets, answer keys, prompts). |
| `34a39562aa9abebba4accb443038402ed3535510` | 14 Nov 02:50 | The protocol document at revision 20, with the predictions. |
| `0f7a41dfd11af95bccd8f9a8c4407ba650f79db3` | 14 Nov 06:35 | The protocol document at revision 25. |
| `c1ef8c6558fef80ee94930fd5927b499ed7b76c5` | 14 Nov 09:02 | The protocol document at revision 28. |
| `95b16297524f97b4f9efc19766df7469f9d5f323` | 14 Nov 18:56 | The protocol document at revision 33. The last commit; it came before any judge sheet existed. |

## Withheld files whose fingerprints were fixed before use

The files below are not published. Their SHA-256 values come from the kit manifests that were committed with the kits (`hashes/MANIFEST_*.sha256`). If they are released later, they can be checked against these values.

### Reading kit (commit f0e608b0)

| File | SHA-256 |
| --- | --- |
| `answer_key.md` | `ff08196b7ccbc04206c7bf2cade5e4fbad1da1d05cf2baf9769a21763184fa3e` |
| `facts.csv` | `75a352ac831330786d03f542dd6f00918dad18fe3b77c610f964e815041981e6` |
| `order.csv` | `921671500e36ad197fcde5c1f3e1e7bb751c4468c2f42398f8c451282618412e` |
| `silex_scoring.xlsx` | `1807ed17b39285c31105f7e4295c0355b50010a6a0df432eaf1a5e2814b33f69` |
| `R_batch1.txt` | `b222bd8b91ce78f7fc80ff8826c4fa9ff31cbcf444bc5a9b40917ce2d8324b65` |
| `R_batch2.txt` | `76f9a197a4dc9d397b6c4e1a109bd3d69b252bbb8f0b017b4e17968b9e83473d` |
| `N_batch1.txt` | `0f31d11e6622707236442af1ffd82c7ed0bb5ea20466b3ad6f2eb34a19feb7c5` |
| `N_batch2.txt` | `2115c9a60f3a16b97920a09c097ad7fd8c056411c353d8351667d6f873eb4784` |
| `P_batch1.txt` | `7e75be1d30cfcc720bb992d3e1d069cf1f264ae2f9a817a77c0a2dc8123f0d65` |
| `P_batch2.txt` | `dc2c3c2ffc1db891fb1a8a9ff4cd161c673505daf66eb7ff2931f45e5816cc53` |
| `E_batch1.txt` | `89df79f2789ab5580b30ca9fda1dca8658826f98523f9b4fd5ba4f2596e77ecb` |
| `E_batch2.txt` | `7312693b1b5979e1dc5f2ed592e0a56873b583046d4eb815946e64f96627638c` |
| `silex_kit_PRIVATE.zip` | `92068da312e1f085b6dbd37751abf4727785f3dc43c45fbc3258bc42673e0418` |

### Test F kit (commit f0e608b0; frozen 13 Nov 23:22)

| File | SHA-256 |
| --- | --- |
| `items_F_PRIVATE.json` | `3315944a031c742914723e5830f6c5a06076cde114901900daafaa53fddecf84` |
| `key_F_PRIVATE.csv` | `681b7832b4f124248df0a3097c7b2359e3a63cb9138b7d316a75dc35e167bc9d` |
| `FR_batch1.txt` | `3c054f37b1e131ec5effc7dc149a8247a95b52560f8420e30ed2b49852660320` |
| `FR_batch2.txt` | `6c900bc1bf16a6d1c7d267586cca82872f63bb66fed949b04225aa0bf1dc6643` |
| `FN_batch1.txt` | `f834f9c6d3e726949f41077fbecf073519ab7e863edcf7ba45c987dc4d9b17f0` |
| `FN_batch2.txt` | `d795bb57218c23e0fe5ded8eee94135b86a672d30ee01caf0cdc9f356b831df9` |

### Round-trip keys

The key files say which writer each reader chat read and in what item order. They are not in the private repository either; only their hashes are (`hashes/KEY_HASH_roundtrip_*.txt`).

| Key file | State | SHA-256 |
| --- | --- | --- |
| `rt_key_PRIVATE.csv` (SILEX round trip) | with the packets of reader chats 1, 2 and 4 (14 Nov 05:16) | `c334539f2796a575389ca029e0d998393c7d4b2dda3ef11642d0cdd39f81fe4c` |
| `rt_key_PRIVATE.csv` (SILEX round trip) | with the packets of all four reader chats (14 Nov 06:00), final | `897ba8a27c580b671cc39b56c8d9de53d0ce3aa91e77b828dc6a53c3fc2ad11e` |
| `rt_key_E_PRIVATE.csv` (English round trip) | with the packets of all four reader chats, final | `4ef4e355cc29b4573d2b4e232d81a19d7a87b41fb74c65e3ce8bf8b9d539db14` |

The runner's key files were hashed again on 14 November, after the report was finished, and match the two final values.

The other kit manifests are in `hashes/`: the round-trip kits (SILEX, English, judging), the tool folders (P, E, F) and the analysis folder. Together they list 109 files, which verified on 14 November at about 19:00 IST (before the first judge sheet) and again after the report was finished.

## Archive of the results and judging folders

Made on 14 November after all results existed, with 1,507 files (replies, parses, judge sheets, judge replies, sheet maps, keys, logs). It is not published.

SHA-256 `51f4d9d8f0467668e724c68a7839719e92d99a3d43a489bf7856440b95497623`

