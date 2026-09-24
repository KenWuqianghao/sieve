# sieve

**sieve** is a CSV loader in pure Python (standard library only) that works from a file's
bytes alone: it detects the encoding, dialect, header, preamble and trailing second table, and
repairs damaged rows, without being told anything about the file.

On all 2,290 files of the [Pollock](https://github.com/HPI-Information-Systems/Pollock)
data-loading benchmark, scored by Pollock's own `evaluate.py`, sieve scores **9.9971 simple /
9.9922 weighted**. The highest published row, DuckDB 1.2, scores 9.961 / 9.599. The setups are
not equivalent. sieve's Pollock script passes only the file path, and sieve receives the bytes.
DuckDB's script receives the dialect from each file's `parameters.json`: delimiter, quote,
escape, rows to skip and column names. Of the other scripts reproduced here, pandas, Python csv
and CleverCSV receive the encoding (pandas also the quote, escape and preamble rows); DuckDB's
auto-detect row, whose script receives nothing, scores 9.075 / 8.439.

## Install and use

```sh
pip install .                 # distribution: sieve-csv, import name: sieve; no dependencies
sieve data.csv                # the loaded table to stdout as normalised CSV
sieve data.csv -o clean.csv   # to a file
cat data.csv | sieve -        # from stdin
python -m sieve data.csv      # same CLI
```

```python
import sieve

rows = sieve.load("data.csv")        # a path (str or os.PathLike)
rows = sieve.load(b"a;b\n1;2,5\n")   # bytes, bytearray or memoryview
with open("data.csv", "rb") as fh:
    rows = sieve.load(fh)            # a binary file object
rows = sieve.load_bytes(data)        # the bytes-only form
```

`load` returns a list of rows (lists of str). The first row is the header when the file has
one; a file without a header is returned as-is (no header is invented). A path is only used to
open the file; nothing about its name reaches the loader. The CLI writes comma-delimited,
minimally quoted, CRLF-terminated UTF-8. Python 3.8 or later; the outputs on the Pollock corpus
are byte-identical under Python 3.8.20, 3.10.5 and 3.11.15.

## Results on Pollock

All numbers are Pollock scores (0-10) from the unmodified upstream `evaluate.py`, Pollock
commit `af36a06`. "README" is the published row; "reproduced" is this repository's run of the
system's own Pollock script (`harness/run_sut.py`, container paths re-rooted only) or, for
sieve, `harness/run.py --loader sieve`. Dev and held-out are the two parts of a split fixed
before any loader work (`harness/splits/`, stratified by pollution type, seed 20260922); all
development used dev, and held-out was scored once and only reported.

| system | README simple / weighted | reproduced, all 2,290 | dev 1,200 | held-out 1,090 | files/s | what the system is given, per file |
|---|---|---|---|---|---|---|
| **sieve 0.1.0** | - | **9.9971 / 9.9922** | 9.9989 / 9.9990 | 9.9952 / 9.9854 | 67 | the file's bytes only (the script passes the path; no name, encoding or parameters reach the loader) |
| DuckDB 1.2 (duckdbparse) | 9.961 / 9.599 | 9.9615 / 9.5997 (identical per file) | 9.9641 / 9.3552 | 9.9586 / 9.8439 | 1209 | delimiter, quotechar, escapechar, skiprows = preamble + header lines, column names; auto-detect off; `ignore_errors`, `null_padding` |
| SQLite 3.39.0 | 9.955 / 9.375 | not reproduced (no sqlite3 CLI) | - | - | - | encoding, delimiter, record delimiter, preamble rows to skip |
| Pandas 1.4.3 | 9.895 / 9.431 | 9.8848 / 7.9090 (pandas 1.5.3, see below) | 9.8825 / 6.0735 | 9.8873 / 9.7428 | 789 | encoding, quotechar, escapechar, lineterminator, skiprows = preamble; sniffs the delimiter |
| Python csv 3.10.5 | 9.721 / 9.436 | 9.7242 / 9.4365 (Python 3.11) | 9.7300 / 9.3919 | 9.7178 / 9.4810 | 125 | encoding; `csv.Sniffer` for the dialect |
| CleverCSV 0.7.4 | 9.193 / 9.453 | 9.1931 / 9.4539 (identical per file) | 9.1825 / 9.1452 | 9.2047 / 9.7622 | 17 | encoding; CleverCSV sniffer |
| DuckDB 1.2 (Auto) | 9.075 / 8.439 | 9.0213 / 8.4400 (1.2.2 vs the paper's pre-release) | 9.0292 / 7.9271 | 9.0125 / 8.9524 | 160 | nothing (DuckDB sniffer) |

- The other README rows (UniVocity 9.939 / 7.936, SpreadDesktop 9.929 / 9.597, LibreOffice
  9.925 / 7.833, SpreadWeb, MySQL, MariaDB, R, CSVCommons, OpenCSV, Dataviz, Hypoparsr,
  PostgreSQL) were not reproduced; each is below 9.961 simple and 9.599 weighted.
  `harness/published.py` recomputes every README number to 3 decimals from the authors'
  committed per-file results.
- Reproduction gaps. Pandas 1.4.3 has no Python 3.11 wheel; from pandas 1.5 on,
  `delimiter=None` is no longer sniffed with the C engine, so 4 delimiter files score 1.0, one
  of which (`file_field_delimiter_0x3B`) carries 18.7% of the weight; 2,283 of 2,290 files are
  identical to the published results. Python csv: 450 files differ between 3.10 and 3.11, net
  +0.003. DuckDB Auto: 69 row_extra_quote files differ (release vs pre-release sniffer).
- files/s is not a like-for-like comparison. For the baselines it is the timing their own
  scripts record, each through a different engine. For sieve it is files / sum of `load()`
  wall time in one process (54 files/s in the Pollock container, where the script's timing
  includes reading the file).
- End to end through Pollock's own flow (the SUT script in its Docker image, then upstream
  `evaluate.py`), sieve scored 9.997100 / 9.992176, with 0 application errors and outputs
  byte-identical to the harness's. The run's `aggregate_results_polluted_files.csv`,
  `sieve_results.csv` and `sieve_time.csv` are in `results/pollock-e2e/`;
  [docs/SUBMISSION.md](docs/SUBMISSION.md) has the details and the text of the Pollock PR.

Group means on all 2,290 files (score10 per file, 0-10):

| pollution group (files) | sieve | DuckDB 1.2, given the dialect | c0: sieve without row repair |
|---|---|---|---|
| T table-level: header, preamble, multitable, ... (13) | 9.9907 | 9.3831 | 9.9907 |
| S dialect singletons: delimiter, quote, escape, record delimiter (9) | 9.5698 | 9.4899 | 9.5698 |
| L row_less_sep (672) | 9.9961 (667 perfect) | 9.9661 | 9.9612 |
| M row_more_sep (756) | 10.0000 (756 perfect) | 10.0000 | 9.9962 |
| Q row_extra_quote (756) | 10.0000 (756 perfect) | 9.9377 | 9.4067 |
| R row_field_delimiter (84) | 10.0000 (84 perfect) | 9.9329 | 8.2444 |

Per file, sieve scores higher than duckdbparse on 1,427 files and lower on 5 (the glued-header
files under Known limitations). Every Pollock file is a pollution of one 83 x 9 source table, so
these scores alone cannot show that the repairs generalise; see the next section and the
limitations. How each number moved, experiment by experiment, is in
[EXPERIMENTS.md](EXPERIMENTS.md) and `results.tsv`.

## External dialect check

A report-only check on real files, never used to tune: 800 files from the CSV Wrangling test
set (van den Burg, Nazabal and Sutton, 2019) that are still downloadable with a matching md5
(1,486 tried: 539 URLs dead, 51 changed, 96 over 256 KB). 539 of the 800 have human-annotated
("messy") dialects, 261 normal-form ones. The same normalisation applies to every system: a
character absent from the file counts as "none", and escape == quote counts as "none".

| system | delimiter | quote | escape | full dialect | full, messy only | header present (89 labels) | failures |
|---|---|---|---|---|---|---|---|
| sieve | 97.1 | 98.0 | 99.1 | 95.2 | 93.1 | 67.4 (60/89) | 0 |
| CleverCSV 0.7.4 | 97.5 | 98.5 | 99.9 | 97.1 | 95.7 | 76.4 (68/89) | 0 |
| csv.Sniffer (Python 3.11) | 87.1 | 94.2 | 95.5 | 86.2 | 82.9 | 76.4 (68/89) | 32 |
| DuckDB 1.2 sniff_csv | 73.2 | 78.2 | 80.6 | 71.6 | 58.1 | 64.0 (57/89) | 146 (145 non-UTF-8) |

On the 654 files DuckDB can read, full-dialect accuracy is sieve 94.8, CleverCSV 96.6, DuckDB
87.6, csv.Sniffer 85.0.

**Header caveat.** CSV Wrangling has no header annotation. The 89 header labels come from one
annotator (the author), who read the first 5 lines of 100 seeded-random files before any
system's output was seen, and excluded 11 as ambiguous. sieve has no explicit header flag (it
emits the first row either way); its "header present" is its own `header_like(first row, next
rows)` test, the one its structure rules use. Treat that column as indicative. This is also a
reachable subset, not the full test set, so the numbers are not comparable with the paper's
tables.

sieve's `load()` output differs from the no-repair baseline on 8 of the 800 files: 5 from the
stray-quote repair (2 read better, 2 worse because text after a closing quote is kept as
literal text, 1 unreadable either way), 1 padded trailing cell (neutral) and 2 headers whose
empty trailing column name is dropped (better or neutral). The file list and labels are in
`harness/external/`; the downloaded files are not redistributed (`harness/external_fetch.py`
fetches them); per-file results are in `results/external/`.

## Known limitations

- **Header detection is the weakest part**: 67% on the external sample, against 76% for
  CleverCSV and csv.Sniffer. Pollock tests headers mainly through `file_no_header`.
- **Glued header names**: when the header row loses a separator, two column names are glued
  (`QtyPRODUCTID`). A header has no column profile to arbitrate, every cut gives two words, so
  sieve leaves it. 5 Pollock files (9.47 each); DuckDB's script is given the column names.
- **Held-out-only singletons**: the space-delimited file (7.88), the `'`-quoted file (8.55) and
  the three multitable files (9.96 each).
- **A literal backslash before an ordinary character can be dropped** when the sniffer picks
  `\` as the escape character (`\'` becomes `'`). A fix was tried (experiment H5) and not
  kept because it changed no dev score; on the external files it raised escape accuracy from
  99.1 to 99.6%.
- **Two cases found by the unit tests**, kept as strict expected failures: an unrepairable row
  (a date and a number glued) can look like the header of a second table and the table is cut
  there; and when every quoted field holds exactly one delimiter, the wrong quote character can
  give a perfectly regular table that the dialect score prefers.
- **Single source table**: the evidence beyond Pollock is the external dialect check, 23
  synthetic cases (`harness/synthetic/`) and 41 unit tests that apply Pollock's pollution types
  to a generated 7-column table. That is a small amount of evidence; a second polluted source
  table would be the natural next test.
- **Throughput**: 67 files/s in one Python process, against 1,209 for DuckDB's script. The
  dialect grid (about 20 trial parses per file) is half of the time.

## How it works

1. **Decode**: BOM sniff, then strict UTF-8, cp1252, latin-1.
2. **Dialect**: a grid over delimiter x quote x escape x skipinitialspace; each candidate parse
   of a 64 KB sample is scored as pattern consistency x share of typed cells (the CleverCSV
   formulation), ties going to the conventional choice.
3. **Row repairs**, each checked against a per-column profile learned from the file being
   loaded: a row written with its own delimiter is re-split; a stray quote that breaks the
   record structure is read as a literal; a lost separator is re-inserted where both halves fit
   the neighbouring columns; the one surplus empty cell of a row one cell too wide is dropped.
4. **Gates** on the separator repairs: no repair of a line starting with a comment marker
   (`#`, `//`, `%`, `--`); the target width must be the width of at least half of the records;
   in every typed column the repaired cell must be at least as typical as the column's least
   typical ordinary cell (leave-one-out); no typed column means no repair; ties are left alone.
5. **Structure**: a preamble closed by a blank line, a multi-row header (joined with a space)
   and a second table (cut) are found with a header-likeness test.

No rule refers to Pollock's source table: no column names, no row or column counts, no value
patterns; type caches are cleared on every `load()` call so nothing carries over between files.

## Reproduce

Prerequisites: Python 3.11 (any version from 3.8 runs sieve itself), a Pollock checkout at
`upstream/` (`git clone https://github.com/HPI-Information-Systems/Pollock upstream`, tested at
`af36a06`) or at the path in `POLLOCK_UPSTREAM`, and the scorer's dependencies:

```sh
uv venv -p 3.11 .venv
uv pip install -p .venv . pytest chardet==4.0.0 multiset==3.0.1 price-parser==0.3.4 \
    pqdm==0.2.0 python-dotenv duckdb==1.2.2 pandas==1.5.3 numpy==1.26.4
echo "setuptools<60" > bc.txt   # CleverCSV 0.7.4 (baseline only) builds with an old setuptools
uv pip install -p .venv clevercsv==0.7.4 --build-constraints bc.txt
```

```sh
make test          # 75 tests: 72 pass, 3 strict expected failures (the limitations above)
make eval-all      # sieve on all 2,290 files through Pollock's evaluate.py (prints dev / held-out)
make identity      # every output byte-identical to the scored run
make speed         # files/s, no-repair baseline vs sieve
make baselines     # the README rows with Pollock's own SUT scripts
make published     # the README rows from the authors' committed per-file results
make synthetic     # synthetic guard and repair cases
make external      # external dialect check (after harness/external_fetch.py --repo <CSV_Wrangling clone>)
make check-split   # the committed dev / held-out lists still match the seed
```

`harness/run.py` writes the loader's outputs, builds a directory shaped like the Pollock root
for the split (symlinks to the split's `polluted_files/{csv,clean}`, `pollock_weights.json` and
the outputs) and calls `evaluate.main()` there unchanged; the only symbol it sets is
`SUT_ORDER`, the list evaluate.py prints. `POLLOCK_LOADING_ROOT` moves the unpacked outputs
(about 55 MB) out of the repository. `harness/worst.py` and `harness/taxonomy.py` are the
per-file diff tools used during development. [docs/benchmark-notes.md](docs/benchmark-notes.md)
explains how Pollock scores, read from its code; [docs/error-profile.md](docs/error-profile.md)
is the failure profile of the baselines and of the no-repair starting point.

## Repository layout

- `sieve/`: the package (`loader.py` is the whole loader; `__init__.py` the API;
  `__main__.py` the CLI).
- `tests/`: pytest suite.
- `harness/`: the Pollock runner and scorer wrapper, split lists, baseline runner, analysis
  tools, `baseline/c0_csvsniff.py` (the no-repair baseline the synthetic guards compare
  against), `synthetic/` (the synthetic cases) and `external/` (the CSV Wrangling file list and
  the 89 header labels).
- `sut/sieve/`: sieve as a Pollock system under test (script, Dockerfile, requirements and a
  copy of the package), exactly the files the Pollock PR adds; `sut/docker-compose.service.yml`
  is its `docker-compose.yml` service block.
- `results/`: the end-to-end Pollock run (`pollock-e2e/`), the SHA-256 of every output file,
  and the per-file external check results. `results.tsv`: every scored run.
- `docs/`: [SUBMISSION.md](docs/SUBMISSION.md), [benchmark-notes.md](docs/benchmark-notes.md),
  [error-profile.md](docs/error-profile.md). [EXPERIMENTS.md](EXPERIMENTS.md): the worklog.

## License

Apache-2.0 ([LICENSE](LICENSE)). Two parts come from other projects under the MIT License:
`sut/sieve/sieve-bench.py` is adapted from Pollock's `sut/pycsv/pycsv.py` (Copyright (c) 20222
Gerardo Vitagliano, as written in Pollock's LICENSE; the notice is in
[sut/LICENSE-Pollock](sut/LICENSE-Pollock)), and `harness/external/manifest.tsv` lists file
URLs and dialect annotations from the CSV Wrangling repository
(https://github.com/alan-turing-institute/CSV_Wrangling, MIT License). The CSV files themselves
are not included.
