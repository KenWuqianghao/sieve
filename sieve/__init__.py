"""sieve - a CSV loader that works from the file's bytes alone.

    import sieve
    rows = sieve.load("data.csv")          # a path (str or os.PathLike)
    rows = sieve.load(b"a,b\\r\\n1,2\\r\\n")  # or the raw bytes (or a binary file object)
    d = sieve.sniff("data.csv")            # Dialect(delimiter, quotechar, escapechar, has_header)

`load` returns a list of rows (lists of str). The first row is the header when the file has one;
a file without a header is returned as-is (no header is invented). Encoding, delimiter, quote and
escape characters, preamble, multi-row header, a trailing second table and damaged rows are all
decided from the file's content. A path is only used to open the file: nothing about its name
reaches the loader. Standard library only.

`sniff` reports the detected dialect and whether the file's first non-blank record is a header,
without loading the table. None means "none": no delimiter (a one-column file), no quote char,
no escape char.

Command line: `python -m sieve file.csv` (or `sieve file.csv` once installed) writes the loaded
table to stdout as RFC-4180 CSV (comma, double quote, CRLF, UTF-8).
"""
import os
from typing import NamedTuple, Optional

from . import loader as _loader

__version__ = "0.2.0"
__all__ = ["Dialect", "load", "load_bytes", "sniff", "__version__"]


class Dialect(NamedTuple):
    """What sieve.sniff() detects. A character field is None when the file has no such character.

    delimiter   the field separator, or None for a one-column file
    quotechar   the character that encloses fields, or None when no field is enclosed
    escapechar  the escape character (reported only when it is used), or None
    has_header  True when the first non-blank record names the columns of the records below it
    """
    delimiter: Optional[str]
    quotechar: Optional[str]
    escapechar: Optional[str]
    has_header: bool


def _read(source, name):
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)
    if isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as fh:
            return fh.read()
    read = getattr(source, "read", None)
    if read is not None:
        data = read()
        if isinstance(data, str):
            raise TypeError(f"sieve.{name} needs a binary file object (open the file with 'rb')")
        return bytes(data)
    raise TypeError(f"sieve.{name} expects a path, bytes or a binary file object, not {type(source).__name__}")


def load_bytes(data):
    """Load a CSV file given as bytes -> list of rows (list of str)."""
    return _loader.load(bytes(data))


def load(source):
    """Load a CSV file -> list of rows (list of str).

    `source` is a path (str or os.PathLike), bytes-like data, or a binary file object. A str is
    always a path; to load CSV text held in a str, pass `text.encode()`.
    """
    return load_bytes(_read(source, "load"))


def sniff(source):
    """Detect a CSV file's dialect and header -> Dialect(delimiter, quotechar, escapechar,
    has_header).

    `source` is taken as by `load`: a path, bytes-like data or a binary file object.

    The dialect is the one `load` parses with, except that `load` reads a file that has no
    quote char with '"' (its row repairs need one).

    `has_header` answers one question: is the file's FIRST non-blank record a header? `load`
    does not use it. `load` emits the first row of the table it returns either way (it never
    invents or drops a header), and its structure stage judges header-likeness on that table,
    after cutting a preamble closed by a blank line. So the two can differ: for a title line,
    a blank line and then a header, `has_header` is False (the first record is a title) while
    `load` returns the table below the title, header first.
    """
    return Dialect(*_loader.detect(_read(source, "sniff")))
