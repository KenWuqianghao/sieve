"""Fetch the external dialect corpus (report-only regression guard; never tune on it).

Source: CSV Wrangling (van den Burg, Nazabal, Sutton, DMKD 2019;
https://github.com/alan-turing-institute/CSV_Wrangling, MIT). The repo ships URL + md5 lists
(urls_github.json, urls_ukdata.json) and the ground-truth dialect annotations of its TEST set
(results/test/detection/out_reference_{github,ukdata}.json: delimiter / quotechar / escapechar,
'' = none; `original_detector` = human (messy files) or normal (automatic normal form)).
The files themselves are not redistributed; we download the ones still reachable whose md5
still matches (so the annotation still applies), from a seeded random order, until a budget.

Output: data/external/files/<md5>.csv (gitignored; or $POLLOCK_EXTERNAL_FILES) and harness/external/manifest.tsv
(committed: md5, source, annotator, delimiter, quotechar, escapechar, bytes, url).

  python harness/external_fetch.py --repo <CSV_Wrangling clone> \
      [--max-files 800] [--max-bytes-file 262144] [--budget-mb 25]
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("POLLOCK_EXTERNAL_FILES") or os.path.join(ROOT, "data", "external", "files")
MANIFEST = os.path.join(ROOT, "harness", "external", "manifest.tsv")
SEED = 20260924
COLS = ["md5", "source", "annotator", "delimiter", "quotechar", "escapechar", "bytes", "url"]


def esc(s):
    return json.dumps(s, ensure_ascii=False)  # keeps tabs / empty strings visible in the TSV


def fetch(url, cap):
    req = urllib.request.Request(url, headers={"User-Agent": "pollock-external-check/1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read(cap + 1)
    return data if len(data) <= cap else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--max-files", type=int, default=800)
    ap.add_argument("--max-bytes-file", type=int, default=256 * 1024)
    ap.add_argument("--budget-mb", type=float, default=25.0)
    ap.add_argument("--max-attempts", type=int, default=3000)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    cands = []
    for src in ("github", "ukdata"):
        urls = {}
        with open(os.path.join(a.repo, f"urls_{src}.json")) as fh:
            for line in fh:
                o = json.loads(line)
                urls[o["md5"]] = o["urls"]
        with open(os.path.join(a.repo, "results", "test", "detection",
                               f"out_reference_{src}.json")) as fh:
            for line in fh:
                o = json.loads(line)
                if o.get("status") != "OK":
                    continue
                md5 = os.path.splitext(os.path.basename(o["filename"]))[0]
                if md5 in urls:
                    cands.append((src, md5, o.get("original_detector", ""), o["dialect"], urls[md5]))
    random.Random(SEED).shuffle(cands)
    print(f"{len(cands)} annotated OK files with URLs", file=sys.stderr)

    have = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as fh:
            next(fh)
            for line in fh:
                have[line.split("\t")[0]] = line
    total = sum(int(l.split("\t")[6]) for l in have.values())
    stats = {"ok": len(have), "dead": 0, "md5": 0, "big": 0}
    rows = list(have.values())
    attempts = 0
    for src, md5, ann, dia, us in cands:
        if len(rows) >= a.max_files or total >= a.budget_mb * 1e6 or attempts >= a.max_attempts:
            break
        if md5 in have:
            continue
        attempts += 1
        data = None
        for u in us:
            try:
                data = fetch(u, a.max_bytes_file)
                if data is None:
                    stats["big"] += 1
                break
            except Exception:
                continue
        else:
            stats["dead"] += 1
            continue
        if data is None:
            continue
        if hashlib.md5(data).hexdigest() != md5:
            stats["md5"] += 1
            continue
        with open(os.path.join(OUT, md5 + ".csv"), "wb") as fh:
            fh.write(data)
        total += len(data)
        stats["ok"] += 1
        rows.append("\t".join([md5, src, ann, esc(dia["delimiter"]), esc(dia["quotechar"]),
                               esc(dia["escapechar"]), str(len(data)), us[0]]) + "\n")
        if attempts % 50 == 0:
            print(f"attempts {attempts} {stats} {total/1e6:.1f} MB", file=sys.stderr)
        time.sleep(0.05)
    with open(MANIFEST, "w") as fh:
        fh.write("\t".join(COLS) + "\n")
        fh.writelines(sorted(rows, key=lambda l: l.split("\t")[0]))
    print(f"done: attempts {attempts} {stats} files {len(rows)} {total/1e6:.2f} MB",
          file=sys.stderr)


if __name__ == "__main__":
    main()
