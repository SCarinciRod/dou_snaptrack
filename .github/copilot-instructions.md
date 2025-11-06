# Copilot project instructions

These guardrails help GitHub Copilot (Chat and inline) work effectively in this repository.

## Project overview
- Name: dou-snaptrack
- Goal: Collect DOU content, plan batch runs, and generate bulletins with a Streamlit UI.
- Languages: Python (packaged under `src/`), PowerShell scripts for Windows automation.
- Primary runtime: Windows with PowerShell 5.1.

## Tech stack and constraints
- Python: Requires >= 3.10. Prefer 3.12 or 3.11 for local installs and automation.
- Packaging: `pyproject.toml` with setuptools; editable installs used for dev (`-e .`).
- Linting/format: Ruff configured in `pyproject.toml` (target-version py311, line length 120, excludes various folders like `.venv`, `artefatos/`, `logs/`). Run ruff on `src/` only.
- Web automation: Playwright (Python). In corporate/SSL-restricted environments, prefer system Chrome/Edge channels over downloading browsers.
- UI: Streamlit entrypoint via console script `dou-ui = dou_snaptrack.ui.launch:main`.

## Key entry points and scripts
- Installer: `scripts/install.ps1` (Windows-only) ensures a compatible Python, installs the package (dev mode), configures Playwright, runs a smoke test, and creates a desktop shortcut.
- Smoke test: `scripts/playwright_smoke.py` uses Playwright to launch via channel `chrome`/`msedge` or explicit executable path. Prints `RESULT SUCCESS` on success.
- Launch UI:
  - Developer: `scripts/run-ui.ps1` or `scripts/run-ui-managed.ps1`.
  - End user: `launch_ui.vbs` or desktop shortcut created by installer.
- Unified test runner: `tests/run_tests.py` supports suites: `imports`, `smoke`, `mapping`.

## Playwright rules (important)
- Do not use `--with-deps` on Windows.
- Prefer launching browsers via channels (`chrome`, `msedge`). Fallback to explicit executable paths if needed.
- When provisioning browsers, use `python -m playwright install chromium` and be tolerant of failures in restricted networks. The app must still run using system Chrome/Edge.
- **CRITICAL**: Always set `PLAYWRIGHT_BROWSERS_PATH` to `.venv/pw-browsers` when using venv to ensure browsers are found at runtime. This must be configured in:
  - `scripts/install.ps1` (during installation)
  - `scripts/run-ui.ps1` (when launching UI)
  - `scripts/run-ui-managed.ps1` (when launching UI via shortcut)
- Browser detection: Verify success by checking for "downloaded to" in stdout OR checking if chromium-* directories exist in the cache, NOT by exit code alone (Node TLS warnings cause non-zero exit codes even on success).
- For diagnostics, use `DEBUG=pw:install` environment variable (not `-v`).
- In restrictive SSL environments, it may be necessary to temporarily set `NODE_TLS_REJECT_UNAUTHORIZED=0` for browser download steps only; always restore it right after.
- Troubleshooting scripts: `scripts/verify-playwright-setup.ps1` (diagnostics) and `scripts/fix-playwright-browsers.ps1` (automatic repair).

## Python environment rules
- Enforce Python 3.12 or 3.11 for tooling/automation. Avoid 3.13 until wheels are broadly available.
- Prefer a project-local venv at `.venv`. If venv creation fails in user contexts, fall back to per-user installs (`--user`).
- Ensure Playwright is installed in the same environment that runs the app/scripts (venv-first).

## Repository layout
- Source: `src/dou_snaptrack/**` and `src/dou_utils/**`.
- Scripts: `scripts/**` (many diagnostics and smoke tests live here).
- Tests: both `scripts/*test*.py` (ad-hoc) and `tests/run_tests.py` (unified runner).
- Artifacts and outputs: `artefatos/`, `resultados/`, `logs/`, `planos/` (excluded from linting and should not be modified by Copilot).

## Coding conventions
- Keep edits minimal and local. Avoid broad refactors or reformatting unrelated code.
- Respect Ruff configuration; don’t fight configured ignores. When adding code, follow the style (double quotes, 120 columns, import sorting).
- Prefer absolute imports within the package (see `utils/browser.py`).
- Async-first browser helpers exist; keep sync wrappers for backward compatibility.
- For Windows compatibility, prefer PowerShell 5.1-safe constructs. Avoid Unix-only flags or assumptions.

## Behavior for Copilot Chat tasks
- Before editing, scan for existing implementations/utilities under `src/dou_snaptrack/**` and reuse them (e.g., URL builders in `utils/browser.py`).
- When touching `scripts/install.ps1`:
  - Preserve Python version enforcement and per-user install logic.
  - Don’t reintroduce `--with-deps` on Windows.
  - Keep the Playwright import-based detection and robust pip fallbacks.
  - Keep smoke test step tolerant and focused on channels.
  - Be explicit in logs but concise; don’t leak secrets or long stack traces unless in a debug section.
- When adding features that depend on Playwright, support both channel and explicit executable paths; never hard-require downloaded browsers.
- For test updates, prefer `tests/run_tests.py` patterns and keep smoke tests fast and headless.

## Quality gates
- Build: Ensure `pip install -e .` succeeds for supported Python versions.
- Lint/Typecheck: Run Ruff on `src/`. Pass is required before merging changes that touch Python code.
- Tests: `python tests/run_tests.py --suite imports` must pass; `--suite smoke` should pass on machines with Chrome/Edge available.

## PowerShell notes
- This project targets Windows PowerShell v5.1. When generating commands:
  - Use `;` to chain commands on a single line.
  - Use `$env:VAR='value'` for env vars in the current session.
  - Prefer `& "C:\\Path\\to\\python.exe" -m module ...` when invoking Python.

## Safe areas vs. sensitive areas
- Safe to extend: new helpers under `src/dou_snaptrack/utils/`, new scripts under `scripts/` (diagnostics), additional tests.
- Sensitive: `scripts/install.ps1`, `scripts/playwright_smoke.py`, browser launch logic in `src/dou_snaptrack/utils/browser.py`. Make focused, reviewed changes only and validate with the smoke test.

## How to validate changes (quick)
- Lint: run Ruff on `src/`.
- Imports: `python tests/run_tests.py --suite imports`.
- Smoke: `python tests/run_tests.py --suite smoke` (expects Chrome/Edge present).

## DOs and DON’Ts for Copilot
- DO reuse existing utilities and patterns; keep Windows compatibility.
- DO prefer minimal patches; add small, well-scoped tests when changing behavior.
- DO document non-obvious environment toggles (e.g., `NODE_TLS_REJECT_UNAUTHORIZED`) and restore their defaults.
- DON’T require admin privileges or system-wide installs when avoidable.
- DON’T assume internet access for downloading browsers; always support using system-installed Chrome/Edge.
