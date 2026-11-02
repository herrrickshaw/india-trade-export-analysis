from __future__ import annotations

import pandas as pd

import trade_common as tc
from synthetic import EXPORT_FILES, COLS


def test_load_trade_file_drops_missing_values_and_tags(fake_home):
    path = tc.data_dir() / EXPORT_FILES[2023]
    df = tc.load_trade_file(path, year=2023, trade_type="EXPORT")
    assert list(df.columns[:8]) == COLS
    assert len(df) == 39  # synthetic row 5 has no value -> dropped
    assert set(df["Year"]) == {2023} and set(df["Type"]) == {"EXPORT"}
    assert pd.api.types.is_numeric_dtype(df["Value_Current_Million"])


def test_load_all_exports_skips_missing_files(fake_home):
    (tc.data_dir() / EXPORT_FILES[2022]).unlink()
    data = tc.load_all_exports(verbose=False)
    assert sorted(data) == [2020, 2023]


def test_load_all_exports_reports_corrupt_file(fake_home, capsys):
    (tc.data_dir() / EXPORT_FILES[2020]).write_bytes(b"not a workbook")
    data = tc.load_all_exports()
    assert 2020 not in data and 2023 in data
    assert "Error loading 2020" in capsys.readouterr().out


def test_paths_follow_home(fake_home):
    assert tc.output_dir() == fake_home / "Downloads"
    assert tc.data_dir().name == "import export data"
