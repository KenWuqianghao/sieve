"""Load + score one variant on one split through the OFFICIAL Pollock scorer.

    python harness/run.py --loader sieve --split all
    python harness/run.py --loader c0-csvsniff --split dev [--record --round 1 --note ..]
    python harness/run.py --loader path/to/loader.py --split dev
    python harness/run.py --sut duckdbparse --split all      (Pollock's own loader script)

--loader X : `sieve` (sieve/loader.py), `c0-csvsniff` (harness/baseline/c0_csvsniff.py) or a
             path to a .py file; it must define `load(data: bytes) -> list[list[str]]`.
             The loader receives ONLY the file's bytes (never its name or path); the first
             returned row is the header (if the loader decided the file has one). The harness
             writes the rows with csv.writer (utf-8, QUOTE_MINIMAL) to
             runs/X/loading/<f>_converted.csv; an exception writes "Application Error" like
             the repo's SUT scripts do. Throughput = files / sum(load() wall time), 1 process.
--sut S    : outputs produced by harness/run_sut.py S (the repo's loader script); runs it if
             the outputs are missing.
Scoring: harness/official_eval.py runs upstream/evaluate.py main() unchanged on a view of the
split. We then read the per-file measures it wrote and report simple / weighted (exactly the
numbers evaluate.py wrote to aggregate_results_polluted_files.csv), plus a breakdown by coarse
group (T S L M Q R) and by pollution family, with each family's share of the loss.
Writes runs/<variant>.<split>.files.tsv and runs/<variant>.<split>.summary.json.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DATA, GROUPS, MEASURES, ROOT, RUNS, UPSTREAM, ensure_outputs,  # noqa: E402
                    family, group, load_loader, outputs_dir, pack_outputs, split_files,
                    variant_name)

PY = sys.executable


def sut_name(variant):
    s = re.sub(r"[^a-z0-9]", "", variant.lower())
    # evaluate.py selects a system's columns with `sut in column` and splits on "_":
    assert s and all(s not in c for c in ("file", "weight", "normalized_weight")), s
    return s


def run_loader(loader, variant, files, reuse):
    mod = load_loader(loader, "run")
    out = outputs_dir(variant)
    os.makedirs(os.path.join(RUNS, variant), exist_ok=True)
    if not reuse and os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    total, n, errors = 0.0, 0, 0
    for f in files:
        dst = os.path.join(out, f + "_converted.csv")
        if reuse and os.path.exists(dst):
            continue
        with open(os.path.join(DATA, "csv", f), "rb") as fh:
            data = fh.read()
        t0 = time.perf_counter()
        try:
            rows = mod.load(data)
            err = None
        except Exception as e:  # noqa: BLE001
            rows, err = None, f"{type(e).__name__}: {e}"
        total += time.perf_counter() - t0
        n += 1
        with open(dst, "w", newline="", encoding="utf-8") as fh:
            if err is not None:
                errors += 1
                fh.write("Application Error\n" + err)
            else:
                csv.writer(fh).writerows(rows)
    return (n / total if total else None), errors


def sut_throughput(sut, files):
    p = os.path.join(RUNS, sut, f"{sut}_time.csv")
    if not os.path.exists(p):
        return None
    tot, n = 0.0, 0
    want = set(files)
    with open(p) as fh:
        for r in csv.DictReader(fh):
            if r["filename"] in want:
                vals = [float(v) for k, v in r.items() if k != "filename" and v]
                tot += sum(vals) / len(vals)
                n += 1
    return n / tot if tot else None


def make_evalroot(variant, split, files, loading_dir):
    s = sut_name(variant)
    root = os.path.join(RUNS, "_eval", f"{variant}.{split}")
    if os.path.isdir(root):
        shutil.rmtree(root)
    for sub in ("csv", "clean"):
        d = os.path.join(root, "polluted_files", sub)
        os.makedirs(d)
        for f in files:
            os.symlink(os.path.join(DATA, sub, f), os.path.join(d, f))
    os.symlink(os.path.join(UPSTREAM, "pollock_weights.json"), os.path.join(root, "pollock_weights.json"))
    rd = os.path.join(root, "results", s, "polluted_files")
    os.makedirs(rd)
    os.symlink(loading_dir, os.path.join(rd, "loading"))
    return root, s


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--loader")
    g.add_argument("--sut")
    ap.add_argument("--split", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--reuse", action="store_true", help="keep existing loader outputs")
    ap.add_argument("--keep", action="store_true", help="leave outputs unpacked (default: tar.xz)")
    ap.add_argument("--record", action="store_true", help="append a row to results.tsv")
    ap.add_argument("--round", default="", help="experiment round, for the results.tsv row")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.split == "heldout":
        print("NOTE: the held-out split is report-only (docs/benchmark-notes.md). Do not tune on it.",
              file=sys.stderr)
    files = split_files(a.split)
    variant = variant_name(a.loader) if a.loader else a.sut
    errors = 0
    ensure_outputs(variant)
    if a.loader:
        fps, errors = run_loader(a.loader, variant, files, a.reuse)
        loading = outputs_dir(variant)
    else:
        loading = os.path.join(RUNS, a.sut, "loading")
        if len(os.listdir(loading) if os.path.isdir(loading) else []) < len(files):
            subprocess.run([PY, os.path.join(ROOT, "harness", "run_sut.py"), a.sut], check=True,
                           stdout=subprocess.DEVNULL)
        fps = sut_throughput(a.sut, files)
    missing = [f for f in files if not os.path.exists(os.path.join(loading, f + "_converted.csv"))]
    assert not missing, f"{len(missing)} outputs missing, e.g. {missing[:3]}"

    root, s = make_evalroot(variant, a.split, files, loading)
    log = os.path.join(RUNS, "logs", f"eval.{variant}.{a.split}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    t0 = time.time()
    with open(log, "w") as lf:
        subprocess.run(["nice", "-n", "10", PY, os.path.join(ROOT, "harness", "official_eval.py"),
                        root, s, str(a.workers)], check=True, stdout=lf, stderr=subprocess.STDOUT)
    eval_s = time.time() - t0

    agg = {}
    with open(os.path.join(root, "results", "aggregate_results_polluted_files.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["sut"] == s:
                agg = r
    simple, weighted = float(agg["pollock_simple"]), float(agg["pollock_weighted"])

    rows = []
    with open(os.path.join(root, "results", "global_results_polluted_files.csv")) as fh:
        for r in csv.DictReader(fh):
            m = [float(r[f"{s}_{k}"]) for k in MEASURES]
            rows.append({"file": r["file"], "family": family(r["file"]), "group": group(r["file"]),
                         "score10": sum(m), "nweight": float(r["normalized_weight"]),
                         **{k: v for k, v in zip(MEASURES, m)}})
    n = len(rows)
    by_g, by_f = defaultdict(list), defaultdict(list)
    for r in rows:
        by_g[r["group"]].append(r)
        by_f[r["family"]].append(r)

    def stats(rs):
        return {"n": len(rs), "mean10": sum(r["score10"] for r in rs) / len(rs),
                "simple_loss": sum(10 - r["score10"] for r in rs) / n,
                "weighted_loss": sum((10 - r["score10"]) * r["nweight"] for r in rs),
                "perfect": sum(r["score10"] >= 10 - 1e-9 for r in rs)}

    gstats = {k: stats(by_g[k]) for k in GROUPS if by_g[k]}
    fstats = {k: stats(v) for k, v in by_f.items()}
    print(f"\n{variant} on {a.split} ({n} files) - official evaluate.py")
    print(f"  simple   {simple:.4f}   (loss {10 - simple:.4f})")
    print(f"  weighted {weighted:.4f}   (loss {10 - weighted:.4f})")
    print(f"  files/s  {fps:.1f}" if fps else "  files/s  n/a", f"  errors {errors}  eval {eval_s:.0f}s")
    print(f"  official subsets (evaluate.py regexes, see docs/benchmark-notes.md for their quirks): " +
          " ".join(f"{k}={float(agg[k + '_cell_f1']):.4f}" for k in ("table", "inconsistent", "structural")
                   if agg.get(k + "_cell_f1") not in (None, "", "nan")))
    print("\n  group  n     mean10   perfect  simple_loss  weighted_loss")
    for k, v in gstats.items():
        print(f"  {k:5s} {v['n']:5d}  {v['mean10']:.4f}  {v['perfect']:6d}   {v['simple_loss']:.4f}       {v['weighted_loss']:.4f}")
    print("\n  family                          n    mean10   simple_loss  weighted_loss")
    for k, v in sorted(fstats.items(), key=lambda kv: -(kv[1]["simple_loss"] + kv[1]["weighted_loss"])):
        if v["simple_loss"] + v["weighted_loss"] > 0:
            print(f"  {k:30s} {v['n']:4d}  {v['mean10']:.4f}   {v['simple_loss']:.4f}       {v['weighted_loss']:.4f}")

    # keep evaluate.py's own output files, drop the symlink farm (thousands of inodes)
    off = os.path.join(RUNS, "official")
    os.makedirs(off, exist_ok=True)
    for kind in ("aggregate", "global"):
        shutil.copy(os.path.join(root, "results", f"{kind}_results_polluted_files.csv"),
                    os.path.join(off, f"{variant}.{a.split}.{kind}.csv"))
    shutil.rmtree(root)

    derived = {}
    if a.split == "all":
        # dev / held-out numbers from the same official per-file measures, aggregated with
        # evaluate.main()'s formulas (weights renormalised within the split). Verified equal
        # to a direct official run on the split (see docs/benchmark-notes.md).
        import json as _json
        wts = _json.load(open(os.path.join(UPSTREAM, "pollock_weights.json")))
        byf = {r["file"]: r for r in rows}
        for sp in ("dev", "heldout"):
            fs = split_files(sp)
            sm = sum(byf[f]["score10"] for f in fs) / len(fs)
            ws = sum(wts[f] for f in fs)
            wt = sum(byf[f]["score10"] * wts[f] / ws for f in fs)
            derived[sp] = {"simple": sm, "weighted": wt}
            print(f"  derived {sp:8s} simple {sm:.4f}  weighted {wt:.4f}")

    base = os.path.join(RUNS, f"{variant}.{a.split}")
    with open(base + ".files.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["score10"]))
    summ = {"variant": variant, "split": a.split, "n": n, "simple": simple, "weighted": weighted,
            "files_per_s": fps, "errors": errors, "groups": gstats, "families": fstats,
            "official_aggregate": agg, "derived_splits": derived}
    with open(base + ".summary.json", "w") as fh:
        json.dump(summ, fh, indent=1)

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tsv = [now, a.round, variant, a.split, f"{simple:.4f}", f"{weighted:.4f}"] + \
          [f"{gstats[k]['mean10']:.4f}" if k in gstats else "" for k in GROUPS] + \
          [f"{fps:.1f}" if fps else "", a.note]
    print("\nresults.tsv row:\n" + "\t".join(tsv))
    if a.record:
        with open(os.path.join(ROOT, "results.tsv"), "a") as fh:
            fh.write("\t".join(tsv) + "\n")
    if not a.keep:
        pack_outputs(variant)


if __name__ == "__main__":
    main()
