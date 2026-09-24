"""Synthetic regression cases for sieve's row repairs (H2b onwards).

Designed from general CSV conventions, NOT from the external (CSV Wrangling) files and not from
the Pollock source table: the tables below are generated here with their own columns, widths
and value types, so they also exercise the repairs on tables other than Pollock's one.

Two kinds of case:
  guard     - files a row repair must NOT touch: comment lines, title / label rows, ragged
              word lists, space-aligned numeric text, free-text notes. Assertion: load() gives
              exactly the rows c0-csvsniff gives (c0 does no row repair).
  limit     - known ambiguous inputs (asserted like guard = c0, but a failure is reported as a
              documented limitation, not a regression; the exit code ignores them).
  positive  - one damaged row in an otherwise regular table (a row written with spaces, a lost
              separator, an extra separator). Assertion: load() gives the expected clean rows.
              Reported per stage; they check that the gates still let obvious repairs through
              on a table that is not Pollock's.

Every case is (name, kind, bytes, expected_rows_or_None). Deterministic (seeded).
"""
import csv
import io
import random

R = random.Random(20260924)

FIRST = ["anna", "ben", "carla", "dmitri", "elena", "farid", "greta", "hugo", "ines", "jonas",
         "kira", "luca", "mona", "nils", "olga", "pavel", "rosa", "sven", "tara", "umar"]
CITIES = ["Lisbon", "Graz", "Tampere", "Ghent", "Brno", "Cork", "Malmo", "Porto", "Bergen", "Lyon"]
WORDS = ["river", "stone", "light", "north", "field", "glass", "paper", "silver", "window",
         "garden", "market", "bridge", "harbor", "forest", "signal", "copper", "canvas"]


def csv_bytes(rows, delim=",", term="\r\n"):
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator=term, quoting=csv.QUOTE_MINIMAL).writerows(rows)
    return buf.getvalue().encode("utf-8")


def people(n, rnd):
    """A typed table: id, name, city, score (float), date, remark (free text)."""
    rows = [["id", "name", "city", "score", "joined", "remark"]]
    for i in range(n):
        rows.append([str(100 + i), rnd.choice(FIRST).title(), rnd.choice(CITIES),
                     f"{rnd.uniform(0, 100):.2f}", f"20{rnd.randint(10, 23)}-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}",
                     " ".join(rnd.choice(WORDS) for _ in range(rnd.randint(2, 4)))])
    return rows


def texty(n, rnd, w=4):
    """A text-only table: every column is words (the hard case for a shape profile)."""
    rows = [[f"field{j}" for j in range(w)]]
    for _ in range(n):
        rows.append([" ".join(rnd.choice(WORDS) for _ in range(rnd.randint(1, 3))) for _ in range(w)])
    return rows


def lines(rows, delim):
    return [delim.join(r) for r in rows]


def build():
    rnd = random.Random(7)
    cases = []

    # ---------------------------------------------------------------- guards: comment lines
    t = people(25, rnd)
    body = lines(t, ",")
    body = ["# exported by nightly job on host alpha two"] + body[:12] + \
           ["# rows below were checked by hand"] + body[12:] + ["# end of export file"]
    cases.append(("comment_hash_typed", "guard", ("\r\n".join(body) + "\r\n").encode(), None))

    t = texty(25, rnd, w=5)
    body = lines(t, "|")
    body = ["# source: survey wave three raw"] + body[:10] + ["# second batch starts here now"] + \
           body[10:] + ["// trailing note written by the export tool"]
    cases.append(("comment_hash_text_pipe", "guard", ("\n".join(body) + "\n").encode(), None))

    t = texty(20, rnd, w=4)
    body = lines(t, ";")
    body = ["% generated table do not edit"] + body
    cases.append(("comment_percent_semicolon", "guard", ("\n".join(body) + "\n").encode(), None))

    t = people(20, rnd)
    body = lines(t, "\t")
    body = ["#id name city score joined remark"] + body[1:]  # commented-out header, W tokens
    cases.append(("comment_header_tab", "guard", ("\n".join(body) + "\n").encode(), None))

    # ---------------------------------------------------------------- guards: title / label rows
    t = people(20, rnd)
    body = lines(t, ";")
    body = ["Staff list spring intake overview for all offices"] + body
    cases.append(("title_row_semicolon", "guard", ("\n".join(body) + "\n").encode(), None))

    t = [["year", "q1", "q2", "q3"]] + [[str(2000 + i)] + [str(rnd.randint(10, 999)) for _ in range(3)]
                                         for i in range(18)]
    body = lines(t, ",")
    body = ["Revenue by quarter"] + body[:10] + ["Figures after restatement"] + body[10:]
    cases.append(("label_rows_numeric", "guard", ("\n".join(body) + "\n").encode(), None))

    t = texty(18, rnd, w=3)
    body = lines(t, ";")
    body = body[:8] + ["Section two follows"] + body[8:] + ["Prepared by records office"]
    cases.append(("label_rows_text", "guard", ("\n".join(body) + "\n").encode(), None))

    # ---------------------------------------------------------------- guards: ragged word lists
    groups = []
    for _ in range(30):
        k = rnd.choice([1, 2, 2, 3, 3, 3, 4, 5])
        groups.append(rnd.sample(WORDS, k))
    cases.append(("ragged_words_comma", "guard", ("\n".join(",".join(g) for g in groups) + "\n").encode(), None))

    groups = []
    for _ in range(30):
        k = rnd.choice([2, 3, 3, 3, 3, 4])
        groups.append([rnd.choice(FIRST)] + [rnd.choice(WORDS) for _ in range(k - 1)])
    cases.append(("ragged_words_tab", "guard", ("\n".join("\t".join(g) for g in groups) + "\n").encode(), None))

    # tags: most rows 3 wide, a sizeable minority 2 wide (not damage: shorter lists)
    groups = [[rnd.choice(FIRST), rnd.choice(WORDS), rnd.choice(WORDS)] for _ in range(14)] + \
             [[rnd.choice(FIRST), rnd.choice(WORDS)] for _ in range(10)]
    rnd.shuffle(groups)
    cases.append(("ragged_tags_majority", "guard", ("\n".join(",".join(g) for g in groups) + "\n").encode(), None))

    # ---------------------------------------------------------------- guards: space-aligned text
    rows = []
    for _ in range(25):
        vals = [f"{rnd.uniform(-50, 500):.{rnd.choice([1, 2, 3])}f}" for _ in range(4)]
        rows.append("".join(v.rjust(10) for v in vals))
    cases.append(("space_aligned_numeric", "guard", ("\n".join(rows) + "\n").encode(), None))

    rows = ["  name        size    count"]
    for _ in range(20):
        rows.append(f"  {rnd.choice(WORDS):<12}{rnd.randint(1, 99999):>6}{rnd.randint(0, 9):>8}")
    cases.append(("space_aligned_mixed", "guard", ("\n".join(rows) + "\n").encode(), None))

    # ---------------------------------------------------------------- guards: free-text notes
    t = people(22, rnd)
    body = lines(t, ",")
    body = body[:15] + ["note that the score column was rescaled in march"] + body[15:]
    cases.append(("note_line_typed", "guard", ("\n".join(body) + "\n").encode(), None))

    # ---------------------------------------------------------------- guards: legit wider rows (H4)
    # an optional trailing column filled on a minority of rows; some of those rows have an empty
    # middle cell. Dropping that empty would shift the trailing note into the typed columns.
    rows = ["id,name,score,joined"]
    for i in range(30):
        base = [str(200 + i), rnd.choice(FIRST).title(), f"{rnd.uniform(0, 9):.1f}",
                f"2020-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}"]
        if i % 4 == 1:
            base[2] = ""
            base.append(" ".join(rnd.choice(WORDS) for _ in range(2)))
        rows.append(",".join(base))
    cases.append(("optional_trailing_column", "guard", ("\n".join(rows) + "\n").encode(), None))

    # an unquoted delimiter inside a text field in a row whose last (often empty) cell is empty:
    # the row is W+1 wide with an empty field, but the damage is the unquoted comma, not an
    # extra separator. c0 leaves the row as parsed; dropping the empty cell would misalign it.
    rows = ["code,label,city,amount,note"]
    for i in range(30):
        rows.append(f"K{300 + i},{rnd.choice(WORDS)},{rnd.choice(CITIES)},{rnd.randint(1, 900)},"
                    + (rnd.choice(WORDS) if i % 3 == 0 else ""))
    rows[12] = f"K311,{WORDS[0]}, {WORDS[1]},{CITIES[0]},42,"
    cases.append(("unquoted_comma_text", "limit", ("\n".join(rows) + "\n").encode(), None))

    # ---------------------------------------------------------------- positives (other tables)
    t = people(30, rnd)
    bad = t[17]
    raw = lines(t, ",")
    raw[17] = " ".join(bad[:5]) + ' "' + bad[5] + '"'  # the row written with spaces
    cases.append(("pos_space_row", "positive", ("\r\n".join(raw) + "\r\n").encode(), t))

    t = people(30, rnd)
    raw = lines(t, ",")
    raw[9] = ",".join(t[9][:2]) + "," + t[9][2] + t[9][3] + "," + ",".join(t[9][4:])  # city+score merged
    cases.append(("pos_merged_cell", "positive", ("\r\n".join(raw) + "\r\n").encode(), t))

    t = people(30, rnd)
    raw = lines(t, ",")
    raw[21] = ",".join(t[21][:3]) + ",," + ",".join(t[21][3:])  # an extra empty cell
    cases.append(("pos_extra_sep", "positive", ("\r\n".join(raw) + "\r\n").encode(), t))

    t = people(30, rnd)
    raw = lines(t, ",")
    raw[0] = ",".join(t[0][:4]) + ",," + ",".join(t[0][4:])  # extra empty cell in the header
    cases.append(("pos_extra_sep_header", "positive", ("\r\n".join(raw) + "\r\n").encode(), t))

    # ---------------------------------------------------------------- escape character (H5)
    # Added before experiment c7-escape was run. Positive = the expected table is known.
    # (a) backslash-escaped quotes (doublequote off): `\"` inside quoted remarks -> escape `\`.
    t = people(24, rnd)
    for i in (3, 9, 15, 20):
        t[i][5] = f'{rnd.choice(WORDS)} {rnd.randint(2, 9)}" {rnd.choice(WORDS)}, {rnd.choice(WORDS)}'
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n", doublequote=False, escapechar="\\").writerows(t)
    cases.append(("esc_backslash_quotes", "positive", buf.getvalue().encode(), t))

    # (b) a literal backslash before an apostrophe inside RFC-4180 (doubled-quote) text: the
    # backslash escapes nothing the parser acts on, so it is data and must be kept.
    t = people(24, rnd)
    for i in (4, 11):
        t[i][5] = f"{rnd.choice(WORDS)} 6\\'2\" {rnd.choice(WORDS)}, {rnd.choice(WORDS)}"
    t[17][5] = f"{rnd.choice(WORDS)} it\\'s {rnd.choice(WORDS)}"
    cases.append(("esc_literal_backslash_apos", "positive", csv_bytes(t), t))

    # (c) unquoted Windows paths: backslashes inside fields, never before a quote, delimiter or
    # another backslash -> no escape character.
    t = [["id", "path", "size", "modified"]]
    for i in range(24):
        t.append([str(500 + i), f"C:\\{rnd.choice(WORDS)}\\{rnd.choice(WORDS)}.txt",
                  str(rnd.randint(1, 99999)), f"2021-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}"])
    cases.append(("esc_windows_paths", "positive", csv_bytes(t), t))

    # (d) near-limit: a directory path ending in a backslash right before the delimiter is
    # evidence for `\` by the rule (`\,`), although it is data; the dialect score decides.
    t = [["id", "dir", "files", "modified"]]
    for i in range(24):
        t.append([str(700 + i), f"D:\\{rnd.choice(WORDS)}\\{rnd.choice(WORDS)}\\",
                  str(rnd.randint(1, 999)), f"2022-0{rnd.randint(1, 9)}-1{rnd.randint(0, 9)}"])
    cases.append(("esc_trailing_backslash_dirs", "positive", csv_bytes(t), t))
    return cases


CASES = build()
