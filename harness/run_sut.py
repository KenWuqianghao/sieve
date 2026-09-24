"""Run one of the repo's own loader scripts (upstream/sut/<sut>/*.py) to reproduce a baseline.

The scripts hard-code absolute container paths (`abspath(f'/{DATASET}/csv/')`,
`abspath(f'/results/{sut}/{DATASET}/loading/')`, ...). We execute the script source
unchanged except for one mechanical rewrite: every `abspath(f'/` becomes
`abspath(f'<fakeroot>/`, where <fakeroot> is runs/_sutroot/<sut>/ holding
    polluted_files -> upstream/polluted_files
    results/<sut>/polluted_files/{loading,...} -> runs/<sut>/  (outputs + their time CSV)
The replacement count is asserted. Loader logic, parameters, N_REPETITIONS: untouched.

Usage: run_sut.py <pycsv|pandas|clevercs|duckdbparse|duckdbauto>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, RUNS, UPSTREAM  # noqa: E402

SCRIPTS = {"pycsv": "pycsv/pycsv.py", "pandas": "pandas/panda.py",
           "clevercs": "clevercs/clevercs.py", "duckdbparse": "duckdbparse/duck-bench.py",
           "duckdbauto": "duckdbauto/duck-bench.py"}


def main():
    sut = sys.argv[1]
    script = os.path.join(UPSTREAM, "sut", SCRIPTS[sut])
    fake = os.path.join(RUNS, "_sutroot", sut)
    out = os.path.join(RUNS, sut)
    os.makedirs(os.path.join(out, "loading"), exist_ok=True)
    os.makedirs(os.path.join(fake, "results", sut), exist_ok=True)
    for link, target in ((os.path.join(fake, "polluted_files"), DATA),
                         (os.path.join(fake, "results", sut, "polluted_files"), out)):
        if not os.path.islink(link):
            os.symlink(target, link)
    src = open(script).read()
    n = src.count("abspath(f'/")
    assert n >= 3, (script, n)
    src = src.replace("abspath(f'/", f"abspath(f'{fake}/")
    os.environ.setdefault("DATASET", "polluted_files")
    # the script does `from utils import ...`: every Dockerfile copies ./sut/utils.py next to
    # the script (duckdbparse's own utils.py is NOT what its image uses), so sut/ goes first.
    sys.path.insert(0, os.path.dirname(script))
    sys.path.insert(0, os.path.join(UPSTREAM, "sut"))
    sys.argv = [script]
    exec(compile(src, script, "exec"), {"__name__": "__main__", "__file__": script})


if __name__ == "__main__":
    main()
