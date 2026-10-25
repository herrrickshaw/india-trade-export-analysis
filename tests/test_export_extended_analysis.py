import math

import pytest

from conftest import load_script

eea = load_script("export_extended_analysis.py")


def test_loader_drops_tradestat_total_row(tradestat_xlsx):
    df = eea.load_export_file(tradestat_xlsx(), 2020)
    assert len(df) == 3
    assert df["Value_Current_Million"].sum() == pytest.approx(1000.0)


def test_project_growth_hand_computed():
    # 100 -> 133.1 over 3 years = 10% CAGR; 2025 = 133.1 * 1.1**2 = 161.051
    assert eea.project_growth(100.0, 133.1, 2025) == pytest.approx(161.051)
    assert eea.project_growth(100.0, 133.1, 2026) == pytest.approx(177.1561)


def test_project_growth_target_2023_returns_last_value():
    assert eea.project_growth(100.0, 133.1, 2023) == pytest.approx(133.1)


@pytest.mark.parametrize("v20,v23", [(0, 10), (10, 0), (-5, 10), (float("nan"), 10), (10, float("nan"))])
def test_project_growth_invalid_inputs_are_nan(v20, v23):
    assert math.isnan(eea.project_growth(v20, v23))


def test_project_growth_caps_explosive_cagr_at_30pct():
    # 1 -> 1000 over 3 years is a 900% CAGR (>500%), so 30% is substituted.
    assert eea.project_growth(1.0, 1000.0, 2025) == pytest.approx(1000.0 * 1.3 ** 2)


def test_extract_year_from_filename():
    assert eea.extract_year("x 2020.xlsx") == 2020
    assert eea.extract_year("x2022.xlsx") == 2022
    assert eea.extract_year("x 2025-26.xlsx") == 2025
    assert eea.extract_year("TradeStat.xlsx") == 2023
