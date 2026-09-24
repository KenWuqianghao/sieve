"""Pollock-shaped cases on a table that is NOT Pollock's.

Each test applies one of Pollock's pollution types (file-level: dialect, preamble, header,
multitable, encoding; row-level: stray quote, row written with spaces, lost separator, extra
separator) to a small table generated here (its own columns, width 7, values and row count),
and checks sieve against Pollock's convention for the expected table: the pollution undone,
a multi-row header joined with ' ', only the first table, no invented header.
"""
import csv
import io
import random

import pytest

import sieve

HEAD = ["day", "units", "sku", "cost", "category", "summary", "memo"]
CATS = ["garden tools", "kitchen", "bike parts", "office chairs", "lamps", "rain gear"]
WORDS = ["sturdy", "light", "folding", "compact", "steel", "oak", "quiet", "warm", "blue", "large"]


def table(n=36, seed=11):
    rnd = random.Random(seed)
    rows = [HEAD[:]]
    for i in range(n):
        # free text with 0-2 commas (so it is quoted on most rows, as in real exports)
        parts = [f"{rnd.choice(WORDS)} {rnd.choice(WORDS)}" for _ in range(rnd.choice([1, 2, 2, 3]))]
        summary = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
        rows.append([f"{rnd.randint(1, 28):02d}/{rnd.randint(1, 12):02d}/2019", str(rnd.randint(0, 40)),
                     f"KX-{rnd.randint(1000, 9999)}", f"${rnd.uniform(1, 99):.2f}", rnd.choice(CATS),
                     summary, ""])
    return rows


T = table()


def write(rows, delim=",", term="\r\n", quoting=csv.QUOTE_MINIMAL):
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator=term, quoting=quoting).writerows(rows)
    return buf.getvalue()


def lines(rows, **kw):
    return write(rows, **kw).splitlines(keepends=True)


def enc(text):
    return text.encode("utf-8")


# ---------------------------------------------------------------- file level
def test_clean():
    assert sieve.load(enc(write(T))) == T


@pytest.mark.parametrize("delim", [";", "\t", "|"])
def test_field_delimiter(delim):
    assert sieve.load(enc(write(T, delim=delim))) == T


def test_comma_space_delimiter():
    text = "".join(", ".join(f'"{c}"' if "," in c else c for c in r) + "\r\n" for r in T)
    assert sieve.load(enc(text)) == T


@pytest.mark.parametrize("term", ["\n", "\r"])
def test_record_delimiter(term):
    assert sieve.load(enc(write(T, term=term))) == T


def test_trailing_newlines():
    text = write(T)
    assert sieve.load(enc(text.rstrip("\r\n"))) == T
    assert sieve.load(enc(text + "\r\n")) == T


def test_bom_and_legacy_encoding():
    rows = [r[:] for r in T]
    rows[5][4] = "café chairs"
    assert sieve.load(b"\xef\xbb\xbf" + enc(write(rows))) == rows
    assert sieve.load(write(rows).encode("cp1252")) == rows


def test_no_header():
    assert sieve.load(enc(write(T[1:]))) == T[1:]


def test_header_only_and_one_row():
    assert sieve.load(enc(write(T[:1]))) == T[:1]
    assert sieve.load(enc(write(T[:2]))) == T[:2]


def test_preamble():
    pre = "EXPORT" + "," * (len(HEAD) - 1) + "\r\n" + "," * (len(HEAD) - 1) + "\r\n"
    assert sieve.load(enc(pre + write(T))) == T


@pytest.mark.parametrize("k", [2, 3])
def test_multirow_header(k):
    want = [[" ".join([h] * k) for h in HEAD]] + T[1:]
    assert sieve.load(enc(write([HEAD] * k + T[1:]))) == want


@pytest.mark.parametrize("width", [len(HEAD) - 1, len(HEAD), len(HEAD) + 1])
def test_second_table_is_cut(width):
    rnd = random.Random(width)
    names = ["region", "visits", "orders", "returns", "rating", "staff", "share", "stock"]
    second = [names[:width]] + \
             [[rnd.choice(WORDS)] + [str(rnd.randint(1, 999)) for _ in range(width - 1)] for _ in range(12)]
    assert sieve.load(enc(write(T) + write(second))) == T


def test_quote_char_apostrophe():
    # the table written with ' as the quote character
    assert sieve.load(enc(write(T).replace('"', "'"))) == T


# ---------------------------------------------------------------- row level
@pytest.mark.parametrize("row,col", [(4, 2), (9, 4), (17, 0), (25, 3)])
def test_stray_quote_unquoted_cell(row, col):
    raw = lines(T)
    cells = [f'"{c}"' if "," in c else c for c in T[row]]
    cells[col] = '"' + cells[col]  # a stray quote at the start of an unquoted cell
    raw[row] = ",".join(cells) + "\r\n"
    want = [r[:] for r in T]
    want[row][col] = '"' + T[row][col]  # Pollock's convention: the quote is kept as a literal
    assert sieve.load(enc("".join(raw))) == want


@pytest.mark.parametrize("row", [4, 14, 27])  # rows whose summary is quoted
def test_stray_quote_quoted_cell(row):
    raw = lines(T)
    assert f'"{T[row][5]}"' in raw[row]
    raw[row] = raw[row].replace(f'"{T[row][5]}"', f'""{T[row][5]}"')
    want = [r[:] for r in T]
    want[row][5] = '"' + T[row][5]
    assert sieve.load(enc("".join(raw))) == want


@pytest.mark.parametrize("row", [2, 12, 33])
def test_row_written_with_spaces(row):
    raw = lines(T)
    raw[row] = write([T[row]], delim=" ")
    assert sieve.load(enc("".join(raw))) == T


@pytest.mark.parametrize("row,col", [(11, 3), (20, 4), (31, 2), (14, 5), (25, 6)])
def test_lost_separator(row, col):
    raw = lines(T)
    cells = [f'"{c}"' if "," in c else c for c in T[row]]
    raw[row] = ",".join(cells[:col - 1] + [cells[col - 1] + cells[col]] + cells[col + 1:]) + "\r\n"
    assert sieve.load(enc("".join(raw))) == T


@pytest.mark.parametrize("row,col", [(0, 3), (6, 1), (15, 4), (22, 6), (35, 2)])
def test_extra_separator(row, col):
    raw = lines(T)
    cells = [f'"{c}"' if "," in c else c for c in T[row]]
    raw[row] = ",".join(cells[:col] + [""] + cells[col:]) + "\r\n"
    assert sieve.load(enc("".join(raw))) == T


def merge(row, col):
    raw = lines(T)
    cells = [f'"{c}"' if "," in c else c for c in T[row]]
    raw[row] = ",".join(cells[:col - 1] + [cells[col - 1] + cells[col]] + cells[col + 1:]) + "\r\n"
    return enc("".join(raw))


def test_glued_text_cells_are_left_alone():
    # two unquoted text cells glued ("office chairs" + "steel folding"): every cut gives two
    # word strings, so the row is left as parsed (the documented ceiling) and nothing else moves
    out = sieve.load(merge(28, 5))
    assert len(out) == len(T) and out[28] == T[28][:4] + [T[28][4] + T[28][5], ""]
    assert out[:28] == T[:28] and out[29:] == T[29:]


@pytest.mark.xfail(strict=True, reason="known limitation: an unrepairable merged "
                   "row (date + number glued, several equally good cuts) can look header-like "
                   "against the misaligned columns below it, and the second-table rule cuts the "
                   "file there")
def test_unrepairable_row_does_not_cut_table():
    out = sieve.load(merge(5, 1))
    assert len(out) == len(T)


@pytest.mark.xfail(strict=True, reason="known limitation: when every quoted field "
                   "holds exactly one delimiter, the wrong quote char (') splits each of them "
                   "into two and yields a perfectly regular table that matches a header with one "
                   "extra separator, so the dialect score prefers it")
def test_uniform_quoted_delimiters_with_damaged_header():
    rows = [r[:] for r in T]
    for r in rows[1:]:
        r[5] = r[5].replace(",", "") .replace(" and ", ", ")  # exactly one comma, quoted
        if "," not in r[5]:
            r[5] = r[5] + ", too"
    raw = lines(rows)
    raw[0] = ",".join(HEAD[:3] + [""] + HEAD[3:]) + "\r\n"
    assert sieve.load(enc("".join(raw))) == rows
