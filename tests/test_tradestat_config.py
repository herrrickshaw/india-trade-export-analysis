import sys

import pandas as pd
import pytest

import tradestat_config as cfg
from helpers import install_books


def test_flag_beats_env_and_env_is_the_fallback(monkeypatch, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    monkeypatch.setenv("TRADESTAT_DIR", str(a))
    assert cfg.data_dir() == a
    monkeypatch.setattr(sys, "argv", ["x", "--data-dir", str(b), "--unrelated", "1"])
    assert cfg.data_dir() == b                                     # unknown flags are ignored


def test_data_dir_errors_are_clear(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as e:
        cfg.data_dir()
    msg = str(e.value)
    assert "TradeStat workbooks directory not set" in msg
    for name in list(cfg.EXPORT_FILENAMES.values()) + [cfg.IMPORT_FILENAME]:
        assert name in msg
    monkeypatch.setenv("TRADESTAT_DIR", str(tmp_path / "missing"))
    with pytest.raises(SystemExit, match="data directory not found"):
        cfg.data_dir()


def test_data_dir_expands_user(monkeypatch, tmp_path):
    (tmp_path / "wb").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TRADESTAT_DIR", "~/wb")
    assert cfg.data_dir() == tmp_path / "wb"


def test_out_dir_defaults_to_cwd_and_creates_nested_directories(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert str(cfg.out_dir()) == "."
    target = tmp_path / "x" / "y"
    monkeypatch.setenv("TRADESTAT_OUT_DIR", str(target))
    assert cfg.out_dir() == target and target.is_dir()
    other = tmp_path / "flag"
    monkeypatch.setattr(sys, "argv", ["x", "--out-dir", str(other)])
    assert cfg.out_dir() == other and other.is_dir()


def test_export_files_all_or_selected_and_missing(monkeypatch, tmp_path):
    install_books(tmp_path / "d")
    monkeypatch.setenv("TRADESTAT_DIR", str(tmp_path / "d"))
    allf = cfg.export_files()
    assert set(allf) == {2020, 2022, 2023} and allf[2020].name == cfg.EXPORT_FILENAMES[2020]
    assert set(cfg.export_files([2023])) == {2023}
    (tmp_path / "d" / cfg.EXPORT_FILENAMES[2022]).unlink()
    with pytest.raises(SystemExit) as e:
        cfg.export_files()
    assert cfg.EXPORT_FILENAMES[2022] in str(e.value) and cfg.EXPORT_FILENAMES[2020] not in str(e.value)
    assert set(cfg.export_files([2020, 2023])) == {2020, 2023}     # an unneeded missing file is fine


def test_import_file_path(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADESTAT_DIR", str(tmp_path))
    assert cfg.import_file() == tmp_path / cfg.IMPORT_FILENAME


def test_drop_total_row_variants():
    df = pd.DataFrame({"Commodity": ["Rice", "India's Total Export", "  india's total import ", "Indias Total", "Total of India", "Tea"],
                       "Value": [1.0, 10.0, 20.0, 30.0, 40.0, 2.0]})
    items, total = cfg.drop_total_row(df, "Commodity", "Value")
    assert items.Commodity.tolist() == ["Rice", "Total of India", "Tea"]       # pattern is anchored at the start
    assert total == 10.0 and isinstance(total, float)                          # first total row wins
    assert len(df) == 6                                                        # input untouched
    items2, none = cfg.drop_total_row(df, "Commodity")
    assert none is None and len(items2) == 3
    clean = pd.DataFrame({"Commodity": ["a", "b"], "Value": [1, 2]})
    c, t = cfg.drop_total_row(clean, "Commodity", "Value")
    assert len(c) == 2 and t is None
    assert cfg.drop_total_row(pd.DataFrame({"Commodity": [None, "x"]}), "Commodity")[0].shape[0] == 2   # NaN is not a total


def test_merge_years_keys_on_hscode_and_commodity():
    a = pd.DataFrame({"HSCode": ["01", "02", "03"], "Commodity": ["x", "x", "y"], "A": [1, 2, 3]})
    b = pd.DataFrame({"HSCode": ["01", "02", "04"], "Commodity": ["x", "x", "y"], "B": [10, 20, 30]})
    m = cfg.merge_years(a, b)
    assert len(m) == 2 and m.sort_values("HSCode").B.tolist() == [10, 20]       # no many-to-many blow-up
    outer = cfg.merge_years(a, b, how="outer")
    assert len(outer) == 4
    assert len(a.merge(b, on="Commodity")) == 5                                  # what the old text-only join did
