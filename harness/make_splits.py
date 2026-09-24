"""Freeze dev / held-out splits (run once; the lists are committed).

dev = 1,200 files stratified by pollution family, seed 20260922.
  * row-level families (1,428 + 756 + 84 files): proportional allocation, drawn at random
    within the family, sorted by (row, col) first so the draw is reproducible;
  * the 20 file-level singletons (incl. source.csv): each is its own pollution type, so they
    cannot be split within type. They are split at random *within* their coarse group
    (T table-level / S structural) in the same 1200/2290 proportion, so the held-out split
    contains file-level pollution types dev has never seen - a real generalisation test.
held-out = everything else. Report-only.

    python harness/make_splits.py           # write harness/splits/{dev,heldout}.txt
    python harness/make_splits.py --check   # verify the committed lists match the seed
"""
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SPLITS, all_files, family, group, row_col  # noqa: E402

SEED = 20260922
N_DEV = 1200


def main():
    files = all_files()
    rng = random.Random(SEED)
    frac = N_DEV / len(files)
    strata = defaultdict(list)
    for f in files:
        fam = family(f)
        key = fam if fam.startswith("row_") else "single_" + group(f)
        strata[key].append(f)
    quotas = {k: round(len(v) * frac) for k, v in strata.items()}
    # fix rounding so the total is exactly N_DEV (adjust the largest stratum)
    diff = N_DEV - sum(quotas.values())
    big = max(strata, key=lambda k: len(strata[k]))
    quotas[big] += diff
    dev = []
    for k in sorted(strata):
        members = sorted(strata[k], key=lambda f: (row_col(f)[0] or 0, row_col(f)[1] or 0, f))
        dev += rng.sample(members, quotas[k])
    dev = sorted(dev)
    held = sorted(set(files) - set(dev))
    if "--check" in sys.argv[1:]:
        ok = True
        for name, lst in (("dev", dev), ("heldout", held)):
            with open(os.path.join(SPLITS, f"{name}.txt")) as fh:
                committed = [l.strip() for l in fh if l.strip()]
            same = committed == lst
            ok &= same
            print(f"{name}: {len(committed)} files, {'matches' if same else 'DIFFERS FROM'} seed {SEED}")
        sys.exit(0 if ok else 1)
    os.makedirs(SPLITS, exist_ok=True)
    for name, lst in (("dev", dev), ("heldout", held)):
        with open(os.path.join(SPLITS, f"{name}.txt"), "w") as fh:
            fh.write("\n".join(lst) + "\n")
    for k in sorted(strata):
        print(f"{k:24s} total {len(strata[k]):4d} dev {quotas[k]:4d}")
    print("dev", len(dev), "heldout", len(held))
    print("dev singletons:", [f for f in dev if not f.startswith("row_")])
    print("heldout singletons:", [f for f in held if not f.startswith("row_")])


if __name__ == "__main__":
    main()
