import math

import pytest

from conftest import load_script

iec = load_script("import_export_comparison.py")


def test_export_loader_keeps_commodity_rows(tradestat_xlsx):
    df = iec.load_export_file(tradestat_xlsx(), 2023)
    assert "BASMATI RICE" in set(df["Commodity"])
    assert set(df["Type"]) == {"EXPORT"}
    assert set(df["Year"]) == {2023}


def test_export_loader_drops_tradestat_total_row(tradestat_xlsx):
    df = iec.load_export_file(tradestat_xlsx(), 2023)
    assert not df["Commodity"].str.contains("Total", case=False).any()
    assert len(df) == 3


def test_trade_balance_totals_equal_sum_of_commodities_not_double(tradestat_xlsx, capsys):
    """Commodities sum to 1,000 exports / 600 imports. With the TradeStat
    'India's Total ...' row counted as a commodity the totals came out 2x."""
    exp = iec.load_export_file(tradestat_xlsx("e.xlsx"), 2023)
    imp = iec.load_import_file(
        tradestat_xlsx("i.xlsx", rows=[("27090000", "CRUDE OIL", 500.0, 550.0),
                                       ("71081200", "GOLD", 100.0, 120.0)],
                       total_label="India's Total Import"), 2023)
    exp_sum, imp_sum = iec.analyze_trade_balance({"exports": {2023: exp}, "imports": {2023: imp}})
    assert exp_sum[2023] == pytest.approx(1000.0)
    assert imp_sum[2023] == pytest.approx(600.0)


def test_import_loader_drops_total_row_and_tags_type(tradestat_xlsx):
    df = iec.load_import_file(tradestat_xlsx(total_label="India's Total Import"))
    assert set(df["Type"]) == {"IMPORT"}
    assert "Year" not in df.columns  # year is optional and only set when given
    assert len(df) == 3


def test_commodity_named_with_word_total_is_not_dropped(tradestat_xlsx):
    rows = [("48025490", "PAPER NOT MORE THAN 10% BY WT OF TOTAL FBR", 15.0, 26.0),
            ("10063020", "BASMATI RICE", 400.0, 500.0)]
    df = iec.load_export_file(tradestat_xlsx(rows=rows), 2023)
    assert len(df) == 2


def test_projection_uses_export_cagr_and_imports_at_90pct(capsys):
    """Hand computed: exports 100 (2020) -> 121 (2022) => CAGR 10%; import CAGR = 9%.
    2026 exports = 121 * 1.1**4 = 177.1561 ; imports = 50 * 1.09**4 = 70.579..."""
    import pandas as pd
    mk = lambda v: pd.DataFrame({"Value_Current_Million": [v]})
    iec.project_trade_balance({"exports": {2020: mk(100.0), 2022: mk(121.0)},
                               "imports": {2022: mk(50.0)}})
    out = capsys.readouterr().out
    assert "Export CAGR (2020-2022): 10.00%" in out
    assert "Projected Import CAGR: 9.00%" in out
    assert "$177M" in out
    assert "$71M" in out  # 70.579 rounds to 71


def test_projection_insufficient_data_message(capsys):
    import pandas as pd
    iec.project_trade_balance({"exports": {2023: pd.DataFrame({"Value_Current_Million": [1.0]})},
                               "imports": {}})
    assert "Insufficient data" in capsys.readouterr().out


def test_commodity_comparison_outer_merge_balance(capsys):
    import pandas as pd
    exp = pd.DataFrame({"Commodity": ["RICE", "GOLD"], "Value_Current_Million": [500.0, 50.0]})
    imp = pd.DataFrame({"Commodity": ["GOLD", "OIL"], "Value_Current_Million": [400.0, 900.0]})
    iec.analyze_commodity_comparison({"exports": {2023: exp}, "imports": {2023: imp}})
    out = capsys.readouterr().out
    net_exp = out.split("TOP NET EXPORTER")[1].split("TOP NET IMPORTER")[0]
    net_imp = out.split("TOP NET IMPORTER")[1]
    assert "RICE" in net_exp and "OIL" not in net_exp
    assert "OIL" in net_imp and "-900" in net_imp
