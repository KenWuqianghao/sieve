# Experiments

The worklog behind the numbers in the README: every experiment in the order it was run (the
Pollock experiments 0-7 on 2026-09-24, in five rounds; the dialect round 8, for 0.2.0, on
2026-09-24 and 25), kept or dropped, with its numbers. Scores are Pollock simple /
weighted from the unmodified upstream `evaluate.py` on the 1,200-file dev split unless noted.
Each scored run is a row of [results.tsv](results.tsv) (columns: time, round, variant, split,
simple, weighted, the six group means T S L M Q R, files/s, notes).

Each experiment was a copy of the current loader with one change (`c1-strayquote`, `c2-rowdelim`,
...; the labels H1, H2, ... are the hypotheses). A kept change became the new `sieve/loader.py`;
the comments in the loader still name the experiment that introduced each stage. The
no-repair starting point is kept as `harness/baseline/c0_csvsniff.py`.

**Acceptance rule**, fixed before experiment 1: dev simple and dev weighted both at least the
current best, at least one of them strictly higher; no group mean down by more than 0.002;
at least 20 files/s. A single-step gain above 0.3 on dev would have triggered a re-read of the
diff for anything specific to Pollock's source table. The robustness change H2b was allowed to
lose at most 0.0005 on dev, and the speed change H7 had to leave every output byte-identical.
The held-out split (1,090 files) was scored once, after five accepted changes, and only
reported. The external dialect check (800 CSV Wrangling files, README) was run after decisions,
report-only, and never used to tune.

Groups: T table-level (7 dev files), S dialect singletons (5), L row_less_sep (352),
M row_more_sep (396), Q row_extra_quote (396), R row_field_delimiter (44).

## Summary

| # | experiment | change | dev simple | dev weighted | group that moved | files/s | verdict | why |
|---|---|---|---|---|---|---|---|---|
| 0 | c0-csvsniff | csv module + dialect grid + structure rules, no row repair | 9.7245 | 9.9911 | T 10.0000, S 9.9403, L 9.9623, M 9.9969, Q 9.3850, R 8.3582 | 77.2 | baseline | |
| 1a | c1 v1: stray quote, also triggered by row width | | 9.9255 | 9.9917 | L 9.9623 -> 9.9555 | 71.0 | dropped | 154 row_less_sep files worse (group drop 0.0068 > 0.002) |
| 1 | c1-strayquote (H1) | a quote that breaks the record structure is read as a literal | 9.7245 -> 9.9275 | 9.9911 -> 9.9921 | Q 9.3850 -> 10.0000 (396/396) | 71.5 | kept | 396 files up, 0 worse |
| 2 | c2-rowdelim (H2) | a row written with its own delimiter is re-split | 9.9275 -> 9.9877 | 9.9921 -> 9.9968 | R 8.3582 -> 10.0000 (44/44) | 68.8 | kept | 44 up, 0 worse |
| 3 | c3-lesssep (H3) | a lost separator is re-inserted where both halves fit their columns | 9.9877 -> 9.9978 | 9.9968 -> 9.9988 | L 9.9623 -> 9.9970 (350/352) | 56.3 | kept | 350 up, 0 worse; the external check then showed 4 real files read worse |
| 4a | c4 v1: gates with a whole-row typicality floor | | 9.9951 | 9.9986 | R 10.0000 -> 9.9264, L -> 9.9967 | 52.1 | dropped | blocks every repair of the source table's least typical row |
| 4 | c4-gates (H2b) | comment-marker, dominant-width and per-typed-column typicality gates on the separator repairs | 9.9978 (=) | 9.9988 (=) | none (0 files differ) | 56.0 | kept | synthetic guards 13/13 (c3: 10/13); the 4 worse external files read as before |
| 5 | c5-moresep (H4) | the one surplus empty cell of a W+1 row is dropped | 9.9978 -> 9.9989 | 9.9988 -> 9.9990 | M 9.9969 -> 10.0000 (396/396) | 50.2 | kept | 396 up, 0 worse; held-out check after this |
| 6 | c6-fast (H7) | profiled hot spots removed; packaging, tests, Pollock SUT | = | = | outputs byte-identical on 2,290 files | 48.0 -> 67.2 | kept | identity change |
| 7 | c7-escape (H5) | `\` is an escape candidate only with evidence | 9.9989 (=) | 9.9990 (=) | 1 file's output changed, same score | 73.8 | dropped | neither dev score rose |
| 8 | dialect round (d1-d5), sieve 0.2.0 | a new dialect grid developed on CSV Wrangling, plus `sniff()` | 9.9989 (=) | 9.9990 (=) | all files: T 9.9907 -> 10.0000 (3 held-out multitable files) | 55 (0.1: 59) | kept (0.2.0) | Pollock no worse on any group; CSV Wrangling held-out 94.51 -> 97.72 |

Final, all 2,290 files: **9.9971 / 9.9922** (dev 9.9989 / 9.9990, held-out 9.9952 / 9.9854);
DuckDB 1.2 given the dialect: 9.9615 / 9.5997; c0: 9.7254 / 9.9843.

## 0: harness, baselines and the no-repair floor

The harness scores a loader with Pollock's own `evaluate.main()`, unchanged, on a directory
shaped like the Pollock root (`harness/run.py`, `harness/official_eval.py`); loaders get the
file's bytes only. Baselines run through Pollock's own SUT scripts with only their container
paths re-rooted (`harness/run_sut.py`). The dev / held-out split was drawn once (1,200 /
1,090, stratified by pollution family, seed 20260922; `harness/make_splits.py`).

Reproductions on all 2,290 files (README in brackets): duckdbparse 9.9615 / 9.5997 (9.961 /
9.599, 0 files differ); CleverCSV 9.1931 / 9.4539 (exact, 0 files differ); Python csv on 3.11
9.7242 / 9.4365 (9.721 / 9.436; 450 files differ from 3.10, net +0.003); pandas 1.5.3 9.8848 /
7.9090 (9.895 / 9.431; since pandas 1.5, `delimiter=None` is no longer sniffed with the C
engine, so 4 delimiter files score 1.0, and `file_field_delimiter_0x3B` carries 18.7% of the
weight; pandas 3.0.6 gives the same per file); DuckDB auto 9.0213 / 8.4400 (9.075 / 8.439; 69
row_extra_quote files differ, release 1.2.2 vs the paper's pre-release).

c0-csvsniff: the `csv` module behind a dialect grid (delimiter x quote x escape x
skipinitialspace, scored as pattern consistency x typed-cell share) and structure rules
(preamble, multi-row header, second table). All files 9.7254 / 9.9843, dev 9.7245 / 9.9911,
held-out 9.7263 / 9.9776, 77 files/s. The weighted score is already close to 10 because the
structure rules cover the heavily weighted file-level pollutions; those rules were written
with all 22 file-level files in view, so held-out is an independent test only for row-level
files.

Findings that shaped what followed (`docs/error-profile.md`):
- The README's leading row, DuckDB 1.2, is handed the true delimiter, quote, escape, skip
  count and column names; 80% of its weighted loss (0.321 of 0.400) is `file_no_header`, where
  its script writes `col_0..col_8` as a header.
- Every file is a pollution of one 83 x 9 table, so no rule may encode that table.
- Records are compared as concatenated normalised cells, so merged or extra empty cells cost
  little; the simple score is decided by row-level repair, the weighted score by about ten
  file-level singletons.
- Dev loss of c0: row_extra_quote 0.203 of 0.276 simple.

## 1: stray quote as a literal (H1): kept

`repair_stray_quotes`: records whose quoting is broken (a strict-mode csv error, or a record
spanning several physical lines in a file whose records take one line) have their first
physical line re-parsed with one field-opening quote at a time made literal. A variant is
accepted when that line parses strict-clean to exactly W fields (W = modal width) and it lowers
the number of broken records in a 200-line window. Caps: 20 broken records per file, 16 quote
positions per line.

Dropped first version (1a): the repair was also triggered by width alone. Dev 9.9255 / 9.9917,
but 154 row_less_sep files got worse (L 9.9623 -> 9.9555): a clean narrow row was padded to W
by un-quoting a description with exactly one comma. A clean one-line row of the wrong width is
a separator problem, so width alone no longer triggers.

Result: 9.7245 / 9.9911 -> 9.9275 / 9.9921. Q 9.3850 -> 10.0000 (396/396 perfect), no other
group moved, 396 files up, 0 worse, 71.5 files/s. On all 396 dev Q files exactly one candidate
reaches the best count (0 ties). Two defects were fixed before the recorded run, both
score-neutral: `str.splitlines()` splits on characters the csv module does not (now
`io.StringIO(newline="")` lines), and a quadratic re-check (now bounded to the window).

External check (first run): sieve's dialect and header results are c0's (the sniffer did not
change); `load()` differs from c0 on 5 of 800 files: 2 read better (literal quotes inside HTML
or quoted words kept), 2 worse (text after a closing quote is now literal), 1 garbage either
way. Recorded, not tuned on.

## 2: per-row delimiter (H2): kept

Diagnosis first: under the comma dialect a space-delimited row parses as one cell, and the
structure rules then took that one-cell row for the header of a second table and cut the file
there. `repair_row_delimiters`: a one-line record narrower than W that splits quote-aware on
another delimiter into at least W clean fields (no unquoted field containing the file
delimiter) is re-split. Tokens are assigned to the W columns by a dynamic programme over split
points that maximises the log-probability of each group's shape under this file's per-column
profile; a quoted token is a whole field. Gates: at least 5 profile rows, W >= 3, at most one
column with a shape never seen there; the first record needs exactly one admissible split, a
W-wide next record and a header-like result.

Ambiguity measured before the run: all 44 dev rows found (0 triggers on the other 1,156 files);
25 split into exactly W tokens, 19 need merges; with the quoted-token rule 0 ties (16 of 44 tie
on shape alone). Result: 9.9275 / 9.9921 -> 9.9877 / 9.9968; R 8.3582 -> 10.0000 (44/44), 44
files up, 0 worse, 68.8 files/s.

## 3: merged cells (H3): kept

`repair_merged_cells`: a one-line record narrower than W, or W wide with a quote inside an
unquoted field (a quoted field that lost the separator in front of it), gets the one separator
insertion whose strict-clean W-field result fits this file's per-column naive-Bayes profile
(shape, first and last character class) uniquely best, with every column's shape seen there.
A header-like first record has no profile: it is repaired only when exactly one insertion
leaves no empty cell and no quote character. Ties are left alone.

Ambiguity first: of 327 dev data rows, the shape-only profile tied on 31 and was wrong on 2;
with the character classes 327/327 unique and correct. Of 3 header rows, 1 is unique and 2
(`QtyPRODUCTID`, `PriceProductType`) are genuinely ambiguous and left alone. A case-boundary
rule would split them but is not generic. Result: 9.9877 / 9.9968 -> 9.9978 / 9.9988; L 9.9623
-> 9.9970 (350/352), 350 files up, 0 worse, 56.3 files/s.

External check after H2 and H3, written up as a regression: `load()` differs from c1 on 7 of
800 files. H2 changed 3, all worse: free-text lines (a label row in a `;` file, `#` comment
lines in a `|` file, a `#` comment above a header that was re-split and then joined into the
header) were re-split on spaces. H3 changed 4: 2 padded a missing trailing cell (neutral), 1
space-aligned numeric file got one more empty cell (garbage either way), 1 ragged word list got
an empty cell prepended (worse). No rule was changed after reading these files; the fix had to
come from general principles and be checked on Pollock dev and on synthetic cases.

## 4: repair gates (H2b): kept

Synthetic cases first (`harness/synthetic/cases.py`, tables generated for the purpose, neither
Pollock's nor the external files): 13 guard cases that must load exactly as c0 (comment lines in
typed, text, pipe and semicolon files, a commented-out header, title and label rows, ragged
word lists, space-aligned text, a free-text note) and 4 repairs on non-Pollock tables. c1
passed 13/13 guards, c2 and c3 10/13, failing in the same way as the external regressions.

Gates on the H2 re-split and the H3 insertion: (a) no repair of a line starting with a comment
marker (`#`, `//`, `%`, `--`); (b) W must be the width of at least half of the non-blank
records; (c) in every typed column (at least half of the file's own values typed), the repaired
cell must score at least the leave-one-out score of that column's least typical ordinary cell;
a file with no typed column gets no repair. Ablation on the guards: typicality alone fails 1,
the comment gate alone fails 1, width alone fails 3, all three pass 13/13.

Dropped first version (4a): a whole-row leave-one-out floor. Dev 9.9951 / 9.9986, R 43/44, L
347/352: it blocked every repair of the source table's least typical row (a product type
ending in `.`). A rank rule at the extreme rejects the least typical genuine row by
construction, so the test moved to typed columns only, where that row is ordinary.

Result: 9.9978 / 9.9988, identical to c3 (0 files differ), 56.0 files/s. External (run once
after the decision): `load()` differs from c1 on 1 of 800 files (c3: 7); all 4 worse-reading
files read as before. The comment-marker gate uses the conventional comment prefixes of CSV
tools, but the idea came up while reading the external regression, so the external set is not
an independent test of that one gate.

## 5: surplus separator (H4): kept

`repair_extra_cells`: a one-line record exactly one cell wider than W with an empty unquoted
field loses one such field. A data row takes the unique best candidate under the per-column
profile, all shapes seen, plus the H2b gates; a header-like first record only when every drop
gives the same row. The row is re-serialised in the file's dialect and kept only if it
re-parses to exactly the chosen row. Ambiguity first: 393/393 dev data rows unique and correct,
3/3 header rows single-candidate. Two synthetic cases were added (an optional trailing column,
and a W+1 row whose empty cell is genuine); both pass.

Result: 9.9978 / 9.9988 -> 9.9989 / 9.9990; M 9.9969 -> 10.0000 (396/396), 396 files up, 0
worse, 50.2 files/s.

**Held-out check** (after five accepted changes; one run, report-only): all 2,290 files
9.9971 / 9.9922 at 48.5 files/s; dev 9.9989 / 9.9990; held-out 9.9952 / 9.9854 (c0 9.7263 /
9.9776, duckdbparse 9.9586 / 9.8439). Against c0: 2,263 files up, 0 down. Against duckdbparse:
higher on 1,427 files, lower on 5 (`row_less_sep_row0_col1..5`, glued header names; DuckDB's
script is given the column names). Held-out losses: 3 glued-header files and the held-out-only
singletons (space delimiter 7.88, `'` quote 8.55, the three multitable files 9.96 each, escape
0x00 9.74, 0x5C 9.96). External: dialect and header unchanged (full dialect 95.2%, messy
93.1%, header 67.4%); `load()` differs from c0 on 8 of 800 files: H1's 5, 1 neutral H3 pad and 2
H4 header rows whose empty trailing column name is dropped (better or neutral).

## 6: speed and packaging (H7): kept, identity

Profiled on 300 dev files: the dialect grid was 38% of the time (typing every cell of every
trial parse), `header_like` 25%, tokenising 12%. Output-preserving changes: distinct cells
counted once and typed with one combined regex; `header_like` skips typed cells and stops once
the answer is fixed; the tokenizer jumps to the next quote with `str.find`; per-file caches of
cell features (cleared in every `load()` call); profiles count distinct values; leave-one-out
floors computed per distinct feature triple; the sniffer skips trial parses that provably
equal an earlier one. Gate (`harness/speed.py`): 2,290/2,290 serialised outputs byte-identical
to c5; 0 of 800 external outputs changed; synthetic results identical. 48.0 -> 67.2 files/s
(second measurement 45.3 -> 64.7), one process, `load()` time.

Packaging: `pyproject.toml` (distribution `sieve-csv`, no dependencies), `sieve.load` /
`sieve.load_bytes`, the CLI, and the pytest suite (11 API / CLI / packaging tests, the synthetic
cases as tests, 41 cases applying each Pollock pollution type to a generated 7-column table).
The tests found two limitations, kept as strict expected failures: an unrepairable merged row
(a date and a number glued) can look like the header of a second table, which cuts the table
there; and when every quoted field holds exactly one delimiter, the wrong quote character can
give a perfectly regular table that the dialect score prefers. Output byte-identical on Python
3.8.20, 3.10.5 and 3.11.15.

End to end through Pollock's own flow: `sut/sieve/` (script, Dockerfile, the package) built
and run with `docker compose up sieve-client` on a copy of the Pollock root with the service
added: 2,290 files x 3 repetitions, 0 application errors, outputs byte-identical to the
harness's, 54.2 files/s by the script's own timing (file read included). Then upstream
`evaluate.py` with `sieve` in `SUT_ORDER`: 9.997100 / 9.992176, next to the published rows
(duckdbparse 9.961516 / 9.599662, sqlite 9.955135 / 9.375923).

## 7: escape on evidence (H5): dropped

`\` is scored as an escape candidate only when the sample holds it before the quote character,
the delimiter or itself (c7-escape). Ambiguity first: 1,197 of the 1,199 dev files that
contain `\` already pick no escape; `file_escape_char_0x5C` picks `\` with evidence
(unambiguous); `file_escape_char_0x00` picks `\` without evidence, by a 0.1% type-score edge
(deleting the backslash of `\'` turns a cell into the plain-words type). So the rule changes
one dev file, whose row 13 is broken either way (an unescaped quote inside a quoted field):
9.7416 before and after. Dev 9.9989 / 9.9990, equal on both scores, so the acceptance rule did
not take it. Synthetic: 4 escape cases written before the run; c7 passes 4/4, sieve 3/4
(`esc_literal_backslash_apos`, kept as an expected failure).

External (report-only, c7 vs c6): escape 99.1 -> 99.6%, full dialect 95.2 -> 95.6%, messy
93.1 -> 93.7%, quote 98.0 -> 97.9%; 3 files read better (`\r\n` and `\n` sequences in text keep
their backslash), 1 worse (a one-column code file where the sniffer falls back to the `'`
quote; garbage either way). Not in the loader; listed under the known limitations.

## 8: dialect round, d1-d5 (sieve 0.2.0): kept

A separate round on dialect and header detection, developed and scored on the CSV Wrangling
test set instead of Pollock, then gated on Pollock through this repository's harness.

**Setup.** Corpus: the annotated CSV Wrangling test files still downloadable with the
annotated md5 and at most 256 KB, 5,146 files (GitHub 3,594, UKdata 1,552), split with seed
20260924, stratified by source x messy x annotator: dev 3,087 (messy 431), held-out 2,059 (messy
288). Metric: the paper's (exact equality of delimiter, quote and escape; "none" for an unused
character; failures wrong; "messy" = non-standard dialect). Header: 200 dev files labelled
blind under a written protocol (195 decided), tunable; the 89 labels of the external check
test-only. Starting point d0 = sieve 0.1's `sniff()` + `header_like()` extracted unchanged.
Keep rule: dev full and dev messy at least the best, one of them (or header) strictly better,
header not lower by more than one file, no source / annotator slice down by more than 0.3,
at least 50 files/s; a single-step gain above 3 points counts as a suspected leak until
confirmed on held-out. Held-out scored once per five keeps, report-only.

| step | change | dev full | dev messy | dev header (195) | verdict |
|---|---|---|---|---|---|
| d0 | sieve 0.1's detector | 94.62 | 82.60 | 69.2 | start |
| d1 | usage evidence: "no quote" in the grid; a quote char only if it encloses a field; `\` only before the delimiter or quote char; ties keep the simpler dialect unless the added char changes the parse (an escape also needs mid-field evidence) | 96.27 | 89.33 | = | kept (messy +6.73, leak-gated) |
| (d3 on d1) | the stricter clean-text type of d3, tried first on d1 | 97.12 | 89.10 | = | dropped (messy down 0.23: commas inside quoted prose; retried as d3 with a quote clause) |
| d2 | URL (`scheme://`, `www.`) and clock-time masking before scoring | 96.79 | 90.26 | = | kept |
| d3 | clean text = single-spaced words, a comma only under `,` or quoting | 97.41 | 90.26 | = | kept |
| d4 | first-record header test (title / comment / key-value rules, type contrast in any column, all-text column votes) | = | = | 96.9 | kept (header +27.7, leak-gated) |
| d5 | "no delimiter" candidate (0.15 x type score) against a space winner only | 97.76 | 92.81 | = | kept |

d5 variants that let "no delimiter" compete with every delimiter broke 3 to 13 files annotated
`,` (one-column lists with commas in a few records), so it competes with space only. Its
internal sentinel is U+E000 (csv on Python 3.10 rejects a NUL delimiter).

**Held-out checkpoint, run once after d5** (2,059 files): d5 97.72 full / 92.71 messy
(GitHub 96.80, UKdata 99.84), CleverCSV 0.8.5 96.55 / 88.54, csv.Sniffer 87.47 / 67.36, d0
94.51 / 86.11. Header on the 89 test labels: d5 94.4 (84/89), CleverCSV 76.4, csv.Sniffer
76.4, d0 67.4. Both leak gates cleared: the messy gain holds on held-out (+6.60 over d0) and
the header gain on the test labels (+18.0 over CleverCSV).

**Into sieve.** d1, d2, d3 and d5 replace `sniff()` in `loader.py`; d4 is `sieve.sniff()`'s
`has_header` and is not used by `load()` (the structure stage keeps `header_like()`). Two
adaptations for the loader: a file with no quote char is loaded with `"` (the repairs need a
quote char), and the "no delimiter" sentinel never leaves the loader (`sniff()` reports
`None`; `load()` swaps in another absent character if U+E000 occurs after the sample). One
change to the detector: the enclosure test of d1 did not see a field whose quotes are
backslash-escaped (`"2\" pipe, 3m"`), so a file quoting every such field lost its quote char
and escape; the synthetic case `esc_backslash_quotes`, which 0.1 passed, failed. The enclosure
test now also accepts backslash-escaped quotes when backslash-quote occurs. This changed the
output on none of the 5,146 CSV Wrangling files (an equivalence check against the checkpoint
detector, no scoring), so the numbers above stand; `sieve.sniff()` equals the checkpoint
detector on all 5,146 files.

**Pollock, all 2,290 files, report-only** (no tuning in this round):

| | all simple / weighted | dev | held-out | T | S | L | M | Q | R |
|---|---|---|---|---|---|---|---|---|---|
| 0.1.0 (re-run) | 9.9971 / 9.9922 | 9.9989 / 9.9990 | 9.9952 / 9.9854 | 9.9907 | 9.5698 | 9.9961 | 10.0000 | 10.0000 | 10.0000 |
| 0.2.0 | 9.9972 / 9.9939 | 9.9989 / 9.9990 | 9.9953 / 9.9888 | 10.0000 | 9.5698 | 9.9961 | 10.0000 | 10.0000 | 10.0000 |

Outputs differ on 4 files: the three held-out multitable files (9.9599 -> 10: `8\'9"` keeps its
backslash, since `\` is no longer an escape candidate without evidence; the error profile had
put their loss on the escape choice of experiment 7) and `file_escape_char_0x00` (keeps its
backslash, 9.7416 either way, as in experiment 7). No group mean went down. files/s, best of
three interleaved passes: 0.1.0 59.3, 0.2.0 55.2. Synthetic cases: 14/14 guards, 8/8 positives
(0.1.0: 7/8). External check (800 files): full dialect 95.2 -> 97.9, header 67.4 -> 94.4 (not
independent: 478 of the 800 are in the round's dev split; on the other 322, 95.0 -> 98.4).
Unit tests: the two expected failures that 0.2.0 fixes (`esc_literal_backslash_apos`,
`test_uniform_quoted_delimiters_with_damaged_header`) are now ordinary tests; 21 `sniff()`
tests added. The outputs are byte-identical under Python 3.8.20, 3.9.23 and 3.11.15.

## Not attempted

Ranked by the remaining loss and by what the tests found:
- a second-table cut that needs more than one header-like row (the unit-test limitation above;
  Pollock never triggers it);
- the whole-file space delimiter and `'` quote (held-out-only singletons, 0.0021 + 0.0048 of
  the all-files weighted loss);
- (done in round 8: the multitable tail, an explicit header decision for `sniff()`, and the
  quote choice when every quoted field holds exactly one delimiter);
- the first-record header cues inside `load()`'s structure stage (needs a Pollock-gated
  experiment);
- glued header names: measured as ambiguous without a header profile, left as the documented
  ceiling (5 files, 0.0012 simple).
