"""Run every CLI script end-to-end on synthetic workbooks under a fake HOME (characterisation of pre-refactor output)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import synthetic

REPO = Path(__file__).resolve().parent.parent


def run_script(name: str, home: Path, cwd: Path):
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, str(REPO / name)], cwd=cwd, env=env,
                          capture_output=True, text=True, check=False)


def test_export_insights(fake_home, tmp_path):
    r = run_script("export_insights.py", fake_home, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Found 37 commodities" in r.stdout
    assert "Total exports: $569,751M" in r.stdout


def test_export_insights_without_data_exits_1(tmp_path):
    r = run_script("export_insights.py", tmp_path, tmp_path)
    assert r.returncode == 1 and "No data loaded!" in r.stdout


def test_export_extended_analysis_writes_csvs_to_cwd(fake_home, tmp_path):
    r = run_script("export_extended_analysis.py", fake_home, tmp_path)
    assert r.returncode == 0, r.stderr
    assert len((tmp_path / "EXTENDED_ANALYSIS_2020_2026.csv").read_text().splitlines()) == 40
    assert len((tmp_path / "HIGH_OPPORTUNITY_2026_PROJECTIONS.csv").read_text().splitlines()) == 39


def test_export_opportunities_writes_to_downloads(fake_home, tmp_path):
    r = run_script("export_opportunities.py", fake_home, tmp_path)
    assert r.returncode == 0, r.stderr
    out = fake_home / "Downloads"
    assert len((out / "HIGH_OPPORTUNITY_EXPORTS.csv").read_text().splitlines()) == 38
    assert len((out / "MEGA_GROWTH_EXPORTS.csv").read_text().splitlines()) == 30
    top = json.loads((out / "TOP_OPPORTUNITIES.json").read_text())
    assert list(top) == ["MEGA_GROWTH", "HIGH_VALUE_GROWING", "EMERGING_OPPORTUNITY"]
    assert "MEGA_GROWTH               | Count:   29" in r.stdout


def test_import_export_comparison(fake_home, tmp_path):
    r = run_script("import_export_comparison.py", fake_home, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Trade Balance:      $-341,850M (DEFICIT)" in r.stdout
    assert "Projected Trade Balance:   $-854,115M" in r.stdout


def test_import_export_comparison_exports_only(tmp_path):
    synthetic.build_home(tmp_path, with_imports=False)
    r = run_script("import_export_comparison.py", tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Import data years available: None" in r.stdout


def test_export_analysis_flat_layout(tmp_path):
    synthetic.build_home(tmp_path, flat=True)
    r = run_script("export_analysis.py", tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Growing commodities: 23" in r.stdout


def test_export_analysis_no_data(tmp_path):
    r = run_script("export_analysis.py", tmp_path, tmp_path)
    assert r.returncode == 0
    assert "No data could be loaded" in r.stdout


@pytest.mark.parametrize("script", ["export_analysis.py", "export_extended_analysis.py", "export_insights.py",
                                    "export_opportunities.py", "import_export_comparison.py"])
def test_scripts_import_without_side_effects(script):
    r = subprocess.run([sys.executable, "-c", f"import importlib; importlib.import_module('{script[:-3]}')"],
                       cwd=REPO, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""
