"""c0-csvsniff: the no-repair baseline (experiment 0 in EXPERIMENTS.md).

Python's csv module behind sieve's dialect + table-structure front-end, without any row
repair. Used as the reference for the synthetic guard cases (tests/test_synthetic.py,
harness/synthetic/check.py): on those files sieve must load exactly what this loader loads.
Input: the file's bytes only. Output: list of rows (first row = header when the file has one;
a headerless file is emitted as-is, since the benchmark expects no invented header). Stages:
  1. decode   BOM sniff (utf-8/utf-16/32), else strict utf-8, else cp1252, else latin-1.
  2. dialect  grid over delimiter x quotechar x escapechar x skipinitialspace, each parsed with
              csv.reader on a sample and scored CleverCSV-style: Q = P * T, where P rewards
              many rows sharing few widths ((1/K) * sum_k N_k (L_k - 1) / L_k, K = number of
              distinct widths) and T is the share of cells matching a known type. Ties prefer
              the conventional choice (',', '"', no escape).
  3. structure  drop blank rows; drop a sparse preamble ended by a blank line; join a stack of
              leading header-like rows (multi-row header) with ' '; cut at the first blank-line-
              separated second table whose first row is header-like.
No row repair: ragged rows are emitted as parsed.
"""
import codecs
import csv
import functools
import io
import re

csv.field_size_limit(1 << 30)

DELIMS = [",", ";", "\t", "|", " ", ":"]
QUOTES = ['"', "'"]
ESCAPES = [None, "\\"]
SAMPLE = 1 << 16

_TYPES = [re.compile(p) for p in (
    r"^$",
    r"^[+-]?\d+$",
    r"^[+-]?(\d+[.,]\d*|\d*[.,]\d+)([eE][+-]?\d+)?$",
    r"^[+-]?\d{1,3}([,. ]\d{3})+([.,]\d+)?$",
    r"^[$€£¥]\s?[+-]?\d[\d,.]*$|^[+-]?\d[\d,.]*\s?[$€£¥%]$",
    r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}$",
    r"^\d{1,2}:\d{2}(:\d{2})?(\s?[aApP][mM])?$",
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?",
    r"^(https?|ftp)://\S+$|^www\.\S+$",
    r"^[\w.+-]+@[\w-]+\.[\w.]+$",
    r"^(true|false|yes|no|null|nan|n/a|na)$",
    r"^[A-Za-z]{1,6}[-_]?\d+$",
    r"^[\w'&().,/ -]+$",  # plain words (CleverCSV counts alphanumeric text as a type too)
)]


def decode(data: bytes) -> str:
    for bom, enc in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                     (codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                     (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            return data.decode(enc, errors="replace")
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


def parse(text, delim, quote, esc, skipsp):
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delim, quotechar=quote,
                           escapechar=esc, doublequote=True, skipinitialspace=skipsp, strict=False))


_STRONG = re.compile("|".join(f"(?:{t.pattern})" for t in _TYPES[1:-1]))
_PLAIN = _TYPES[-1]


@functools.lru_cache(maxsize=1 << 16)
def strong(cell):
    """Typed as something other than empty / plain words (number, date, time, money, url, code...)."""
    c = cell.strip()
    return bool(_STRONG.match(c))


@functools.lru_cache(maxsize=1 << 16)
def typed(cell):
    c = cell.strip()
    return (not c) or strong(c) or bool(_PLAIN.match(c))


def dialect_score(rows):
    rows = [r for r in rows if r]
    if not rows:
        return 0.0
    widths = {}
    for r in rows:
        widths[len(r)] = widths.get(len(r), 0) + 1
    p = sum(n * (w - 1) / w for w, n in widths.items()) / len(widths) / len(rows)
    cells = [c for r in rows for c in r]
    t = sum(typed(c) for c in cells) / len(cells) if cells else 0.0
    return p * t


def sniff(text):
    sample = text[:SAMPLE]
    if len(text) > SAMPLE:  # do not score a torn last line
        cut = max(sample.rfind("\n"), sample.rfind("\r"))
        sample = sample[:cut] if cut > 0 else sample
    best, best_q = (",", '"', None, False), -1.0
    for d in DELIMS:
        if d not in sample:
            continue
        for q in QUOTES:
            for e in ESCAPES:
                if e is not None and e not in sample:
                    continue
                for sp in ((False, True) if d != " " else (False,)):
                    try:
                        s = dialect_score(parse(sample, d, q, e, sp))
                    except csv.Error:
                        continue
                    if s > best_q + 1e-9:  # strict: earlier (conventional) candidates win ties
                        best, best_q = (d, q, e, sp), s
    return best


def is_blank(r):
    return all(not c.strip() for c in r)


def header_like(row, below):
    """A row is header-like when its non-empty cells are untyped text while the rows below have
    typed values in most of those columns."""
    cells = [(i, c.strip()) for i, c in enumerate(row) if c.strip()]
    if not cells or not below:
        return False
    hits = 0
    for i, c in cells:
        col = [r[i].strip() for r in below if i < len(r) and r[i].strip()]
        if not col:
            continue
        col_typed = sum(strong(v) for v in col) / len(col)
        if col_typed >= 0.5 and not strong(c):
            hits += 1
    return hits >= max(1, len(cells) // 2)


def structure(rows):
    # preamble: sparse rows at the top closed by a blank row
    for i in range(min(len(rows), 12)):
        if is_blank(rows[i]) and i > 0:
            above = rows[:i]
            width = max((len(r) for r in rows[i + 1:i + 20]), default=0)
            if all(sum(bool(c.strip()) for c in r) <= max(1, width // 2) for r in above):
                rows = rows[i + 1:]
            break
    rows = [r for r in rows if r and not is_blank(r)]
    # second table: a header-like row after some data rows -> keep the first table only
    start = 1
    while start < min(len(rows), 6) and header_like(rows[start], rows[start + 1:start + 40]):
        start += 1  # skip a multi-row header stack
    for i in range(start + 1, len(rows) - 1):
        if header_like(rows[i], rows[i + 1:i + 21]) and not header_like(rows[i - 1], rows[i + 1:i + 21]):
            rows = rows[:i]
            break
    # multi-row header: leading header-like rows stacked -> join column-wise with ' '
    k = 0
    while k < min(len(rows) - 1, 5) and header_like(rows[k], rows[k + 1:k + 40]):
        k += 1
    if k >= 2:
        # only rows that are header-like w.r.t. the data (not w.r.t. another header row)
        data = rows[k:k + 40]
        k = sum(1 for j in range(k) if header_like(rows[j], data))
    if k >= 2:
        width = max(len(r) for r in rows[:k])
        joined = [" ".join(r[i].strip() for r in rows[:k] if i < len(r) and r[i].strip())
                  for i in range(width)]
        rows = [joined] + rows[k:]
    return rows


def load(data: bytes):
    # the type caches are per file: every Pollock file is a variant of the same table, so a
    # cross-file cache would inflate throughput with content memorised from other files
    strong.cache_clear()
    typed.cache_clear()
    if not data:
        return []
    text = decode(data)
    d, q, e, sp = sniff(text)
    rows = parse(text, d, q, e, sp)
    return structure(rows)
