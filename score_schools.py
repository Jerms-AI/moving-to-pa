#!/usr/bin/env python3
"""Re-score schools from current PA assessment data (2024 PSSA + Keystone).

Replaces the stale 2018 EDFacts-derived scores. For each PA school we take the
"All Students" Percent Proficient and above across PSSA (grades 3-8, ELA/Math/
Science) and Keystone (grade 11, Algebra/Literature/Biology), average it, and
rank statewide into 1-10 deciles — the same methodology as before, newer data.

PA files key schools by AUN+School Number; our schools.json uses NCES IDs, so we
join on normalized (district, school name). Unmatched schools keep their old
score (and are reported). District elementary/middle/high band scores in
districts_scores.json are recomputed as the mean of member schools' new scores.

Source files live in .assessment_src/ (gitignored). Run with --write to apply.
Usage: python3 score_schools.py [--write]
"""
import openpyxl, json, re, sys, statistics
from collections import defaultdict
from parse_emails import HERE

SRC = f"{HERE}/.assessment_src"
COL = "Percent Proficient and above"
STOP = {"school", "el", "es", "ms", "hs", "sch", "the", "of", "at", "ms.", "jhs", "shs", "ehs",
        # grade-level descriptors — identity lives in the proper name, not these
        "senior", "junior", "sr", "jr", "high", "middle", "elementary", "elem",
        "intermediate", "primary", "vocational", "technical", "votech", "learning", "center", "ctr"}


def load_prof(fn, header_row, grade_keep, grades=None):
    """Proficiency per school from the Grade=='Total' rows. If `grades` (a dict)
    is passed, also record each school's tested numeric grades — used to flag K-8
    (combined) schools that test both elementary (<=5) and middle (>=6) grades."""
    wb = openpyxl.load_workbook(fn, read_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    idx = {h: i for i, h in enumerate(rows[header_row]) if h}
    out = defaultdict(list)
    for r in rows[header_row + 1:]:
        if not r or r[idx["Group"]] != "All Students":
            continue
        key = (r[idx["District Name"]], r[idx["School Name"]])
        g = str(r[idx["Grade"]])
        if grades is not None and g.isdigit():
            grades[key].add(int(g))
        if g != grade_keep:
            continue
        try:
            pa = float(r[idx[COL]])
        except (TypeError, ValueError):
            continue
        out[key].append(pa)
    return out


def ndist(s):
    s = re.sub(r"\bSCHOOL DISTRICT\b|\bSD\b|\bCS\b|\bCHARTER\b", "", (s or "").upper())
    return re.sub(r"[^A-Z0-9]", "", s)


def ntokens(s):
    return frozenset(t for t in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if t not in STOP)


def main():
    write = "--write" in sys.argv
    # PA proficiency by school, merged across both assessments; grade spans from PSSA
    grade_span = defaultdict(set)
    merged = defaultdict(list)
    for d in (load_prof(f"{SRC}/pssa-2024.xlsx", 4, "Total", grade_span),
              load_prof(f"{SRC}/keystone-2024.xlsx", 3, "11")):
        for k, v in d.items():
            merged[k].extend(v)
    prof = {k: sum(v) / len(v) for k, v in merged.items()}
    vals = sorted(prof.values())

    def decile(p):
        return min(10, int(sum(1 for x in vals if x < p) / len(vals) * 10) + 1)

    def is_k8(key):  # a K-8 school spans the full PSSA range — tests grade 3 AND grade 8
        g = grade_span.get(key, set())
        return 3 in g and 8 in g

    # index PA schools by (normalized district -> [(token-set, score, k8, name)])
    pa_by_dist = defaultdict(list)
    for (dist, name), p in prof.items():
        pa_by_dist[ndist(dist)].append((ntokens(name), decile(p), is_k8((dist, name)), name))

    schools = json.load(open(f"{HERE}/schools.json"))
    matched = unmatched = changed = 0
    misses = []
    for s in schools:
        cands = pa_by_dist.get(ndist(s["district"]), [])
        toks = ntokens(s["name"])
        best, best_j = None, 0.0
        for ptoks, sc, k8, pname in cands:
            if not toks or not ptoks:
                continue
            j = len(toks & ptoks) / len(toks | ptoks)
            if j > best_j:
                best, best_j = (sc, k8), j
        if best and best_j >= 0.5:
            old = s.get("score")
            s["score"] = best[0]
            s["k8"] = best[1]
            matched += 1
            if old != best[0]:
                changed += 1
        else:
            s["k8"] = False
            unmatched += 1
            misses.append(f'{s["name"]} / {s["district"]}')

    # recompute district band scores from new school scores
    districts = json.load(open(f"{HERE}/districts_scores.json"))
    name2geoid = {v["name"]: g for g, v in districts.items()}
    band = defaultdict(lambda: defaultdict(list))
    for s in schools:
        if s["score"] is None or s["level"] not in ("elementary", "middle", "high"):
            continue
        g = name2geoid.get(s["district"])
        if g:
            band[g][s["level"]].append(s["score"])
    for g, lv in band.items():
        for level, scs in lv.items():
            if not isinstance(districts[g].get(level), dict):
                districts[g][level] = {}
            districts[g][level]["score"] = round(sum(scs) / len(scs))
            districts[g][level]["rank"] = f"avg of {len(scs)} schools (2024 PSSA/Keystone)"

    print(f"PA schools scored: {len(prof)}  (state median prof {statistics.median(vals):.1f}%)")
    print(f"matched {matched}/{len(schools)} of our schools ({changed} score changes); {unmatched} unmatched")
    if misses:
        print("UNMATCHED (kept old score):")
        for m in misses[:40]:
            print("   -", m)
        if len(misses) > 40:
            print(f"   ... +{len(misses)-40} more")
    if write:
        json.dump(schools, open(f"{HERE}/schools.json", "w"), indent=2)
        json.dump(districts, open(f"{HERE}/districts_scores.json", "w"), indent=2)
        print("WROTE schools.json + districts_scores.json")
    else:
        print("(report only — pass --write to apply)")


if __name__ == "__main__":
    main()
