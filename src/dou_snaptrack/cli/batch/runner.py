from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ...utils.text import sanitize_filename
from .summary_config import SummaryConfig, apply_summary_overrides_from_job


def render_out_filename(pattern: str, job: dict[str, Any]) -> str:
    date_str = job.get("data") or ""
    tokens = {
        "topic": job.get("topic") or "job",
        "secao": job.get("secao") or "DO",
        "date": (date_str or "").replace("/", "-"),
        "idx": str(job.get("_combo_index") or job.get("_job_index") or ""),
        "rep": str(job.get("_repeat") or ""),
        "key1": job.get("key1") or "",
        "key2": job.get("key2") or "",
        "key3": job.get("key3") or "",
    }
    name = pattern
    for k, v in tokens.items():
        name = name.replace("{" + k + "}", sanitize_filename(str(v)))
    return name

def expand_batch_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand batch configuration into list of jobs.

    Supports three patterns:
    1. Simple jobs list
    2. Topics + combos (cross-product)
    3. Combos only

    Args:
        cfg: Batch configuration dictionary

    Returns:
        List of expanded job dictionaries
    """
    from .config import expand_combo_only_jobs, expand_simple_jobs, expand_topic_combo_jobs

    defaults = cfg.get("defaults", {})
    base_data = cfg.get("data")
    base_secao = cfg.get("secaoDefault")

    jobs: list[dict[str, Any]] = []

    # Pattern 1: Simple jobs list
    if cfg.get("jobs"):
        jobs.extend(expand_simple_jobs(cfg, defaults, base_data, base_secao))

    # Pattern 2: Topics + combos cross-product
    topics = cfg.get("topics") or []
    combos = cfg.get("combos") or []

    if topics and combos:
        jobs.extend(expand_topic_combo_jobs(cfg, defaults, base_data, base_secao))

    # Pattern 3: Combos only (no topics)
    if not topics and combos:
        jobs.extend(expand_combo_only_jobs(cfg, defaults, base_data, base_secao))

    return jobs

def _worker_process(payload: dict[str, Any]) -> dict[str, Any]:
    """Process-based worker to avoid Playwright sync threading issues."""
    from ..runner import run_once
    from .job import process_single_job
    from .worker import (
        cleanup_page_cache,
        launch_browser_with_fallback,
        setup_asyncio_for_windows,
        setup_browser_context,
        setup_worker_logging,
    )

    # Setup async and logging
    setup_asyncio_for_windows()
    _log_fp = setup_worker_logging(payload)

    # Defer heavy imports until after stdout is redirected
    from playwright.sync_api import sync_playwright  # type: ignore

    # Extract payload
    # Backward compatible formats:
    # - legacy: payload has full `jobs` list + `indices`
    # - optimized: payload has `bucket_jobs` (list of {index, job}) + `total_jobs`
    jobs: list[dict[str, Any]] | None = payload.get("jobs")
    defaults: dict[str, Any] = payload["defaults"]
    out_dir = Path(payload["out_dir"])
    out_pattern: str = payload["out_pattern"]
    headful: bool = bool(payload.get("headful", False))
    slowmo: int = int(payload.get("slowmo", 0))
    state_file: str | None = payload.get("state_file")
    reuse_page: bool = bool(payload.get("reuse_page", False))
    summary: SummaryConfig = SummaryConfig(**(payload.get("summary") or {}))
    indices: list[int] | None = payload.get("indices")
    bucket_jobs: list[dict[str, Any]] | None = payload.get("bucket_jobs")
    total_jobs: int = int(payload.get("total_jobs") or (len(jobs) if jobs else 0) or (len(bucket_jobs) if bucket_jobs else 0))
    fast_mode = (os.environ.get("DOU_FAST_MODE", "").strip() or "0").lower() in ("1", "true", "yes")

    report = {"total_jobs": total_jobs, "ok": 0, "fail": 0, "items_total": 0, "outputs": [], "metrics": {"jobs": [], "summary": {}}}

    with sync_playwright() as p:
        # Launch browser with fallbacks
        prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1", "true", "yes")
        launch_opts = {
            "headless": not headful,
            "slow_mo": slowmo,
            "args": [
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-features=Translate,BackForwardCache",
            ],
        }

        browser = launch_browser_with_fallback(p, prefer_edge, launch_opts)
        context = setup_browser_context(browser, block_resources=True)
        page_cache: dict[tuple[str, str], Any] = {}

        try:
            if bucket_jobs:
                for entry in bucket_jobs:
                    try:
                        j_idx = int(entry.get("index") or 0)
                    except Exception:
                        j_idx = 0
                    job = entry.get("job") or {}
                    if not isinstance(job, dict) or j_idx <= 0:
                        continue

                # Process job using extracted helper
                    job_result = process_single_job(
                        job=job,
                        job_index=j_idx,
                        jobs=(jobs or []),
                    defaults=defaults,
                    out_dir=out_dir,
                    out_pattern=out_pattern,
                    context=context,
                    page_cache=page_cache,
                    reuse_page=reuse_page,
                    fast_mode=fast_mode,
                    state_file=state_file,
                    summary=summary,
                    run_once_fn=run_once,
                    render_out_filename_fn=render_out_filename,
                    apply_summary_overrides_fn=apply_summary_overrides_from_job,
                )

                # Aggregate results
                report["ok"] += job_result["ok"]
                report["fail"] += job_result["fail"]
                report["items_total"] += job_result["items_total"]
                report["outputs"].extend(job_result["outputs"])
                if job_result["job_metrics"]:
                    report["metrics"]["jobs"].append(job_result["job_metrics"])

            else:
                # Legacy mode: indices + full jobs list
                if not jobs or not indices:
                    return report

                for j_idx in indices:
                    job = jobs[j_idx - 1]

                    job_result = process_single_job(
                        job=job,
                        job_index=j_idx,
                        jobs=jobs,
                        defaults=defaults,
                        out_dir=out_dir,
                        out_pattern=out_pattern,
                        context=context,
                        page_cache=page_cache,
                        reuse_page=reuse_page,
                        fast_mode=fast_mode,
                        state_file=state_file,
                        summary=summary,
                        run_once_fn=run_once,
                        render_out_filename_fn=render_out_filename,
                        apply_summary_overrides_fn=apply_summary_overrides_from_job,
                    )

                    # Aggregate results
                    report["ok"] += job_result["ok"]
                    report["fail"] += job_result["fail"]
                    report["items_total"] += job_result["items_total"]
                    report["outputs"].extend(job_result["outputs"])
                    if job_result["job_metrics"]:
                        report["metrics"]["jobs"].append(job_result["job_metrics"])

        finally:
            cleanup_page_cache(page_cache)
            with contextlib.suppress(Exception):
                context.close()
            with contextlib.suppress(Exception):
                browser.close()

    # Ensure file buffer is flushed before returning
    try:
        if _log_fp:
            _log_fp.flush()
    except Exception:
        pass
    return report

def _init_worker(log_file: str | None = None) -> None:
    """Initializer for worker processes to confirm spawn and set basic policy early."""
    try:
        import asyncio as _asyncio
        import os as _os
        import sys as _sys
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        if log_file:
            try:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(f"[Init {_os.getpid()}] worker process spawned\n")
            except Exception:
                pass
    except Exception:
        pass

def _run_fast_async_subprocess(async_input: dict, _log) -> dict:
    """
    Executa o collector async via subprocess (para evitar conflitos de event loop).

    Similar ao padrão usado em eagendas_collect_parallel.
    """
    import tempfile

    try:
        # Escrever input em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(async_input, f, ensure_ascii=False)
            input_path = f.name

        # Escrever resultado em arquivo temporário
        result_path = input_path.replace('.json', '_result.json')

        # Encontrar script
        script_path = Path(__file__).parent.parent.parent / "ui" / "collectors" / "dou_parallel.py"
        if not script_path.exists():
            _log(f"[FAST ASYNC SUBPROCESS] Script não encontrado: {script_path}")
            return {"success": False, "error": f"Script não encontrado: {script_path}"}

        # Executar subprocess
        env = os.environ.copy()
        env["INPUT_JSON_PATH"] = input_path
        env["RESULT_JSON_PATH"] = result_path
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            capture_output=True,
            timeout=600,  # 10 min timeout
            text=True
        )

        # Ler resultado
        if Path(result_path).exists():
            result = json.loads(Path(result_path).read_text(encoding='utf-8'))
        else:
            # Tentar parsear stdout
            try:
                result = json.loads(proc.stdout)
            except Exception:
                result = {"success": False, "error": proc.stderr or "No output"}

        # Cleanup
        try:
            Path(input_path).unlink(missing_ok=True)
            Path(result_path).unlink(missing_ok=True)
        except Exception:
            pass

        return result

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Subprocess timeout (10 min)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_batch(playwright, args, summary: SummaryConfig) -> None:
    """Execute batch processing with optional fast async mode.

    This function coordinates batch execution with multiple strategies:
    1. Fast async mode (single browser, multiple contexts) - fastest
    2. Multi-browser fallback modes (subprocess, thread, or process pool)

    Args:
        playwright: Playwright instance (may be unused if fast async succeeds)
        args: Command-line arguments
        summary: Summary configuration
    """
    # Setup logging
    log_file = getattr(args, "log_file", None)
    def _log(msg: str) -> None:
        try:
            print(msg)
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(str(msg) + "\n")
        except Exception:
            pass

    # Load and parse configuration
    cfg_path = Path(args.config)
    txt = cfg_path.read_text(encoding="utf-8-sig")
    cfg = json.loads(txt)

    # Prefer explicit plan name from config (UI injects it). Only default to filename stem if missing.
    # This avoids temp configs like "_run_cfg.json" overriding the intended plan name.
    existing_plan_name = (cfg.get("plan_name") or "").strip()
    if not existing_plan_name:
        plan_file_stem = (cfg_path.stem or "").strip()
        if plan_file_stem:
            cfg["plan_name"] = plan_file_stem
    out_dir = Path(args.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = expand_batch_config(cfg)
    if not jobs:
        _log("[Erro] Nenhum job gerado a partir do config.")
        return

    out_pattern = (cfg.get("output") or {}).get("pattern") or "{topic}_{secao}_{date}_{idx}.json"
    report = {"total_jobs": len(jobs), "ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    defaults = cfg.get("defaults") or {}

    # ============================================================================
    # FAST ASYNC MODE: Try single-browser async collector first (2x faster)
    # ============================================================================
    from .async_runner import try_fast_async_mode

    async_report = try_fast_async_mode(jobs, defaults, out_dir, out_pattern, args, cfg, _log)
    if async_report:
        # Fast async succeeded! Write report and finish
        report = async_report
        from .helpers import finalize_with_aggregation, write_report

        rep_path = write_report(report, out_dir, cfg)
        _log(f"\n[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")

        finalize_with_aggregation(report, out_dir, cfg, rep_path, _log)
        return

    # ============================================================================
    # FALLBACK: Multi-browser approach (slower but robust)
    # ============================================================================
    _log("[FALLBACK] Usando método multi-browser original...")

    # Import helper functions
    from .executor import (
        execute_inline_with_threads,
        execute_with_process_pool,
        execute_with_subprocess,
        execute_with_threads,
    )
    from .helpers import (
        aggregate_report_metrics,
        determine_parallelism,
        distribute_jobs_into_buckets,
        finalize_with_aggregation,
        write_report,
    )

    # Load deduplication state (state_file_path passed to execute functions)
    state_file_path = None
    if cfg.get("state_file"):
        state_file_path = Path(cfg["state_file"])
    elif getattr(args, "state_file", None):
        state_file_path = Path(args.state_file)

    # Determine parallelism
    parallel = determine_parallelism(args, len(jobs))
    pool_pref = os.environ.get("DOU_POOL", "process").strip().lower() or "process"
    reuse_page = bool(getattr(args, "reuse_page", False))

    # Distribute jobs into buckets
    buckets, desired_size = distribute_jobs_into_buckets(jobs, cfg, parallel)

    effective_parallel = min(parallel, int(os.environ.get("DOU_MAX_WORKERS", "4") or "4"))
    _log(f"[Parent] total_jobs={len(jobs)} parallel={parallel} (effective={effective_parallel}) reuse_page={reuse_page}")
    _log(f"[Parent] buckets={len(buckets)} desired_size={desired_size}")

    # Execute batch with appropriate strategy
    try:
        if pool_pref == "subprocess" and parallel > 1:
            exec_report = execute_with_subprocess(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log
            )
        elif pool_pref == "thread" and parallel > 1:
            exec_report = execute_with_threads(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log, _worker_process
            )
        elif parallel <= 1:
            exec_report = execute_inline_with_threads(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, _log, _worker_process
            )
        else:
            exec_report = execute_with_process_pool(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log,
                _worker_process, _init_worker, log_file
            )

        # Update report with execution results
        report.update(exec_report)
    finally:
        pass

    # Aggregate metrics
    aggregate_report_metrics(report)

    # Write report
    rep_path = write_report(report, out_dir, cfg)
    _log("")
    _log(f"[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")

    # Perform plan aggregation if configured
    finalize_with_aggregation(report, out_dir, cfg, rep_path, _log)
