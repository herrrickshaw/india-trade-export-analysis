"""Shared loaders and paths for the TradeStat (DGCI&S) commodity-wise export/import workbooks.

The workbooks are not tracked in this repo; they are expected under
``~/Downloads/import export data`` and the derived CSV/JSON files are written to ``~/Downloads``
(or the working directory, for ``export_extended_analysis.py``) exactly as before.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

TRADE_COLUMNS = ["S.No.", "HSCode", "Commodity", "Value_Current_Million",
                 "Share_Current", "Value_Next_Million", "Share_Next", "Growth_%"]
HEADER_ROWS_TO_SKIP = 2  # title rows above the column header in the TradeStat workbooks

EXPORT_FILENAMES: Dict[int, str] = {
    2020: "TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
    2022: "TradeStat-Eidb-Export-Commodity-wise2022.xlsx",
    2023: "TradeStat-Eidb-Export-Commodity-wise.xlsx",
}
IMPORT_FILENAME = "TradeStat-Eidb-Import-Commodity-wise.xlsx"

# Errors a malformed / unreadable workbook can raise while loading.
LOAD_ERRORS = (OSError, ValueError, KeyError, zipfile.BadZipFile)


def output_dir() -> Path:
    """Directory that receives derived CSV/JSON files (``~/Downloads``)."""
    return Path.home() / "Downloads"


def data_dir() -> Path:
    """Directory holding the TradeStat workbooks (``~/Downloads/import export data``)."""
    return output_dir() / "import export data"


def export_paths() -> Dict[int, Path]:
    """Map data year -> export workbook path."""
    base = data_dir()
    return {year: base / name for year, name in EXPORT_FILENAMES.items()}


def load_trade_file(filepath, year: Optional[int] = None, trade_type: Optional[str] = None) -> pd.DataFrame:
    """Read a TradeStat workbook into a frame with ``TRADE_COLUMNS`` (values in USD million).

    Rows missing Commodity or Value are dropped; Value and Growth are coerced to numeric.
    ``year`` / ``trade_type`` ("EXPORT" or "IMPORT") add ``Year`` / ``Type`` columns when given.
    """
    df = pd.read_excel(filepath, sheet_name=0, skiprows=HEADER_ROWS_TO_SKIP)
    df.columns = TRADE_COLUMNS
    df = df.dropna(subset=["Commodity", "Value_Current_Million"])
    df["Value_Current_Million"] = pd.to_numeric(df["Value_Current_Million"], errors="coerce")
    df["Growth_%"] = pd.to_numeric(df["Growth_%"], errors="coerce")
    if year:
        df["Year"] = year
    if trade_type:
        df["Type"] = trade_type
    return df


def load_all_exports(verbose: bool = True) -> Dict[int, pd.DataFrame]:
    """Load every export workbook that exists, keyed by year; unreadable files are reported and skipped."""
    data: Dict[int, pd.DataFrame] = {}
    for year, filepath in export_paths().items():
        if not filepath.exists():
            continue
        try:
            data[year] = load_trade_file(filepath, year)
            if verbose:
                print(f"✓ Loaded {year}: {len(data[year])} commodities")
        except LOAD_ERRORS as exc:
            print(f"✗ Error loading {year}: {exc}")
    return data
