"""Throughput + output-identity check for a loader on the Pollock corpus (experiment H7).

    python harness/speed.py --loader sieve --compare results/sieve-outputs.sha256.tsv
    python harness/speed.py --loader sieve --save runs/ref.sha.tsv          # a new reference
    python harness/speed.py --loaders c0-csvsniff,sieve --repeat 2          # files/s

For every file: load(bytes) is timed (reading excluded, like run.py), the rows are serialised
exactly as run.py writes them (csv.writer, utf-8, QUOTE_MINIMAL) and hashed (sha256).
--compare exits 1 unless every file's serialised output is byte-identical to the reference.
--repeat N runs the corpus N times and reports the best (least-noisy) pass; files/s is noisy
on a shared machine, so compare variants in the same call (--loaders a,b) where possible:
passes are interleaved a, b, a, b, ...
results/sieve-outputs.sha256.tsv holds the hashes of sieve's outputs on all 2,290 files (the
outputs scored in README.md).
"""
import argparse
import csv
import hashlib
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, load_loader, split_files  # noqa: E402


def one_pass(mod, blobs):
    total, hashes = 0.0, {}
    for f, data in blobs:
        t0 = time.perf_counter()
        try:
            rows = mod.load(data)
            err = None
        except Exception as e:  # noqa: BLE001
            rows, err = None, f"{type(e).__name__}: {e}"
        total += time.perf_counter() - t0
        buf = io.StringIO(newline="")
        if err is not None:
            buf.write("Application Error\n" + err)
        else:
            csv.writer(buf).writerows(rows)
        hashes[f] = hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest()
    return len(blobs) / total, total, hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loaders", "--loader", default="sieve")
    ap.add_argument("--split", default="all")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--save")
    ap.add_argument("--compare")
    a = ap.parse_args()
    files = split_files(a.split)
    blobs = []
    for f in files:
        with open(os.path.join(DATA, "csv", f), "rb") as fh:
            blobs.append((f, fh.read()))
    names = a.loaders.split(",")
    mods = {n: load_loader(n, "speed") for n in names}
    best, hashes = {n: None for n in names}, {}
    for rep in range(a.repeat):
        for n in names:
            fps, tot, hs = one_pass(mods[n], blobs)
            print(f"  pass {rep + 1} {n:20s} {fps:7.1f} files/s  ({tot:.1f} s load time)", flush=True)
            best[n] = fps if best[n] is None else max(best[n], fps)
            if n in hashes and hashes[n] != hs:
                print(f"  WARNING: {n} is not deterministic across passes")
            hashes[n] = hs
    for n in names:
        print(f"{n:20s} best {best[n]:7.1f} files/s over {a.repeat} pass(es), {len(files)} files")
    rc = 0
    if a.save:
        with open(a.save, "w") as fh:
            for f in files:
                fh.write(f"{f}\t{hashes[names[0]][f]}\n")
        print(f"saved {len(files)} hashes of {names[0]} to {a.save}")
    if a.compare:
        ref = dict(l.rstrip("\n").split("\t") for l in open(a.compare))
        for n in names:
            diff = [f for f in files if ref.get(f) != hashes[n][f]]
            print(f"{n}: {len(files) - len(diff)}/{len(files)} outputs byte-identical to {a.compare}"
                  + (f"; differ e.g. {diff[:5]}" if diff else ""))
            rc |= bool(diff)
    sys.exit(rc)


if __name__ == "__main__":
    main()
