#!/usr/bin/env python3
"""Unified test runner for dou_snaptrack.

Supports multiple test suites:
- imports: Basic import tests
- unit: Unit tests with pytest
- smoke: Playwright browser tests
- mapping: Long-running mapping tests
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
PY = sys.executable or "python"


def run(cmd, timeout=None, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or "Timeout"


def suite_imports():
    """Test that all core modules can be imported."""
    mods = [
        "dou_snaptrack",
        "dou_snaptrack.constants",
        "dou_snaptrack.utils.browser",
        "dou_snaptrack.utils.responses",
        "dou_snaptrack.utils.exceptions",
        "dou_snaptrack.utils.browser_factory",
        "dou_snaptrack.utils.wait_helpers",
        "dou_snaptrack.mappers.pairs_mapper",
        "dou_snaptrack.cli.plan_live_eagendas_async",
        "dou_snaptrack.utils.eagendas_calendar",
    ]
    ok = True
    for m in mods:
        try:
            __import__(m)
            print(f"[imports] OK   - {m}")
        except Exception as e:
            ok = False
            print(f"[imports] FAIL - {m}: {e}")
    return ok


def suite_unit(timeout=120, verbose=False):
    """Run unit tests with pytest."""
    unit_dir = TESTS_DIR / "unit"
    if not unit_dir.exists():
        print(f"[unit] SKIP - directory not found: {unit_dir}")
        return True
    
    cmd = [PY, "-m", "pytest", str(unit_dir), "-v" if verbose else "-q", "--tb=short"]
    print(f"[unit] Running: {' '.join(cmd)}")
    rc, out, err = run(cmd, timeout=timeout)
    
    # Print output
    if out:
        print(out)
    if err and rc != 0:
        print(err)
    
    if rc == 0:
        print("[unit] PASS")
        return True
    print(f"[unit] FAIL (exit code {rc})")
    return False


def suite_smoke(timeout=60):
    script = ROOT / "scripts" / "playwright_smoke.py"
    if not script.exists():
        print(f"[smoke] SKIP - script not found: {script}")
        return True
    rc, out, err = run([PY, str(script)], timeout=timeout)
    if rc == 0:
        print("[smoke] PASS")
        return True
    print("[smoke] FAIL")
    if out:
        print(out)
    if err:
        print(err)
    return False


def suite_mapping(allow_long=False, timeout=180):
    script = ROOT / "scripts" / "map_eagendas_full.py"
    if not script.exists():
        print(f"[mapping] SKIP - script not found: {script}")
        return True
    if not allow_long:
        print("[mapping] SKIP - long run disabled (use --allow-long to enable)")
        return True
    rc, out, err = run([PY, str(script)], timeout=timeout)
    if rc == 0:
        print("[mapping] PASS")
        return True
    print("[mapping] FAIL")
    if out:
        print(out)
    if err:
        print(err)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Unified test runner for dou_snaptrack")
    ap.add_argument("--suite", choices=["imports", "unit", "smoke", "mapping", "all"], default="imports")
    ap.add_argument("--allow-long", action="store_true", help="Allow long-running suites (e.g., mapping)")
    ap.add_argument("--timeout", type=int, default=90, help="Default timeout for suites (seconds)")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose output for pytest")
    args = ap.parse_args(argv)

    results = []
    if args.suite in ("imports", "all"):
        results.append(suite_imports())
    if args.suite in ("unit", "all"):
        results.append(suite_unit(timeout=args.timeout, verbose=args.verbose))
    if args.suite in ("smoke", "all"):
        results.append(suite_smoke(timeout=args.timeout))
    if args.suite in ("mapping", "all"):
        results.append(suite_mapping(allow_long=args.allow_long, timeout=max(120, args.timeout)))

    ok = all(results) if results else True
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
