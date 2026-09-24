"""Files with the largest loss for a scored variant, with the loaded-vs-expected diff.

    harness/worst.py --variant c0-csvsniff --split dev [--n 15] [--family row_less_sep]
                     [--by weighted] [--files a.csv,b.csv] [--no-diff]

Reads runs/<variant>.<split>.files.tsv (written by run.py). Diff = what the official scorer
compares: header row (normalised cells), records (rows 1.., normalised cells joined) and the
raw cell multiset. Expected = upstream/polluted_files/clean/<f>; loaded =
runs/<variant>/loading/<f>_converted.csv. Analysis only - never import this from a loader.
"""
import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, RUNS, UPSTREAM, drop_unpacked, ensure_outputs, outputs_dir  # noqa: E402

sys.path.insert(0, UPSTREAM)
from pollock.data_types import normalize_cell as _normalize_cell  # noqa: E402
import functools  # noqa: E402

normalize_cell = functools.lru_cache(maxsize=1 << 18)(_normalize_cell)  # analysis-side memo


def read_rows(p):
    try:
        with open(p, encoding="utf-8-sig", newline="") as fh:
            return list(csv.reader(fh))
    except UnicodeDecodeError:
        with open(p, encoding="latin-1", newline="") as fh:
            return list(csv.reader(fh))


def short(x, n=60):
    x = repr(x)
    return x if len(x) <= n else x[: n - 3] + "..."


def diff(f, variant, maxrows=4):
    exp = read_rows(os.path.join(DATA, "clean", f))
    got = read_rows(os.path.join(outputs_dir(variant), f + "_converted.csv"))
    shape = lambda rows: f"{len(rows)} rows, widths {dict(Counter(len(r) for r in rows).most_common(4))}"
    print(f"    expected: {shape(exp)}")
    print(f"    loaded:   {shape(got)}")
    if got and got[0][:1] == ["Application Error"]:
        print("    APPLICATION ERROR:", " ".join(sum(got[1:2], []))[:200])
        return
    if exp and (not got or [normalize_cell(c) for c in exp[0]] != [normalize_cell(c) for c in got[0]]):
        print(f"    header exp: {[short(c, 24) for c in exp[0]]}")
        print(f"    header got: {[short(c, 24) for c in got[0]] if got else None}")
    nrec = lambda rows: ["".join(normalize_cell(c) for c in r) for r in rows[1:]]
    ce, cg = Counter(nrec(exp)), Counter(nrec(got))
    miss = ce - cg
    extra = cg - ce
    if miss or extra:
        print(f"    records: {sum(miss.values())} expected-not-loaded, {sum(extra.values())} loaded-not-expected")
        idx_e = {k: i for i, k in enumerate(nrec(exp), 1)}
        idx_g = {k: i for i, k in enumerate(nrec(got), 1)}
        for k in list(miss)[:maxrows]:
            i = idx_e[k]
            print(f"      - exp row {i}: {[short(c, 22) for c in exp[i]]}")
        for k in list(extra)[:maxrows]:
            i = idx_g[k]
            print(f"      + got row {i}: {[short(c, 22) for c in got[i]]}")
    cme, cmg = Counter(c for r in exp for c in r), Counter(c for r in got for c in r)
    cm, cx = cme - cmg, cmg - cme
    if cm or cx:
        print(f"    cells: {sum(cm.values())} missing, {sum(cx.values())} extra;"
              f" missing e.g. {[short(c, 30) for c in list(cm)[:4]]}; extra e.g. {[short(c, 30) for c in list(cx)[:4]]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--family")
    ap.add_argument("--by", default="simple", choices=["simple", "weighted"])
    ap.add_argument("--files")
    ap.add_argument("--no-diff", action="store_true")
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
    for r in rows:
        r["loss"] = 10 - float(r["score10"])
        r["wloss"] = r["loss"] * float(r["nweight"])
    if a.files:
        want = set(a.files.split(","))
        rows = [r for r in rows if r["file"] in want]
    if a.family:
        rows = [r for r in rows if r["family"] == a.family]
    key = "loss" if a.by == "simple" else "wloss"
    rows = sorted(rows, key=lambda r: -r[key])[: a.n]
    for r in rows:
        if r["loss"] <= 0 and not a.files:
            break
        ms = " ".join(f"{k[:1]}{k.split('_')[-1][:1]}={float(r[k]):.3f}" for k in
                      ("header_f1", "record_f1", "cell_f1"))
        print(f"{r['file']}  [{r['family']}]  score10 {float(r['score10']):.4f}  "
              f"simple_loss {r['loss'] / n:.5f}  weighted_loss {r['wloss']:.5f}  succ={r['success'][:1]} {ms}")
        if not a.no_diff:
            diff(r["file"], a.variant)


if __name__ == "__main__":
    main()
