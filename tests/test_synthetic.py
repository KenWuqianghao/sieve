"""The synthetic regression cases (harness/synthetic/cases.py) as unit tests.

guard / limit: sieve must load the file exactly as c0-csvsniff (the no-repair baseline) does:
               comment lines, title / label rows, ragged lists, space-aligned text, optional
               trailing columns - nothing a row repair may touch.
positive:      one damaged row (or an escape convention) in a table that is not Pollock's;
               sieve must return the clean table.
"""
import os

import pytest

import sieve
from cases import CASES
from conftest import ROOT, load_module

c0 = load_module(os.path.join(ROOT, "harness", "baseline", "c0_csvsniff.py"), "c0_ref")

# Known limitation, kept as an expected failure: H5 (escape only on positive evidence) fixes it
# but was not kept (no dev gain; see EXPERIMENTS.md). sieve reads `\'` as an escaped
# apostrophe and drops the backslash.
XFAIL = {"esc_literal_backslash_apos": "H5 not kept: a literal backslash before ' is dropped"}


@pytest.mark.parametrize("name,kind,data,expected",
                         [c for c in CASES if c[1] in ("guard", "limit")], ids=lambda v: v if isinstance(v, str) else "")
def test_guard(name, kind, data, expected):
    assert sieve.load(data) == c0.load(data)


@pytest.mark.parametrize("name,kind,data,expected",
                         [pytest.param(*c, marks=pytest.mark.xfail(reason=XFAIL[c[0]], strict=True))
                          if c[0] in XFAIL else c for c in CASES if c[1] == "positive"],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_positive(name, kind, data, expected):
    assert sieve.load(data) == expected
