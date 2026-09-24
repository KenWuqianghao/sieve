"""Public API, CLI and packaging of sieve."""
import csv
import io
import os
import pathlib
import subprocess
import sys

import pytest

import sieve
from conftest import ROOT

DATA = b"id,city,amount\r\n1,Graz,3.50\r\n2,Cork,4.25\r\n3,Lyon,1.00\r\n"
ROWS = [["id", "city", "amount"], ["1", "Graz", "3.50"], ["2", "Cork", "4.25"], ["3", "Lyon", "1.00"]]


def normalised(rows):
    buf = io.StringIO(newline="")
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8")


def test_load_bytes_like():
    assert sieve.load(DATA) == ROWS
    assert sieve.load(bytearray(DATA)) == ROWS
    assert sieve.load(memoryview(DATA)) == ROWS
    assert sieve.load_bytes(DATA) == ROWS


def test_load_path_and_file_object(tmp_path):
    p = tmp_path / "some name that must not matter.csv"
    p.write_bytes(DATA)
    assert sieve.load(str(p)) == ROWS
    assert sieve.load(p) == ROWS
    with open(p, "rb") as fh:
        assert sieve.load(fh) == ROWS
    assert sieve.load(io.BytesIO(DATA)) == ROWS


def test_file_name_is_irrelevant(tmp_path):
    # the path is only used to open the file: same bytes, any name -> same rows
    a, b = tmp_path / "file_no_header.csv", tmp_path / "x.tsv"
    a.write_bytes(DATA)
    b.write_bytes(DATA)
    assert sieve.load(a) == sieve.load(b) == ROWS


def test_bad_inputs():
    with pytest.raises(TypeError):
        sieve.load(io.StringIO("a,b\n"))
    with pytest.raises(TypeError):
        sieve.load(42)
    with pytest.raises(FileNotFoundError):
        sieve.load("/nonexistent/definitely/missing.csv")


def test_empty_and_whitespace():
    assert sieve.load(b"") == []
    assert sieve.load(b"\r\n\r\n") == []


def test_no_state_between_calls():
    other = b"name;score\nanna;1,5\nben;2,5\ncarla;3,0\n"
    first = sieve.load(DATA)
    sieve.load(other)
    assert sieve.load(DATA) == first


def test_stdlib_only():
    """sieve imports nothing outside the standard library."""
    src = [pathlib.Path(ROOT, "sieve", f).read_text() for f in ("__init__.py", "__main__.py", "loader.py")]
    code = "\n".join(src)
    mods = {line.split()[1].split(".")[0] for line in code.splitlines()
            if line.startswith(("import ", "from ")) and not line.startswith("from .")}
    stdlib = set(getattr(sys, "stdlib_module_names", mods))
    assert mods <= stdlib, mods - stdlib


def test_cli_stdout(tmp_path):
    p = tmp_path / "in.csv"
    p.write_bytes(b"a;b;c\n1;2;x y\n3;4;\"q;r\"\n5;6;z\n")
    out = subprocess.run([sys.executable, "-m", "sieve", str(p)], cwd=ROOT, capture_output=True, check=True)
    assert out.stdout == normalised(sieve.load(p))
    assert out.stdout.startswith(b"a,b,c\r\n")
    assert b'"q;r"' not in out.stdout and b"q;r" in out.stdout


def test_cli_stdin_and_output_file(tmp_path):
    o = tmp_path / "out.csv"
    subprocess.run([sys.executable, "-m", "sieve", "-", "-o", str(o)], cwd=ROOT, input=DATA, check=True)
    assert o.read_bytes() == normalised(ROWS)


def test_cli_missing_file():
    r = subprocess.run([sys.executable, "-m", "sieve", "/nonexistent/x.csv"], cwd=ROOT, capture_output=True)
    assert r.returncode == 1 and b"sieve:" in r.stderr


def test_pollock_sut_script_uses_the_package():
    """sut/sieve/ (the Pollock SUT script) ships this package, and passes only the path."""
    vendored = pathlib.Path(ROOT, "sut", "sieve", "sieve")
    for f in ("__init__.py", "loader.py"):
        assert (vendored / f).read_bytes() == pathlib.Path(ROOT, "sieve", f).read_bytes()
    script = pathlib.Path(ROOT, "sut", "sieve", "sieve-bench.py").read_text()
    assert "sieve.load(in_filepath)" in script
    assert "load_parameters(" not in script and "PARAM_DIR" not in script
