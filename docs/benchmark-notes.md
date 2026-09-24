# Pollock: how the benchmark scores (read from the code, not the paper)

Source: https://github.com/HPI-Information-Systems/Pollock (MIT), checked out at `upstream/`
(gitignored) or at `$POLLOCK_UPSTREAM`, commit `af36a06`. The scorer is `upstream/evaluate.py`
+ `upstream/pollock/metrics.py` + `upstream/pollock/data_types.py`. **None of them is edited,
nor anything under `upstream/polluted_files/`.**

## The corpus
* `polluted_files/csv/` holds **2,290** files (the paper rounds this to 2,289; the extra one
  is `source.csv`, the unpolluted file, which is scored like any other).
  `polluted_files/clean/<f>` is the expected loading result, `parameters/<f>_parameters.json`
  the true dialect/structure (encoding, delimiter, quotechar, escapechar, row delimiter,
  header_lines, preamble_lines, column_names, n_columns).
* **Every file is a pollution of one source table**: 83 data rows x 9 columns (DATE, TIME, Qty,
  PRODUCTID, Price, ProductType, ProductDescription, URL, Comments), CRLF, comma, `"` quote,
  RFC-4180 doubled quotes, 1 header row. Row 13 of the source contains a literal backslash
  inside a quoted field (`8\'9"" length`) - this single cell is what trips escape sniffers.
  Consequence: a loader must not know this table (no column names, column count 9, row
  count 83, value patterns of this data written into code), or its score says nothing.
* Generator: `upstream/pollute_main.py`. The clean file is the *source table with the
  pollution undone* - e.g. for `row_less_sep` the expected output re-splits the two merged
  cells, for `row_extra_quote` the stray quote is kept as a literal character of that cell
  (`"CC-9259`), for `row_field_delimiter` the space-delimited row is expected as 9 proper cells,
  for `file_header_multirow_k` the k header rows are joined column-wise with a space
  (`DATE DATE`), for `file_multitable_*` only the FIRST table is expected, for
  `file_preamble` the preamble and its blank line are dropped, for `file_no_header` the
  expected first row is the first data row (no invented header).

## Pollution taxonomy (README table + generator), our coarse groups

| group | family (files) | what changes |
|---|---|---|
| T | source (1) | nothing |
| T | file_no_payload (1) | 0-byte file (expected: empty -> all measures 1) |
| T | file_no_trailing_newline, file_double_trailing_newline (1+1) | last record terminator removed / doubled |
| T | file_no_header (1) | header row removed |
| T | file_header_multirow_2, _3 (1+1) | header repeated on 2/3 rows (expected: joined with ' ') |
| T | file_preamble (1) | `PREAMBLE,,,,,,,,` + delimited blank row before the header |
| T | file_multitable_less/same/more (1+1+1) | a second table (8/9/10 cols, own header) appended, no blank line |
| T | file_header_only, file_one_data_row (1+1) | 0 / 1 data rows |
| S | file_field_delimiter_0x3B / 0x9 / 0x20 / 0x2C_0x20 (4) | `;` / tab / space / `, ` everywhere (space: unquoted cells contain spaces) |
| S | file_quotation_char_0x27 (1) | `'` as quote char (cells contain apostrophes) |
| S | file_escape_char_0x5C / 0x00 (2) | quotes escaped `\"` / not escaped at all |
| S | file_record_delimiter_0xA / 0xD (2) | LF / CR line endings |
| L | row_less_sep_rowX_colY (672) | row X lost the delimiter before col Y (cells Y-1,Y merged) |
| M | row_more_sep_rowX_colY (756) | row X got an extra delimiter at col Y (one extra empty cell) |
| Q | row_extra_quoteX_colY (756) | cell (X,Y) got a stray `"` at its start |
| R | row_field_delimiter_X_0x20 (84) | row X delimited by spaces instead of commas |

Row X = 0 is the header row. Groups are defined in `harness/common.py:group()`.

## How a system is scored (evaluate.py / metrics.py)
For each file f the SUT writes `results/<sut>/polluted_files/loading/<f>_converted.csv`, a
plain RFC-4180 CSV (read back with `csv.reader(delimiter=",", quotechar='"', doublequote=True)`,
encoding utf-8-sig, chardet fallback). Ten measures, each in [0, 1]:

1. `success` - 0 only if the output's first line is exactly `Application Error`; an empty
   output counts as success.
2. header precision / recall / F1 - multiset intersection of the **normalised** cells of the
   first row of expected vs loaded (`normalize_cell`: typed canonicalisation - dates via
   dateutil -> `YYYY-MM-DD 00:00:00`, times, ints, floats `str(float)`, booleans incl. `0`/`1`
   -> `0`/`1`, currency `$`+amount, else lowercased string). Note the naming is swapped
   relative to convention: "precision" = |I|/|expected|, "recall" = |I|/|loaded|.
3. record P / R / F1 - multiset over rows 1.. of `"".join(normalised cells)`. **Cell
   boundaries do not matter for records**: an extra empty cell or two merged cells give the
   same record string unless normalisation of the parts differs (e.g. dates, floats, money).
4. cell P / R / F1 - multiset over **all** raw (unnormalised) cells, header included, position-
   free. Extra empty cells cost precision; merged cells cost both sides.
If the expected file is empty all nine non-success measures are 1.0.

Per file the SUT gets `score10(f) = sum of the 10 measures` (0..10).

* **Pollock simple** = mean over files of score10 (evaluate.py: sum over measures of
  the per-measure mean). Every file counts 1/2290, so the 2,268 row-level files dominate.
* **Pollock weighted** = sum_f score10(f) * w_f / sum(w), `w` from `pollock_weights.json`
  (the paper's frequency of each pollution in real-world open-data CSVs). The weight mass is
  extremely concentrated: `file_record_delimiter_0xA` 38.0%, `file_field_delimiter_0x3B`
  18.7%, `file_no_header` 10.6%, `file_preamble` 6.3%, all row_more 6.3%, all row_less 5.6%,
  `file_no_trailing_newline` 4.1%, `file_field_delimiter_0x2C_0x20` 2.3%, header multirow
  2.1%, multitable 3x1.4%; the 756 row_extra_quote files together only 0.16%.
  So **simple is won on row-level repair, weighted on ~10 file-level singletons**.

Official subsets (printed by evaluate.py, NOT used in either score) have regex quirks:
`inconsistent` is `"%row_less.*|row_more"` - the `%` means no row_less file ever matches;
`structural` uses `file_quote.*`, which does not match `file_quotation_char_0x27`. We report
them for completeness but use our own groups (T S L M Q R) and families.

## How a loader plugs in
Upstream: one script per system in `upstream/sut/<sut>/` run in Docker; each reads
`parameters/<f>_parameters.json` via `sut/utils.py:load_parameters` and writes
`<f>_converted.csv` (or `Application Error\n<msg>`). **Crucially, systems get different
amounts of ground truth**:

| script | README row | what it is told from parameters.json | what it detects itself |
|---|---|---|---|
| `duckdbparse` | DuckDB 1.2 (9.961 / 9.599) | delimiter, quotechar, escapechar, skiprows = preamble + header lines, column NAMES (as header), no auto-detect; `ignore_errors`, `null_padding` | nothing |
| `duckdbauto` | DuckDB 1.2 (Auto) (9.075 / 8.439) | nothing | everything (sniffer) |
| `pandas` | Pandas 1.4.3 | encoding, quotechar, escapechar, lineterminator, skiprows=preamble | delimiter (python engine sniff), header=infer; `on_bad_lines='skip'` |
| `pycsv` | Python native csv | encoding | `csv.Sniffer` dialect |
| `clevercs` | CleverCSV 0.7.4 | encoding | CleverCSV sniffer dialect |

So the README leader is DuckDB **with the true dialect and header handed to it**; the
zero-knowledge DuckDB row is 9.075 / 8.439. sieve gets **only the file's bytes**
(`load(data: bytes) -> list[list[str]]`, the harness never passes the name or path), which is
the setting of the duckdbauto row (pycsv and CleverCSV also get the encoding). Scores under
the two settings are not directly comparable, and any write-up must say so.

The harness (`harness/run.py`): writes the loader's rows with `csv.writer` (utf-8,
QUOTE_MINIMAL) to `runs/<variant>/loading/`, builds a directory that looks like the upstream
root for the split (symlinks to `polluted_files/{csv,clean}` of the split's files,
`pollock_weights.json`, `results/<sut>/polluted_files/loading`), and runs `evaluate.main()`
there unchanged (`harness/official_eval.py`; the only touched symbol is `SUT_ORDER`, the list
main() prints). Simple / weighted are read from the `aggregate_results_polluted_files.csv`
that evaluate.py writes. On a split the weights are renormalised within the split (that is
what evaluate.py does with whatever files are in `polluted_files/csv`).
`--split all` also prints dev / held-out numbers aggregated from the same official per-file
measures with evaluate.py's formulas; checked equal to a direct official run on dev (pycsv:
9.7300 / 9.3919 both ways). `harness/published.py` applies the same formulas to the authors'
committed per-file results (`results/global_results_polluted_files.csv`) and reproduces every
README number to 3 decimals.

Baselines are reproduced with the repo's own scripts (`harness/run_sut.py`): the script
source is executed unchanged except that its absolute container paths `abspath(f'/...` are
re-rooted to `runs/_sutroot/<sut>/` (asserted), and `sut/utils.py` is importable first, as
every Dockerfile copies it next to the script.

## Protocol
* dev = 1,200 files (`harness/splits/dev.txt`), stratified by family, seed 20260922
  (`harness/make_splits.py`): L 352, M 396, Q 396, R 44, and 12 of the 22 file-level
  singletons split within T / S (T 7, S 5). held-out = the other 1,090 (`heldout.txt`),
  frozen, **report-only**; it holds 10 file-level types dev does not contain (incl.
  `file_record_delimiter_0xA`, 38% of the global weight, the three multitable files,
  multirow_2, quotation_char_0x27, field_delimiter_0x20). Caveat: all 22 file-level files were
  inspected at the start to write this document and the structure rules of the no-repair
  baseline (c0); the held-out is a clean test only for row-level instances.
* Iterate on dev. Final numbers: `run.py --split all` (official, all 2,290 files).
* Throughput floor: 20 files/s on the corpus, 1 process, measured as files / sum of `load()`
  wall time (reading bytes excluded, writing excluded). Per-file caches must be cleared per
  file (all files share one source table; cross-file memoisation would be a leak of content).
