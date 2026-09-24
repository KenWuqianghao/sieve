"""Run the OFFICIAL Pollock scorer (upstream/evaluate.py, unmodified) on one SUT.

Usage (called by run.py in a subprocess):
    official_eval.py <evalroot> <sutname> <njobs>

UPSTREAM is the Pollock checkout (harness/common.py: `upstream/` or $POLLOCK_UPSTREAM).
<evalroot> is a directory prepared by run.py that looks exactly like the upstream repo root
as evaluate.py expects it (all relative paths are evaluate.py's own):
    polluted_files/csv/<f>, polluted_files/clean/<f>   symlinks for the files of one split
    pollock_weights.json                               symlink to upstream's weights
    results/<sutname>/polluted_files/loading           symlink to the loader outputs
We chdir there and call evaluate.main() with `--sut <sutname> --njobs <n>`.
The only thing we touch is evaluate.SUT_ORDER, the list of system names main() uses to
*print* its table (it would KeyError on the 18 published systems we do not re-score); it is
not used in any computation. Scores come out in results/aggregate_results_polluted_files.csv
and results/global_results_polluted_files.csv, written by evaluate.main() itself.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UPSTREAM  # noqa: E402


def main():
    evalroot, sut, njobs = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, UPSTREAM)
    os.chdir(evalroot)
    import evaluate  # noqa: E402  (upstream/evaluate.py, unchanged)
    evaluate.SUT_ORDER = [sut]
    sys.argv = ["evaluate.py", "--sut", sut, "--dataset", "polluted_files",
                "--result", "./results", "--njobs", str(njobs)]
    evaluate.main()


if __name__ == "__main__":
    main()
