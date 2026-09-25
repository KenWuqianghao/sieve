"""sieve.sniff(): the detected dialect and the first-record header test."""
import io

import pytest

import sieve
from sieve import loader

NONE = loader.NONE  # the internal "no delimiter" sentinel (U+E000): never part of the API

TABLE = b"id,city,amount\r\n1,Graz,3.50\r\n2,Cork,4.25\r\n3,Lyon,1.00\r\n"
WORDS = ["apple", "banana split", "cherry pie", "date", "elder berry", "fig", "grape juice", "kiwi"]


def word_list(n):
    return "".join(WORDS[i % len(WORDS)] + "\n" for i in range(n))


# ------------------------------------------------------------------------------ API
def test_returns_a_dialect_tuple():
    d = sieve.sniff(TABLE)
    assert isinstance(d, sieve.Dialect) and isinstance(d, tuple)
    assert d == (",", None, None, True)
    assert (d.delimiter, d.quotechar, d.escapechar, d.has_header) == (",", None, None, True)
    assert d._fields == ("delimiter", "quotechar", "escapechar", "has_header")


def test_sources_like_load(tmp_path):
    p = tmp_path / "any name.csv"
    p.write_bytes(TABLE)
    want = sieve.sniff(TABLE)
    assert sieve.sniff(str(p)) == sieve.sniff(p) == want
    assert sieve.sniff(bytearray(TABLE)) == sieve.sniff(memoryview(TABLE)) == want
    assert sieve.sniff(io.BytesIO(TABLE)) == want
    with open(p, "rb") as fh:
        assert sieve.sniff(fh) == want


def test_bad_inputs_and_empty():
    with pytest.raises(TypeError):
        sieve.sniff(io.StringIO("a,b\n"))
    with pytest.raises(TypeError):
        sieve.sniff(42)
    assert sieve.sniff(b"") == (None, None, None, False)


def test_dialect_is_the_one_load_parses_with():
    data = b"name;score\nanna;1,5\nben;2,5\ncarla;3,0\n"
    assert sieve.sniff(data) == (";", None, None, True)
    assert sieve.load(data) == [["name", "score"], ["anna", "1,5"], ["ben", "2,5"], ["carla", "3,0"]]


def test_no_state_between_calls():
    first = sieve.sniff(TABLE)
    sieve.sniff(word_list(20).encode())
    assert sieve.sniff(TABLE) == first


# ------------------------------------------------------------------------------ no delimiter
def test_no_delimiter_word_list():
    # a one-column list whose values contain spaces: not a space-delimited table
    data = word_list(40).encode()
    assert sieve.sniff(data).delimiter is None
    assert sieve.load(data)[:3] == [["apple"], ["banana split"], ["cherry pie"]]


def test_no_candidate_character_at_all():
    assert sieve.sniff(b"alpha\nbeta\ngamma\n").delimiter is None


def test_sentinel_never_leaks():
    # the sentinel occurs in the file after the 64 KB sample: sniff() still reports None and
    # load() does not split on it
    tail = "odd \ue000 line\nfig\n"
    data = (word_list(12000) + tail).encode()
    assert len(data) > loader.SAMPLE
    d = sieve.sniff(data)
    assert d.delimiter is None and NONE not in d[:3]
    rows = sieve.load(data)
    assert {len(r) for r in rows} == {1}
    assert ["odd \ue000 line"] in rows
    # the sentinel inside the sample: the one-column candidate is not tried at all
    d = sieve.sniff(("x \ue000 y\n" + word_list(40)).encode())
    assert d.delimiter != NONE


def test_space_delimited_table_is_kept():
    data = b"x y z\n1 2 3\n4 5 6\n7 8 9\n10 11 12\n"
    assert sieve.sniff(data) == (" ", None, None, True)


# ------------------------------------------------------------------------------ header
def test_header_only_file():
    assert sieve.sniff(b"name,age,city\n").has_header is True
    assert sieve.sniff(b"1,2,3\n").has_header is False
    assert sieve.sniff(b"name,name,city\n").has_header is False  # repeated cells


def test_type_contrast_header_and_data_first():
    assert sieve.sniff(TABLE).has_header is True
    assert sieve.sniff(b"1,Graz,3.50\n2,Cork,4.25\n3,Lyon,1.00\n").has_header is False


def test_title_line_is_not_a_header():
    data = b"Sales by region\nregion,units,price\nNorth,12,3.50\nSouth,7,4.25\nEast,9,1.00\n"
    assert sieve.sniff(data) == (",", None, None, False)


def test_comment_line_is_not_a_header():
    data = b"# exported 2024-01-02\nregion,units\nNorth,12\nSouth,7\nEast,9\n"
    assert sieve.sniff(data).has_header is False


def test_has_header_versus_load():
    # a title closed by a blank line: the first record is not a header, while load() cuts the
    # preamble and returns the table below it, header first
    data = b"Sales by region\n\nregion,units,price\nNorth,12,3.50\nSouth,7,4.25\nEast,9,1.00\n"
    assert sieve.sniff(data).has_header is False
    assert sieve.load(data)[0] == ["region", "units", "price"]
    # no preamble: both agree, and load() emits the header row as the first row
    assert sieve.sniff(TABLE).has_header is True
    assert sieve.load(TABLE)[0] == ["id", "city", "amount"]


# ------------------------------------------------------------------------------ quote char
def test_quote_must_enclose_a_field():
    inches = b'item,size\npipe,12" long\nrod,3" wide\nbar,8" thick\n'
    assert sieve.sniff(inches).quotechar is None
    assert sieve.load(inches)[1] == ["pipe", '12" long']
    apostrophes = b"name,note\nO'Brien,it's fine\nD'Arcy,don't\nAnn,ok\n"
    assert sieve.sniff(apostrophes).quotechar is None
    quoted = b'name,note\n"Smith, J",ok\n"Doe, A",fine\n"Roe, B",good\n'
    assert sieve.sniff(quoted).quotechar == '"'
    assert sieve.load(quoted)[1] == ["Smith, J", "ok"]


def test_single_quote_char():
    data = b"id,name\n1,'Smith, J'\n2,'Doe, A'\n3,'Roe, B'\n"
    assert sieve.sniff(data)[:3] == (",", "'", None)
    assert sieve.load(data)[1] == ["1", "Smith, J"]


# ------------------------------------------------------------------------------ escape char
def test_escape_needs_evidence():
    # backslashes that precede neither the delimiter nor the quote char are text (paths)
    paths = b"id,path\n1,C:\\temp\\a\n2,C:\\temp\\b\n3,D:\\x\\y\n"
    assert sieve.sniff(paths).escapechar is None
    assert sieve.load(paths)[1] == ["1", "C:\\temp\\a"]
    escaped = b'id,text\n1,"say \\"hi\\" now"\n2,"a \\"b\\" c"\n3,"plain"\n'
    assert sieve.sniff(escaped)[:3] == (",", '"', "\\")
    assert sieve.load(escaped)[1] == ["1", 'say "hi" now']


# ------------------------------------------------------------------------------ masking
def test_mask_urls_and_clock_times():
    assert loader.mask("see http://a.org/x:y at 10:30 or 09:15:00.5") == "see U at 0 or 0"
    assert loader.mask("www.a.org,5") == "U,5"
    assert loader.mask("host:alpha") == "host:alpha"  # a key:value colon survives
    assert loader.mask("12:30:45:10") == "12:30:45:10"  # a longer run of digits and colons


def test_url_list_is_not_colon_delimited(monkeypatch):
    data = b"http://a.org/x\nhttps://b.org/y\nhttp://c.org/z\nhttps://d.org/w\n"
    assert sieve.sniff(data).delimiter is None
    monkeypatch.setattr(loader, "mask", lambda s: s)
    assert sieve.sniff(data).delimiter == ":"  # what masking prevents


def test_clock_times_do_not_make_colon_the_delimiter(monkeypatch):
    data = b"10:30 went to the store\n11:45 came back home\n12:15 lunch\n13:00 read a book\n14:20 nap\n"
    assert sieve.sniff(data).delimiter != ":"
    monkeypatch.setattr(loader, "mask", lambda s: s)
    assert sieve.sniff(data).delimiter == ":"


def test_key_value_colon_is_kept():
    assert sieve.sniff(b"host:alpha\nport:8080\nuser:ann\nmode:fast\n").delimiter == ":"
