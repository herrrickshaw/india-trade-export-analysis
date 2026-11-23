"""Exact-boundary cases that the broader suites do not reach (found by mutation testing)."""
import importlib
import runpy
import sys

import numpy as np
import pandas as pd
import pytest

import tradestat_config as cfg
from helpers import BOOK, write_workbook
from tradestat_config import EXPORT_FILENAMES, IMPORT_FILENAME


def fresh(name):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    d = tmp_path / "wb"
    d.mkdir()
    monkeypatch.setenv("TRADESTAT_DIR", str(d))
    monkeypatch.setenv("TRADESTAT_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.chdir(tmp_path)
    return d


def install(d, rows_by_year):
    for y, rows in rows_by_year.items():
        write_workbook(d / EXPORT_FILENAMES[y], rows)


def run_script(name, capsys):
    sys.argv = [name]
    runpy.run_path(str(cfg.Path(__file__).resolve().parent.parent / name), run_name="__main__")
    return capsys.readouterr().out


def test_total_row_pattern_is_anchored_at_the_start():
    df = pd.DataFrame({"Commodity": ["Rest of India's Total", "India's total", "Tea"], "V": [1.0, 2.0, 3.0]})
    items, total = cfg.drop_total_row(df, "Commodity", "V")
    assert items.Commodity.tolist() == ["Rest of India's Total", "Tea"] and total == 2.0


def test_insights_value_floor_and_five_year_growth_edges_are_strict(dirs, capsys):
    base = [("1", "OneM", 1.0, 50.0),              # value exactly 1 with growth 50: not > 1
            ("2", "TenPct", 200.0, 50.0)]          # 200 -> 220 is exactly +10%: not > 10%
    rows23 = [("1", "OneM", 1.0, 50.0), ("2", "TenPct", 220.0, 50.0)]
    install(dirs, {2020: [("1", "OneM", 1.0, 0.0), ("2", "TenPct", 200.0, 0.0)],
                   2022: base, 2023: rows23})
    out = run_script("export_insights.py", capsys)
    first = out.split("HIGH-VALUE EXPORTS WITH STRONG GROWTH (Last Available Year)")[1].split("5-YEAR")[0]
    assert "OneM" not in first and "TenPct" in first          # TenPct qualifies here (value > 1, growth 50 > 20)
    five = out.split("Exports: Value $50M+ in 2023 + 10%+ Growth (2020-2023):")[1].split("EMERGING")[0]
    assert "Found 0 commodities" in five and "TenPct" not in five


def test_project_growth_with_numpy_zero_base_is_rejected():
    ext = fresh("export_extended_analysis")
    assert np.isnan(ext.project_growth(np.float64(0.0), np.float64(5.0)))     # numpy division would give inf, not an error


def test_cagr_of_exactly_500_percent_is_not_capped():
    ext = fresh("export_extended_analysis")
    v23 = 216.00000000000003                                  # (v23 / 1) ** (1/3) - 1 == 5.0 exactly
    assert (v23 ** (1 / 3)) - 1 == 5.0
    assert ext.project_growth(1.0, v23, 2024) == pytest.approx(v23 * 6.0)       # real CAGR, not the 30% fallback
    assert ext.project_growth(1.0, v23 * 1.001, 2024) == pytest.approx(v23 * 1.001 * 1.3)


def test_consistent_performers_need_more_than_100m(dirs, capsys):
    ext = fresh("export_extended_analysis")
    rows20 = [("1", "Exactly100", 50.0, 0.0), ("2", "Above100", 50.0, 0.0), ("3", "Anchor", 10.0, 0.0)]
    rows23 = [("1", "Exactly100", 100.0, 0.0), ("2", "Above100", 101.0, 0.0), ("3", "Anchor", 10.0, 0.0)]
    install(dirs, {2020: rows20, 2022: rows20, 2023: rows23})
    ext.analyze_extended_trends()
    stable = capsys.readouterr().out.split("CONSISTENT PERFORMERS")[1].split("EXPORTING EXTENDED DATA")[0]
    assert "Above100" in stable and "Exactly100" not in stable


def test_equal_imports_and_exports_are_a_deficit_not_a_surplus(dirs, capsys):
    cmp_ = fresh("import_export_comparison")
    rows = [("1", "Alpha", 100.0, 0.0), ("2", "Bravo", 50.0, 0.0)]
    install(dirs, {2020: rows, 2022: rows, 2023: rows})
    write_workbook(dirs / IMPORT_FILENAME, rows, total_label="India's Total Import")
    cmp_.analyze_trade_balance(cmp_.load_all_data())
    out = capsys.readouterr().out
    assert "Trade Balance:      $0M (DEFICIT)" in out


def test_export_analysis_filters_use_the_median_and_strict_thresholds(dirs, capsys):
    def write(path, rows):
        pd.DataFrame(rows + [("India's Total Export", sum(r[1] for r in rows), sum(r[2] for r in rows))],
                     columns=["Commodity", "Value (US $ Million)", "Quantity (Qty)"]).to_excel(path, index=False)
    # every row has value-per-unit 2, so average == median: nothing is "above the median"
    flat = {2020: [("A", 100, 50), ("B", 60, 30)], 2022: [("A", 100, 50), ("B", 60, 30)],
            2023: [("A", 150, 75), ("B", 90, 45)]}
    for y, r in flat.items():
        write(dirs / EXPORT_FILENAMES[y], r)
    out = run_script("export_analysis.py", capsys)
    assert "Growing commodities: 0" in out and "High-value commodities (>2x median): 0" in out
    # exactly +10% value growth is not > 10%
    ten = {2020: [("A", 100, 10), ("B", 50, 50)], 2022: [("A", 100, 10), ("B", 50, 50)],
           2023: [("A", 110, 10), ("B", 50, 50)]}
    for y, r in ten.items():
        write(dirs / EXPORT_FILENAMES[y], r)
    assert "Growing commodities: 0" in run_script("export_analysis.py", capsys)
    # a commodity whose value per unit is above the median but under twice the median is NOT "high value"
    mid = {2020: [("A", 100, 10), ("B", 50, 50), ("C", 30, 30), ("D", 20, 1)],
           2022: [("A", 110, 10), ("B", 50, 50), ("C", 30, 30), ("D", 20, 1)],
           2023: [("A", 200, 10), ("B", 45, 50), ("C", 30, 30), ("D", 40, 1)]}
    for y, r in mid.items():
        write(dirs / EXPORT_FILENAMES[y], r)
    out = run_script("export_analysis.py", capsys)
    hv = out.split("HIGH-VALUE EXPORTS (Value per Unit > Median)")[1].split("5-YEAR")[0]
    a_row = [l.split() for l in hv.splitlines() if l.split()[1:2] == ["A"]][0]
    assert float(a_row[2]) == 200.0 and float(a_row[3]) == 10.0               # only A's 2023 bar (20/unit) qualifies
