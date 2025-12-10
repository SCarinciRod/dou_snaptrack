"""Executor strategies for batch processing.

This module contains different execution strategies (subprocess, thread, process)
to reduce complexity of the main batch.py file.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ...constants import TIMEOUT_SUBPROCESS_LONG


def execute_with_subprocess(
    buckets: list[list[int]],
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    state_file_path: Path | None,
    reuse_page: bool,
    summary: dict[str, Any],
    parallel: int,
    log_fn: Callable[[str], None],
) -> dict[str, Any]:
    """Execute batch using subprocess pool.

    Args:
        buckets: List of job index buckets
        jobs: All jobs
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        state_file_path: Path to state file
        reuse_page: Whether to reuse browser page
        summary: Summary configuration
        parallel: Number of workers
        log_fn: Logging function

    Returns:
        Report dictionary with ok, fail, items_total, and outputs
    """
    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    log_fn(f"[Parent] Using subprocess pool (workers={parallel})")

    futs = []
    tmp_dir = out_dir / "_subproc"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for w_id, bucket in enumerate(buckets):
        if not bucket:
            continue

        log_fn(
            f"[Parent] Scheduling (subproc) bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}"
        )

        payload = {
            "jobs": jobs,
            "defaults": defaults,
            "out_dir": str(out_dir),
            "out_pattern": out_pattern,
            "headful": bool(args.headful),
            "slowmo": int(args.slowmo),
            "state_file": str(state_file_path) if state_file_path else None,
            "reuse_page": reuse_page,
            "summary": {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords},
            "indices": bucket,
            "log_file": getattr(args, "log_file", None),
        }

        payload_path = (tmp_dir / f"payload_{w_id+1}.json").resolve()
        result_path = (tmp_dir / f"result_{w_id+1}.json").resolve()
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        # Build subprocess command
        py = sys.executable or "python"
        cmd = [py, "-m", "dou_snaptrack.cli.worker_entry", "--payload", str(payload_path), "--out", str(result_path)]

        # Set up environment with proper PYTHONPATH
        repo_root = Path(__file__).resolve().parents[3]
        src_dir = (repo_root / "src").resolve()
        env = os.environ.copy()
        existing_pp = env.get("PYTHONPATH", "")
        if str(src_dir) not in (existing_pp.split(";") if os.name == "nt" else existing_pp.split(":")):
            separator = ";" if os.name == "nt" else ":"
            env["PYTHONPATH"] = (str(src_dir) + separator + existing_pp) if existing_pp else str(src_dir)

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(repo_root), env=env)
        futs.append((p, result_path))

    log_fn(f"[Parent] {len(futs)} subprocesses spawned")

    # Collect results
    for p, result_path in futs:
        try:
            out = p.communicate(timeout=TIMEOUT_SUBPROCESS_LONG)[0].decode("utf-8", errors="ignore") if p.stdout else ""
        except Exception:
            out = ""

        if out:
            log_fn(out.strip())

        if result_path.exists():
            try:
                r = json.loads(result_path.read_text(encoding="utf-8"))
                report["ok"] += r.get("ok", 0)
                report["fail"] += r.get("fail", 0)
                report["items_total"] += r.get("items_total", 0)
                report["outputs"].extend(r.get("outputs", []))
                log_fn(f"[Parent] Subproc done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
            except Exception as e:
                log_fn(f"[Subproc parse FAIL] {e}")
        else:
            log_fn("[Subproc FAIL] result file missing")

    return report


def execute_with_threads(
    buckets: list[list[int]],
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    state_file_path: Path | None,
    reuse_page: bool,
    summary: dict[str, Any],
    parallel: int,
    log_fn: Callable[[str], None],
    worker_fn: Callable,
) -> dict[str, Any]:
    """Execute batch using thread pool.

    Args:
        buckets: List of job index buckets
        jobs: All jobs
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        state_file_path: Path to state file
        reuse_page: Whether to reuse browser page
        summary: Summary configuration
        parallel: Number of workers
        log_fn: Logging function
        worker_fn: Worker function to call

    Returns:
        Report dictionary with ok, fail, items_total, and outputs
    """
    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    log_fn(f"[Parent] Using ThreadPoolExecutor (workers={parallel})")

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as tpex:
        futs = []
        for w_id, bucket in enumerate(buckets):
            if not bucket:
                continue

            log_fn(
                f"[Parent] Scheduling (thread) bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}"
            )

            payload = {
                "jobs": jobs,
                "defaults": defaults,
                "out_dir": str(out_dir),
                "out_pattern": out_pattern,
                "headful": bool(args.headful),
                "slowmo": int(args.slowmo),
                "state_file": str(state_file_path) if state_file_path else None,
                "reuse_page": reuse_page,
                "summary": {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords},
                "indices": bucket,
                "log_file": getattr(args, "log_file", None),
            }
            futs.append(tpex.submit(worker_fn, payload))

        log_fn(f"[Parent] {len(futs)} thread-futures scheduled")

        for fut in as_completed(futs):
            try:
                r = fut.result()
                report["ok"] += r.get("ok", 0)
                report["fail"] += r.get("fail", 0)
                report["items_total"] += r.get("items_total", 0)
                report["outputs"].extend(r.get("outputs", []))
                log_fn(f"[Parent] Thread future done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
            except Exception as e:
                log_fn(f"[Worker FAIL thread] {e}")

    return report


def execute_inline_with_threads(
    buckets: list[list[int]],
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    state_file_path: Path | None,
    reuse_page: bool,
    summary: dict[str, Any],
    log_fn: Callable[[str], None],
    worker_fn: Callable,
) -> dict[str, Any]:
    """Execute batch inline using single-threaded approach.

    Args:
        buckets: List of job index buckets
        jobs: All jobs
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        state_file_path: Path to state file
        reuse_page: Whether to reuse browser page
        summary: Summary configuration
        log_fn: Logging function
        worker_fn: Worker function to call

    Returns:
        Report dictionary with ok, fail, items_total, and outputs
    """
    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    log_fn("[Parent] Running single bucket inline (thread, no ProcessPool)")

    for w_id, bucket in enumerate(buckets):
        if not bucket:
            continue

        log_fn(
            f"[Parent] Scheduling bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}"
        )

        payload = {
            "jobs": jobs,
            "defaults": defaults,
            "out_dir": str(out_dir),
            "out_pattern": out_pattern,
            "headful": bool(args.headful),
            "slowmo": int(args.slowmo),
            "state_file": str(state_file_path) if state_file_path else None,
            "reuse_page": reuse_page,
            "summary": {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords},
            "indices": bucket,
            "log_file": getattr(args, "log_file", None),
        }

        try:
            with ThreadPoolExecutor(max_workers=1) as tpex:
                fut = tpex.submit(worker_fn, payload)
                r = fut.result()
                report["ok"] += r.get("ok", 0)
                report["fail"] += r.get("fail", 0)
                report["items_total"] += r.get("items_total", 0)
                report["outputs"].extend(r.get("outputs", []))
                log_fn(f"[Parent] Inline (thread) done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
        except Exception as e:
            log_fn(f"[Worker FAIL inline-thread] {e}")

    return report


def execute_with_process_pool(
    buckets: list[list[int]],
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    state_file_path: Path | None,
    reuse_page: bool,
    summary: dict[str, Any],
    parallel: int,
    log_fn: Callable[[str], None],
    worker_fn: Callable,
    init_worker_fn: Callable,
    log_file: str | None,
) -> dict[str, Any]:
    """Execute batch using process pool with timeout and fallback.

    Args:
        buckets: List of job index buckets
        jobs: All jobs
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        state_file_path: Path to state file
        reuse_page: Whether to reuse browser page
        summary: Summary configuration
        parallel: Number of workers
        log_fn: Logging function
        worker_fn: Worker function to call
        init_worker_fn: Worker initialization function
        log_file: Path to log file

    Returns:
        Report dictionary with ok, fail, items_total, and outputs
    """
    import multiprocessing as mp

    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    ctx = mp.get_context("spawn")

    with ProcessPoolExecutor(
        max_workers=max(1, parallel), mp_context=ctx, initializer=init_worker_fn, initargs=(log_file,)
    ) as ex:
        log_fn("[Parent] ProcessPoolExecutor started")
        futs = []

        for w_id, bucket in enumerate(buckets):
            if not bucket:
                continue

            log_fn(
                f"[Parent] Scheduling bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}"
            )

            payload = {
                "jobs": jobs,
                "defaults": defaults,
                "out_dir": str(out_dir),
                "out_pattern": out_pattern,
                "headful": bool(args.headful),
                "slowmo": int(args.slowmo),
                "state_file": str(state_file_path) if state_file_path else None,
                "reuse_page": reuse_page,
                "summary": {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords},
                "indices": bucket,
                "log_file": getattr(args, "log_file", None),
            }
            futs.append(ex.submit(worker_fn, payload))

        log_fn(f"[Parent] {len(futs)} futures scheduled")

        try:
            # Wait for workers with timeout
            any_done = False
            for fut in as_completed(futs, timeout=60):
                any_done = True
                try:
                    r = fut.result()
                    report["ok"] += r.get("ok", 0)
                    report["fail"] += r.get("fail", 0)
                    report["items_total"] += r.get("items_total", 0)
                    report["outputs"].extend(r.get("outputs", []))
                    log_fn(f"[Parent] Future done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                except Exception as e:
                    log_fn(f"[Worker FAIL] {e}")

            if not any_done:
                raise TimeoutError("no worker finished within timeout")

        except TimeoutError:
            log_fn("[Parent] Timeout aguardando workers. Fazendo fallback para execução inline…")

            # Fallback to thread pool
            with contextlib.suppress(Exception):
                ex.shutdown(wait=False, cancel_futures=True)

            # Execute fallback
            fallback_report = execute_with_threads(
                buckets,
                jobs,
                defaults,
                out_dir,
                out_pattern,
                args,
                state_file_path,
                reuse_page,
                summary,
                parallel,
                log_fn,
                worker_fn,
            )

            # Replace report with fallback results
            report = fallback_report

    return report
