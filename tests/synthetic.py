"""Build tiny synthetic TradeStat-style workbooks under a fake HOME (no real data, no network)."""
from __future__ import annotations

from pathlib import Path

import openpyxl

COLS = ["S.No.", "HSCode", "Commodity", "Value_Current_Million", "Share_Current",
        "Value_Next_Million", "Share_Next", "Growth_%"]
EXPORT_FILES = {
    2020: "TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
    2022: "TradeStat-Eidb-Export-Commodity-wise2022.xlsx",
    2023: "TradeStat-Eidb-Export-Commodity-wise.xlsx",
}
IMPORT_FILE = "TradeStat-Eidb-Import-Commodity-wise.xlsx"


def _commodities(n: int = 40):
    return [f"COMMODITY {i:02d}" for i in range(n)]


def _value(i: int, year: int) -> float:
    base = 20.0 * (i + 1) ** 1.7
    factor = {2020: 1.0, 2022: 1.4, 2023: 1.9 + (i % 7) * 0.5}[year]
    if i == 3:
        factor *= 40  # extreme-growth outlier (CAGR cap branch)
    return round(base * factor, 2)


def write_trade_xlsx(path: Path, year: int, skip_header: bool = True, scale: float = 1.0) -> None:
    """Write 2 junk rows + header + data rows (the layout the scripts read with skiprows=2)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    if skip_header:
        ws.append(["TradeStat title"])
        ws.append([])
    ws.append(COLS)
    for i, name in enumerate(_commodities()):
        val = _value(i, year) * scale
        growth = round(((_value(i, year) / _value(i, 2020)) - 1) * 100, 2) if year != 2020 else 5.0 + i
        row = [i + 1, f"{1000 + i}", name, val, 0.1, val * 1.1, 0.1, growth]
        if i == 5:
            row[3] = None  # dropped by dropna
        if i == 6:
            row[3] = 0  # zero value branch
        ws.append(row)
    wb.save(path)


def write_flat_xlsx(path: Path, year: int) -> None:
    """Header-on-row-0 layout used by export_analysis.py (Commodity / Value / Quantity)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Commodity Name", "Export Value", "Quantity"])
    for i, name in enumerate(_commodities()):
        ws.append([name, _value(i, year) * 1000, 10.0 + (i % 9) * 3 + (year - 2019)])
    wb.save(path)


def build_home(home: Path, flat: bool = False, with_imports: bool = True) -> Path:
    data_dir = home / "Downloads" / "import export data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for year, name in EXPORT_FILES.items():
        if flat:
            write_flat_xlsx(data_dir / name, year)
        else:
            write_trade_xlsx(data_dir / name, year)
    if with_imports and not flat:
        write_trade_xlsx(data_dir / IMPORT_FILE, 2023, scale=1.6)
    return home
