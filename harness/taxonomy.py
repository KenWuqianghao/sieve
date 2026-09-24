"""Failure taxonomy: for every file where a variant loses points, WHAT went wrong.

    harness/taxonomy.py --variant duckdbparse [--split all] [--examples 2]

Needs runs/<variant>.<split>.files.tsv (run.py) and the outputs in runs/<variant>/loading.
Each losing file gets a symptom signature derived from the loaded-vs-expected comparison:
  ERR            application error
  HDR:<kind>     header row differs (synthetic = col_0/column0 names; data = a data row was
                 promoted/lost; joined = multi-row header not joined; other)
  ROWS<+/-k>     loaded row count minus expected
  WIDE / NARROW  unmatched loaded rows wider / narrower than the expected width
  PADDED         unmatched rows with the expected width but trailing empties (null padding)
  ALTERED        unmatched rows with the expected width (cell content changed: escape/quote/space)
  CELLS          records all match; only the raw cell multiset differs (e.g. an extra '' cell)
and the table is aggregated per (family, signature) with simple / weighted loss.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, RUNS, UPSTREAM, drop_unpacked, ensure_outputs, outputs_dir  # noqa: E402

sys.path.insert(0, UPSTREAM)
from pollock.data_types import normalize_cell as _normalize_cell  # noqa: E402
import functools  # noqa: E402

normalize_cell = functools.lru_cache(maxsize=1 << 18)(_normalize_cell)  # analysis-side memo
from worst import read_rows  # noqa: E402


def signature(f, variant):
    exp = read_rows(os.path.join(DATA, "clean", f))
    got = read_rows(os.path.join(outputs_dir(variant), f + "_converted.csv"))
    if got and got[0][:1] == ["Application Error"]:
        return ["ERR"]
    sig = []
    norm = lambda r: [normalize_cell(c) for c in r]
    if exp and (not got or norm(exp[0]) != norm(got[0])):
        h = got[0] if got else []
        if h and all(re.fullmatch(r"(col|column)_?\d+", c.strip().lower()) for c in h if c.strip()):
            kind = "synthetic"
        elif len(exp) > 1 and h and norm(h) == norm(exp[1]):
            kind = "data-lost"          # expected header missing, first data row on top
        elif len(got) > 1 and norm(got[1]) == norm(exp[0]):
            kind = "extra-row-on-top"   # e.g. preamble / 2nd header row emitted first
        elif any(" " in c for c in exp[0]) and not any(" " in c for c in h):
            kind = "not-joined"
        else:
            kind = "other"
        sig.append("HDR:" + kind)
    d = len(got) - len(exp)
    if d:  # bucketed so signatures aggregate across row positions
        sig.append(f"ROWS{d:+d}" if abs(d) <= 2 else ("ROWS+3..9" if 0 < d < 10 else "ROWS+10+" if d > 0
                   else "ROWS-3..9" if d > -10 else "ROWS-10+(swallowed)"))
    W = Counter(len(r) for r in exp).most_common(1)[0][0] if exp else 0
    rec = lambda rows: ["".join(normalize_cell(c) for c in r) for r in rows[1:]]
    ce = Counter(rec(exp))
    extra = Counter(rec(got)) - ce
    bad_rows = []
    left = dict(extra)
    for r, k in zip(got[1:], rec(got)):
        if left.get(k, 0) > 0:
            left[k] -= 1
            bad_rows.append(r)
    kinds = Counter()
    for r in bad_rows:
        if len(r) > W:
            kinds["WIDE"] += 1
        elif len(r) < W:
            kinds["NARROW"] += 1
        elif r and not r[-1].strip() and sum(not c.strip() for c in r) >= 2:
            kinds["PADDED"] += 1
        else:
            kinds["ALTERED"] += 1
    for k, v in sorted(kinds.items()):
        sig.append(k if v == 1 else f"{k}x{v}" if v <= 2 else f"{k}x3..9" if v < 10 else f"{k}x10+")
    if not sig:
        sig.append("CELLS")
    return sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--split", default="all")
    ap.add_argument("--examples", type=int, default=2)
    ap.add_argument("--min-files", type=int, default=1)
    a = ap.parse_args()
    unpacked = ensure_outputs(a.variant)
    try:
        _main(a)
    finally:
        if unpacked:
            drop_unpacked(a.variant)


def _main(a):
    with open(os.path.join(RUNS, f"{a.variant}.{a.split}.files.tsv")) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    n = len(rows)
    agg = defaultdict(lambda: [0, 0.0, 0.0, []])
    fam_tot = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for r in rows:
        loss = 10 - float(r["score10"])
        fam_tot[r["family"]][0] += 1
        if loss <= 1e-9:
            continue
        sig = " ".join(signature(r["file"], a.variant))
        k = (r["family"], sig)
        agg[k][0] += 1
        agg[k][1] += loss / n
        agg[k][2] += loss * float(r["nweight"])
        agg[k][3].append(r["file"])
        fam_tot[r["family"]][1] += 1
        fam_tot[r["family"]][2] += loss / n
        fam_tot[r["family"]][3] += loss * float(r["nweight"])
    tot_s = sum(v[1] for v in agg.values())
    tot_w = sum(v[2] for v in agg.values())
    print(f"{a.variant} on {a.split}: {sum(v[0] for v in agg.values())} losing files of {n}; "
          f"simple loss {tot_s:.4f}, weighted loss {tot_w:.4f}\n")
    print("family                          losing/n   simple_loss  weighted_loss")
    for fam, (nt, nl, sl, wl) in sorted(fam_tot.items(), key=lambda kv: -(kv[1][2] + kv[1][3])):
        if nl:
            print(f"{fam:30s} {nl:5d}/{nt:<5d}  {sl:.4f}       {wl:.4f}")
    print("\nfamily / symptom signature                                   files  simple_loss  weighted_loss  e.g.")
    for (fam, sig), (c, sl, wl, fs) in sorted(agg.items(), key=lambda kv: -(kv[1][1] + kv[1][2])):
        if c >= a.min_files:
            print(f"{fam[:24]:24s} {sig[:36]:36s} {c:5d}  {sl:.4f}       {wl:.4f}   {', '.join(fs[:a.examples])}")


if __name__ == "__main__":
    main()
