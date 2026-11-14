#!/usr/bin/env python3
"""Reliability checks of the judging (ANALYSIS_PLAN.md, rules 15 to 17). FORM AND SAMPLING ONLY: this program never scores anything.

Four commands. All of them read the checked judge files (JSON made by check_judge_reply.py / check_judge_reply_rt.py --json), the private sheet maps of the
first judge and the parsed reader replies; none of them changes a file of the results folder or of the kit. Run them only after the last first-judge reply is checked.

  second-draw     draw a random share (default 20 percent) of the judged explanations (an explanation = one item of one reader reply) with a seed that the user
                  has seen written in the log BEFORE the draw, and build blind sheets for the second judge from them: the frozen judge prompt verbatim
                  (judge_recovery.txt for reading items, judge_roundtrip.txt for round-trip items), new random sheet codes, the same fact lists and the same explanation
                  text (with any correction note) as on the first judge's sheet, no scenario item twice on one sheet, at most 20 items per sheet, items and sheets shuffled.
                  Output: sheets/sheet_CODE.txt, second_map_PRIVATE.csv (code, kind, n_items, order, sources, sheet_sha16), draw_info_PRIVATE.json.
                  The replies of the second judge are checked with check_judge_reply.py (reading sheets) or check_judge_reply_rt.py (round-trip sheets) with
                  --map second_map_PRIVATE.csv, exactly as for the first judge.
  second-compare  compare the second judge's scores with the first judge's on the drawn explanations: share of facts where the two scores differ
                  (rule 16), above 10 percent when 10 * differing > compared (rule 17: exactly 10 percent is not above). Also by kind and by arm, the direction of the
                  differences, false-count differences, Cohen's kappa (extra), and the list of differing facts.
  audit-draw      draw 30 judged facts at random (seed logged before the draw) from all judged facts of the reading and round-trip arms and write the audit sheet
                  for the user: only the fact and the explanation, the scoring rule of the judge prompt, no judge score, no arm, no model, no code.
                  Output: audit_sheet.txt, audit_key_PRIVATE.csv, audit_info_PRIVATE.json.
  audit-compare   compare the user's 1/0 answers with the judge's scores: share of the entries where they differ (rule 15), above 10 percent when 10 * differing > entries.

Usage:
  python3 -I reliability.py second-draw --results RES --kit KIT --reading-map MAP --reading-scores DIR [--rt-map MAP --rt-scores DIR] --seed N [--fraction 0.2] --out OUT
  python3 -I reliability.py second-compare --draw OUT --second-scores DIR --kit KIT --reading-map MAP --reading-scores DIR [--rt-map MAP --rt-scores DIR] [--report FILE.md] [--json FILE]
  python3 -I reliability.py audit-draw --results RES --kit KIT --reading-map MAP --reading-scores DIR [--rt-map MAP --rt-scores DIR] --seed N [--n 30] --out OUT
  python3 -I reliability.py audit-compare --key OUT/audit_key_PRIVATE.csv --answers FILE [--report FILE.md] [--json FILE]
Exit code: 0 done, 1 a problem with the input (nothing is guessed or filled in), 2 usage.
"""
import argparse
import csv
import glob
import hashlib
import json
import math
import os
import random
import re
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_judge_sheets as bj  # noqa: E402

READING_ARMS = ("R", "N")
RT_ARMS = ("RTP", "RTE")
BATCH_ITEMS = bj.BATCH_ITEMS
ALL_ITEMS = BATCH_ITEMS[1] + BATCH_ITEMS[2]
MAX_ITEMS_PER_SHEET = 20
THRESHOLD_NOTE = "above 10 percent means 10 * (differing) > (compared); exactly 10 percent is not above"


def die(msg):
    print("reliability.py: " + msg, file=sys.stderr)
    sys.exit(1)


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def above_ten_percent(differing, compared):
    """True when the share of differing is strictly above 10 percent (exact integers)."""
    return compared > 0 and 10 * differing > compared


# ---------------------------------------------------------------------------------------------- loading
class Ctx:
    """Everything the four commands need: the kit's facts, the prompts, the first judge's sheets and scores, the reader replies."""

    def __init__(self, results, kit, reading_map, reading_scores, rt_map, rt_scores, need_results=True):
        self.results, self.kit = results, kit
        self.facts_all = bj.load_facts(kit)
        self.facts_c = {it: [x for x in lst if x[1] == "C"] for it, lst in self.facts_all.items()}
        for it, lst in self.facts_c.items():
            if not lst:
                die("%s has no C fact" % it)
        self.prompts = {}
        for kind, name in (("reading", "judge_recovery.txt"), ("rt", "judge_roundtrip.txt")):
            self.prompts[kind] = open(os.path.join(kit, name), "rb").read().decode("utf-8")
        self.corr = {}
        if need_results and results:
            cp = os.path.join(results, "corrections.json")
            if os.path.exists(cp):
                self.corr = json.load(open(cp, encoding="utf-8"))
        if bool(rt_map) != bool(rt_scores):
            die("give both --rt-map and --rt-scores, or neither")
        self.sheets = {}      # first-judge code -> dict(kind, row, items{item: dict(scores, false)})
        self._load_kind("reading", reading_map, reading_scores, READING_ARMS)
        if rt_map:
            self._load_kind("rt", rt_map, rt_scores, RT_ARMS)
        self._expl_cache = {}

    def facts(self, kind, item):
        return (self.facts_all if kind == "reading" else self.facts_c)[item]

    def expected_ks(self, kind, item):
        return set(k for k, _, _ in self.facts(kind, item))

    def _load_kind(self, kind, map_path, scores_dir, arms):
        rows = read_csv(map_path)
        if not rows:
            die("%s is empty" % map_path)
        mine = {}
        for r in rows:
            if r["arm"] not in arms:
                die("%s: sheet %s has the arm %r, not one of %s" % (map_path, r["code"], r["arm"], "/".join(arms)))
            if r["code"] in self.sheets or r["code"] in mine:
                die("sheet code %s twice" % r["code"])
            order = r["order"].split()
            if sorted(order) != BATCH_ITEMS[int(r["batch"])]:
                die("sheet %s: its items are not the items of batch %s" % (r["code"], r["batch"]))
            mine[r["code"]] = dict(kind=kind, row=r, items={})
        files = sorted(glob.glob(os.path.join(scores_dir, "*.json")))
        for fp in files:
            d = json.load(open(fp, encoding="utf-8"))
            code = d.get("code")
            if code not in mine:
                die("%s: sheet code %r is not in %s" % (fp, code, map_path))
            sh = mine[code]
            order = sh["row"]["order"].split()
            for item, v in d.get("items", {}).items():
                if item not in order:
                    die("%s: %s is not on sheet %s" % (fp, item, code))
                sc = {}
                for key, val in v["scores"].items():
                    m = re.match(r"^F(\d+)$", key)
                    if not m or type(val) is not int or val not in (0, 1):
                        die("%s: %s has the score %r for %r" % (fp, item, val, key))
                    sc[int(m.group(1))] = val
                if set(sc) != self.expected_ks(kind, item):
                    die("%s: %s is scored on the facts %s, the sheet type needs %s" % (fp, item, sorted(sc), sorted(self.expected_ks(kind, item))))
                if type(v["false"]) is not int or v["false"] < 0:
                    die("%s: %s has the false count %r" % (fp, item, v["false"]))
                if item in sh["items"]:
                    continue      # the first usable scoring is kept (ANALYSIS_PLAN.md rule 4)
                sh["items"][item] = dict(scores=sc, false=v["false"], file=os.path.basename(fp))
        self.sheets.update(mine)

    def require_complete(self):
        bad = [c for c, sh in self.sheets.items() if len(sh["items"]) != len(sh["row"]["order"].split())]
        if bad:
            die("first-judge sheets not fully scored: %s" % " ".join(sorted(bad)))

    def explanation(self, code, item):
        """The explanation text and correction notes of the item on the first judge's sheet `code`, checked against the hash of the reply file used for that sheet."""
        sh = self.sheets[code]
        r = sh["row"]
        rid = r["recv"]
        if rid not in self._expl_cache:
            if not self.results:
                die("--results is needed to read the explanations")
            p = os.path.join(self.results, "parsed", rid + ".json")
            if not os.path.exists(p):
                die("no parsed reply %s for sheet %s" % (p, code))
            parsed = json.load(open(p, encoding="utf-8"))
            if parsed.get("sha256", "")[:16] != r["raw_sha16"]:
                die("%s: the parsed reply was made from another file than the one the sheet %s was built from" % (rid, code))
            notes = {k: [v] for k, v in self.corr.get(rid, {}).get("items", {}).items()}
            self._expl_cache[rid] = (parsed["items"], notes)
        items, notes = self._expl_cache[rid]
        if item not in items:
            die("%s has no item %s" % (rid, item))
        return items[item], notes.get(item, [])

    def pool_items(self):
        """Every (kind, code, item) with a usable first-judge scoring, in a fixed order."""
        out = []
        for code in sorted(self.sheets):
            sh = self.sheets[code]
            for item in sorted(sh["items"]):
                out.append((sh["kind"], code, item))
        out.sort()
        return out


def new_codes(rng, n, taken):
    out = []
    while len(out) < n:
        c = "".join(rng.choice(bj.ALPHABET) for _ in range(4))
        if c not in taken:
            taken.add(c)
            out.append(c)
    return out


def hash_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def make_ctx(a, need_results=True):
    return Ctx(getattr(a, "results", None), a.kit, a.reading_map, a.reading_scores, a.rt_map, a.rt_scores, need_results)


def empty_out(path):
    if os.path.exists(path) and os.listdir(path):
        die("%s exists and is not empty; the draw is made once" % path)
    os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------------------------- second judge
def cmd_second_draw(a):
    ctx = make_ctx(a)
    ctx.require_complete()
    pool = ctx.pool_items()
    N = len(pool)
    if N == 0:
        die("nothing is judged yet")
    frac = Fraction(str(a.fraction))
    if not (0 < frac <= 1):
        die("--fraction must be above 0 and at most 1")
    k = int(frac * N + Fraction(1, 2))
    if k < 1:
        die("the share gives no explanation")
    empty_out(a.out)
    rng = random.Random(a.seed)
    sample = sorted(rng.sample(pool, k))
    taken = set(ctx.sheets)
    sheets = []   # dict(kind, items[(item, source_code)])
    for kind in ("reading", "rt"):
        lst = [(c, it) for kd, c, it in sample if kd == kind]
        if not lst:
            continue
        by_item = {}
        for c, it in sorted(lst, key=lambda x: (x[1], x[0])):
            by_item.setdefault(it, []).append(c)
        nb = max(len(v) for v in by_item.values())
        buckets = [[] for _ in range(nb)]
        for it in sorted(by_item):
            cs = by_item[it][:]
            rng.shuffle(cs)
            for j, c in enumerate(cs):
                buckets[j].append((it, c))       # one scenario item at most once per bucket, so never twice on one sheet
        for b in buckets:
            rng.shuffle(b)
            nch = math.ceil(len(b) / MAX_ITEMS_PER_SHEET)
            size = math.ceil(len(b) / nch)
            for i in range(0, len(b), size):
                sheets.append(dict(kind=kind, items=b[i:i + size]))
    rng.shuffle(sheets)
    codes = new_codes(rng, len(sheets), taken)
    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    rows = []
    for code, sh in zip(codes, sheets):
        kind = sh["kind"]
        order = [it for it, _ in sh["items"]]
        assert len(order) == len(set(order)) <= MAX_ITEMS_PER_SHEET
        expl, notes = {}, {}
        for it, src in sh["items"]:
            text, nts = ctx.explanation(src, it)
            expl[it] = text
            if nts:
                notes[it] = nts
        txt = bj.sheet_text(ctx.prompts[kind], code, order, ctx.facts_all if kind == "reading" else ctx.facts_c, expl, notes)
        with open(os.path.join(a.out, "sheets", "sheet_%s.txt" % code), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        rows.append(dict(code=code, kind=kind, n_items=len(order), order=" ".join(order),
                         sources=json.dumps({it: src for it, src in sh["items"]}, sort_keys=True), sheet_sha16=sha16(txt.encode("utf-8"))))
    with open(os.path.join(a.out, "second_map_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    info = dict(command="second-draw", seed=a.seed, fraction=str(frac), pool_items=N, drawn_items=k, n_sheets=len(rows),
                drawn_by_kind={kd: sum(1 for x in sample if x[0] == kd) for kd in ("reading", "rt")},
                reading_map_sha256=hash_file(a.reading_map), rt_map_sha256=hash_file(a.rt_map) if a.rt_map else None,
                judge_prompts_sha256={kd: hashlib.sha256(ctx.prompts[kd].encode("utf-8")).hexdigest() for kd in ctx.prompts},
                facts_csv_sha256=hash_file(os.path.join(a.kit, "facts.csv")), script_sha16=sha16(open(__file__, "rb").read()))
    json.dump(info, open(os.path.join(a.out, "draw_info_PRIVATE.json"), "w"), indent=2)
    print("second-judge draw: %d of %d explanations (seed %d), %d sheets (%s) in %s" % (
        k, N, a.seed, len(rows), ", ".join("%s %d" % (kd, sum(1 for r in rows if r["kind"] == kd)) for kd in ("reading", "rt")), a.out))


def kappa(pairs):
    """Cohen's kappa for 0/1 scores of two judges (extra; None when undefined)."""
    n = len(pairs)
    if n == 0:
        return None
    a_yes = sum(x for x, _ in pairs)
    b_yes = sum(y for _, y in pairs)
    po = sum(1 for x, y in pairs if x == y) / n
    pe = (a_yes / n) * (b_yes / n) + (1 - a_yes / n) * (1 - b_yes / n)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def load_second(a, ctx):
    mp = os.path.join(a.draw, "second_map_PRIVATE.csv")
    rows = read_csv(mp)
    draw = {}
    for r in rows:
        draw[r["code"]] = dict(row=r, kind=r["kind"], sources=json.loads(r["sources"]), items={})
        if sorted(draw[r["code"]]["sources"]) != sorted(r["order"].split()):
            die("second map: the sources of sheet %s do not match its items" % r["code"])
    for fp in sorted(glob.glob(os.path.join(a.second_scores, "*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        code = d.get("code")
        if code not in draw:
            die("%s: sheet code %r is not in the second map" % (fp, code))
        sh = draw[code]
        for item, v in d.get("items", {}).items():
            if item not in sh["sources"]:
                die("%s: %s is not on second sheet %s" % (fp, item, code))
            sc = {}
            for key, val in v["scores"].items():
                m = re.match(r"^F(\d+)$", key)
                if not m or type(val) is not int or val not in (0, 1):
                    die("%s: %s has the score %r for %r" % (fp, item, val, key))
                sc[int(m.group(1))] = val
            if set(sc) != ctx.expected_ks(sh["kind"], item):
                die("%s: %s is scored on the facts %s, the sheet type needs %s" % (fp, item, sorted(sc), sorted(ctx.expected_ks(sh["kind"], item))))
            if item in sh["items"]:
                continue
            sh["items"][item] = dict(scores=sc, false=v["false"])
    return draw


def cmd_second_compare(a):
    ctx = make_ctx(a, need_results=False)
    ctx.require_complete()
    draw = load_second(a, ctx)
    missing = [(c, it) for c, sh in sorted(draw.items()) for it in sh["row"]["order"].split() if it not in sh["items"]]
    if missing and not a.partial:
        die("second-judge scores missing for %d items (first: %s); --partial only for a look that is not a result" % (len(missing), missing[0]))
    n = d = 0
    n_by, d_by, pairs, lost, gained = {}, {}, [], 0, 0
    fl_items, fl_diff, fl_abs = 0, 0, 0
    diffs = []
    for c2, sh in sorted(draw.items()):
        for it, src in sorted(sh["sources"].items()):
            if it not in sh["items"]:
                continue
            f1 = ctx.sheets[src]["items"][it]
            f2 = sh["items"][it]
            arm = ctx.sheets[src]["row"]["arm"]
            fl_items += 1
            if f1["false"] != f2["false"]:
                fl_diff += 1
            fl_abs += abs(f1["false"] - f2["false"])
            for k in sorted(f1["scores"]):
                s1, s2 = f1["scores"][k], f2["scores"][k]
                n += 1
                n_by[("kind", sh["kind"])] = n_by.get(("kind", sh["kind"]), 0) + 1
                n_by[("arm", arm)] = n_by.get(("arm", arm), 0) + 1
                pairs.append((s1, s2))
                if s1 != s2:
                    d += 1
                    d_by[("kind", sh["kind"])] = d_by.get(("kind", sh["kind"]), 0) + 1
                    d_by[("arm", arm)] = d_by.get(("arm", arm), 0) + 1
                    if s1 == 1:
                        lost += 1
                    else:
                        gained += 1
                    diffs.append((arm, src, it, k, s1, s2))
    share = d / n if n else None
    res = dict(second_map=os.path.join(a.draw, "second_map_PRIVATE.csv"), items_compared=fl_items, facts_compared=n, facts_differing=d,
               share_differing=share, above_ten_percent=above_ten_percent(d, n), rule=THRESHOLD_NOTE,
               first_credits_second_not=lost, second_credits_first_not=gained, kappa=kappa(pairs),
               items_with_other_false_count=fl_diff, mean_abs_false_difference=(fl_abs / fl_items if fl_items else None),
               by_kind={k[1]: dict(compared=n_by[k], differing=d_by.get(k, 0), above_ten_percent=above_ten_percent(d_by.get(k, 0), n_by[k])) for k in sorted(n_by) if k[0] == "kind"},
               by_arm={k[1]: dict(compared=n_by[k], differing=d_by.get(k, 0)) for k in sorted(n_by) if k[0] == "arm"},
               missing_items=len(missing), partial=bool(missing))
    lines = ["# Second judge against the first judge (ANALYSIS_PLAN.md rules 16 and 17)", ""]
    if missing:
        lines += ["**PARTIAL: %d sampled items have no second-judge score yet. This is not a result.**" % len(missing), ""]
    lines += ["Explanations compared: %d; facts compared: %d; facts where the two scores differ: %d (%.1f percent)." % (fl_items, n, d, 100 * share if share is not None else float("nan")),
              "Rule: %s. Result: **%s**." % (THRESHOLD_NOTE, "above 10 percent: the second model re-judges everything and both sets are reported (rule 17)" if res["above_ten_percent"] else "not above 10 percent"),
              "Direction: first judge credits and second does not: %d; second credits and first does not: %d. Cohen's kappa (extra): %s." % (lost, gained, "n/a" if res["kappa"] is None else "%.3f" % res["kappa"]),
              "False counts: %d of %d explanations have a different false count; mean absolute difference %s." % (fl_diff, fl_items, "n/a" if res["mean_abs_false_difference"] is None else "%.3f" % res["mean_abs_false_difference"]),
              "", "| part | facts compared | differing | share | above 10 percent |", "|---|---|---|---|---|"]
    for kd, v in res["by_kind"].items():
        lines.append("| %s | %d | %d | %.1f%% | %s |" % ({"reading": "reading arms", "rt": "round trip"}.get(kd, kd), v["compared"], v["differing"], 100 * v["differing"] / v["compared"], "yes" if v["above_ten_percent"] else "no"))
    for arm, v in res["by_arm"].items():
        lines.append("| arm %s | %d | %d | %.1f%% | |" % (arm, v["compared"], v["differing"], 100 * v["differing"] / v["compared"]))
    lines += ["", "Differing facts (arm, first-judge sheet, item, fact, first score, second score):"]
    for arm, src, it, k, s1, s2 in diffs:
        lines.append("- %s %s %s F%d: %d -> %d" % (arm, src, it, k, s1, s2))
    text = "\n".join(lines) + "\n"
    if a.report:
        open(a.report, "w", encoding="utf-8").write(text)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    print(text)


# ---------------------------------------------------------------------------------------------- audit by the user
def scoring_rule(prompt):
    m = re.search(r"(Score each fact 1 or 0.*?Extra true detail is not penalised\.)", prompt, re.S)
    if not m:
        die("the scoring rule was not found in the judge prompt")
    return m.group(1)


def cmd_audit_draw(a):
    ctx = make_ctx(a)
    ctx.require_complete()
    pool = []
    for kind, code, item in ctx.pool_items():
        for k in sorted(ctx.sheets[code]["items"][item]["scores"]):
            pool.append((kind, code, item, k))
    pool.sort()
    if len(pool) < a.n:
        die("only %d judged facts, cannot draw %d" % (len(pool), a.n))
    empty_out(a.out)
    rng = random.Random(a.seed)
    sample = rng.sample(pool, a.n)           # the order of the draw is the order of the entries
    rule = scoring_rule(ctx.prompts["reading"])
    out = ["AUDIT OF THE JUDGE (%d entries)" % a.n, "",
           "Each entry has one fact and one explanation that a reader wrote about some messages. For each entry decide whether the fact is credited (1) or not (0), by this rule (the rule the judge was given):",
           "", rule, "", "Facts marked (S) are status facts; score them like the others.", "",
           "Reply with one line per entry: the entry number, a colon, then 1 or 0 (for example \"7: 1\"), and nothing else.", "", "=" * 60, ""]
    key = []
    for n, (kind, code, item, k) in enumerate(sample, 1):
        fact = next(f for kk, typ, f in ((x[0], x[1], x[2]) for x in ctx.facts(kind, item)) if kk == k)
        typ = next(x[1] for x in ctx.facts(kind, item) if x[0] == k)
        text, notes = ctx.explanation(code, item)
        out += ["Entry %d" % n, "Fact: " + ("(S) " if typ == "S" else "") + fact, "Explanation:", text.strip("\n")]
        for nt in notes:
            out.append("[Correction later in the same reply: %s]" % nt)
        out += ["", "-" * 60, ""]
        key.append(dict(entry=n, kind=kind, arm=ctx.sheets[code]["row"]["arm"], code=code, item=item, fact="F%d" % k, fact_type=typ,
                        judge_score=ctx.sheets[code]["items"][item]["scores"][k]))
    sheet = "\n".join(out)
    open(os.path.join(a.out, "audit_sheet.txt"), "w", encoding="utf-8", newline="\n").write(sheet)
    with open(os.path.join(a.out, "audit_key_PRIVATE.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    info = dict(command="audit-draw", seed=a.seed, entries=a.n, judged_facts_in_pool=len(pool), audit_sheet_sha256=hashlib.sha256(sheet.encode("utf-8")).hexdigest(),
                reading_map_sha256=hash_file(a.reading_map), rt_map_sha256=hash_file(a.rt_map) if a.rt_map else None,
                facts_csv_sha256=hash_file(os.path.join(a.kit, "facts.csv")), script_sha16=sha16(open(__file__, "rb").read()))
    json.dump(info, open(os.path.join(a.out, "audit_info_PRIVATE.json"), "w"), indent=2)
    print("audit draw: %d of %d judged facts (seed %d); sheet for the user: %s" % (a.n, len(pool), a.seed, os.path.join(a.out, "audit_sheet.txt")))


ANSWER = re.compile(r"^\s*(?:entry\s*)?(\d{1,3})\s*(?:[:.)=\-]|\s)\s*([01])\s*$", re.I)


def cmd_audit_compare(a):
    key = read_csv(a.key)
    want = [int(r["entry"]) for r in key]
    got, problems = {}, []
    for raw in open(a.answers, encoding="utf-8").read().splitlines():
        line = raw.strip().strip("*`>- ").strip()
        if not line:
            continue
        m = ANSWER.match(line)
        if not m:
            problems.append("line not understood: %r" % raw[:60])
            continue
        e, v = int(m.group(1)), int(m.group(2))
        if e in got:
            problems.append("entry %d answered twice" % e)
            continue
        got[e] = v
    for e in want:
        if e not in got:
            problems.append("entry %d has no answer" % e)
    for e in got:
        if e not in want:
            problems.append("entry %d is not on the audit sheet" % e)
    if problems:
        print("The answers cannot be used as they are (nothing is guessed):")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    n = len(key)
    diffs = [(r, got[int(r["entry"])]) for r in key if got[int(r["entry"])] != int(r["judge_score"])]
    d = len(diffs)
    res = dict(entries=n, differing=d, share_differing=d / n, above_ten_percent=above_ten_percent(d, n), rule=THRESHOLD_NOTE,
               judge_credits_user_not=sum(1 for r, v in diffs if int(r["judge_score"]) == 1),
               user_credits_judge_not=sum(1 for r, v in diffs if int(r["judge_score"]) == 0),
               differing_entries=[dict(entry=int(r["entry"]), arm=r["arm"], code=r["code"], item=r["item"], fact=r["fact"], judge=int(r["judge_score"]), user=v) for r, v in diffs])
    lines = ["# Audit by the user against the judge (ANALYSIS_PLAN.md rule 15)", "",
             "Entries: %d; the user's score differs from the judge's on %d (%.1f percent). Rule: %s. Result: **%s**." % (
                 n, d, 100 * d / n, THRESHOLD_NOTE, "above 10 percent: the second model re-judges everything and both sets are reported (rule 17)" if res["above_ten_percent"] else "not above 10 percent"),
             "Direction: the judge credits and the user does not: %d; the user credits and the judge does not: %d." % (res["judge_credits_user_not"], res["user_credits_judge_not"]), ""]
    for r, v in diffs:
        lines.append("- entry %s (%s, sheet %s, %s %s): judge %s, user %d" % (r["entry"], r["arm"], r["code"], r["item"], r["fact"], r["judge_score"], v))
    text = "\n".join(lines) + "\n"
    if a.report:
        open(a.report, "w", encoding="utf-8").write(text)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, results=True):
        if results:
            p.add_argument("--results", required=True)
        p.add_argument("--kit", required=True)
        p.add_argument("--reading-map", required=True)
        p.add_argument("--reading-scores", required=True)
        p.add_argument("--rt-map")
        p.add_argument("--rt-scores")

    p = sub.add_parser("second-draw")
    common(p)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--fraction", default="0.2")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_second_draw)
    p = sub.add_parser("second-compare")
    common(p, results=False)
    p.add_argument("--draw", required=True)
    p.add_argument("--second-scores", required=True)
    p.add_argument("--report")
    p.add_argument("--json")
    p.add_argument("--partial", action="store_true")
    p.set_defaults(fn=cmd_second_compare)
    p = sub.add_parser("audit-draw")
    common(p)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_audit_draw)
    p = sub.add_parser("audit-compare")
    p.add_argument("--key", required=True)
    p.add_argument("--answers", required=True)
    p.add_argument("--report")
    p.add_argument("--json")
    p.set_defaults(fn=cmd_audit_compare)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
