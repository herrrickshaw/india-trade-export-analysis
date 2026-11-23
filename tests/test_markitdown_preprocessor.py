import importlib.util
import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parent.parent / "markitdown-preprocessor.py"


@pytest.fixture
def mk(tmp_path, monkeypatch):
    """Import the hook with HOME redirected: the module creates ~/.claude/hooks/.markitdown-cache at import."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    spec = importlib.util.spec_from_file_location("markitdown_preprocessor", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_import_creates_the_cache_under_home_only(mk, tmp_path):
    assert mk.CACHE_DIR == tmp_path / "home" / ".claude" / "hooks" / ".markitdown-cache" and mk.CACHE_DIR.is_dir()


def test_cache_key_depends_on_path_and_mtime(mk, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    k1 = mk.get_cache_key(str(f))
    assert len(k1) == 32 and k1 == mk.get_cache_key(str(f))
    import os
    os.utime(f, (1, 1))
    assert mk.get_cache_key(str(f)) != k1
    assert mk.get_cache_key(str(tmp_path / "missing")) is None


def test_cache_round_trip_and_missing_file(mk, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert mk.get_cached_markdown(str(f)) is None
    mk.save_to_cache(str(f), "# md")
    assert mk.get_cached_markdown(str(f)) == "# md"
    assert mk.get_cached_markdown(str(tmp_path / "nope")) is None
    mk.save_to_cache(str(tmp_path / "nope"), "ignored")                 # no key -> silently skipped
    assert len(list(mk.CACHE_DIR.glob("*.md"))) == 1


def test_converters(mk, tmp_path):
    csvf = tmp_path / "t.csv"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(csvf, index=False)
    md = mk.convert_csv_to_markdown(str(csvf))
    lines = md.splitlines()
    assert [c.strip() for c in lines[0].strip("|").split("|")] == ["a", "b"]
    assert [c.strip() for c in lines[-1].strip("|").split("|")] == ["2", "y"]
    xl = tmp_path / "t.xlsx"
    pd.DataFrame({"a": range(150)}).to_excel(xl, index=False)
    assert len(mk.convert_excel_to_markdown(str(xl)).splitlines()) == 102      # header + rule + 100 rows (nrows cap)
    j = tmp_path / "t.json"
    j.write_text('{"k": [1, 2]}')
    assert mk.convert_json_to_markdown(str(j)) == '```json\n{\n  "k": [\n    1,\n    2\n  ]\n}\n```'
    t = tmp_path / "t.txt"
    t.write_text("héllo", encoding="utf-8")
    assert mk.convert_text_to_markdown(str(t)) == "héllo"
    for fn in (mk.convert_excel_to_markdown, mk.convert_csv_to_markdown, mk.convert_json_to_markdown, mk.convert_text_to_markdown):
        assert fn(str(tmp_path / "missing.bin")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert mk.convert_json_to_markdown(str(bad)) is None


@pytest.mark.parametrize("name,payload", [("a.md", "# hi"), ("a.py", "print(1)"), ("a.yml", "k: v"), ("a.weird", "plain")])
def test_text_like_extensions_are_read_verbatim(mk, tmp_path, name, payload):
    f = tmp_path / name
    f.write_text(payload)
    assert mk.convert_file_to_markdown(str(f)) == payload


def test_convert_file_dispatch_cache_and_missing(mk, tmp_path, monkeypatch):
    f = tmp_path / "d.csv"
    f.write_text("a,b\n1,2\n")
    first = mk.convert_file_to_markdown(str(f))
    assert [c.strip() for c in first.splitlines()[0].strip("|").split("|")] == ["a", "b"]
    monkeypatch.setattr(mk, "convert_csv_to_markdown", lambda p: pytest.fail("cache must be used"))
    assert mk.convert_file_to_markdown(str(f)) == first                    # second call served from the cache
    assert mk.convert_file_to_markdown(str(tmp_path / "missing.csv")) is None
    assert mk.convert_file_to_markdown(str(tmp_path)) is None              # a directory is not a file
    empty = tmp_path / "e.txt"
    empty.write_text("")
    assert mk.convert_file_to_markdown(str(empty)) is None                 # empty result is not cached or returned


def test_convert_expands_tilde(mk, tmp_path, monkeypatch):
    (tmp_path / "home").mkdir(exist_ok=True)
    (tmp_path / "home" / "n.txt").write_text("note")
    assert mk.convert_file_to_markdown("~/n.txt") == "note"


def test_process_prompt_replaces_references(mk, tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("body")
    out = mk.process_prompt(f"see @\"{f}\" and @'{f}' please")
    assert out.count("**File: n.txt**") == 2 and out.count("```\nbody\n```") == 2
    assert out.startswith("see \n**File: n.txt**") and out.endswith(" please")


def test_process_prompt_keeps_unconvertible_references_and_empty_prompts(mk, tmp_path):
    ref = f'@"{tmp_path}/missing.txt"'
    assert mk.process_prompt(f"x {ref} y") == f"x {ref} y"
    assert mk.process_prompt("") == "" and mk.process_prompt(None) is None
    assert mk.process_prompt("no refs here") == "no refs here"


def test_process_prompt_truncates_at_fifty_thousand_characters(mk, tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("a" * 50_000)
    assert "truncated" not in mk.process_prompt(f'@"{f}"')                 # exactly the limit is kept whole
    f.write_text("a" * 50_001)
    out = mk.process_prompt(f'@"{f}"')
    assert "... (truncated, 50001 total chars)" in out
    assert "a" * 50_000 in out and "a" * 50_001 not in out


def run_main(mk, monkeypatch, capsys, stdin_text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    mk.main()
    return json.loads(capsys.readouterr().out)


def test_main_reports_converted_references(mk, tmp_path, monkeypatch, capsys):
    f = tmp_path / "n.txt"
    f.write_text("body")
    res = run_main(mk, monkeypatch, capsys, json.dumps({"prompt": f'look @"{f}"'}))
    assert res["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "Converted 1 file reference(s)" in res["hookSpecificOutput"]["additionalContext"]
    assert res["systemMessage"] == "✓ Markitdown: 1 file(s) converted to markdown format"


def test_main_counts_every_reference_even_unconvertible_ones(mk, tmp_path, monkeypatch, capsys):
    res = run_main(mk, monkeypatch, capsys, json.dumps({"prompt": f'@"{tmp_path}/a.txt" @"{tmp_path}/b.txt"'}))
    assert "Converted 2 file reference(s)" in res["hookSpecificOutput"]["additionalContext"]
    assert "systemMessage" not in res                                       # nothing actually changed


def test_main_without_prompt_or_with_bad_json(mk, monkeypatch, capsys):
    assert run_main(mk, monkeypatch, capsys, json.dumps({"prompt": ""})) == {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
    assert run_main(mk, monkeypatch, capsys, json.dumps({})) == {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
    assert run_main(mk, monkeypatch, capsys, "{not json") == {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}


def test_main_never_blocks_on_unexpected_errors(mk, monkeypatch, capsys):
    monkeypatch.setattr(mk, "process_prompt", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    res = run_main(mk, monkeypatch, capsys, json.dumps({"prompt": "x"}))
    assert res["hookSpecificOutput"]["additionalContext"] == "Markitdown hook skipped: boom"
