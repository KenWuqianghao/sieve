"""Run the synthetic regression cases (harness/synthetic/cases.py) on loaders.

    python harness/synthetic/check.py --loaders c0-csvsniff,sieve [--ref c0-csvsniff] [-v]

Loaders: `sieve`, `c0-csvsniff` or a path to a loader .py file (see harness/common.py).
guard cases: PASS when load() == the reference loader's load() (default c0-csvsniff, the
no-repair baseline in harness/baseline/). positive cases: PASS when load() == the expected clean table. Exit code 1 if any
guard case fails for the LAST loader listed.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from cases import CASES  # noqa: E402
from common import load_loader  # noqa: E402


def load_module(variant):
    return load_loader(variant, "syn")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loaders", default="sieve")
    ap.add_argument("--ref", default="c0-csvsniff")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    ref = load_module(a.ref)
    names = a.loaders.split(",")
    mods = {n: load_module(n) for n in names}
    print(f"{'case':28s} {'kind':8s} " + " ".join(f"{n:>14s}" for n in names))
    fails = {n: 0 for n in names}
    for name, kind, data, expected in CASES:
        want = ref.load(data) if kind in ("guard", "limit") else expected
        res = []
        for n in names:
            got = mods[n].load(data)
            ok = got == want
            fails[n] += (not ok) and kind == "guard"
            res.append("PASS" if ok else "FAIL")
            if not ok and a.v:
                for i, (x, y) in enumerate(zip(got, want)):
                    if x != y:
                        print(f"   {n} row {i}: got {x}\n   {' ' * len(n)}  want {y}")
                if len(got) != len(want):
                    print(f"   {n}: {len(got)} rows vs {len(want)}")
        print(f"{name:28s} {kind:8s} " + " ".join(f"{r:>14s}" for r in res))
    print("guard failures: " + ", ".join(f"{n}={v}" for n, v in fails.items()))
    sys.exit(1 if fails[names[-1]] else 0)


if __name__ == "__main__":
    main()
