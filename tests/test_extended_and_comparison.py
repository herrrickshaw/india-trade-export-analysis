import importlib
import math
import sys

import numpy as np
import pandas as pd
import pytest

from helpers import BOOK, install_books, write_workbook
from tradestat_config import EXPORT_FILENAMES, IMPORT_FILENAME


def fresh(name):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    d = tmp_path / "data"
    install_books(d)
    monkeypatch.setenv("TRADESTAT_DIR", str(d))
    monkeypatch.setenv("TRADESTAT_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.chdir(tmp_path)
    return d, tmp_path / "out"


# ── project_growth ───────────────────────────────────────────────────────────
@pytest.fixture
def ext():
    return fresh("export_extended_analysis")


def test_project_growth_is_a_three_year_cagr(ext):
    assert ext.project_growth(100.0, 200.0, 2025) == pytest.approx(200 * (2 ** (1 / 3)) ** 2)
    assert ext.project_growth(100.0, 200.0, 2026) == pytest.approx(200 * 2 ** (3 / 3))
    assert ext.project_growth(100.0, 200.0, 2023) == pytest.approx(200.0)
    assert ext.project_growth(200.0, 100.0, 2026) == pytest.approx(50.0)           # shrinking series project down


@pytest.mark.parametrize("v20,v23", [(0, 5), (-1, 5), (5, 0), (5, -1), (np.nan, 5), (5, np.nan)])
def test_project_growth_rejects_nonpositive_or_missing(ext, v20, v23):
    assert math.isnan(ext.project_growth(v20, v23))


def test_project_growth_caps_runaway_cagr(ext):
    # CAGR > 500%: (v23/v20)^(1/3) - 1 > 5  <=>  v23/v20 > 216 -> replaced by a conservative 30%
    assert ext.project_growth(1.0, 217.0, 2025) == pytest.approx(217.0 * 1.3 ** 2)
    just_under = 216.0                                # CAGR exactly 5.0 is not > 5: the real CAGR is used
    assert ext.project_growth(1.0, just_under, 2024) == pytest.approx(216.0 * (just_under ** (1 / 3)))


def test_extract_year(ext):
    assert [ext.extract_year(p) for p in ("a 2020.xlsx", "x2022.xlsx", "f_2025.xlsx", "f2026.xlsx", "plain.xlsx")] == [2020, 2022, 2025, 2025, 2023]


def test_load_export_file_drops_total_and_prints_reconciliation(env, ext, capsys):
    d, _ = env
    df = ext.load_export_file(d / EXPORT_FILENAMES[2023], 2023)
    assert len(df) == len(BOOK) and (df.Year == 2023).all()
    assert df.Value_Current_Million.sum() == pytest.approx(sum(b[3] for b in BOOK))
    assert "2023: workbook total $" in capsys.readouterr().out
    assert "Year" not in ext.load_export_file(d / EXPORT_FILENAMES[2023]).columns


def test_load_all_files_reports_bad_workbooks(env, ext, capsys):
    d, _ = env
    (d / EXPORT_FILENAMES[2022]).write_bytes(b"not an excel file")
    data = ext.load_all_files()
    assert set(data) == {2020, 2023}
    assert "✗ Error loading 2022" in capsys.readouterr().out


def test_extended_analysis_outputs_and_projection_math(env, ext, capsys):
    d, out = env
    ext.analyze_extended_trends()
    text = capsys.readouterr().out
    full = pd.read_csv(out / "EXTENDED_ANALYSIS_2020_2026.csv", dtype={"HSCode": str})
    assert len(full) == len(BOOK) and full.Value_2023.is_monotonic_decreasing
    a = full.set_index("Commodity").loc["Alpha"]
    assert a["Growth_2020_2023_%"] == pytest.approx(100.0)
    assert a["Projected_2025_Million"] == pytest.approx(200 * 2 ** (2 / 3))
    assert a["Projected_2026_Million"] == pytest.approx(400.0)
    assert a["Projected_Growth_2023_2026_%"] == pytest.approx(100.0)
    opp = pd.read_csv(out / "HIGH_OPPORTUNITY_2026_PROJECTIONS.csv")
    # value > 50 OR growth > 50% (either is enough)
    want = {n for hs, n, v20, v23, g in BOOK if v23 > 50 or (v23 - v20) / v20 * 100 > 50}
    assert set(opp.Commodity) == want
    v20, v23 = sum(b[2] for b in BOOK), sum(b[3] for b in BOOK)
    assert f"2020: ${v20:,.0f}M" in text and f"2023: ${v23:,.0f}M (Growth: +{(v23 - v20) / v20 * 100:.1f}%)" in text
    assert f"Average CAGR 2020-2023: {((v23 / v20) ** (1 / 3) - 1) * 100:.2f}%" in text
    sec = text.split("HIGH-GROWTH EXPORTS (Value >$50M in 2023, 10%+ growth 2020-2023)")[1].split("COMPOUND ANNUAL")[0]
    names = [l.split()[0] for l in sec.splitlines() if l.split() and l.split()[0] in {b[1] for b in BOOK}]
    assert names == ["India", "Juliet", "Alpha", "Bravo"]
    emerging = text.split("EMERGING WITH HIGH GROWTH POTENTIAL")[1].split("CONSISTENT PERFORMERS")[0]
    assert [l.split()[0] for l in emerging.splitlines() if l.split() and l.split()[0] in {b[1] for b in BOOK}] == ["Golf", "Echo"]
    stable = text.split("CONSISTENT PERFORMERS")[1].split("EXPORTING EXTENDED DATA")[0]
    assert [l.split()[0] for l in stable.splitlines() if l.split() and l.split()[0] in {b[1] for b in BOOK}] == ["India", "Juliet", "Alpha"]


def test_not_enough_years_message(tmp_path, ext, capsys, monkeypatch):
    monkeypatch.setattr(ext, "load_all_files", lambda: {2023: pd.DataFrame()})
    assert ext.analyze_extended_trends() is None
    assert "Not enough data for trend analysis (need at least 2 years)" in capsys.readouterr().out


def test_no_emerging_branch(env, capsys, ext):
    d, _ = env
    rows = [(hs, nm, v20, g) for hs, nm, v20, v23, g in BOOK]
    only_big = [("01", "Big", 1000.0, 1.0), ("02", "Big2", 800.0, 1.0)]
    for y in (2020, 2022, 2023):
        write_workbook(d / EXPORT_FILENAMES[y], only_big)
    ext.analyze_extended_trends()
    assert "No emerging commodities found matching criteria" in capsys.readouterr().out


# ── import_export_comparison ─────────────────────────────────────────────────
@pytest.fixture
def cmp_():
    return fresh("import_export_comparison")


def install_import(d, rows):
    write_workbook(d / IMPORT_FILENAME, rows, total_label="India's Total Import")


IMPORTS = [("01", "Alpha", 150.0, 1.0), ("02", "Bravo", 60.0, 1.0), ("03", "Charlie", 70.0, 1.0),
           ("09", "India", 1500.0, 1.0), ("99", "Zulu", 40.0, 1.0)]


def test_loaders_tag_type_and_drop_totals(env, cmp_):
    d, _ = env
    install_import(d, IMPORTS)
    e = cmp_.load_export_file(d / EXPORT_FILENAMES[2023], 2023)
    i = cmp_.load_import_file(d / IMPORT_FILENAME)
    assert (e.Type == "EXPORT").all() and (i.Type == "IMPORT").all()
    assert len(e) == len(BOOK) and len(i) == len(IMPORTS)
    assert "Year" in e.columns and "Year" not in i.columns


def test_load_all_data_assigns_imports_to_the_latest_export_year(env, cmp_, capsys):
    d, _ = env
    install_import(d, IMPORTS)
    data = cmp_.load_all_data()
    assert set(data["exports"]) == {2020, 2022, 2023} and set(data["imports"]) == {2023}
    assert (data["imports"][2023].Year == 2023).all()
    out = capsys.readouterr().out
    assert f"✓ Imports 2023: {len(IMPORTS)} commodities, ${sum(r[2] for r in IMPORTS):,.0f}M total" in out


def test_load_all_data_without_an_import_file(env, cmp_):
    data = cmp_.load_all_data()
    assert data["imports"] == {} and set(data["exports"]) == {2020, 2022, 2023}


def test_trade_balance_table_and_latest_year(env, cmp_, capsys):
    d, _ = env
    install_import(d, IMPORTS)
    data = cmp_.load_all_data()
    exp_s, imp_s = cmp_.analyze_trade_balance(data)
    text = capsys.readouterr().out
    v23, imp = sum(b[3] for b in BOOK), sum(r[2] for r in IMPORTS)
    assert exp_s[2023] == pytest.approx(v23) and imp_s == {2023: pytest.approx(imp)}
    assert f"Total Exports:      ${v23:,.0f}M" in text and f"Total Imports:      ${imp:,.0f}M" in text
    assert f"Trade Balance:      ${v23 - imp:,.0f}M (DEFICIT)" in text
    assert f"Export/Import Ratio: {v23 / imp:.2f}x" in text
    # years with no import data show a zero import column and N/A ratio
    row2020 = [l for l in text.splitlines() if l.strip().startswith("2020")][0]
    assert "N/A" in row2020
    row2023 = [l for l in text.splitlines() if l.strip().startswith("2023")][0]
    assert f"{v23 / imp:.2f}x" in row2023


def test_surplus_label_when_exports_exceed_imports(env, cmp_, capsys):
    d, _ = env
    install_import(d, [("01", "Alpha", 10.0, 1.0)])
    cmp_.analyze_trade_balance(cmp_.load_all_data())
    assert "(SURPLUS)" in capsys.readouterr().out


def test_commodity_comparison_rankings(env, cmp_, capsys):
    d, _ = env
    install_import(d, IMPORTS)
    cmp_.analyze_commodity_comparison(cmp_.load_all_data())
    text = capsys.readouterr().out
    net_exp = text.split("TOP NET EXPORTER COMMODITIES (2023)")[1].split("TOP NET IMPORTER")[0]
    net_imp = text.split("TOP NET IMPORTER COMMODITIES (2023)")[1].split("BALANCED TRADE")[0]
    bal = text.split("BALANCED TRADE (Trade Balance within ±$1B)")[1]
    names = {b[1] for b in BOOK} | {"Zulu"}
    pick = lambda blk: [l.split()[0] for l in blk.splitlines() if l.split() and l.split()[0] in names]
    # export - import: Alpha 200-150=50 (+), Bravo 60-60=0 (neither), Charlie 50-70=-20, India 501-1500=-999, Zulu 0-40
    assert pick(net_exp)[0] == "Juliet" and "Alpha" in pick(net_exp) and "Bravo" not in pick(net_exp)
    assert pick(net_imp)[0] == "India" and set(pick(net_imp)) >= {"Zulu", "Charlie"} and "Alpha" not in pick(net_imp)
    assert pick(bal) == ["India", "Alpha", "Bravo", "Charlie"]          # both flows > 0 and |balance| <= 1000 ($1B)
    assert "Zulu" not in pick(bal) and "Juliet" not in pick(bal)          # no import / no export side


def test_balanced_trade_window_edges(env, cmp_, capsys):
    d, _ = env
    for y in (2020, 2022, 2023):
        write_workbook(d / EXPORT_FILENAMES[y], [("1", "EdgeIn", 1000.0, 1.0), ("2", "EdgeOut", 1000.0, 1.0)])
    install_import(d, [("1", "EdgeIn", 2000.0, 1.0), ("2", "EdgeOut", 2001.0, 1.0)])
    cmp_.analyze_commodity_comparison(cmp_.load_all_data())
    bal = capsys.readouterr().out.split("BALANCED TRADE (Trade Balance within ±$1B)")[1]
    assert "EdgeIn" in bal and "EdgeOut" not in bal                     # |-1000| is inside, |-1001| is not


def test_comparison_needs_matching_years(env, cmp_, capsys):
    cmp_.analyze_commodity_comparison({"exports": {2023: pd.DataFrame()}, "imports": {}})
    assert "Insufficient data for commodity-level comparison" in capsys.readouterr().out


def test_projection_uses_export_cagr_and_a_slower_import_rate(env, cmp_, capsys):
    d, _ = env
    install_import(d, IMPORTS)
    cmp_.project_trade_balance(cmp_.load_all_data())
    text = capsys.readouterr().out
    v20, v23 = sum(b[2] for b in BOOK), sum(b[3] for b in BOOK)
    imp = sum(r[2] for r in IMPORTS)
    cagr = (v23 / v20) ** (1 / 3) - 1
    assert f"Export CAGR (2020-2023): {cagr * 100:.2f}%" in text
    assert f"Projected Import CAGR: {cagr * 0.9 * 100:.2f}%" in text
    pe, pi = v23 * (1 + cagr) ** 3, imp * (1 + cagr * 0.9) ** 3
    assert f"Projected 2026 Exports:    ${pe:,.0f}M" in text and f"Projected 2026 Imports:    ${pi:,.0f}M" in text
    assert f"Projected Trade Balance:   ${pe - pi:,.0f}M" in text
    sc = text.split("TRADE BALANCE SCENARIOS (2026)")[1]
    export_led = [l for l in sc.splitlines() if l.strip().startswith("Export-Led")][0]
    ex = v23 * (1 + cagr * 1.2) ** 3
    im = imp * (1 + cagr * 0.9 * 0.8) ** 3
    assert f"${ex:,.0f}" in export_led and f"${im:,.0f}" in export_led and f"{ex / im:.2f}x" in export_led
    assert [l.split()[0] for l in sc.splitlines() if l.split() and l.split()[0] in ("Balanced", "Export-Led", "Import-Heavy")] == ["Balanced", "Export-Led", "Import-Heavy"]


def test_projection_needs_two_export_years_and_an_import_year(env, cmp_, capsys):
    cmp_.project_trade_balance({"exports": {2023: pd.DataFrame({"Value_Current_Million": [1.0]})}, "imports": {}})
    assert "Insufficient data for trade balance projections" in capsys.readouterr().out


def test_main_runs_end_to_end_and_handles_no_exports(env, cmp_, capsys, monkeypatch):
    d, _ = env
    install_import(d, IMPORTS)
    cmp_.main()
    out = capsys.readouterr().out
    assert "ANALYSIS COMPLETE" in out and "Export data years available: [2020, 2022, 2023]" in out
    assert "Import data years available: [2023]" in out
    monkeypatch.setattr(cmp_, "load_all_data", lambda: {"exports": {}, "imports": {}})
    cmp_.main()
    assert "No export data loaded. Exiting." in capsys.readouterr().out
