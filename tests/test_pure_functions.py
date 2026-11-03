from __future__ import annotations

import math

import pytest

import export_analysis as ea
import export_extended_analysis as ext
import export_opportunities as opp
from trade_common import load_all_exports


def test_project_growth_compounds_cagr():
    # 8x over 3 years -> CAGR 100%; 2025 is 2 years past 2023 -> 4x
    assert ext.project_growth(1, 8, 2025) == pytest.approx(8 * 4)


def test_project_growth_caps_extreme_cagr():
    assert ext.project_growth(1, 1000, 2024) == pytest.approx(1000 * 1.3)


@pytest.mark.parametrize("a,b", [(0, 5), (5, 0), (-1, 5), (float("nan"), 5)])
def test_project_growth_invalid_inputs_are_nan(a, b):
    assert math.isnan(ext.project_growth(a, b))


@pytest.mark.parametrize("value,growth,label", [
    (6000, 60, "MEGA_GROWTH"),
    (2000, 30, "HIGH_VALUE_GROWING"),
    (200, 150, "EMERGING_OPPORTUNITY"),
    (600, 5, "PREMIUM_STABLE"),
    (50, 5, "OTHER"),
])
def test_classify_opportunity(value, growth, label):
    assert opp.classify_opportunity({"Value_2023_M": value, "Growth_5yr_%": growth}) == label


def test_extract_year_defaults_to_latest():
    assert ea.extract_year("x 2020.xlsx") == 2020
    assert ea.extract_year("x2022.xlsx") == 2022
    assert ea.extract_year("x.xlsx") == 2023


def test_find_columns_by_keyword():
    assert ea.find_columns(["Commodity Name", "Export Value", "Quantity"]) == ("Commodity Name", "Export Value", "Quantity")
    assert ea.find_columns(["a", "b"]) == (None, None, None)


def test_build_projection_frame_columns(fake_home):
    frame = ext.build_projection_frame(load_all_exports(verbose=False))
    for col in ("Growth_2020_2023_%", "Projected_2025_Million", "Projected_2026_Million"):
        assert col in frame.columns
    assert len(frame) == 39  # 40 synthetic commodities minus the one with no value in either year
