"""Fast async mode support for batch processing.

This module handles the fast async execution path that uses a single browser
for faster parallel collection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable


def try_fast_async_mode(
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    cfg: dict[str, Any],
    log_fn: Callable[[str], None],
) -> dict[str, Any] | None:
    """Try to execute batch using fast async mode.

    Fast async mode uses a single browser with multiple contexts for
    2x faster collection compared to multi-browser approach.

    Args:
        jobs: List of jobs to execute
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        cfg: Batch configuration
        log_fn: Logging function

    Returns:
        Report dictionary if successful, None if failed or not applicable
    """
    # Check if fast async is enabled
    use_fast_async = os.environ.get("DOU_FAST_ASYNC", "1").strip().lower() in ("1", "true", "yes")
    if hasattr(args, "no_fast_async") and args.no_fast_async:
        use_fast_async = False

    if not use_fast_async:
        return None

    log_fn("[FAST ASYNC] Tentando modo browser único (2x mais rápido)...")

    try:
        # Prepare async input
        async_input = {
            "jobs": jobs,
            "defaults": defaults,
            "out_dir": str(out_dir),
            "out_pattern": out_pattern,
            "max_workers": int(os.environ.get("DOU_MAX_WORKERS", "4") or "4"),
        }

        # Try direct method first
        async_result = _try_direct_async(async_input, log_fn)

        if not async_result:
            return None

        if async_result.get("ok", 0) > 0 or async_result.get("success"):
            # Success! Return formatted report
            report = {
                "total_jobs": len(jobs),
                "ok": async_result.get("ok", 0),
                "fail": async_result.get("fail", 0),
                "items_total": async_result.get("items_total", 0),
                "outputs": async_result.get("outputs", []),
                "metrics": async_result.get("metrics", {}),
                "mode": "fast_async",
            }

            elapsed = async_result.get("elapsed", 0)
            log_fn(
                f"[FAST ASYNC] ✓ Concluído em {elapsed:.1f}s — ok={report['ok']} fail={report['fail']} items={report['items_total']}"
            )

            return report
        else:
            error_msg = async_result.get("error", "unknown") if async_result else "no result"
            log_fn(f"[FAST ASYNC] Falhou ({error_msg}), usando fallback...")
            return None

    except Exception as e:
        log_fn(f"[FAST ASYNC] Erro ao importar/executar: {e}, usando fallback...")
        return None


def _try_direct_async(async_input: dict[str, Any], log_fn: Callable[[str], None]) -> dict[str, Any] | None:
    """Try to run async collector directly.

    Args:
        async_input: Input configuration for async collector
        log_fn: Logging function

    Returns:
        Async result or None if failed
    """
    try:
        from ..ui.dou_collect_parallel import run_parallel_batch

        return run_parallel_batch(async_input)
    except RuntimeError as e:
        if "event loop" in str(e).lower():
            # Event loop is running, use subprocess
            log_fn("[FAST ASYNC] Event loop detectado, usando subprocess...")
            return _run_fast_async_subprocess(async_input, log_fn)
        else:
            raise
    except Exception:
        return None


def _run_fast_async_subprocess(async_input: dict[str, Any], log_fn: Callable[[str], None]) -> dict[str, Any] | None:
    """Run async collector in subprocess.

    Args:
        async_input: Input configuration
        log_fn: Logging function

    Returns:
        Result dictionary or None if failed
    """
    import subprocess
    import sys
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(async_input, f, ensure_ascii=False)
            input_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            output_path = f.name

        py = sys.executable or "python"
        cmd = [py, "-m", "dou_snaptrack.ui.dou_collect_parallel", "--input", input_path, "--output", output_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0 and Path(output_path).exists():
            with open(output_path, encoding="utf-8") as f:
                return json.load(f)
        else:
            log_fn(f"[FAST ASYNC] Subprocess failed with code {result.returncode}")
            if result.stderr:
                log_fn(f"[FAST ASYNC] Error: {result.stderr[:500]}")
            return None

    except Exception as e:
        log_fn(f"[FAST ASYNC] Subprocess error: {e}")
        return None
    finally:
        # Cleanup temp files
        try:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
        except Exception:
            pass
