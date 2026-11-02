from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("markitdown_pre", Path(__file__).parent.parent / "markitdown-preprocessor.py")


@pytest.fixture
def mp(tmp_path, monkeypatch):
    mod = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(mod)
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
    return mod


def test_text_reference_is_inlined_and_cached(mp, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello world")
    out = mp.process_prompt(f'see @"{f}" please')
    assert "**File: note.txt**" in out and "hello world" in out
    assert len(list(mp.CACHE_DIR.glob("*.md"))) == 1
    assert mp.get_cached_markdown(str(f)) == "hello world"


def test_json_reference_is_fenced(mp, tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"a": 1}))
    assert mp.convert_file_to_markdown(str(f)).startswith("```json")


def test_missing_file_reference_is_left_alone(mp):
    prompt = 'see @"/nonexistent/file.txt"'
    assert mp.process_prompt(prompt) == prompt


def test_large_file_is_truncated(mp, tmp_path, monkeypatch):
    monkeypatch.setattr(mp, "MAX_CHARS", 10)
    f = tmp_path / "big.txt"
    f.write_text("x" * 100)
    assert "truncated, 100 total chars" in mp.process_prompt(f"@'{f}'")


def test_invalid_utf8_returns_none(mp, tmp_path):
    f = tmp_path / "bad.txt"
    f.write_bytes(b"\xff\xfe\x00bad")
    assert mp.convert_text_to_markdown(str(f)) is None


def test_main_passes_through_invalid_json(mp, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    mp.main()
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


def test_main_reports_converted_count(mp, tmp_path, monkeypatch, capsys):
    f = tmp_path / "a.md"
    f.write_text("# hi")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": f'@"{f}"'})))
    mp.main()
    out = json.loads(capsys.readouterr().out)
    assert "1 file(s) converted" in out["systemMessage"]
