"""Shared fixtures: synthetic TradeStat commodity-wise workbooks (no network, no real data)."""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]


def load_script(name):
    """Import a top-level script (some have hyphens in the filename) as a module."""
    path = REPO / name
    mod_name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def write_tradestat_xlsx(path, rows, total_label="India's Total Export"):
    """Write a workbook laid out like a TradeStat EIDB commodity-wise download.

    Two title rows, then a header row, then commodity rows, then the
    national-total row that TradeStat appends (Commodity and HSCode both carry
    the label, as seen in this repo's committed outputs, e.g.
    HIGH_OPPORTUNITY_EXPORTS.csv). ``rows`` is a list of (hs, name, v_cur, v_next).
    """
    header = ["S.No.", "HSCode", "Commodity", "2022-2023", "%Share", "2023-2024", "%Share", "%Growth"]
    body = []
    for i, (hs, name, cur, nxt) in enumerate(rows, start=1):
        body.append([i, hs, name, cur, None, nxt, None, (nxt - cur) / cur * 100])
    if total_label is not None:
        tc = sum(r[2] for r in rows)
        tn = sum(r[3] for r in rows)
        body.append([None, total_label, total_label, tc, 100.0, tn, 100.0, (tn - tc) / tc * 100])
    sheet = [["Department of Commerce - Export Import Data Bank", *[None] * 7],
             ["Commodity-wise all commodities (Values in US$ Million)", *[None] * 7],
             header, *body]
    pd.DataFrame(sheet).to_excel(path, header=False, index=False)
    return path


@pytest.fixture
def tradestat_xlsx(tmp_path):
    def make(name="exports.xlsx", rows=None, total_label="India's Total Export"):
        rows = rows or [("10063020", "BASMATI RICE", 400.0, 500.0),
                        ("30049099", "OTHER MEDICAMENTS", 300.0, 330.0),
                        ("71023910", "CUT DIAMONDS", 300.0, 270.0)]
        return write_tradestat_xlsx(tmp_path / name, rows, total_label)
    return make
