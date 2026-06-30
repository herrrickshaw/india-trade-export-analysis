#!/usr/bin/env python3
"""
Markitdown preprocessing hook for Claude Code.
Automatically converts file references (@"/path/file") to markdown before sending to Claude.
Caches results to avoid reprocessing identical files.
Uses pandas/openpyxl for Excel, built-in tools for others.
"""

import sys
import json
import re
import os
import hashlib
from pathlib import Path

# Cache directory
CACHE_DIR = Path.home() / ".claude" / "hooks" / ".markitdown-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_cache_key(filepath: str) -> str:
    """Generate cache key from file path and modification time."""
    try:
        mtime = os.path.getmtime(filepath)
        key_string = f"{filepath}:{mtime}"
        return hashlib.md5(key_string.encode()).hexdigest()
    except:
        return None

def get_cached_markdown(filepath: str) -> str:
    """Retrieve cached markdown for a file."""
    cache_key = get_cache_key(filepath)
    if not cache_key:
        return None

    cache_file = CACHE_DIR / f"{cache_key}.md"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding='utf-8')
        except:
            return None
    return None

def save_to_cache(filepath: str, markdown: str) -> None:
    """Save markdown to cache."""
    cache_key = get_cache_key(filepath)
    if not cache_key:
        return

    cache_file = CACHE_DIR / f"{cache_key}.md"
    try:
        cache_file.write_text(markdown, encoding='utf-8')
    except:
        pass

def convert_excel_to_markdown(filepath: str) -> str:
    """Convert Excel file to markdown."""
    try:
        import pandas as pd
        df = pd.read_excel(filepath, sheet_name=0, nrows=100)
        return df.to_markdown(index=False)
    except:
        return None

def convert_csv_to_markdown(filepath: str) -> str:
    """Convert CSV file to markdown."""
    try:
        import pandas as pd
        df = pd.read_csv(filepath, nrows=100)
        return df.to_markdown(index=False)
    except:
        return None

def convert_json_to_markdown(filepath: str) -> str:
    """Convert JSON to markdown."""
    try:
        import json as json_module
        with open(filepath) as f:
            data = json_module.load(f)
        return f"```json\n{json_module.dumps(data, indent=2)}\n```"
    except:
        return None

def convert_text_to_markdown(filepath: str) -> str:
    """Read text/markdown file as-is."""
    try:
        with open(filepath, encoding='utf-8') as f:
            return f.read()
    except:
        return None

def convert_file_to_markdown(filepath: str) -> str:
    """Convert file to markdown using appropriate handler, with caching."""
    filepath = os.path.expanduser(filepath)

    # Check if file exists
    if not os.path.isfile(filepath):
        return None

    # Try to get from cache first
    cached = get_cached_markdown(filepath)
    if cached:
        return cached

    # Determine file type and convert accordingly
    ext = os.path.splitext(filepath)[1].lower()

    markdown = None
    if ext in ['.xlsx', '.xls']:
        markdown = convert_excel_to_markdown(filepath)
    elif ext == '.csv':
        markdown = convert_csv_to_markdown(filepath)
    elif ext == '.json':
        markdown = convert_json_to_markdown(filepath)
    elif ext in ['.md', '.txt', '.py', '.sh', '.yaml', '.yml']:
        markdown = convert_text_to_markdown(filepath)
    else:
        # Try text for unknown types
        markdown = convert_text_to_markdown(filepath)

    if markdown:
        # Save to cache
        save_to_cache(filepath, markdown)
        return markdown

    return None

def process_prompt(prompt_text: str) -> str:
    """
    Process prompt to replace file references with markdown content.
    Detects patterns like @"/path/to/file" and replaces with converted markdown.
    """
    if not prompt_text:
        return prompt_text

    # Pattern to match @"/path/to/file" or @'/path/to/file'
    pattern = r'@["\']([^"\']+)["\']'

    def replace_with_markdown(match):
        filepath = match.group(1)
        markdown = convert_file_to_markdown(filepath)

        if markdown:
            # Wrap in markdown code block with filename
            filename = os.path.basename(filepath)
            # Truncate very large files to avoid token explosion
            max_chars = 50000
            if len(markdown) > max_chars:
                markdown = markdown[:max_chars] + f"\n\n... (truncated, {len(markdown)} total chars)"
            return f"\n**File: {filename}**\n\n```\n{markdown}\n```\n"
        else:
            # If conversion fails, keep the original reference
            return match.group(0)

    # Replace all file references with their markdown content
    return re.sub(pattern, replace_with_markdown, prompt_text)

def main():
    """Main hook handler - reads JSON from stdin, processes prompt, outputs result."""
    try:
        # Read hook input from stdin
        hook_input = json.load(sys.stdin)

        # Get the user prompt text
        prompt = hook_input.get('prompt', '')

        if prompt:
            # Process the prompt to replace file references with markdown
            processed_prompt = process_prompt(prompt)

            # Count file references
            file_ref_count = len(re.findall(r'@["\']([^"\']+)["\']', prompt))

            # Return result with modified prompt
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": f"Markitdown: Converted {file_ref_count} file reference(s) to markdown (cached & token-optimized)"
                }
            }

            # If prompt changed, include a note
            if processed_prompt != prompt:
                result["systemMessage"] = f"✓ Markitdown: {file_ref_count} file(s) converted to markdown format"

            print(json.dumps(result))
        else:
            # No prompt to process
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}))

    except json.JSONDecodeError:
        # Invalid JSON input - just pass through
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}))
    except Exception as e:
        # On any error, pass through without blocking
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"Markitdown hook skipped: {str(e)}"
            }
        }))

if __name__ == '__main__':
    main()
