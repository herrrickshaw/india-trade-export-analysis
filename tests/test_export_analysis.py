import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

from tradestat_config import EXPORT_FILENAMES

ROOT = Path(__file__).resolve().parent.parent

TOTAL = "India's Total Export"
YEARS = {
    2020: [("A", 100, 10), ("B", 50, 50), ("C", 30, 30), ("D", 20, 1)],
    2022: [("A", 110, 10), ("B", 50, 50), ("C", 30, 30), ("D", 20, 1)],
    2023: [("A", 200, 10), ("B", 45, 50), ("C", 30, 30), ("D", 40, 1)],
}


def write(path, rows, qty_name="Quantity (Qty)"):
    df = pd.DataFrame(rows + [(TOTAL, sum(r[1] for r in rows), sum(r[2] for r in rows))],
                      columns=["Commodity", "Value (US $ Million)", qty_name])
    df.to_excel(path, index=False)


@pytest.fixture
def d(tmp_path, monkeypatch):
    base = tmp_path / "wb"
    base.mkdir()
    for y, rows in YEARS.items():
        write(base / EXPORT_FILENAMES[y], rows)
    monkeypatch.setenv("TRADESTAT_DIR", str(base))
    return base


def run(capsys):
    sys.argv = ["export_analysis.py"]
    runpy.run_path(str(ROOT / "export_analysis.py"), run_name="__main__")
    return capsys.readouterr().out


def test_full_report(d, capsys):
    out = run(capsys)
    for y, n in ((2020, "TradeStat-Eidb-Export-Commodity-wise 2020.xlsx"),):
        assert f"✓ Loaded {n} (Year: {y})" in out
    assert "(Year: 2022)" in out and "(Year: 2023)" in out
    # the grand-total row must not be counted as a commodity or added to totals
    summ = out.split("SUMMARY STATISTICS")[1]
    assert "Total commodities analyzed: 4" in summ
    assert "Total export value: $725" in summ
    assert "Median value per unit: $5.50" in summ
    assert "High-value commodities (>2x median): 2" in summ and "Growing commodities: 2" in summ
    hv = out.split("HIGH-VALUE EXPORTS (Value per Unit > Median)")[1].split("5-YEAR GROWTH ANALYSIS")[0]
    rows = [l.split() for l in hv.splitlines() if l.split() and l.split()[1:2] and l.split()[1] in ("A", "D")]
    assert [r[1] for r in rows] == ["D", "A"]                          # by mean value per unit, descending
    d_row = rows[0]
    assert float(d_row[2]) == 80.0 and float(d_row[3]) == 3.0 and float(d_row[4]) == pytest.approx(26.666667, rel=1e-6) and d_row[5] == "3"
    growth = out.split("HIGH-VALUE EXPORTS WITH STRONG GROWTH")[1].split("TOP OPPORTUNITIES")[0]
    g_rows = [l.split() for l in growth.splitlines() if l.split() and l.split()[1:2] and l.split()[1] in {"A", "B", "C", "D"}]
    assert sorted(r[1] for r in g_rows) == ["A", "D"]                  # B shrank, C flat
    assert all(float(r[2]) == pytest.approx(100.0) for r in g_rows)    # first -> last year value growth
    opp = out.split("TOP OPPORTUNITIES: High Unit Value + Consistent Growth")[1].split("SUMMARY")[0]
    assert [l.split()[1] for l in opp.splitlines() if l.split() and l.split()[1:2] and l.split()[1] in {"A", "D"}] == ["D", "A"]


def test_commodity_in_a_single_year_is_not_a_growth_candidate(d, capsys):
    write(d / EXPORT_FILENAMES[2023], YEARS[2023] + [("Z", 500, 1)])
    out = run(capsys)
    assert "Total commodities analyzed: 5" in out
    growth = out.split("HIGH-VALUE EXPORTS WITH STRONG GROWTH")[1].split("TOP OPPORTUNITIES")[0]
    assert not [l for l in growth.splitlines() if l.split()[1:2] == ["Z"]]


def test_zero_base_year_reports_zero_growth_not_infinity(d, capsys):
    write(d / EXPORT_FILENAMES[2020], [("A", 0, 10)] + YEARS[2020][1:])
    out = run(capsys)
    assert "inf" not in out.lower().replace("information", "")


def test_unidentifiable_columns_are_skipped_with_a_warning(d, capsys):
    write(d / EXPORT_FILENAMES[2020], YEARS[2020], qty_name="Mystery")
    out = run(capsys)
    assert "Warning: Could not identify columns for 2020" in out
    assert "Found: Commodity=Commodity, Value=Value (US $ Million), Qty=None" in out
    assert "Total commodities analyzed: 4" in out                       # 2022 + 2023 still produce the report


def test_unreadable_file_is_reported_and_skipped(d, capsys):
    (d / EXPORT_FILENAMES[2022]).write_bytes(b"not an excel file")
    out = run(capsys)
    assert "✗ Error reading TradeStat-Eidb-Export-Commodity-wise2022.xlsx" in out
    assert "Total commodities analyzed: 4" in out


@pytest.mark.xfail(strict=True, raises=KeyError,
                   reason="export_analysis.py:101-103 — when only one year loads, no commodity has >= 2 years, "
                          "growth_summary is empty and growth_df.sort_values('Value_Growth_%') raises KeyError "
                          "instead of reporting that growth needs two years")
def test_a_single_loadable_year_still_reports(d, capsys):
    write(d / EXPORT_FILENAMES[2020], YEARS[2020], qty_name="Mystery")
    (d / EXPORT_FILENAMES[2022]).write_bytes(b"not an excel file")
    out = run(capsys)
    assert "SUMMARY STATISTICS" in out


def test_nothing_loadable(d, capsys):
    for y in YEARS:
        (d / EXPORT_FILENAMES[y]).write_bytes(b"junk")
    assert "No data could be loaded. Check file paths and Excel structure." in run(capsys)
