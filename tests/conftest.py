import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """No test may see the caller's TradeStat env, and CLI flags never leak in from pytest's argv."""
    monkeypatch.delenv("TRADESTAT_DIR", raising=False)
    monkeypatch.delenv("TRADESTAT_OUT_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["script"])
