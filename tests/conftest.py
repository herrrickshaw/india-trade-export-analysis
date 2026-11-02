from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import synthetic  # noqa: E402


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """A fake HOME with synthetic TradeStat workbooks under Downloads/import export data."""
    synthetic.build_home(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path
