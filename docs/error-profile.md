# Failure profile of the baselines and of the no-repair starting point

Written before any row repair existed (experiment 0 in EXPERIMENTS.md). It is the map the
experiments worked from; sieve's own remaining losses are in README.md and EXPERIMENTS.md.

Tools: `harness/published.py --sut S --families` (the authors' committed per-file results),
`harness/taxonomy.py --variant S` (symptom signature of every losing file, from our reproduced
outputs), `harness/worst.py --variant S --files ...` (loaded-vs-expected diff).
Our reproduced CleverCSV 0.7.4 and DuckDB 1.2 (duckdbparse) outputs score **identically to
the published per-file results on all 2,290 files**, so the symptom analysis below is the
analysis of the README rows. Losses are in score points: simple loss = sum over files of
(10 - score10) / 2290; weighted loss = sum of (10 - score10) * normalised weight.
Symptoms: HDR = first row differs (synthetic `col_0..` names / not-joined multi-row header /
other); ROWS+-k = loaded row count minus expected; WIDE/NARROW/PADDED/ALTERED = unmatched
loaded rows wider / narrower / null-padded / same width but content changed; CELLS = records
all right, only the raw cell multiset differs (e.g. one extra `''`).

Two facts about the metric shape everything below (docs/benchmark-notes.md):
* records are compared as the concatenation of normalised cells, so a merged pair of cells or
  one extra empty cell does NOT break the record - only the raw cell multiset notices;
* 83 of 84 source rows have an empty last column (Comments), so dropping *any* one empty cell
  of a row_more_sep row restores both the record and the cell multiset exactly.

## 1. DuckDB 1.2 (duckdbparse) - 9.9615 / 9.5997 - told the true dialect and header

Simple loss 0.0385, weighted loss 0.4003. 1,428 of 2,290 files lose points.

| family | losing / n | simple loss | weighted loss | what went wrong (signature: files) |
|---|---|---|---|---|
| file_no_header | 1/1 | 0.0013 | **0.3206** | HDR:synthetic ROWS+1 - the script writes the parameter column names `col_0..col_8` as a header row, so header F1 = 0 and the first data row falls out of the record set. 80% of DuckDB's weighted loss is this one harness artefact. |
| file_multitable_less/same/more | 3/3 | 0.0021 | **0.0702** | ROWS+83: the second table is appended (with its own header) instead of stopping after the first. |
| row_extra_quote | 756/756 | **0.0206** | 0.0001 | PADDED 294 (row cut at the stray quote and null-padded), ROWS-1 ALTERED 182 (stray quote swallows the next line), ALTERED 213, ROWS-1 PADDED 40, ROWS-2 27. |
| row_less_sep | 581/672 | **0.0099** | 0.0019 | PADDED 426 (merged cell kept, row null-padded -> normalisation of merged date/number/money differs), ALTERED 72, CELLS 83 (merged cell only costs the cell multiset). |
| row_field_delimiter | 83/84 | 0.0025 | 0.0002 | PADDED 83: the space-delimited row lands in column 1 and is null-padded. |
| file_quotation_char_0x27 | 1/1 | 0.0009 | 0.0048 | ROWS-14 ALTERED 28: `'` quote with apostrophes in the text. |
| file_field_delimiter_0x20 | 1/1 | 0.0010 | 0.0021 | ALTERED 49: space delimiter, unquoted multi-word cells split. |
| file_escape_char_0x00 / 0x5C | 2/2 | 0.0001 | 0.0004 | ALTERED 6 / 1: unescaped `"` inside quoted cells. |
| row_more_sep | 0/756 | 0 | 0 | 9 declared columns + `strict_mode=False`: the extra (empty) trailing field is dropped - exact by the empty-Comments fact above. |

**What costs DuckDB its 0.04 simple**: row_extra_quote 0.021 (54%), row_less_sep 0.010 (26%),
row_field_delimiter 0.0025, and 0.0055 of file-level singletons.
**What costs DuckDB its 0.40 weighted**: file_no_header 0.321 (80%), the three multitable
files 0.070 (18%), everything else 0.010.

## 2. CleverCSV 0.7.4 - 9.1931 / 9.4539 - encoding given, dialect sniffed

Simple loss 0.8069, weighted loss 0.5461. 2,279 files lose points.

| family | losing / n | simple loss | weighted loss | what went wrong |
|---|---|---|---|---|
| row_extra_quote | 756/756 | **0.7762** | 0.0037 | 441 files ROWS-10+ (swallowed: the stray quote opens a field that runs to the file end or the next quote many lines later), 225 files HDR:other + WIDE x10+ (the sniffer flips the quote / escape choice for the whole file because of one stray quote), 63 ROWS-3..9. |
| file_preamble | 1/1 | 0.0013 | **0.1946** | HDR:other ROWS+2: preamble + blank row emitted as rows 0-1. |
| file_field_delimiter_0x2C_0x20 | 1/1 | 0.0036 | **0.1891** | HDR:other ALTERED x83: `, ` split on `,` without skipping the space -> every cell has a leading space (raw cells) and quoted cells keep their quotes. |
| file_header_multirow_2/3 | 2/2 | 0.0027 | 0.0652 | HDR:not-joined ROWS+1/+2. |
| file_multitable_* | 3/3 | 0.0021 | 0.0701 | ROWS+83: second table appended. |
| file_quotation_char_0x27, file_escape_char_0x00 | 2/2 | 0.0040 | 0.0188 | quote/escape sniffed wrong -> HDR:other, WIDE x10+. |
| row_less_sep | 672/672 | 0.0113 | 0.0021 | NARROW 498 (merged cell), CELLS 166, HDR:other 8 (header row merged). |
| row_field_delimiter | 84/84 | 0.0033 | 0.0002 | NARROW 83 (space row read as 1 cell), HDR 1. |
| row_more_sep | 756/756 | 0.0013 | 0.0002 | CELLS 747 (extra `''` kept), HDR:other 9 (header row). |

## 3. DuckDB 1.2 auto-detect (duckdbauto) - 9.0213 / 8.4400 (published 9.075 / 8.439)
Everything above plus: type inference rewrites cells on every file (ALTERED x3..9 on
`source.csv` itself: times / dates re-rendered), so every file loses a little; row_more
(0.286) and row_less (0.243) lose whole rows under `ignore_errors`; no_header 0.416,
record_delimiter_0xA 0.342, preamble 0.210, 0x3B 0.169 weighted. Reproduction gap: 69
row_extra_quote files (release 1.2.2 vs the `--pre` build the authors used).

## 4. c0-csvsniff (sieve's no-repair baseline, bytes only) - all 9.7254 / 9.9843; dev 9.7245 / 9.9911

Simple loss 0.2746, weighted loss 0.0157. The structure rules already take every file-level
T file to 10.0 except the multitable trio (9.96: see escape below), so weighted is 0.016 from
10 - **but those rules were written with all 22 file-level files in view (held-out included);
held-out is not an independent test of them.**

| family (all 2,290) | losing / n | simple loss | weighted loss | signature: files |
|---|---|---|---|---|
| row_extra_quote | 756/756 | **0.1959** | 0.0009 | ROWS-10+ (swallowed) 209 files = 0.179; ALTERED 173, WIDE 136, NARROW 122, ROWS-1 WIDE 82, ROWS-3..9 20, HDR 11 |
| row_field_delimiter | 84/84 | **0.0644** | 0.0047 | ROWS-10+ (swallowed) 73 = 0.062: the space row's mid-cell quotes open fields that run for many lines |
| row_less_sep | 672/672 | 0.0114 | 0.0022 | NARROW 426, CELLS 166, ALTERED 47, WIDE 25, HDR 8 (header row) |
| file_quotation_char_0x27 | 1/1 | 0.0006 | 0.0036 | ALTERED x10+ WIDE x10+ (apostrophes inside `'`-quoted text) |
| file_field_delimiter_0x20 | 1/1 | 0.0009 | 0.0019 | WIDE x10+ (unquoted multi-word cells split on space) |
| row_more_sep | 756/756 | 0.0013 | 0.0002 | CELLS 747 (extra `''` kept), HDR 9 |
| file_multitable_* | 3/3 | 0.0000 | 0.0018 | ALTERED 1 each: escape `\` chosen for the file, eats the `\` of `8\'9""` in source row 13 |
| file_escape_char_0x00 / 0x5C | 2/2 | 0.0001 | 0.0004 | unescaped / backslash-escaped quotes |

## 5. The headroom map (what 10.0 requires, by pollution)

| pollution | c0 loss (simple / weighted, all) | DuckDB-parse loss | CleverCSV loss | what a 10.0 loader must do (from bytes only) |
|---|---|---|---|---|
| row_extra_quote (756) | 0.196 / 0.001 | 0.021 / 0.000 | 0.776 / 0.004 | notice the one record whose quoting breaks the file's width / line structure, re-parse that physical line with the offending quote as a literal character (expected keeps it: `"CC-9259`) |
| row_field_delimiter (84) | 0.064 / 0.005 | 0.0025 / 0.000 | 0.003 / 0.000 | per-row dialect: re-split the odd row on its own delimiter (quote-aware), then merge surplus tokens into the text columns the profile says take spaces |
| row_less_sep (672) | 0.011 / 0.002 | 0.010 / 0.002 | 0.011 / 0.002 | split the merged cell of the (W-1)-wide row where prefix / suffix fit the adjacent columns' type profiles (header row too) |
| row_more_sep (756) | 0.001 / 0.000 | 0 / 0 | 0.001 / 0.000 | drop the one surplus cell (empty) of the (W+1)-wide row |
| file_no_header | 0 / 0 | 0.001 / **0.321** | 0 / 0 | do not invent a header |
| file_multitable (3) | 0.000 / 0.002 | 0.002 / **0.070** | 0.002 / 0.070 | stop at the second table's header; do not pick an escape char it does not need |
| file_preamble, header multirow, `, ` | 0 / 0 | 0 / 0 | 0.008 / 0.45 | preamble skip, header-stack join, skipinitialspace |
| quote / escape / space-delimited singletons (4) | 0.002 / 0.006 | 0.002 / 0.007 | 0.004 / 0.02 | quote-char and escape evidence per file; profile-guided merge for space delimiter |

Ambiguity to measure before chasing (possible hard ceiling): merged cells whose split point
is not determined by type profiles (two adjacent free-text columns: ProductType |
ProductDescription), and the space-delimited file / rows where an unquoted multi-word text
cell sits next to another text column.
