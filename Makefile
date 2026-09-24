# sieve: build, test, and score against Pollock (all from the repo root).
# PY = a Python with the harness deps (see README "Reproduce"); the Pollock checkout is
# upstream/ or $POLLOCK_UPSTREAM.
PY ?= .venv/bin/python

.PHONY: install test eval eval-all identity speed baselines published synthetic external check-split

install:            ## pip install . (standard library only; `sieve` CLI + `python -m sieve`)
	$(PY) -m pip install .

test:               ## unit tests: API / CLI / packaging, synthetic cases, Pollock-shaped cases
	$(PY) -m pytest

eval:               ## score sieve on the 1,200-file dev split with Pollock's own evaluate.py
	nice -n 10 $(PY) harness/run.py --loader sieve --split dev

eval-all:           ## score sieve on all 2,290 files (the README row; prints dev / held-out too)
	nice -n 10 $(PY) harness/run.py --loader sieve --split all

identity:           ## every output byte-identical to the scored run (results/sieve-outputs.sha256.tsv)
	$(PY) harness/speed.py --loader sieve --compare results/sieve-outputs.sha256.tsv

speed:              ## files/s of the no-repair baseline and sieve, interleaved passes
	$(PY) harness/speed.py --loaders c0-csvsniff,sieve --repeat 2

baselines:          ## reproduce the README rows with Pollock's own SUT scripts
	for s in duckdbparse duckdbauto clevercs pycsv pandas; do nice -n 10 $(PY) harness/run.py --sut $$s --split all; done

published:          ## the README rows, recomputed from the authors' committed per-file results
	$(PY) harness/published.py --split all

synthetic:          ## synthetic guard / positive cases (tables that are not Pollock's)
	$(PY) harness/synthetic/check.py --loaders c0-csvsniff,sieve

external:           ## report-only dialect check on CSV Wrangling files (run harness/external_fetch.py first)
	nice -n 10 $(PY) harness/external.py --loaders c0-csvsniff,sieve

check-split:        ## verify harness/splits/{dev,heldout}.txt still match the seed
	$(PY) harness/make_splits.py --check
