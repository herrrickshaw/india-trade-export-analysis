import io
import json

import pytest

from conftest import load_script


@pytest.fixture
def mp(tmp_path, monkeypatch):
    # The module creates its cache dir under ~ at import time: point HOME at tmp.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return load_script("markitdown-preprocessor.py")


def test_cache_dir_is_created_under_home(mp, tmp_path):
    assert str(mp.CACHE_DIR).startswith(str(tmp_path / "home"))
    assert mp.CACHE_DIR.is_dir()


def test_csv_reference_is_replaced_with_markdown_table(mp, tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("a,b\n1,2\n")
    out = mp.process_prompt(f'look at @"{f}" please')
    assert "**File: t.csv**" in out
    assert "|   a |   b |" in out and "|   1 |   2 |" in out


def test_missing_file_reference_left_untouched(mp, tmp_path):
    prompt = f'see @"{tmp_path}/nope.csv"'
    assert mp.process_prompt(prompt) == prompt


def test_large_file_is_truncated(mp, tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 60000)
    out = mp.process_prompt(f"@'{f}'")
    assert "truncated, 60000 total chars" in out


def test_conversion_is_cached_by_path_and_mtime(mp, tmp_path):
    f = tmp_path / "n.md"
    f.write_text("hello")
    assert mp.convert_file_to_markdown(str(f)) == "hello"
    assert len(list(mp.CACHE_DIR.glob("*.md"))) == 1


def test_hook_output_carries_converted_file_content(mp, tmp_path, monkeypatch, capsys):
    """The hook advertises that file references are converted 'before sending to
    Claude', but main() computed processed_prompt and never emitted it: only a
    count reached the model. The converted content must be in the hook output."""
    f = tmp_path / "data.csv"
    f.write_text("commodity,value\nRICE,500\n")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": f'summarise @"{f}"'})))
    mp.main()
    result = json.loads(capsys.readouterr().out)
    ctx = result["hookSpecificOutput"].get("additionalContext", "")
    assert "RICE" in ctx


def test_hook_passes_through_on_invalid_json(mp, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    mp.main()
    assert json.loads(capsys.readouterr().out) == {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
