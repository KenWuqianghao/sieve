"""Per-split scores of the PUBLISHED systems, from upstream/results/global_results_polluted_files.csv
(the per-file measures the authors committed; duckdbparse = "DuckDB 1.2" in the README).

Same formulas as evaluate.main(): simple = sum over the 10 measures of their mean over files;
weighted = sum_f (sum of f's 10 measures) * w_f / sum(w) with w from pollock_weights.json,
normalised over the files in the split.

    harness/published.py [--split all|dev|heldout] [--sut duckdbparse] [--families]
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MEASURES, UPSTREAM, family, group, split_files  # noqa: E402

GLOBAL = os.path.join(UPSTREAM, "results", "global_results_polluted_files.csv")


def load_published():
    with open(GLOBAL) as fh:
        rows = list(csv.DictReader(fh))
    suts = sorted({c[: -len("_success")] for c in rows[0] if c.endswith("_success")})
    per = {s: {} for s in suts}
    for r in rows:
        for s in suts:
            per[s][r["file"]] = [float(r[f"{s}_{m}"] or 0) for m in MEASURES]
    return per


def scores(per_sut, files, weights):
    n = len(files)
    simple = sum(sum(per_sut[f]) for f in files) / n
    wsum = sum(weights[f] for f in files)
    weighted = sum(sum(per_sut[f]) * weights[f] / wsum for f in files)
    return simple, weighted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--sut")
    ap.add_argument("--families", action="store_true")
    a = ap.parse_args()
    weights = json.load(open(os.path.join(UPSTREAM, "pollock_weights.json")))
    files = split_files(a.split)
    per = load_published()
    suts = [a.sut] if a.sut else sorted(per, key=lambda s: -scores(per[s], files, weights)[0])
    print(f"published per-file results, split={a.split} ({len(files)} files)")
    for s in suts:
        sm, wt = scores(per[s], files, weights)
        print(f"  {s:14s} simple {sm:.4f}  weighted {wt:.4f}")
        if a.families:
            wsum = sum(weights[f] for f in files)
            fam = defaultdict(list)
            for f in files:
                fam[family(f)].append(f)
            for k, fs in sorted(fam.items(), key=lambda kv: -sum(10 - sum(per[s][f]) for f in kv[1])):
                sl = sum(10 - sum(per[s][f]) for f in fs) / len(files)
                wl = sum((10 - sum(per[s][f])) * weights[f] / wsum for f in fs)
                if sl > 0 or wl > 0:
                    print(f"      {k:32s} n={len(fs):4d} simple_loss {sl:.4f} weighted_loss {wl:.4f}")


if __name__ == "__main__":
    main()
