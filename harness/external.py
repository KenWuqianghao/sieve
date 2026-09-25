"""External dialect check: a report-only generality check (never tune on it).

Every Pollock file is a pollution of one 83x9 table, so the Pollock scores alone cannot show
that a loader generalises. This runs our loaders' dialect front-end on real CSV files with
human / normal-form annotated dialects (CSV Wrangling test set, fetched by
harness/external_fetch.py into data/external/files, manifest harness/external/manifest.tsv)
and compares with Python's csv.Sniffer, CleverCSV 0.7.4 and DuckDB 1.2 auto-detect.

    python harness/external.py --loaders c0-csvsniff,sieve [--no-baselines]

The files are downloaded by harness/external_fetch.py into data/external/files (or the
directory POLLOCK_EXTERNAL_FILES points to); they are not part of this repository.

Measures (per system, exact match after one normalisation applied to every system alike: a
delimiter / quote / escape character that does not occur in the file is "none", and an escape
equal to the quote char means doubled quotes, i.e. "none"):
  delimiter acc, quote acc, escape acc, full dialect acc (all three), failures (exception /
  timeout -> counted wrong). Reported on all files and on the human-annotated subset (files
  whose dialect the automatic normal-form detection could not decide). This is not the CSV
  Wrangling paper's "messy" subset (files with a non-standard dialect); README.md's CSV
  Wrangling section reports that one.
  header-present acc on the blind hand-labelled sample harness/external/header_labels.tsv
  (labelled from the first lines of each file BEFORE any system's output was looked at; CSV
  Wrangling has no header annotation).
Loaders are additionally run end to end (load(bytes)) to count exceptions and the files whose
output differs from the first loader listed (what a candidate's repairs change on real data).

Our header decision: a loader module that defines `detect(data)` (sieve 0.2 on, the function
behind `sieve.sniff()`) is scored on it: its dialect and its first-record header test. For a
loader without it (sieve 0.1, c0-csvsniff), which emits the first row either way, ours = the
loader's own `header_like(first_row, next_rows)` on its structured output - the rule its
multi-row-header / multitable logic uses.

Writes runs/external.<name>.tsv (per file) and prints the table. CPU: 1 process, nice it.
The per-file results behind README.md are in results/external/.
"""
import argparse
import csv
import json
import os
import signal
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_loader  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.environ.get("POLLOCK_EXTERNAL_FILES") or os.path.join(ROOT, "data", "external", "files")
MANIFEST = os.path.join(ROOT, "harness", "external", "manifest.tsv")
LABELS = os.path.join(ROOT, "harness", "external", "header_labels.tsv")
RUNS = os.path.join(ROOT, "runs")
TIMEOUT = 60


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def load_module(variant):
    return load_loader(variant, "ext")


def norm(text, d, q, e):
    d = d or ""
    q = q or ""
    e = e or ""
    if d == "\x00" or (d and d not in text):
        d = ""
    if q == "\x00" or (q and q not in text):
        q = ""
    if e == "\x00" or e == q or (e and e not in text):
        e = ""
    return d, q, e


def decode(data):
    # a shared decoding for the baselines (ours decode themselves), as the Pollock pycsv /
    # clevercs scripts are handed the encoding
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            return data.decode(enc, errors="replace")
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


# ------------------------------------------------------------------ systems: -> (d, q, e, header)
def sys_ours(mod):
    def run(data, path):
        if hasattr(mod, "detect"):  # sieve.sniff(): dialect + first-record header
            d, q, e, hdr = mod.detect(data)
            return mod.decode(data), d, q, e, hdr
        mod.strong.cache_clear()
        mod.typed.cache_clear()
        text = mod.decode(data)
        d, q, e, sp = mod.sniff(text)
        rows = mod.structure(mod.parse(text, d, q, e, sp))
        hdr = bool(rows) and len(rows) > 1 and mod.header_like(rows[0], rows[1:41])
        return text, d, q, e, hdr
    return run


def sys_sniffer(data, path):
    text = decode(data)
    s = csv.Sniffer()
    dia = s.sniff(text)  # as upstream/sut/pycsv: the whole file
    try:
        hdr = s.has_header(text)
    except csv.Error:
        hdr = None
    return text, dia.delimiter, dia.quotechar, dia.escapechar, hdr


def sys_clevercsv(data, path):
    import clevercsv
    text = decode(data)
    s = clevercsv.Sniffer()
    dia = s.sniff(text)  # as upstream/sut/clevercs: the whole file
    if dia is None:
        raise ValueError("no dialect")
    try:
        hdr = s.has_header(text)
    except Exception:
        hdr = None
    return text, dia.delimiter, dia.quotechar, dia.escapechar, hdr


_DUCK = None


def sys_duckdb(data, path):
    global _DUCK
    import duckdb
    if _DUCK is None:
        _DUCK = duckdb.connect()
    r = _DUCK.execute("SELECT Delimiter, Quote, Escape, HasHeader FROM sniff_csv(?)",
                      [path]).fetchone()
    return decode(data), r[0], r[1], r[2], bool(r[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loaders", default="c0-csvsniff,sieve")
    ap.add_argument("--no-baselines", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    with open(MANIFEST) as fh:
        man = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    man = [m for m in man if os.path.exists(os.path.join(FILES, m["md5"] + ".csv"))]
    if a.limit:
        man = man[:a.limit]
    labels = {}
    if os.path.exists(LABELS):
        with open(LABELS) as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if r["header"] in ("0", "1"):
                    labels[r["md5"]] = r["header"] == "1"

    loaders = [x for x in a.loaders.split(",") if x]
    mods = {v: load_module(v) for v in loaders}
    systems = [(f"ours:{v}", sys_ours(mods[v])) for v in loaders]
    if not a.no_baselines:
        systems += [("csv.Sniffer (py3.11)", sys_sniffer), ("CleverCSV 0.7.4", sys_clevercsv),
                    ("DuckDB 1.2 sniff_csv", sys_duckdb)]
    signal.signal(signal.SIGALRM, _alarm)

    table = []
    for name, fn in systems:
        n = n_messy = 0
        acc = {k: 0 for k in ("d", "q", "e", "all", "all_messy", "fail", "hdr_n", "hdr_ok")}
        t0 = time.time()
        per = []
        for m in man:
            path = os.path.join(FILES, m["md5"] + ".csv")
            with open(path, "rb") as fh:
                data = fh.read()
            gold = (json.loads(m["delimiter"]), json.loads(m["quotechar"]), json.loads(m["escapechar"]))
            messy = m["annotator"] == "human"
            n += 1
            n_messy += messy
            signal.alarm(TIMEOUT)
            try:
                text, d, q, e, hdr = fn(data, path)
                signal.alarm(0)
                pred = norm(text, d, q, e)
                ok = True
            except BaseException as ex:  # noqa: B902 - a crash or timeout is a wrong answer
                signal.alarm(0)
                if isinstance(ex, KeyboardInterrupt):
                    raise
                pred, hdr, ok = ("<fail>", "<fail>", "<fail>"), None, False
                acc["fail"] += 1
            hits = [p == g for p, g in zip(pred, gold)]
            acc["d"] += hits[0]
            acc["q"] += hits[1]
            acc["e"] += hits[2]
            acc["all"] += all(hits)
            acc["all_messy"] += all(hits) and messy
            if m["md5"] in labels:
                acc["hdr_n"] += 1
                acc["hdr_ok"] += hdr is not None and bool(hdr) == labels[m["md5"]]
            per.append([m["md5"], m["annotator"], json.dumps(gold), json.dumps(pred), int(all(hits)),
                        "" if hdr is None else int(bool(hdr)), int(ok)])
        dt = time.time() - t0
        table.append((name, n, n_messy, acc, dt))
        safe = name.split(" ")[0].replace(":", "_").replace("/", "_")
        with open(os.path.join(RUNS, f"external.{safe}.tsv"), "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["md5", "annotator", "gold", "pred", "dialect_ok", "header", "ran"])
            w.writerows(per)
        print(f"  done {name}: {dt:.0f}s", file=sys.stderr)

    # end-to-end loader run: exceptions and outputs that differ from the first loader
    diffs = {}
    if len(loaders) > 1:
        base = loaders[0]
        outs = {}
        for v in loaders:
            outs[v] = {}
            for m in man:
                with open(os.path.join(FILES, m["md5"] + ".csv"), "rb") as fh:
                    data = fh.read()
                try:
                    outs[v][m["md5"]] = mods[v].load(data)
                except Exception as ex:  # noqa: BLE001
                    outs[v][m["md5"]] = f"<exception {type(ex).__name__}>"
        for v in loaders[1:]:
            changed = [k for k in outs[v] if outs[v][k] != outs[base][k]]
            exc = [k for k in outs[v] if isinstance(outs[v][k], str)]
            diffs[v] = (changed, exc)
        # consecutive pairs: what each listed candidate changes vs the one listed before it
        for p, v in zip(loaders[1:], loaders[2:]):
            ch = [k for k in outs[v] if outs[v][k] != outs[p][k]]
            print(f"load(): {v} differs from {p} on {len(ch)} files: {ch[:25]}", file=sys.stderr)

    print(f"\nExternal dialect check - CSV Wrangling test-set files still reachable "
          f"({table[0][1]} files, {table[0][2]} human-annotated); header on "
          f"{table[0][3]['hdr_n']} blind hand-labelled files")
    print(f"| system | delimiter | quote | escape | full dialect | full, human-annotated only | header present | failures | s |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, n, nm, acc, dt in table:
        pct = lambda x, d: f"{100 * x / d:.1f}%" if d else "-"
        print(f"| {name} | {pct(acc['d'], n)} | {pct(acc['q'], n)} | {pct(acc['e'], n)} | "
              f"{pct(acc['all'], n)} | {pct(acc['all_messy'], nm)} | "
              f"{pct(acc['hdr_ok'], acc['hdr_n'])} ({acc['hdr_ok']}/{acc['hdr_n']}) | {acc['fail']} | {dt:.0f} |")
    for v, (changed, exc) in diffs.items():
        print(f"\nload(): {v} output differs from {loaders[0]} on {len(changed)} / {len(man)} files; "
              f"exceptions {len(exc)}" + (f": {changed[:25]}" if changed else ""))


if __name__ == "__main__":
    main()
