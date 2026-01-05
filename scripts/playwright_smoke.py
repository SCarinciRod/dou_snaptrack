"""Playwright smoke test.

Contract:
- Exits with code 0 on success
- Prints "RESULT SUCCESS" on stdout when successful

This is used by `scripts/install.ps1` and `tests/run_tests.py --suite smoke`.

Rules (repo guardrails):
- Prefer launching via browser channels (chrome/msedge)
- Fallback to explicit executable paths
- Do not use --with-deps on Windows
- Prefer setting PLAYWRIGHT_BROWSERS_PATH to a project-local cache when running from a venv
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path


def _configure_pw_browsers_path() -> None:
    root = Path(__file__).resolve().parents[1]
    pw_browsers = root / ".venv" / "pw-browsers"

    # Always point Playwright to the project-local cache when using the repo venv.
    # Even if it doesn't exist yet, Playwright can create it on install.
    if (root / ".venv").exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers)


def main() -> int:
    _configure_pw_browsers_path()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"RESULT FAIL: playwright import error: {e}")
        return 2

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--ignore-certificate-errors",
    ]

    with sync_playwright() as p:
        browser = None

        for channel in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=channel, headless=True, args=launch_args)
                break
            except Exception:
                browser = None

        if browser is None:
            exe_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]

            for exe in exe_paths:
                if Path(exe).exists():
                    try:
                        browser = p.chromium.launch(executable_path=exe, headless=True, args=launch_args)
                        break
                    except Exception:
                        browser = None

        if browser is None:
            print("RESULT FAIL: no Chrome/Edge available")
            return 3

        try:
            page = browser.new_page()
            page.goto("about:blank", wait_until="domcontentloaded", timeout=15_000)
        except Exception as e:
            print(f"RESULT FAIL: navigation error: {e}")
            return 4
        finally:
            with contextlib.suppress(Exception):
                browser.close()

    print("RESULT SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
