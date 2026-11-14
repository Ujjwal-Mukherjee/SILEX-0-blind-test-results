#!/usr/bin/env python3
"""Tests of phrase_judge_f.py (the phrase judge of Test F) on MADE-UP data only: a made-up key, made-up replies, made-up judge replies.
It reads no real key and no real reply, and it checks that the real results folder is not changed.
Usage: python3 -I test_phrase_judge_f.py
"""
import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "phrase_judge_f.py")
REAL = os.path.dirname(HERE)  # the real results folder (silex_results)

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   [" + str(detail)[-500:] + "]"))
    if not cond:
        FAILS.append(name)


def run(args):
    p = subprocess.run([sys.executable, "-I", TOOL] + args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def fingerprint(root):
    fp = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("tools", "__pycache__")]
        for f in files:
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
                fp[p] = (st.st_size, st.st_mtime_ns)
            except OSError:
                pass
    return fp


VERDICTS = ["E-SYN", "E-LEX", "E-ARITY", "E-KIND", "E-NAME", "E-REDEF", "E-HEAD", "E-TIME", "E-QUOTE", "E-ENGLISH", "E-BUDGET", "E-REF", "E-COUNT", "E-CODE", "E-MATH"]
CLEAN = {3, 7, 11, 15, 19, 23, 27, 31, 35, 39}
FAULTY = [i for i in range(1, 41) if i not in CLEAN]
PROMPT = "FAKE JUDGE PROMPT. Score each phrase 1 or 0.\nReply with one line per item: F07 | 1 | reason if 0, at most 12 words\n"
FIFTEEN = "w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11 w12 w13 w14 w15"


def iid(i):
    return "F%02d" % i


def make_kit(root):
    os.makedirs(root)
    rows = []
    for i in range(1, 41):
        faulty = i in FAULTY
        v = VERDICTS[FAULTY.index(i) % 15] if faulty else "ok"
        rows.append(dict(id=iid(i), batch=1 if i <= 20 else 2, tag="t", seed_item="s", verdict=v, location=("Z9.%d" % i if faulty else ""), also_accept="",
                         n_places=6, kind=("KIND-%s" % v if faulty else "none"), description=("SECRETDESC fault of %s in item %d" % (v, i) if faulty else "no fault"),
                         checker_text=("CHECKERSECRET %d" % i if faulty else "")))
    with open(os.path.join(root, "key_F_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    open(os.path.join(root, "judge_fault.txt"), "w", encoding="utf-8").write(PROMPT)


# the made-up answers: (arm, model, run) -> {item number: (place, place_raw, phrase)}
def design():
    d = {}
    # FR claude 1: every faulty item found; good phrase on even item numbers, a vague one on odd; clean items "none"
    a = {}
    for i in range(1, 41):
        if i in FAULTY:
            a[i] = ("Z9.%d" % i, "Z9.%d" % i, ("good description %d" % i) if i % 2 == 0 else ("vague wrong %d" % i))
        else:
            a[i] = ("none", "none", "")
    d[("FR", "claude", 1)] = a
    # FR claude 2: first 10 faulty found (good), next 10 wrong place (good for the first 5 of them), the last 10 "none"; clean: two false alarms
    a = {}
    for n, i in enumerate(FAULTY):
        if n < 10:
            a[i] = ("Z9.%d" % i, "Z9.%d" % i, "good found %d" % i)
        elif n < 20:
            a[i] = ("A1.2", "A1.2", ("good but elsewhere %d" % i) if n < 15 else ("bad elsewhere %d" % i))
        else:
            a[i] = ("none", "none", "")
    for i in sorted(CLEAN):
        a[i] = ("A1.2", "A1.2", "false alarm %d" % i) if i in (3, 23) else ("none", "none", "")
    d[("FR", "claude", 2)] = a
    # FN grok 1: everything none except 5 unreadable places, 3 wrong places, one phrase of 15 words, one empty phrase
    a = {i: ("none", "none", "") for i in range(1, 41)}
    for n, i in enumerate(FAULTY[:5]):
        a[i] = (None, "somewhere odd", "unreadable place %d" % i)
    for i in FAULTY[5:7]:
        a[i] = ("A2.1", "A2.1", "vague wrong b %d" % i)
    a[FAULTY[7]] = ("A2.1", "A2.1", "this is the Gemini way, wrong")
    a[FAULTY[8]] = ("A1.3", "A1.3", FIFTEEN)
    a[FAULTY[9]] = ("A1.3", "A1.3", "")
    d[("FN", "grok", 1)] = a
    return d


def make_results(root, des):
    os.makedirs(os.path.join(root, "parsed_f"))
    cells, n = [], 0
    for (arm, model, run_n), ans in des.items():
        for batch in (1, 2):
            n += 1
            recv = "recv%d" % n
            answers, order = {}, []
            for ln, i in enumerate([x for x in range(1, 41) if (x <= 20) == (batch == 1)], 1):
                place, raw, phrase = ans[i]
                answers[iid(i)] = dict(place_raw=raw, place=place, phrase=phrase, line="%s | %s | %s" % (iid(i), raw, phrase), line_no=ln)
                order.append(iid(i))
            json.dump(dict(source="made up", sha256="0", preamble=[], other_lines_after_first_answer=[], duplicates=[], form_notes=[], order=order, answers=answers),
                      open(os.path.join(root, "parsed_f", recv + ".json"), "w", encoding="utf-8"))
            cells.append(dict(recv=recv, arm=arm, model=model, run=run_n, batch=batch, status="data", run_assumed="no", file="x", sha256_16="0"))
    with open(os.path.join(root, "cells_F.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["recv", "arm", "model", "run", "batch", "status", "run_assumed", "file", "sha256_16"])
        w.writeheader()
        w.writerows(cells)


def read_csv(p):
    return list(csv.DictReader(open(p, newline="", encoding="utf-8")))


def expected_entries(des):
    """independent count of the answers that name a fault on a faulty item"""
    out = []
    for (arm, model, run_n), ans in des.items():
        for i in FAULTY:
            place, raw, phrase = ans[i]
            if place != "none":
                out.append((arm, model, run_n, iid(i)))
    return out


def judge_reply_from_entries(build, scores_by_phrase, code):
    """a made-up judge reply for one sheet: 1 when the phrase contains 'good', else 0 with a reason"""
    ents = [e for e in read_csv(os.path.join(build, "entries_PRIVATE.csv")) if e["code"] == code]
    lines = []
    for e in sorted(ents, key=lambda x: int(x["pos"])):
        ok = "good" in e["phrase"]
        lines.append("%s | 1" % e["item"] if ok else "%s | 0 | does not say what is wrong" % e["item"])
    return "\n".join(lines) + "\n"


def main():
    before = fingerprint(REAL)
    tmp = tempfile.mkdtemp(prefix="pjf_test_")
    kit, res = os.path.join(tmp, "kit"), os.path.join(tmp, "res")
    make_kit(kit)
    des = design()
    make_results(res, des)
    kit_fp, res_fp = fingerprint(kit), fingerprint(res)

    # ---------------- build
    b1 = os.path.join(tmp, "build1")
    rc, out, err = run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", b1])
    check("build runs", rc == 0, out + err)
    ents = read_csv(os.path.join(b1, "entries_PRIVATE.csv"))
    exp = expected_entries(des)
    check("one entry for every answer that names a fault on a faulty item (%d)" % len(exp), len(ents) == len(exp) == 60, (len(ents), len(exp)))
    got = sorted((e["arm"], e["model"], int(e["run"]), e["item"]) for e in ents)
    check("the entries are exactly those answers (none, clean items and false alarms have no entry)", got == sorted(exp))
    check("an answer of a clean item never has an entry", all(int(e["item"][1:]) not in CLEAN for e in ents))
    maprows = read_csv(os.path.join(b1, "sheets_map_PRIVATE.csv"))
    check("sheets of at most 20 entries", all(int(r["n_items"]) <= 20 for r in maprows) and sum(int(r["n_items"]) for r in maprows) == 60, [r["n_items"] for r in maprows])
    check("no item code twice on a sheet", all(len(r["order"].split()) == len(set(r["order"].split())) for r in maprows))
    check("sheet codes are four characters of the sheet alphabet and unique", all(re.fullmatch(r"[A-HJKMNPQRT-Z2-9]{4}", r["code"]) for r in maprows) and len({r["code"] for r in maprows}) == len(maprows))
    texts = {r["code"]: open(os.path.join(b1, "sheets", "sheet_%s.txt" % r["code"]), encoding="utf-8").read() for r in maprows}
    check("every sheet starts with the judge prompt verbatim", all(t.startswith(PROMPT) for t in texts.values()))
    alltext = "\n".join(texts.values())
    noname = "\n".join(ln for ln in alltext.splitlines() if "Gemini way" not in ln)
    check("no model name, arm, chat number or checker text on a sheet (apart from the one phrase that names a model on purpose)", not re.search(r"(?i)claude|grok|gemini|recv|\bFR\b|\bFN\b|CHECKERSECRET", noname))
    check("the key's kind and description are on the sheets", "KIND-E-SYN" in alltext and "SECRETDESC fault of E-SYN" in alltext)
    check("the true place appears only as a reader's place (never as a key line)",
          all((("Z9." not in ln) or ln.startswith("Reader's place: ")) for ln in alltext.splitlines()))
    check("a phrase of 15 words is cut after the 12th word", ("Reader's phrase: " + " ".join(FIFTEEN.split()[:12])) in alltext and "w13" not in alltext)
    check("the original word count is kept in the private entries", any(e["words_original"] == "15" for e in ents))
    check("an empty phrase is shown as (empty)", "Reader's phrase: (empty)" in alltext)
    check("a place that could not be read is shown as the reader wrote it", "Reader's place: somewhere odd" in alltext)
    info = json.load(open(os.path.join(b1, "build_info_PRIVATE.json"), encoding="utf-8"))
    check("build info: counts", info["entries"] == 60 and info["phrases_cut_after_12_words"] == 1 and info["empty_phrases"] == 1 and info["phrases_naming_a_model"] == 1, info)
    check("build info: judge prompt hash", info["judge_prompt_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest())

    b2 = os.path.join(tmp, "build2")
    run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", b2])
    same = all(open(os.path.join(b1, "sheets", f), "rb").read() == open(os.path.join(b2, "sheets", f), "rb").read() for f in os.listdir(os.path.join(b1, "sheets"))) and \
        open(os.path.join(b1, "sheets_map_PRIVATE.csv"), "rb").read() == open(os.path.join(b2, "sheets_map_PRIVATE.csv"), "rb").read()
    check("the same seed gives the same sheets", same)
    b3 = os.path.join(tmp, "build3")
    run(["build", "--results", res, "--kit", kit, "--seed", "8", "--out", b3])
    check("another seed gives other sheets", open(os.path.join(b1, "sheets_map_PRIVATE.csv"), "rb").read() != open(os.path.join(b3, "sheets_map_PRIVATE.csv"), "rb").read())
    b4 = os.path.join(tmp, "build4")
    rc, out, err = run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", b4, "--per-sheet", "5"])
    m4 = read_csv(os.path.join(b4, "sheets_map_PRIVATE.csv"))
    check("--per-sheet 5 gives sheets of at most 5 with no item twice", rc == 0 and all(int(r["n_items"]) <= 5 for r in m4) and all(len(set(r["order"].split())) == len(r["order"].split()) for r in m4)
          and sum(int(r["n_items"]) for r in m4) == 60, out + err)
    rc, out, err = run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", b1])
    check("build refuses a non-empty OUT", rc == 1 and "OUT must not exist" in err, err)
    rc, out, err = run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", os.path.join(tmp, "b5"), "--per-sheet", "21"])
    check("--per-sheet over 20 is a usage error", rc == 2, (rc, err))
    avoid_map = os.path.join(tmp, "avoid.csv")
    open(avoid_map, "w").write("code\n" + "\n".join(r["code"] for r in maprows) + "\n")
    b6 = os.path.join(tmp, "build6")
    run(["build", "--results", res, "--kit", kit, "--seed", "7", "--out", b6, "--avoid", avoid_map])
    m6 = read_csv(os.path.join(b6, "sheets_map_PRIVATE.csv"))
    check("--avoid keeps the codes of another build out", not ({r["code"] for r in m6} & {r["code"] for r in maprows}))

    # ---------------- collect
    outbox, replies, scores = os.path.join(tmp, "outbox"), os.path.join(tmp, "REPLIES"), os.path.join(tmp, "SCORES")
    os.makedirs(outbox)
    codes = [r["code"] for r in maprows]
    for c in codes:
        open(os.path.join(outbox, "reply_%s.txt" % c), "w").write(judge_reply_from_entries(b1, None, c))
    rc, out, err = run(["collect", "--outbox", outbox, "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", replies, "--scores", scores])
    check("collect: all sheets clean, exit 0", rc == 0 and out.count("status: clean") == len(codes), out + err)
    check("collect prints no score and no reason", not re.search(r"\| *[01]\b|does not say", out))
    check("collected files are byte for byte copies and read-only", all(open(os.path.join(replies, "reply_%s.txt" % c), "rb").read() == open(os.path.join(outbox, "reply_%s.txt" % c), "rb").read()
          and not (os.stat(os.path.join(replies, "reply_%s.txt" % c)).st_mode & stat.S_IWUSR) for c in codes))
    lg = read_csv(os.path.join(replies, "collected_log.csv"))
    check("collected_log.csv has one row per sheet with the sha256", len(lg) == len(codes) and all(r["sha256"] == hashlib.sha256(open(os.path.join(outbox, "reply_%s.txt" % r["code"]), "rb").read()).hexdigest() for r in lg))
    rc, out, err = run(["collect", "--outbox", outbox, "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", replies, "--scores", scores])
    check("collect again: unchanged files are skipped", rc == 0 and out.count("already collected, unchanged") == len(codes), out)
    c0 = codes[0]
    os.chmod(os.path.join(outbox, "reply_%s.txt" % c0), 0o644)
    open(os.path.join(outbox, "reply_%s.txt" % c0), "a").write("F01 | 1\n")
    rc, out, err = run(["collect", "--outbox", outbox, "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", replies, "--scores", scores])
    check("a changed outbox file is NOT collected (exit 1)", rc == 1 and "NOT collected" in out, out)
    sc = json.load(open(os.path.join(scores, c0 + ".json")))
    check("the JSON of a clean sheet lists every item with 0 or 1", sc["status"] == "clean" and len(sc["items"]) == int(maprows[0]["n_items"]) and all(v["score"] in (0, 1) for v in sc["items"].values()))

    def scenario(name, mutate, expect_status, expect_in_out=None, expect_rc=None):
        d = os.path.join(tmp, "sc_" + name)
        ob = os.path.join(d, "outbox")
        os.makedirs(ob)
        row = maprows[1]
        base = judge_reply_from_entries(b1, None, row["code"]).splitlines()
        text = mutate(base, row)
        open(os.path.join(ob, "reply_%s.txt" % row["code"]), "w").write(text)
        rc, out, err = run(["collect", "--outbox", ob, "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", os.path.join(d, "R"), "--scores", os.path.join(d, "S"),
                            "--codes", row["code"]])
        js = json.load(open(os.path.join(d, "S", row["code"] + ".json")))
        ok = js["status"] == expect_status and (expect_in_out is None or expect_in_out in out) and (expect_rc is None or rc == expect_rc)
        check("collect: " + name, ok, (rc, out, js["status"], js["problems"], js["warnings"]))
        return js

    scenario("bold and bullets are stripped, noted", lambda L, r: "\n".join(("- **" + x + "**") if i % 2 == 0 else x for i, x in enumerate(L)) + "\n", "notes", expect_rc=0)
    scenario("a heading and a SHEET echo are ignored, noted", lambda L, r: "SHEET %s\nHere are my scores\n" % r["code"] + "\n".join(L) + "\n", "notes", expect_rc=0)
    scenario("a 0 without a reason is a note", lambda L, r: "\n".join(x.split(" | 0")[0] + " | 0" if " | 0" in x else x for x in L) + "\n", "notes" if any(" | 0" in x for x in judge_reply_from_entries(b1, None, maprows[1]["code"]).splitlines()) else "clean", expect_rc=0)
    scenario("a reason on a 1 and a reason over 12 words are notes", lambda L, r: "\n".join(L[:-1]) + "\n" + L[-1].replace(" | 1", " | 1 | fine").replace(" | 0 | does not say what is wrong", " | 0 | " + FIFTEEN) + "\n", "notes", expect_rc=0)
    js = scenario("a malformed line is a problem (redo)", lambda L, r: "\n".join(["%s: 1" % L[0].split()[0]] + L[1:]) + "\n", "redo", "PROBLEM", expect_rc=1)
    check("the malformed item is not used and the others are", len(js["items"]) == int(maprows[1]["n_items"]) - 1)
    scenario("a missing item is a problem (redo)", lambda L, r: "\n".join(L[1:]) + "\n", "redo", "no line for this item", expect_rc=1)
    scenario("a doubled item is a problem (redo)", lambda L, r: "\n".join(L + [L[0]]) + "\n", "redo", "more than once", expect_rc=1)
    other = next(i for i in range(1, 41) if iid(i) not in maprows[1]["order"].split())
    scenario("an item that is not on the sheet is a problem (redo)", lambda L, r: "\n".join(L + ["%s | 1" % iid(other)]) + "\n", "redo", "not on this sheet", expect_rc=1)
    scenario("a score other than 0 or 1 is a problem (redo)", lambda L, r: "\n".join([L[0].replace(" | 1", " | 2").replace(" | 0", " | 2")] + L[1:]) + "\n", "redo", "malformed", expect_rc=1)
    d = os.path.join(tmp, "sc_missing")
    os.makedirs(os.path.join(d, "ob"))
    rc, out, err = run(["collect", "--outbox", os.path.join(d, "ob"), "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", os.path.join(d, "R"), "--scores", os.path.join(d, "S"), "--codes", codes[0]])
    check("a sheet with no reply file is listed as MISSING (exit 1)", rc == 1 and "MISSING" in out, out)
    rc, out, err = run(["collect", "--outbox", outbox, "--map", os.path.join(b1, "sheets_map_PRIVATE.csv"), "--replies", os.path.join(d, "R"), "--scores", os.path.join(d, "S"), "--codes", "ZZZZ"])
    check("an unknown --codes value is a usage error", rc == 1 and "not in the map" in err or rc == 2, (rc, err))

    # ---------------- tables (replies of the first sheets were collected above; restore the one changed file first)
    open(os.path.join(outbox, "reply_%s.txt" % c0), "w").write(judge_reply_from_entries(b1, None, c0))
    t1 = os.path.join(tmp, "tables1")
    rc, out, err = run(["tables", "--results", res, "--kit", kit, "--build", b1, "--scores", scores, "--out", t1])
    check("tables run on a complete set", rc == 0, out + err)
    items = read_csv(os.path.join(t1, "phrase_f_items.csv"))
    check("one row per named answer in the items file", len(items) == 60)
    summ = json.load(open(os.path.join(t1, "phrase_f_summary.json"), encoding="utf-8"))["per_run"]
    # expected, from the design alone
    good1 = sum(1 for i in FAULTY if i % 2 == 0)
    r1 = summ["FR-claude-1"]
    check("FR claude 1: 30 faulty, 30 named, 30 found, credited = even item numbers", (r1["faulty"], r1["named"], r1["found"], r1["credited"], r1["found_credited"], r1["wrong_judged"]) == (30, 30, 30, good1, good1, 0), r1)
    r2 = summ["FR-claude-2"]
    check("FR claude 2: 20 named, 10 found (all credited), 10 wrong place (5 credited), false alarms not judged", (r2["named"], r2["found"], r2["found_credited"], r2["wrong_judged"], r2["wrong_credited"], r2["credited"]) == (20, 10, 10, 10, 5, 15), r2)
    r3 = summ["FN-grok-1"]
    check("FN grok 1: 10 named, none credited, none with the right place", (r3["named"], r3["credited"], r3["found"]) == (10, 0, 0), r3)
    md = open(os.path.join(t1, "phrase_f_tables.md"), encoding="utf-8").read()
    check("the tables file has the per run, by arm and model, by arm and by verdict parts", all(x in md for x in ("## Per run", "## By arm and model", "## By arm (all models)", "## By verdict")), md[:200])
    check("the all-faulty denominator is 30 per run (none counts 0)", "| FR | claude | 2 | 30 | 20 | 15/20 (75%) | 15/30 (50%) |" in md, md)
    rc, out, err = run(["tables", "--results", res, "--kit", kit, "--build", b1, "--scores", scores, "--out", t1])
    check("tables refuse a non-empty OUT", rc == 1 and "OUT must not exist" in err, err)
    # incomplete: drop one sheet's judge file
    scores_inc = os.path.join(tmp, "SCORES_inc")
    os.makedirs(scores_inc)
    for c in codes[:-1]:
        open(os.path.join(scores_inc, c + ".json"), "w").write(open(os.path.join(scores, c + ".json")).read())
    t2 = os.path.join(tmp, "tables2")
    rc, out, err = run(["tables", "--results", res, "--kit", kit, "--build", b1, "--scores", scores_inc, "--out", t2])
    check("tables stop while a sheet has no judge file (exit 1, nothing written)", rc == 1 and "incomplete judging" in err and not os.path.exists(os.path.join(t2, "phrase_f_tables.md")), err)
    rc, out, err = run(["tables", "--results", res, "--kit", kit, "--build", b1, "--scores", scores_inc, "--out", t2, "--partial"])
    check("--partial makes a table marked PARTIAL", rc == 0 and "PARTIAL" in open(os.path.join(t2, "phrase_f_tables.md")).read(), out + err)
    # a redo sheet also blocks the tables
    scores_redo = os.path.join(tmp, "SCORES_redo")
    os.makedirs(scores_redo)
    for c in codes:
        open(os.path.join(scores_redo, c + ".json"), "w").write(open(os.path.join(scores, c + ".json")).read())
    js = json.load(open(os.path.join(scores_redo, codes[0] + ".json")))
    js["status"] = "redo"
    json.dump(js, open(os.path.join(scores_redo, codes[0] + ".json"), "w"))
    rc, out, err = run(["tables", "--results", res, "--kit", kit, "--build", b1, "--scores", scores_redo, "--out", os.path.join(tmp, "tables3")])
    check("tables stop while a sheet has status redo", rc == 1 and "incomplete judging" in err, err)

    # ---------------- nothing else changed
    check("the made-up kit and results folder are unchanged by the tool", fingerprint(kit) == kit_fp and fingerprint(res) == res_fp)
    check("the real results folder is unchanged by the tests", fingerprint(REAL) == before)
    print()
    print("ALL PASS: 0 check(s) failed" if not FAILS else "%d FAILED: %s" % (len(FAILS), FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
