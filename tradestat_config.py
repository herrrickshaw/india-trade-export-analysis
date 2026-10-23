"""Shared input/output configuration for the TradeStat export analysis scripts.

The TradeStat-Eidb workbooks are NOT in this repo (download them from
https://tradestat.commerce.gov.in/eidb and save with the names below).
Point the scripts at them with ``--data-dir DIR`` or the ``TRADESTAT_DIR``
environment variable. Outputs go to ``--out-dir DIR`` / ``TRADESTAT_OUT_DIR``
(default: current directory).
"""
import argparse
import os
import sys
from pathlib import Path

EXPORT_FILENAMES = {
    2020: "TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
    2022: "TradeStat-Eidb-Export-Commodity-wise2022.xlsx",
    2023: "TradeStat-Eidb-Export-Commodity-wise.xlsx",
}
IMPORT_FILENAME = "TradeStat-Eidb-Import-Commodity-wise.xlsx"

def _opt(flag, env):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(flag)
    val = vars(p.parse_known_args()[0])[flag.lstrip("-").replace("-", "_")]
    return val or os.environ.get(env)


def data_dir():
    """Directory holding the TradeStat workbooks; exits with a clear message if unset/missing."""
    d = _opt("--data-dir", "TRADESTAT_DIR")
    if not d:
        sys.exit("ERROR: TradeStat workbooks directory not set. Pass --data-dir DIR or set "
                 "TRADESTAT_DIR. Expected files:\n  " + "\n  ".join(
                     list(EXPORT_FILENAMES.values()) + [IMPORT_FILENAME + " (import comparison only)"])
                 + "\nDownload them from https://tradestat.commerce.gov.in/eidb (see README).")
    p = Path(d).expanduser()
    if not p.is_dir():
        sys.exit(f"ERROR: data directory not found: {p}")
    return p


def out_dir():
    p = Path(_opt("--out-dir", "TRADESTAT_OUT_DIR") or ".").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def export_files(years=None):
    """{year: Path} of the export workbooks that exist; exits if a required one is missing."""
    base = data_dir()
    years = list(years or EXPORT_FILENAMES)
    found, missing = {}, []
    for y in years:
        f = base / EXPORT_FILENAMES[y]
        if f.exists():
            found[y] = f
        else:
            missing.append(f.name)
    if missing:
        sys.exit(f"ERROR: missing workbook(s) in {base}: " + ", ".join(missing))
    return found


def import_file():
    return data_dir() / IMPORT_FILENAME


def drop_total_row(df, commodity_col="Commodity", value_col=None):
    """Remove the workbook's grand-total row ("India's Total Export/Import").

    Summing the raw sheet counts that row on top of the line items, i.e. every
    total comes out exactly 2x (see README, "Known data issues"). Returns
    (line_items, total_value_or_None).
    """
    is_total = df[commodity_col].astype(str).str.strip().str.lower().str.match(r"^india'?s total")
    total = None
    if value_col and is_total.any():
        total = float(df.loc[is_total, value_col].iloc[0])
    return df[~is_total].copy(), total


def merge_years(a, b, how="inner"):
    """Join two years on HSCode+Commodity. Joining on Commodity text alone is
    many-to-many (descriptions repeat across HS codes) and multiplies rows."""
    return a.merge(b, on=["HSCode", "Commodity"], how=how)
