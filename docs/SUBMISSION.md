# sieve on Pollock: results and submission notes

This document collects what a Pollock maintainer or reviewer needs: the claim, the numbers,
how they were produced end to end through Pollock's own flow, the evidence on generality, the
known limitations, the reproduction commands and the text of the pull request to
[HPI-Information-Systems/Pollock](https://github.com/HPI-Information-Systems/Pollock) (the same
shape as the DuckDB results PR, #6). Numbers are from 2026-09-24, Pollock commit `af36a06`.

This document describes sieve **0.1.0** (commit `22cf0ba`), the version the PR text below
submits. sieve 0.2.0 replaced the dialect detector and scores 9.9972 / 9.9939 on the same
2,290 files through the same harness (README); `sut/sieve/` in this repository now vendors
0.2.0, and the 0.2.0 end-to-end Docker run has not been done.

## Claim in one paragraph

sieve is a pure-Python CSV loader, standard library only (`sieve/`: `loader.py` with about 880
lines of dialect / structure / row-repair logic on top of the `csv` module, plus a small API and
CLI). On all 2,290 Pollock files, scored by Pollock's own `evaluate.py`, it scores **9.9971
simple / 9.9922 weighted**. The highest published row is DuckDB 1.2 at 9.961 / 9.599. The two
setups are not equivalent: sieve is given **only the file's bytes** (its Pollock script passes
only the path), while DuckDB's README row is produced by a script that passes it the true
delimiter, quote, escape, preamble/header row count and column names from each file's
`parameters.json`. The numbers were reproduced end to end through Pollock's own flow: the SUT
script in its Docker image, then the upstream `evaluate.py` (section "End-to-end run").

## The package

- `pip install .` (pyproject.toml; distribution `sieve-csv` 0.1.0, import name `sieve`).
  **No dependencies**: standard library only. Tested on Python 3.8.20, 3.10.5 and 3.11.15; the
  output is byte-identical on all 2,290 Pollock files under the three versions.
- API: `sieve.load(path_or_bytes) -> list[list[str]]`. A str or `os.PathLike` is a path, bytes /
  bytearray / memoryview are the file content, a binary file object is read. The path is only
  used to open the file. The first row is the header when the file has one; a headerless file
  is returned as-is. `sieve.load_bytes(data)` is the bytes-only form.
- CLI: `python -m sieve file.csv` (or `sieve file.csv` after installing) writes the table to
  stdout as normalised CSV (comma, `"` where needed, CRLF, UTF-8); `-` reads stdin, `-o` writes a
  file.
- Tests: `python -m pytest` (75 tests: 72 pass, 3 are strict expected failures that document
  known limitations). 11 API / CLI / packaging tests; 23 synthetic cases (15 guard / limit
  cases that must load exactly as the no-repair baseline, 8 repair / escape cases on tables
  that are not Pollock's); 41 Pollock-shaped cases (every Pollock pollution type applied to a
  7-column table generated in the test).
- Throughput: **67 files/s** (one process, `load()` time only; 48 files/s before the profiling
  pass of experiment H7, same machine, same outputs), 54 files/s in the Pollock container (the
  script's own timing: file read + load, mean of 3 repetitions). DuckDB's script: 1,209.

## Numbers (all 2,290 files, official evaluate.py)

| system | README simple / weighted | reproduced, all 2,290 | dev 1,200 | held-out 1,090 | files/s | what the system is given (per file) |
|---|---|---|---|---|---|---|
| **sieve** | - | **9.9971 / 9.9922** | 9.9989 / 9.9990 | **9.9952 / 9.9854** | 67 (1 process, pure Python) | **the file's bytes only** (the script passes the path; no name, encoding or parameters reach the loader) |
| DuckDB 1.2 (duckdbparse) | 9.961 / 9.599 | 9.9615 / 9.5997 (identical per file) | 9.9641 / 9.3552 | 9.9586 / 9.8439 | 1209 | delimiter, quotechar, escapechar, skiprows = preamble + header lines, column names; auto-detect off; `ignore_errors`, `null_padding` |
| SQLite 3.39.0 | 9.955 / 9.375 | not reproduced (no sqlite3 CLI available) | - | - | - | encoding, delimiter, record delimiter, preamble rows to skip (`.import --skip`) |
| Pandas 1.4.3 | 9.895 / 9.431 | 9.8848 / 7.9090 (pandas 1.5.3; see note) | 9.8825 / 6.0735 | 9.8873 / 9.7428 | 789 | encoding, quotechar, escapechar, lineterminator, skiprows = preamble; sniffs the delimiter |
| Python csv 3.10.5 | 9.721 / 9.436 | 9.7242 / 9.4365 (py 3.11) | 9.7300 / 9.3919 | 9.7178 / 9.4810 | 125 | encoding; `csv.Sniffer` for the dialect |
| CleverCSV 0.7.4 | 9.193 / 9.453 | 9.1931 / 9.4539 (identical per file) | 9.1825 / 9.1452 | 9.2047 / 9.7622 | 17 | encoding; CleverCSV sniffer |
| DuckDB 1.2 (Auto) | 9.075 / 8.439 | 9.0213 / 8.4400 (1.2.2 vs the paper's pre-release) | 9.0292 / 7.9271 | 9.0125 / 8.9524 | 160 | nothing (DuckDB sniffer) |

Other README rows (UniVocity 9.939 / 7.936, SpreadDesktop 9.929 / 9.597, LibreOffice
9.925 / 7.833, SpreadWeb, MySQL, MariaDB, R, CSVCommons, OpenCSV, Dataviz, Hypoparsr,
PostgreSQL) were not reproduced. Each of them is below 9.961 simple and 9.599 weighted.

Reproduction notes. `harness/published.py` recomputes every README number to 3 decimals from
the authors' committed per-file results. Pandas: 1.4.3 has no Python 3.11 wheel. From 1.5 on,
`delimiter=None` is no longer sniffed with engine="c", so 4 delimiter files score 1.0 and
`file_field_delimiter_0x3B` carries 18.7% of the weight. 2,283 / 2,290 files are identical to
the published results. Python csv: 450 files differ between 3.10 and 3.11, net +0.003.
DuckDB Auto: 69 row_extra_quote files differ (release vs pre-release sniffer). Throughput for
the baselines is the timing their own scripts record, and each loads through a different
engine. sieve's is files / sum of `load()` wall time on one process, so the files/s column
compares loaders only roughly.

The dev / held-out split (`harness/splits/`, stratified by pollution family, seed 20260922)
was fixed before any loader work. All development used dev; the held-out split was scored
once, after the fifth accepted change, and not used for any decision.

Group means (score10, 0-10) on all 2,290:

| group (files) | sieve | DuckDB 1.2 told the dialect | c0 (sieve without row repair) |
|---|---|---|---|
| T table-level (13) | 9.9907 | 9.3831 | 9.9907 |
| S dialect singletons (9) | 9.5698 | 9.4899 | 9.5698 |
| L row_less_sep (672) | 9.9961 (667 perfect) | 9.9661 | 9.9612 |
| M row_more_sep (756) | **10.0000** (756) | 10.0000 | 9.9962 |
| Q row_extra_quote (756) | **10.0000** (756) | 9.9377 | 9.4067 |
| R row_field_delimiter (84) | **10.0000** (84) | 9.9329 | 8.2444 |

Per file, sieve beats duckdbparse on 1,427 files and loses on 5: the glued-header files
under Limitations.

## End-to-end run through Pollock's own flow

1. A copy of the upstream root (commit af36a06) with: `sut/sieve/` (script, Dockerfile,
   requirements, and the package as real files), the `sieve-client` service
   (`sut/docker-compose.service.yml` in this repository) inserted under `services:` in
   `docker-compose.yml`, and `"sieve"` appended to `SUT_ORDER` in `evaluate.py`. The other
   systems' per-file results were restored from upstream git
   (`results/<sut>/polluted_files/<sut>_results.csv`; DuckDB's two from the committed
   `global_results_polluted_files.csv`).
2. `DATASET=polluted_files docker compose build sieve-client` and `... up sieve-client`.
   The script ran unchanged in its image: 2,290 files x 3 repetitions, 0 Application Errors.
   Its outputs are byte-identical to the harness's on all 2,290 files.
3. `python evaluate.py --sut sieve --njobs 2` in that root. The table evaluate.py prints:
   **sieve 9.997100 / 9.992176**; duckdbparse 9.961516 / 9.599662, sqlite 9.955135 / 9.375923,
   spreaddesktop 9.929668 / 9.597198, pandas 9.895015 / 9.431498, clevercs 9.193083 / 9.453858
   (the published numbers).

Environment differences, all outside the SUT: the upstream `.env` has CRLF line endings, so
Docker Compose v2 reads `DATASET` as `"polluted_files\r#DATASET=survey_sample"`; `DATASET=polluted_files`
was set in the shell. The build machine reached PyPI through a TLS-intercepting proxy, so the
base image `python:3.11.15-slim` was rebuilt locally with the host's CA bundle (`PIP_CERT`).
evaluate.py was run with Python 3.11 / pandas 1.5.3, not in the `evaluate` image (python:3.8,
pandas 1.2.2), because that image did not fit the available disk.
Artefacts in `results/pollock-e2e/`: the `aggregate_results_polluted_files.csv` that run
wrote, `sieve_results.csv` (per-file measures) and `sieve_time.csv` (the script's timings).
`results/sieve-outputs.sha256.tsv` holds the SHA-256 of each of the 2,290 output files.

## What sieve does (bytes in, rows out)

1. Decode: BOM sniff, then strict UTF-8, cp1252, latin-1.
2. Dialect: a grid over delimiter x quote x escape x skipinitialspace, scored CleverCSV-style
   (pattern consistency x type share).
3. Row repairs. Each one is checked against a per-column profile learned from **the file
   being loaded**, never from the benchmark table:
   - a row written with its own delimiter is re-split (row_field_delimiter);
   - a stray quote that breaks the record structure is read as a literal (row_extra_quote);
   - a lost separator is re-inserted where both halves fit the neighbouring columns
     (row_less_sep);
   - the one surplus empty cell of a W+1 row is dropped (row_more_sep).
4. Gates on the separator repairs:
   - no repair of a line that starts with a comment marker (`#`, `//`, `%`, `--`);
   - W must be the width of at least half of the records;
   - in every typed column, the repaired row must be at least as typical as that column's
     least typical ordinary cell (leave-one-out);
   - a file with no typed column gets no repair;
   - ties are left alone.
5. Structure: a preamble closed by a blank line, a multi-row header (joined with a space),
   and a second table (cut) are detected with a header-likeness test.

## Evidence it was not fitted to the one source table

Every Pollock file is a pollution of **one** 83 x 9 table, which makes memorisation easy, so
the work followed these rules:
- The harness gives the loader bytes only. No file names.
- The code encodes no column names, no counts (9 / 83) and no value patterns of that table.
  Caches are cleared per `load()` call.
- `clean/` and `parameters/` are never read by the loader.
- Development used a frozen dev split (1,200 files, stratified, seed 20260922).
- The held-out split (1,090 files) was scored once, after the fifth accepted change, and only
  reported.

Held-out 9.9952 / 9.9854 against dev 9.9989 / 9.9990. Held-out contains 10 file-level types
dev does not, and all its remaining loss is there or in the glued-header files. Caveat: the
22 file-level files were all read while writing the structure rules, so held-out is an
independent test only for the row-level files.

## External dialect check (report-only; generality beyond Pollock's one table)

800 real CSV files from the CSV Wrangling test set (van den Burg et al. 2019, MIT). These are
the ones still downloadable with a matching md5: 1,486 were tried, 539 URLs are dead, 51
changed and 96 are over 256 KB. 539 of the 800 are human-annotated "messy" files, 261 are
normal-form. Normalisation, applied to every system alike: a character absent from the file
counts as "none", and escape == quote counts as "none".

| system | delimiter | quote | escape | full dialect | full, messy only | header present (89 blind labels) | failures |
|---|---|---|---|---|---|---|---|
| sieve | 97.1 | 98.0 | 99.1 | **95.2** | 93.1 | 67.4 (60/89) | 0 |
| CleverCSV 0.7.4 | 97.5 | 98.5 | 99.9 | **97.1** | 95.7 | 76.4 (68/89) | 0 |
| csv.Sniffer (py 3.11) | 87.1 | 94.2 | 95.5 | 86.2 | 82.9 | 76.4 (68/89) | 32 |
| DuckDB 1.2 sniff_csv | 73.2 | 78.2 | 80.6 | 71.6 | 58.1 | 64.0 (57/89) | 146 (145 non-UTF-8) |

On the 654 files DuckDB can read, full dialect accuracy is: sieve 94.8, CleverCSV 96.6,
DuckDB 87.6, Sniffer 85.0. The speed pass (H7) changed no output on these 800 files.

**Header caveat.** CSV Wrangling has no header annotation. The 89 labels come from one
annotator: an LLM-assisted annotation pass (not a person, and not human-verified) that read the first 5 lines of 100 seeded-random files **before** any
system's output was seen. 11 files were excluded as ambiguous. sieve has no explicit header
flag (it emits the first row either way). Its "header present" is its own
`header_like(first row, next rows)` test, the one its structure rules use. Treat the column as
indicative.
**Subset caveat.** This is 800 reachable files, not the full test set, so the numbers are
not comparable to the paper's tables.

End to end, sieve's `load()` output differs from the no-repair baseline (c0) on 8 of the 800
files:
- 5 from the stray-quote repair: 2 read better, 2 read worse (text after a closing quote is
  literalised), 1 is garbage either way.
- 1 pads a missing trailing cell (neutral).
- 2 drop an empty trailing column name from a header with a trailing delimiter (better or
  neutral).

The separator-repair gates were added after an earlier version re-split free-text and comment
lines on 4 of these files. That regression was written up, the gates were designed on
synthetic cases (`harness/synthetic/`), and the external files were then re-run once,
report-only. The comment-marker gate uses the conventional comment prefixes of CSV tools, but
the idea came up while reading that regression, so the external set is not an independent
test of that one gate.

## Known limitations

- **Header detection is the weak spot**: 67% on the external blind sample, against 76% for
  CleverCSV and csv.Sniffer. Pollock hardly tests it (only `file_no_header`), so the 10.0
  there says little about headers in general.
- **Glued header names** (`row_less_sep_row0_*`): when the header row loses a separator, two
  column names are glued (`QtyPRODUCTID`, `PriceProductType`, ...). A header has no column
  profile, and every cut of two glued words gives two words, so sieve does not guess.
  Measured on dev: 2 files, genuinely ambiguous. On all 2,290 there are 5 such files (2 dev,
  3 held-out), each at 9.47. DuckDB gets them right because the script passes it the column
  names. A case-boundary rule would split them but is not generic, so it was not used.
- **Held-out-only singletons**: the space delimiter (7.88), the `'` quote (8.55) and the three
  multitable files (9.96 each).
- **A literal backslash before a non-special character can be dropped.** The sniffer may pick
  `\` as the escape character when the type score favours it, and then `\'` loses its
  backslash (Pollock's source row 13, and the multitable files). A fix (use `\` only when it
  precedes the quote char, the delimiter or itself; experiment H5, c7-escape) changed no dev
  score (the one affected dev file is broken either way), so the acceptance rule did not take
  it. On the external files it improved the escape accuracy (99.1 -> 99.6%, full dialect
  95.2 -> 95.6%) with 3 files reading better and 1 worse. It is not in this loader.
- **Found by the unit tests** (non-Pollock table, kept as strict expected failures):
  (a) a damaged row that cannot be repaired (a date and a number glued, several equally good
  cuts) can look like the header of a second table against the misaligned columns below it,
  and the table is then cut at that row; (b) when every quoted field holds exactly one
  delimiter, the wrong quote character splits each of them into two and gives a perfectly
  regular table that matches a header with one extra separator, so the dialect score picks it.
- **Single-source generality**: every Pollock file comes from one 83 x 9 table, so the Pollock
  scores alone cannot show that the repairs generalise. The evidence beyond Pollock is the
  external dialect check above, the 23 synthetic cases in `harness/synthetic/` and the 41
  Pollock-shaped unit tests on a generated 7-column table. That is still a small amount of
  evidence. A second polluted source table would be the natural next test.
- **Throughput**: 67 files/s in pure Python, against DuckDB's 1,209 files/s. The dialect grid
  (about 20 trial parses per file) is now half of the time.

## How to reproduce (this repository)

```sh
git clone https://github.com/KenWuqianghao/sieve && cd sieve
git clone https://github.com/HPI-Information-Systems/Pollock upstream   # tested at af36a06
# (or point POLLOCK_UPSTREAM at an existing Pollock checkout)
uv venv -p 3.11 .venv
uv pip install -p .venv . pytest
.venv/bin/python -m pytest                                    # 72 passed, 3 xfailed
# Pollock's scorer and the baselines
uv pip install -p .venv chardet==4.0.0 multiset==3.0.1 price-parser==0.3.4 pqdm==0.2.0 \
    python-dotenv duckdb==1.2.2 pandas==1.5.3 numpy==1.26.4
echo "setuptools<60" > bc.txt   # CleverCSV 0.7.4 only builds with an old setuptools
uv pip install -p .venv clevercsv==0.7.4 --build-constraints bc.txt   # baselines only
# sieve on all 2,290 files through the unchanged upstream evaluate.py
# (POLLOCK_LOADING_ROOT=<a directory outside the repository> keeps the 55 MB of unpacked outputs out)
nice -n 10 .venv/bin/python harness/run.py --loader sieve --split all
# byte-identity of every output with the scored run, and files/s
.venv/bin/python harness/speed.py --loader sieve --compare results/sieve-outputs.sha256.tsv
.venv/bin/python harness/speed.py --loaders c0-csvsniff,sieve --repeat 2
# baselines with Pollock's own SUT scripts (paths re-rooted only)
.venv/bin/python harness/run.py --sut duckdbparse --split all
.venv/bin/python harness/published.py --split all   # the README rows from the committed results
# synthetic regression cases and the external dialect check
.venv/bin/python harness/synthetic/check.py --loaders c0-csvsniff,sieve
.venv/bin/python harness/external_fetch.py --repo <CSV_Wrangling clone>
.venv/bin/python harness/external.py --loaders c0-csvsniff,sieve
```

`make install`, `make test`, `make eval-all` and the other Makefile targets wrap these.

## What a Pollock maintainer would run

In a Pollock checkout with the PR applied (or, by hand, with this repository at `$SIEVE`:
`cp -r $SIEVE/sut/sieve sut/`, the service block from `$SIEVE/sut/docker-compose.service.yml`
under `services:` in `docker-compose.yml`, and `"sieve"` in `SUT_ORDER` of `evaluate.py`):

```sh
DATASET=polluted_files docker-compose up sieve-client   # writes results/sieve/polluted_files/
DATASET=polluted_files docker-compose up evaluate       # or: python evaluate.py --sut sieve
```

(`DATASET=` in the shell only because the committed `.env` has CRLF line endings; see above.)
Expected: `sieve` 9.9971 simple / 9.9922 weighted in `results/aggregate_results_polluted_files.csv`.

## What the Pollock PR contains

One commit on top of `af36a06`, in the layout of the DuckDB PR (#6):

- `sut/sieve/sieve-bench.py`, `Dockerfile`, `sieve-requirements.txt` and the `sieve/` package
  (3 files, standard library only; pandas in the image is for `sut/utils.py`'s timing CSV).
  **Unlike the other scripts, it does not call `load_parameters`.** It passes only the path.
- The `sieve-client` service in `docker-compose.yml`, `"sieve"` in `SUT_ORDER` of
  `evaluate.py`, `docker-compose up sieve-client` in `benchmark.sh`, and a `.gitignore` entry
  for `results/sieve/polluted_files/loading/` (the per-file outputs are not committed; the
  service regenerates them).
- `results/sieve/polluted_files/sieve_results.csv` and `sieve_time.csv` from the end-to-end run.
- `results/aggregate_results_polluted_files.csv` and `results/global_results_polluted_files.csv`
  with the sieve row and columns added (the other systems' values unchanged).
- A README row, `sieve 0.1.0 | 9.997 | 9.992`, at the top of the table (ranked by simple score),
  with a footnote: sieve's script passes only the file path, while the other scripts receive
  parts of `parameters.json` (see `sut/*`); the loading command in the README's list; and a
  link to this repository.

## Pull request text

**Title:** Add sieve (bytes-only Python CSV loader) as a system under test

**Body:**

This PR adds sieve, a pure-Python CSV loader (standard library only; https://github.com/KenWuqianghao/sieve), as a system under test, in the layout of #6:

- `sut/sieve/`: script, Dockerfile, requirements and the package;
- the `sieve-client` service in `docker-compose.yml`, its line in `benchmark.sh`, `sieve` in `SUT_ORDER`, and a `.gitignore` entry for its loading outputs, which are not committed;
- `results/sieve/polluted_files/sieve_results.csv` and `sieve_time.csv`, the sieve row in `aggregate_results_polluted_files.csv` and its columns in `global_results_polluted_files.csv` (other systems' values unchanged);
- a README row with a footnote, and the loading command.

With the unchanged scoring code on all 2,290 files, sieve scores 9.9971 simple and 9.9922 weighted. In the same evaluate.py run, DuckDB 1.2 (duckdbparse) scores 9.9615 and 9.5997.

The setups are not equivalent. sieve's script passes only the file path; sieve detects encoding, dialect, header, preamble and damaged rows itself. DuckDB's script receives the dialect from each file's parameters.json: delimiter, quote, escape, rows to skip and column names.

Limitations:
- All Pollock files derive from one source table, so these scores cannot show that sieve's row repairs generalise. Other evidence is limited: dialect detection on 800 real files from the CSV Wrangling set (95.2% full dialect, CleverCSV 97.1%) and synthetic test cases.
- Header detection is weak on real files: 67% on 89 labelled files (LLM-assisted labels, not human-verified) (CleverCSV and csv.Sniffer: 76%).
- Five files whose header row lost a separator are left unrepaired.

Throughput is 54 files/s in the container (one process, file read included).
