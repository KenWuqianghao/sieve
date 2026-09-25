# sieve

**sieve** is a CSV loader in pure Python (standard library only) that works from a file's
bytes alone: it detects the encoding, dialect, header, preamble and trailing second table, and
repairs damaged rows, without being told anything about the file. `sieve.sniff()` reports the
detected dialect and whether the first record is a header.

On all 2,290 files of the [Pollock](https://github.com/HPI-Information-Systems/Pollock)
data-loading benchmark, scored by Pollock's own `evaluate.py`, sieve 0.2.0 scores **9.9972
simple / 9.9939 weighted** (0.1.0: 9.9971 / 9.9922). The highest published row, DuckDB 1.2,
scores 9.961 / 9.599. The setups are not equivalent. sieve's Pollock script passes only the
file path, and sieve receives the bytes.
DuckDB's script receives the dialect from each file's `parameters.json`: delimiter, quote,
escape, rows to skip and column names. Of the other scripts reproduced here, pandas, Python csv
and CleverCSV receive the encoding (pandas also the quote, escape and preamble rows); DuckDB's
auto-detect row, whose script receives nothing, scores 9.075 / 8.439.

On the held-out part of the CSV Wrangling test set (van den Burg, Nazabal and Sutton, 2019),
sieve's dialect detection scores **97.72% full / 92.71% messy**, against 96.55 / 88.54 for
CleverCSV 0.8.5. `sieve.sniff().has_header` gets **94.4%** of 89 blind header labels, against
76.4% for CleverCSV and csv.Sniffer (see "CSV Wrangling: dialect and header detection").

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

d = sieve.sniff("data.csv")          # same sources as load()
d          # Dialect(delimiter=';', quotechar='"', escapechar=None, has_header=True)
d.delimiter, d.quotechar, d.escapechar, d.has_header
```

`load` returns a list of rows (lists of str). The first row is the header when the file has
one; a file without a header is returned as-is (no header is invented). A path is only used to
open the file; nothing about its name reaches the loader. The CLI writes comma-delimited,
minimally quoted, CRLF-terminated UTF-8.

`sniff` returns a `Dialect(delimiter, quotechar, escapechar, has_header)` named tuple without
loading the table. `None` means "none": no delimiter (a one-column file), no quote character
(no field is enclosed by one), no escape character (a `\` is reported only when it precedes
the delimiter or the quote character). The dialect is the one `load` parses with, except that
`load` reads a file without a quote character with `"` (its row repairs need one).

**`sniff().has_header` and `load()`** answer different questions. `has_header` asks whether
the file's *first non-blank record* names the columns of the records below it (a title,
comment or note line is not a header). `load` does not use it. `load` emits the first row of
its table either way (it never invents a header), and its structure stage keeps 0.1.0's
table-level test: it cuts a preamble closed by a blank line, then judges header-likeness to
find a multi-row header or a second table. The Pollock scores depend on that stage, so 0.2.0
leaves it unchanged. For a title line, a blank line and then a header, `has_header` is `False`
(the first record is a title) while `load` returns the table below the title, header first.
When the file starts with its header, that header is `load()`'s first row.

Python 3.8 or later. The tests pass and the outputs on the Pollock corpus are byte-identical
under Python 3.8.20, 3.9.23 and 3.11.15.

## Results on Pollock

All numbers are Pollock scores (0-10) from the unmodified upstream `evaluate.py`, Pollock
commit `af36a06`. "README" is the published row; "reproduced" is this repository's run of the
system's own Pollock script (`harness/run_sut.py`, container paths re-rooted only) or, for
sieve, `harness/run.py --loader sieve`. Dev and held-out are the two parts of a split fixed
before any loader work (`harness/splits/`, stratified by pollution type, seed 20260922); all
development used dev, and held-out was scored once and only reported.

| system | README simple / weighted | reproduced, all 2,290 | dev 1,200 | held-out 1,090 | files/s | what the system is given, per file |
|---|---|---|---|---|---|---|
| **sieve 0.2.0** | - | **9.9972 / 9.9939** | 9.9989 / 9.9990 | 9.9953 / 9.9888 | 55 | the file's bytes only (the script passes the path; no name, encoding or parameters reach the loader) |
| sieve 0.1.0 | - | 9.9971 / 9.9922 | 9.9989 / 9.9990 | 9.9952 / 9.9854 | 59 | the same |
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
  wall time in one process, best of three interleaved passes of 0.1.0 and 0.2.0 on the same
  machine (`harness/speed.py`; 0.1.0 measured 67 files/s when it was first scored, on a less
  loaded machine, and 54 files/s in the Pollock container, where the script's timing includes
  reading the file).
- 0.1.0 -> 0.2.0 changed the output of 4 of the 2,290 files: the three multitable files
  (9.9599 -> 10.0 each, all in held-out: a literal backslash before an apostrophe is now kept,
  because `\` is an escape candidate only with evidence) and `file_escape_char_0x00` (keeps
  its backslash, same score 9.7416). No group mean went down.
- End to end through Pollock's own flow (the SUT script in its Docker image, then upstream
  `evaluate.py`), sieve 0.1.0 scored 9.997100 / 9.992176, with 0 application errors and outputs
  byte-identical to the harness's; it was not repeated for 0.2.0. The run's
  `aggregate_results_polluted_files.csv`, `sieve_results.csv` and `sieve_time.csv` are in
  `results/pollock-e2e/`; [docs/SUBMISSION.md](docs/SUBMISSION.md) has the details and the
  text of the Pollock PR.

Group means on all 2,290 files (score10 per file, 0-10):

| pollution group (files) | sieve 0.2.0 | sieve 0.1.0 | DuckDB 1.2, given the dialect | c0: sieve 0.1 without row repair |
|---|---|---|---|---|
| T table-level: header, preamble, multitable, ... (13) | 10.0000 (13 perfect) | 9.9907 | 9.3831 | 9.9907 |
| S dialect singletons: delimiter, quote, escape, record delimiter (9) | 9.5698 | 9.5698 | 9.4899 | 9.5698 |
| L row_less_sep (672) | 9.9961 (667 perfect) | 9.9961 | 9.9661 | 9.9612 |
| M row_more_sep (756) | 10.0000 (756 perfect) | 10.0000 | 10.0000 | 9.9962 |
| Q row_extra_quote (756) | 10.0000 (756 perfect) | 10.0000 | 9.9377 | 9.4067 |
| R row_field_delimiter (84) | 10.0000 (84 perfect) | 10.0000 | 9.9329 | 8.2444 |

Per file, sieve (0.1.0 and 0.2.0 alike) scores higher than duckdbparse on 1,427 files and lower
on 5 (the glued-header files under Known limitations). Every Pollock file is a pollution of one
83 x 9 source table, so these scores alone cannot show that the repairs generalise; see the
next section and the limitations. How each number moved, experiment by experiment, is in
[EXPERIMENTS.md](EXPERIMENTS.md) and `results.tsv`.

## CSV Wrangling: dialect and header detection

sieve 0.2.0's dialect detector (the grid behind `load()` and `sniff()`) and the first-record
header test behind `sniff().has_header` were developed on the test set of the CSV Wrangling
paper (G.J.J. van den Burg, A. Nazabal and C. Sutton, "Wrangling messy CSV files by detecting
row and type patterns", Data Mining and Knowledge Discovery 33, 2019), with its annotations
from
[alan-turing-institute/CSV_Wrangling](https://github.com/alan-turing-institute/CSV_Wrangling)
(MIT License), and scored with the paper's metric: exact equality of (delimiter, quote char,
escape char), "none" for a character the file does not use, failures counted wrong. "Messy" is
the paper's subset of files with a non-standard dialect.

Corpus and protocol: every annotated test file still downloadable with its annotated md5 and
at most 256 KB, 5,146 files (GitHub 3,594, UKdata 1,552), split once with a fixed seed,
stratified by source, messy and annotator: dev 3,087 (messy 431) and held-out 2,059 (messy
288). All development used dev. Held-out was scored once, at a checkpoint after the last change
(the table below), and only reported. The development harness is not part of this repository;
it ran the detector as a standalone module, and `sieve.sniff()` gives identical output on all
5,146 files (Python 3.11).

Held-out, 2,059 files (full-dialect accuracy, %):

| system | all | messy (288) | GitHub (1,438) | GitHub messy (284) | UKdata (621) | failures |
|---|---|---|---|---|---|---|
| **sieve 0.2.0** | **97.72** | **92.71** | **96.80** | **92.61** | **99.84** | 0 |
| CleverCSV 0.8.5 | 96.55 | 88.54 | 95.20 | 88.73 | 99.68 | 9 |
| csv.Sniffer (Python 3.11, the paper's wrapper) | 87.47 | 67.36 | 85.95 | 67.25 | 90.98 | 76 |
| sieve 0.1.0 | 94.51 | 86.11 | 92.56 | 86.27 | 99.03 | 0 |

On dev (tuned on) sieve 0.2.0 scores 97.76 / 92.81 and CleverCSV 96.21 / 86.77. For context,
the paper's own "Full" row (its whole test set, CleverCSV's method) is GitHub 93.75, GitHub
messy 85.63, UKdata 99.68. The only held-out slice where CleverCSV leads is the files with
automatically derived ("normal form") annotations: 99.85 against 99.39 (3 files). On 300 dev
files, sniffing takes about 11 times less time than CleverCSV 0.8.5 (160 against 14.6 files/s,
same machine, paired).

Header, `sniff().has_header` against hand labels of "is the first non-blank record a header":

| system | 89 blind labels (test) | 195 dev labels (tuned on) |
|---|---|---|
| **sieve 0.2.0 `sniff()`** | **94.4 (84/89)** | 96.9 (189/195) |
| CleverCSV 0.8.5 `has_header` | 76.4 (68/89) | 82.6 |
| csv.Sniffer `has_header` | 76.4 (68/89) | 76.9 |
| sieve 0.1.0 (`header_like` on the structured table) | 67.4 (60/89) | 69.2 |

Caveats:
- **A reachable subset.** 5,146 of the 9,355 annotated test files: two thirds of the UKdata
  files are no longer reachable, so the corpus is 70% GitHub against 47% in the paper, and
  messier. Pooled numbers are not comparable with the paper's tables; the per-source columns
  are the comparable ones.
- **The 200 dev header labels** (CSV Wrangling has no header annotation) were drawn from the
  dev split with a fixed seed, excluding the 100 files of the 89-label test sample, and labelled
  under a protocol written before the first label: the labeller saw only the first 8 lines of
  each file (each cut to 160 characters), before any system was run on those files, and
  nothing else about the file (name, URL, source, dialect annotation or any detector output).
  The question is the one above: a title, comment, note or metadata line above the table
  counts as "not a header", and a file that cannot be decided from its first lines is labelled
  "?" and excluded (5 of 200; 195 remain, 118 header and 77 not). These labels were used to
  develop the header test.
- **The 89 test labels** are the blind sample described under "External dialect check"
  below. They were never used for development, and were scored once, at the held-out
  checkpoint.
- The CleverCSV version here is 0.8.5; the Pollock rows and the external check below use
  0.7.4, as reproduced by those harnesses.
- On Python 3.10 and earlier, the csv module rejects NUL bytes, so a file containing one can
  be sniffed differently (1 of the 5,146 files, a dev file, where Python 3.11 finds the quote
  char and 3.10 does not).

## External dialect check

A report-only check on real files, never used to tune sieve 0.1: 800 files from the CSV
Wrangling test set that are still downloadable with a matching md5 (1,486 tried: 539 URLs
dead, 51 changed, 96 over 256 KB). 539 of the 800 have human-annotated dialects, 261
normal-form ones. The same normalisation applies to every system: a character absent from the
file counts as "none", and escape == quote counts as "none". For sieve 0.2.0 the check scores
`sniff()`.

| system | delimiter | quote | escape | full dialect | full, human-annotated only | header present (89 labels) | failures |
|---|---|---|---|---|---|---|---|
| **sieve 0.2.0** | **98.6** | **99.0** | **99.9** | **97.9** | **96.8** | **94.4 (84/89)** | 0 |
| sieve 0.1.0 | 97.1 | 98.0 | 99.1 | 95.2 | 93.1 | 67.4 (60/89) | 0 |
| CleverCSV 0.7.4 | 97.5 | 98.5 | 99.9 | 97.1 | 95.7 | 76.4 (68/89) | 0 |
| csv.Sniffer (Python 3.11) | 87.1 | 94.2 | 95.5 | 86.2 | 82.9 | 76.4 (68/89) | 32 |
| DuckDB 1.2 sniff_csv | 73.2 | 78.2 | 80.6 | 71.6 | 58.1 | 64.0 (57/89) | 146 (145 non-UTF-8) |

On the 654 files DuckDB can read, full-dialect accuracy is sieve 0.2.0 97.6, sieve 0.1.0
94.8, CleverCSV 96.6, DuckDB 87.6, csv.Sniffer 85.0. The "human-annotated" column was called
"messy" in 0.1.0's README; it is not the paper's messy subset (the table above has that one).

**These 800 files are not independent of sieve 0.2.** They are part of the 5,146-file corpus
above: 478 fall in its dev split, which the detector was developed on, and 322 in held-out. On
those 322 alone, full-dialect accuracy is sieve 0.2.0 98.4, CleverCSV 0.7.4 97.5 and sieve
0.1.0 95.0. The 89 header labels were not used for development.

**Header caveat.** CSV Wrangling has no header annotation. The 89 header labels come from one
annotator (the author), who read the first 5 lines of 100 seeded-random files before any
system's output was seen, and excluded 11 as ambiguous. sieve 0.1.0 has no explicit header
flag (it emits the first row either way); its "header present" is its own `header_like(first
row, next rows)` test, the one its structure rules use. sieve 0.2.0's is `sniff().has_header`.
This is also a reachable subset, not the full test set, so the numbers are not comparable with
the paper's tables.

sieve 0.1.0's `load()` output differs from the no-repair baseline on 8 of the 800 files: 5 from
the stray-quote repair (2 read better, 2 worse because text after a closing quote is kept as
literal text, 1 unreadable either way), 1 padded trailing cell (neutral) and 2 headers whose
empty trailing column name is dropped (better or neutral). sieve 0.2.0's `load()` output
differs from 0.1.0's on 25 files, all through the dialect: its dialect answer changed on 29
files, of which 22 now match the annotation, 1 no longer does (a tab-delimited file annotated
with quote char `"`, which occurs there only inside two fields; `load()` reads it as before)
and 6 are wrong either way. The file list and labels are in `harness/external/`; the downloaded
files are not redistributed (`harness/external_fetch.py` fetches them); per-file results are in
`results/external/`.

## Known limitations

- **`load()` still decides the header with 0.1's rule.** `sniff().has_header` (94.4% on the 89
  blind labels) is not used by `load()`: its structure stage keeps 0.1's table-level
  `header_like()` test (67.4% on the same labels, as a first-record answer), because the
  multi-row-header and second-table rules and the Pollock scores depend on it. Moving the new
  cues into that stage would be a separate experiment, gated on Pollock. Pollock tests headers
  mainly through `file_no_header`.
- **Glued header names**: when the header row loses a separator, two column names are glued
  (`QtyPRODUCTID`). A header has no column profile to arbitrate, every cut gives two words, so
  sieve leaves it. 5 Pollock files (9.47 each); DuckDB's script is given the column names.
- **Held-out-only singletons**: the space-delimited file (7.88) and the `'`-quoted file (8.55).
  (0.1.0's third, the three multitable files at 9.96 each, came from a dropped backslash; 0.2.0
  scores them 10.)
- **One case found by the unit tests**, kept as a strict expected failure: an unrepairable row
  (a date and a number glued) can look like the header of a second table and the table is cut
  there. (0.1.0's second, a wrong quote char when every quoted field holds exactly one
  delimiter, passes since 0.2.0: a quote char must enclose a field.)
- **NUL bytes on Python 3.10 and earlier**: the csv module there rejects a NUL byte, and
  `load()` raises `csv.Error` on such a file (as 0.1.0 did); `sniff()` does not raise but can
  miss the quote char. Python 3.11 and later read these files.
- **The "no delimiter" answer** is only weighed against a space-delimited reading: a one-column
  list whose values hold commas or semicolons in some records is read as delimited (the CSV
  Wrangling annotations mostly agree), and a file that contains U+E000 in its first 64 KB is
  never read as one column.
- **Single source table**: the evidence beyond Pollock for the repairs is the external dialect
  check, 23 synthetic cases (`harness/synthetic/`) and 41 unit tests that apply Pollock's
  pollution types to a generated 7-column table. That is a small amount of evidence; a second
  polluted source table would be the natural next test.
- **Throughput**: 55 files/s in one Python process (0.1.0: 59 in the same interleaved run),
  against 1,209 for DuckDB's script. The dialect grid is about two thirds of the time on the
  Pollock files.

## How it works

1. **Decode**: BOM sniff, then strict UTF-8, cp1252, latin-1.
2. **Dialect**: a grid over delimiter x quote x escape x skipinitialspace; each candidate parse
   of a 64 KB sample is scored as pattern consistency x share of typed cells (the CleverCSV
   formulation). Since 0.2.0, candidates need usage evidence: "no quote" is a candidate, a
   quote char is tried only if it encloses a field, `\` only if it precedes the delimiter or
   the quote char, and a tie keeps the simpler dialect unless the added character changes the
   parse. URLs and clock times are masked before scoring, "clean text" cells are single-spaced
   words (a comma only under `,` or quoting), and a "no delimiter" reading competes with a
   space-delimited one.
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
6. **`sniff()`** reports the dialect and a first-record header test: not a header when the
   first record repeats a cell, is a `#` comment, a title over a wider table or a key/value
   line; a header when some column contrasts a text first cell with typed values below; in
   all-text tables, a per-column vote on whether the first cell stands out from the cells
   below (by category, letter case and spacing, or length), as csv.Sniffer's vote but over
   shapes and categories.

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
make test          # 96 tests: 95 pass, 1 strict expected failure (the limitation above)
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
  copy of the package, kept equal to `sieve/` by a test, so it now holds 0.2.0); the Pollock PR
  described in docs/SUBMISSION.md adds these files as of 0.1.0 (commit `22cf0ba`).
  `sut/docker-compose.service.yml` is its `docker-compose.yml` service block.
- `results/`: the end-to-end Pollock run of 0.1.0 (`pollock-e2e/`), the SHA-256 of every
  0.2.0 output file, and the per-file external check results (0.1.0's in
  `external.ours_sieve-0.1.0.tsv`). `results.tsv`: every scored run.
- `docs/`: [SUBMISSION.md](docs/SUBMISSION.md), [benchmark-notes.md](docs/benchmark-notes.md),
  [error-profile.md](docs/error-profile.md). [EXPERIMENTS.md](EXPERIMENTS.md): the worklog.

## License

Apache-2.0 ([LICENSE](LICENSE)). Two parts come from other projects under the MIT License:
`sut/sieve/sieve-bench.py` is adapted from Pollock's `sut/pycsv/pycsv.py` (Copyright (c) 20222
Gerardo Vitagliano, as written in Pollock's LICENSE; the notice is in
[sut/LICENSE-Pollock](sut/LICENSE-Pollock)), and `harness/external/manifest.tsv` lists file
URLs and dialect annotations from the CSV Wrangling repository
(https://github.com/alan-turing-institute/CSV_Wrangling, Copyright (c) 2018 The Alan Turing
Institute, MIT License; the notice is in
[harness/external/LICENSE-CSV_Wrangling](harness/external/LICENSE-CSV_Wrangling)). The CSV
files themselves are not included.

## Credits

sieve's dialect detection builds on the CSV Wrangling paper: G.J.J. van den Burg, A. Nazabal
and C. Sutton, "Wrangling messy CSV files by detecting row and type patterns", Data Mining and
Knowledge Discovery 33, 1799-1820 (2019). The dialect score is its pattern x type formulation;
the escape-evidence rule, the tie rules and the URL masking follow CleverCSV, the paper's
implementation (https://github.com/alan-turing-institute/CleverCSV, MIT License), reimplemented
here (no CleverCSV code is included). The paper's annotated test set and code
(https://github.com/alan-turing-institute/CSV_Wrangling, MIT License) are the benchmark of the
CSV Wrangling section and the external check.
