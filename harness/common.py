"""Shared paths, pollution taxonomy and split lists for the Pollock harness.

Analysis-side code only. Loaders never import this module and never see file names.

Paths: the Pollock checkout is `upstream/` in the repository root, or wherever the
POLLOCK_UPSTREAM environment variable points. Outputs go to `runs/` (gitignored);
POLLOCK_LOADING_ROOT moves the unpacked loader outputs (about 55 MB per all-files run)
elsewhere.
"""
import importlib.util
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.abspath(os.environ.get("POLLOCK_UPSTREAM") or os.path.join(ROOT, "upstream"))
DATA = os.path.join(UPSTREAM, "polluted_files")
RUNS = os.path.join(ROOT, "runs")
SPLITS = os.path.join(ROOT, "harness", "splits")
MEASURES = ["success", "header_precision", "header_recall", "header_f1",
            "record_precision", "record_recall", "record_f1",
            "cell_precision", "cell_recall", "cell_f1"]

# Coarse groups used in results.tsv. File-level pollutions are single files.
#   T  file/table-level (header, preamble, multitable, trailing newline, empty ...)
#   S  file-level structural (dialect: delimiter, quote, escape, record delimiter)
#   L  row_less_sep  (one row lost one delimiter -> two cells merged)
#   M  row_more_sep  (one row gained one delimiter -> one extra empty cell)
#   Q  row_extra_quote (one cell got an unescaped quote char in front)
#   R  row_field_delimiter (one row uses space as delimiter)
GROUPS = ["T", "S", "L", "M", "Q", "R"]


def family(fname: str) -> str:
    """Fine pollution type (the stratum). Row-level files collapse to one family each;
    file-level files are their own family (they are singletons)."""
    if fname.startswith("row_less_sep"):
        return "row_less_sep"
    if fname.startswith("row_more_sep"):
        return "row_more_sep"
    if fname.startswith("row_extra_quote"):
        return "row_extra_quote"
    if fname.startswith("row_field_delimiter"):
        return "row_field_delimiter"
    return fname[:-4]  # e.g. file_preamble, file_field_delimiter_0x3B, source


def group(fname: str) -> str:
    fam = family(fname)
    return {"row_less_sep": "L", "row_more_sep": "M", "row_extra_quote": "Q",
            "row_field_delimiter": "R"}.get(fam) or (
        "S" if re.match(r"file_(field_delimiter|quotation_char|escape_char|record_delimiter)", fam)
        else "T")


def row_col(fname: str):
    m = re.search(r"row(?:_less_sep_row|_more_sep_row|_extra_quote)(\d+)_col(\d+)", fname)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"row_field_delimiter_(\d+)_", fname)
    if m:
        return int(m.group(1)), None
    return None, None


# Loaders the harness can run by name. Any other name must be a path to a .py file that
# defines `load(data: bytes) -> list[list[str]]` (the variant is then named after the file).
LOADERS = {
    "sieve": os.path.join(ROOT, "sieve", "loader.py"),
    "c0-csvsniff": os.path.join(ROOT, "harness", "baseline", "c0_csvsniff.py"),
}


def loader_path(variant):
    if variant in LOADERS:
        return LOADERS[variant]
    if variant.endswith(".py") and os.path.exists(variant):
        return os.path.abspath(variant)
    raise SystemExit(f"unknown loader {variant!r}: use one of {sorted(LOADERS)} or a path to a .py file")


def variant_name(variant):
    return variant if variant in LOADERS else os.path.splitext(os.path.basename(variant))[0]


def load_loader(variant, prefix="loader"):
    """Import a loader module from its file (a fresh module object per call)."""
    path = loader_path(variant)
    name = f"{prefix}_{re.sub(r'[^A-Za-z0-9]', '_', variant_name(variant))}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def all_files():
    return sorted(f for f in os.listdir(os.path.join(DATA, "csv")) if f.endswith("csv"))


def split_files(split: str):
    if split == "all":
        return all_files()
    with open(os.path.join(SPLITS, f"{split}.txt")) as fh:
        return [l.strip() for l in fh if l.strip()]


# Loader outputs: ~55 MB per variant as files, ~100 KB as a solid tar.xz (all files are
# near-duplicates). run.py packs them after scoring; analysis tools unpack on demand.
def outputs_dir(variant):
    # POLLOCK_LOADING_ROOT moves the unpacked outputs out of the repository; the packed
    # tar.xz still lands in runs/<variant>/.
    return os.path.join(os.environ.get("POLLOCK_LOADING_ROOT") or RUNS, variant, "loading")


def pack_outputs(variant):
    import shutil
    import subprocess
    d = outputs_dir(variant)
    if not os.path.isdir(d):
        return
    tgt = os.path.join(RUNS, variant, "loading.tar.xz")
    subprocess.run(f"tar -cf - -C '{os.path.dirname(d)}' loading | xz -1 -T1 > '{tgt}.tmp' && mv '{tgt}.tmp' '{tgt}'",
                   shell=True, check=True)
    shutil.rmtree(d)


def ensure_outputs(variant):
    """Unpack runs/<variant>/loading.tar.xz if the loading dir is absent. Returns True if it
    unpacked (caller may call pack_outputs / remove the dir again when done)."""
    import subprocess
    d = outputs_dir(variant)
    tgt = os.path.join(RUNS, variant, "loading.tar.xz")
    if os.path.isdir(d) or not os.path.exists(tgt):
        return False
    subprocess.run(f"xz -dc '{tgt}' | tar -xf - -C '{os.path.dirname(d)}'", shell=True, check=True)
    return True


def drop_unpacked(variant):
    import shutil
    if os.path.exists(os.path.join(RUNS, variant, "loading.tar.xz")):
        shutil.rmtree(outputs_dir(variant), ignore_errors=True)
