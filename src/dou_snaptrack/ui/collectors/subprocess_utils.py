"""
Subprocess utilities for DOU SnapTrack UI.

This module provides the subprocess execution helper that enforces the
RESULT_JSON_PATH contract for IPC between Streamlit and Playwright scripts.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Environment variable names (shared with app.py constants)
RESULT_JSON_ENV = "RESULT_JSON_PATH"


def execute_script_and_read_result(
    script_content: str | None = None,
    script_path: str | None = None,
    timeout: int = 120,
    cwd: str | None = None,
    extra_env: dict | None = None,
    input_text: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Execute Python script in subprocess and return (dict, stderr).

    Uses RESULT_JSON_PATH contract: child script writes JSON to temp file.
    This is the primary mechanism for running Playwright scripts from Streamlit
    without blocking the UI or hitting Windows event loop issues.

    Args:
        script_content: Python script content to execute (creates temp file)
        script_path: Path to existing script file (alternative to script_content)
        timeout: Timeout in seconds
        cwd: Working directory for subprocess
        extra_env: Additional environment variables to merge
        input_text: Text to pass to subprocess stdin

    Returns:
        Tuple of (parsed_json_dict or None, stderr_string)

    Raises:
        ValueError: If neither script_content nor script_path is provided
        subprocess.TimeoutExpired: If the subprocess times out
    """
    tmp_script = None
    tmp_json = None
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    try:
        # Arquivo temporário para resultado JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as jf:
            tmp_json = jf.name
        env[RESULT_JSON_ENV] = str(tmp_json)
        env["PYTHONUNBUFFERED"] = "1"

        # Choose command: script_path or script_content
        if script_path:
            cmd = [sys.executable, str(script_path)]
        else:
            if not script_content:
                raise ValueError("Either script_content or script_path must be provided")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(script_content)
                tmp_script = f.name
            cmd = [sys.executable, str(tmp_script)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            input=input_text,
        )

        stderr = result.stderr or ""

        # Ler resultado JSON
        if tmp_json and Path(tmp_json).exists():
            try:
                content = Path(tmp_json).read_text(encoding="utf-8")
                data = json.loads(content)
                return data, stderr
            except Exception:
                return None, stderr
        return None, stderr
    finally:
        if tmp_script:
            try:
                Path(tmp_script).unlink(missing_ok=True)
            except Exception:
                pass
        if tmp_json:
            try:
                Path(tmp_json).unlink(missing_ok=True)
            except Exception:
                pass


def write_result(data: dict) -> None:
    """Write result to RESULT_JSON_PATH file (subprocess contract).

    This function should be called by child scripts to write their
    final JSON payload. Falls back to stdout if no path is set.

    Args:
        data: Dictionary to serialize as JSON result
    """
    result_path = os.environ.get(RESULT_JSON_ENV)
    if result_path:
        Path(result_path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    else:
        # Fallback to stdout if no RESULT_JSON_PATH (for direct testing)
        print(json.dumps(data, ensure_ascii=False))
