import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from helpers import BOOK, install_books, write_workbook
from tradestat_config import EXPORT_FILENAMES, IMPORT_FILENAME

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def books(tmp_path, monkeypatch):
    d = tmp_path / "data"
    totals = install_books(d)
    out = tmp_path / "out"
    monkeypatch.setenv("TRADESTAT_DIR", str(d))
    monkeypatch.setenv("TRADESTAT_OUT_DIR", str(out))
    monkeypatch.chdir(tmp_path)
    return d, out, totals


def run_script(name, capsys, *args):
    sys.argv = [name, *args]
    try:
        runpy.run_path(str(ROOT / name), run_name="__main__")
    except SystemExit as e:
        return capsys.readouterr().out, e
    return capsys.readouterr().out, None


def table_names(block):
    return [l.split()[0] for l in block.splitlines() if l.split() and l.split()[0] in {b[1] for b in BOOK}]


# ── export_insights.py ───────────────────────────────────────────────────────
def test_insights_filters_and_summary(books, capsys):
    out, exit_ = run_script("export_insights.py", capsys)
    assert exit_ is None
    for y in (2020, 2022, 2023):
        assert f"✓ Loaded {y}: {len(BOOK)} commodities" in out            # the total row was dropped, not counted
    a1 = out.split("HIGH-VALUE EXPORTS WITH STRONG GROWTH (Last Available Year)")[1].split("5-YEAR GROWTH")[0]
    # latest file: value > 1 and growth > 20, by value desc. Bravo (growth exactly 20) and Kilo (value < 1) are out.
    names = table_names(a1)
    assert names[0] == "Alpha" and set(names[1:3]) == {"Charlie", "Golf"} and names[3:] == ["Hotel", "Echo", "Foxtrot"]
    assert not {"Bravo", "Kilo", "India", "Delta"} & set(names)
    assert "Top 20 exports: Value >$1M + Growth >20% (Year 2023)" in a1
    five = out.split("Exports: Value $50M+ in 2023 + 10%+ Growth (2020-2023):")[1].split("EMERGING HIGH-GROWTH")[0]
    # 2023 value > 50 and 2020->2023 growth > 10%: Charlie (exactly 50, 0%) is out; India/Juliet grew 25%
    assert "Found 4 commodities" in five and table_names(five) == ["India", "Juliet", "Alpha", "Bravo"]
    emerging = out.split("EMERGING HIGH-GROWTH EXPORTS")[1].split("PREMIUM EXPORTS")[0]
    assert "Found 2 commodities" in emerging
    assert table_names(emerging) == ["Golf", "Echo"]                        # 10 < value <= 50, growth > 50%, by growth desc
    premium = out.split("Top premium exports ($500M+ value in 2023):")[1].split("SUMMARY STATISTICS")[0]
    assert table_names(premium) == ["India"]                                # 501 yes, exactly 500 no
    summ = out.split("SUMMARY STATISTICS")[1]
    v20, v23 = sum(b[2] for b in BOOK), sum(b[3] for b in BOOK)
    y2020, y2023 = summ.split("2020:")[1].split("2022:")[0], summ.split("2023:")[1]
    assert f"Total exports: ${v20:,.0f}M" in y2020 and f"Total exports: ${v23:,.0f}M" in y2023   # not doubled by the total row
    assert f"Commodities: {len(BOOK)}" in y2020
    assert f"Avg value/commodity: ${v23 / len(BOOK):,.1f}M" in y2023
    assert "Top 5 commodities: India... ($501M), Juliet... ($500M), Alpha... ($200M), Bravo... ($60M)" in y2023


def test_insights_no_high_growth_branch(books, capsys, tmp_path):
    rows = [(hs, nm, v, 1.0) for hs, nm, v, _, _ in BOOK]
    write_workbook(books[0] / EXPORT_FILENAMES[2023], rows)
    out, _ = run_script("export_insights.py", capsys)
    assert "No exports found with Value >$1M and Growth >20%" in out


def test_insights_missing_workbook_exits(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TRADESTAT_DIR", str(tmp_path))
    out, exit_ = run_script("export_insights.py", capsys)
    assert exit_ is not None and "missing workbook" in str(exit_.code)


# ── export_opportunities.py ──────────────────────────────────────────────────
@pytest.fixture
def opp():
    import importlib
    sys.modules.pop("export_opportunities", None)
    return importlib.import_module("export_opportunities")


# (hs, name, value_2020, value_2023)
CASES = [
    ("M1", "MegaOk", 1000, 5001), ("M2", "MegaValEdge", 3000, 5000), ("M3", "MegaGrowEdge", 4000, 6000),
    ("H1", "HighOk", 500, 1001), ("H2", "HighValEdge", 500, 1000), ("H3", "HighGrowEdge", 1000, 1200),
    ("E1", "EmergOk", 40, 101), ("E2", "EmergValEdge", 40, 100), ("E3", "EmergGrowEdge", 50.5, 101),
    ("P1", "PremiumOk", 400, 501), ("P2", "PremiumEdge", 400, 500), ("O1", "Other", 10, 10),
]


def install_cases(d, cases):
    for y in (2020, 2022, 2023):
        rows = [(hs, nm, (v23 if y == 2023 else v20), 5.0) for hs, nm, v20, v23 in cases]
        write_workbook(d / EXPORT_FILENAMES[y], rows)


def test_opportunity_class_thresholds_are_strict(books, opp):
    install_cases(books[0], CASES)
    merged = opp.create_optimized_export()
    cls = merged.set_index("Commodity").Opportunity.to_dict()
    assert cls == {
        "MegaOk": "MEGA_GROWTH",
        "MegaValEdge": "HIGH_VALUE_GROWING",       # exactly 5000 is not > 5000
        "MegaGrowEdge": "HIGH_VALUE_GROWING",      # exactly 50% growth is not > 50%
        "HighOk": "HIGH_VALUE_GROWING",
        "HighValEdge": "PREMIUM_STABLE",           # exactly 1000 is not > 1000 (growth 100% is not > 100 either)
        "HighGrowEdge": "PREMIUM_STABLE",          # exactly 20% is not > 20%
        "EmergOk": "EMERGING_OPPORTUNITY",
        "EmergValEdge": "OTHER",                   # exactly 100 is not > 100
        "EmergGrowEdge": "OTHER",                  # exactly 100% is not > 100%
        "PremiumOk": "PREMIUM_STABLE",
        "PremiumEdge": "OTHER",                    # exactly 500 is not > 500
        "Other": "OTHER"}
    g = merged.set_index("Commodity")["Growth_5yr_%"]
    assert g["MegaOk"] == pytest.approx(400.1) and g["MegaGrowEdge"] == pytest.approx(50.0)


def test_opportunity_outputs(books, opp, capsys):
    d, out, _ = books
    install_cases(d, CASES)
    opp.create_optimized_export()
    text = capsys.readouterr().out
    high = pd.read_csv(out / "HIGH_OPPORTUNITY_EXPORTS.csv", dtype={"HSCode": str})
    assert list(high.columns) == ["Commodity", "HSCode", "Value_2020_M", "Value_2023_M", "Growth_5yr_%", "Opportunity"]
    assert set(high.Opportunity) == {"MEGA_GROWTH", "HIGH_VALUE_GROWING", "EMERGING_OPPORTUNITY"}
    assert list(high.Value_2023_M) == sorted(high.Value_2023_M, reverse=True)
    assert high.Commodity.iloc[0] == "MegaGrowEdge"                              # 6000 is the largest 2023 value
    assert set(high.Commodity) == {"MegaOk", "MegaValEdge", "MegaGrowEdge", "HighOk", "EmergOk"}
    assert f"✓ HIGH_OPPORTUNITY_EXPORTS.csv ({len(high)} rows)" in text
    mega = pd.read_csv(out / "MEGA_GROWTH_EXPORTS.csv")
    assert list(mega.columns) == ["Commodity", "Value_2023_M", "Growth_5yr_%"] and list(mega.Commodity) == ["MegaOk"]
    top = json.load(open(out / "TOP_OPPORTUNITIES.json"))
    assert set(top) == {"MEGA_GROWTH", "HIGH_VALUE_GROWING", "EMERGING_OPPORTUNITY"}
    assert [r["Commodity"] for r in top["HIGH_VALUE_GROWING"]][0] == "MegaGrowEdge"
    row = [l for l in text.splitlines() if l.startswith("MEGA_GROWTH")][0]
    assert "Count:    1" in row and "Avg Value: $   5,001M" in row and "Avg Growth:  400.1%" in row
    assert "PREMIUM_STABLE" in text


def test_top_five_per_category_in_the_json(books, opp):
    d, out, _ = books
    many = [(f"H{i}", f"High{i}", 500, 1100 + i) for i in range(7)]
    install_cases(d, many)
    opp.create_optimized_export()
    top = json.load(open(out / "TOP_OPPORTUNITIES.json"))
    assert [r["Commodity"] for r in top["HIGH_VALUE_GROWING"]] == [f"High{i}" for i in (6, 5, 4, 3, 2)]
    assert top["MEGA_GROWTH"] == [] and top["EMERGING_OPPORTUNITY"] == []


def test_opportunities_cli_writes_files_and_announces_the_output_dir(books, capsys):
    out_text, exit_ = run_script("export_opportunities.py", capsys)
    assert exit_ is None and f"✓ Token-optimized exports created in {books[1]}" in out_text
    assert (books[1] / "HIGH_OPPORTUNITY_EXPORTS.csv").exists()


def test_totals_row_is_not_double_counted_in_the_merge(books, opp):
    merged = opp.create_optimized_export()
    assert len(merged) == len(BOOK)
    assert not merged.Commodity.str.lower().str.startswith("india's total").any()
