"""Additional helper for processing individual jobs in worker.

This module contains the job execution logic extracted from _worker_process.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import Any

from ...constants import TIMEOUT_PAGE_DEFAULT
from .summary_config import SummaryConfig


def process_single_job(
    job: dict[str, Any],
    job_index: int,
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    context,
    page_cache: dict[tuple[str, str], Any],
    reuse_page: bool,
    fast_mode: bool,
    state_file: str | None,
    summary: SummaryConfig,
    run_once_fn,
    render_out_filename_fn,
    apply_summary_overrides_fn,
) -> dict[str, Any]:
    """Process a single job and return results.

    Args:
        job: Job configuration
        job_index: Index of job in batch
        jobs: All jobs
        defaults: Default configuration  
        out_dir: Output directory
        out_pattern: Output filename pattern
        context: Browser context
        page_cache: Page cache dictionary
        reuse_page: Whether to reuse pages
        fast_mode: Whether fast mode is enabled
        state_file: Path to state file
        summary: Summary configuration
        run_once_fn: Function to run once
        render_out_filename_fn: Function to render output filename
        apply_summary_overrides_fn: Function to apply summary overrides

    Returns:
        Dictionary with ok, fail, items_total, outputs, elapsed, job_metrics
    """
    from .batch_worker import (
        extract_job_parameters,
        apply_fast_mode_optimizations,
        get_or_create_page,
        recreate_page_after_failure,
    )

    start_ts = time.time()
    result_dict = {"ok": 0, "fail": 0, "items_total": 0, "outputs": [], "job_metrics": None}

    print(f"\n[PW{os.getpid()}] [Job {job_index}/{len(jobs)}] {job.get('topic','')}: {job.get('query','')}")
    print(f"[DEBUG] Job {job_index} start_ts={start_ts:.3f}")

    # Extract and validate job parameters
    params = extract_job_parameters(job, defaults, job_index)

    # Apply fast mode optimizations if enabled
    if fast_mode:
        apply_fast_mode_optimizations(params)

    # Compute output paths
    out_name = render_out_filename_fn(out_pattern, {**job, "_job_index": job_index})
    out_path = out_dir / out_name

    bulletin_out = None
    if params["bulletin"] and params["bulletin_out_pat"]:
        bulletin_out = str(out_dir / render_out_filename_fn(params["bulletin_out_pat"], {**job, "_job_index": job_index}))

    # Validate required parameters
    if not params["key1"] or not params["key1_type"] or not params["key2"] or not params["key2_type"]:
        print(f"[FAIL] Job {job_index}: parâmetros faltando (key1/key2)")
        result_dict["fail"] = 1
        return result_dict

    # Apply summary overrides
    s_cfg = apply_summary_overrides_fn(summary, job)

    # Get or create page
    page = None
    keep_open = False
    if reuse_page:
        page, keep_open = get_or_create_page(page_cache, context, params["data"], params["secao"])

    # Execute job with retry
    def _run_with_retry(cur_page) -> dict[str, Any] | None:
        for attempt in (1, 2):
            try:
                return run_once_fn(
                    context,
                    date=str(params["data"]),
                    secao=str(params["secao"]),
                    key1=str(params["key1"]),
                    key1_type=str(params["key1_type"]),
                    key2=str(params["key2"]),
                    key2_type=str(params["key2_type"]),
                    key3=None,
                    key3_type=None,
                    query=job.get("query", ""),
                    max_links=params["max_links"],
                    out_path=str(out_path),
                    scrape_details=params["do_scrape_detail"],
                    detail_timeout=params["detail_timeout"],
                    fallback_date_if_missing=params["fallback_date"],
                    label1=params["label1"],
                    label2=params["label2"],
                    label3=None,
                    max_scrolls=params["max_scrolls"],
                    scroll_pause_ms=params["scroll_pause_ms"],
                    stable_rounds=params["stable_rounds"],
                    state_file=state_file,
                    bulletin=params["bulletin"],
                    bulletin_out=bulletin_out,
                    summary=SummaryConfig(lines=s_cfg.lines, mode=s_cfg.mode, keywords=s_cfg.keywords),
                    detail_parallel=params["detail_parallel"],
                    page=cur_page,
                    keep_page_open=keep_open,
                )
            except Exception:
                if attempt == 1 and reuse_page:
                    try:
                        cur_page = recreate_page_after_failure(
                            page_cache, context, cur_page, params["data"], params["secao"]
                        )
                        continue
                    except Exception:
                        pass
                raise

    # Execute and collect results
    try:
        result = _run_with_retry(page)
        result_dict["ok"] = 1
        result_dict["outputs"] = [str(out_path)]
        result_dict["items_total"] = result.get("total", 0) if isinstance(result, dict) else 0

        elapsed = time.time() - start_ts
        items_count = result.get("total", 0) if isinstance(result, dict) else 0
        print(f"[PW{os.getpid()}] [Job {job_index}] concluído em {elapsed:.1f}s — itens={items_count}")

        # Debug timing comparison
        try:
            if isinstance(result, dict):
                reported_total = result.get("_timings", {}).get("total_sec", 0)
                if reported_total > 0:
                    diff = abs(elapsed - reported_total)
                    if diff > 5:
                        print(
                            f"[TIMING WARN] Job {job_index}: wall-clock={elapsed:.1f}s vs reported={reported_total:.1f}s (diff={diff:.1f}s)"
                        )
        except Exception:
            pass

        # Collect job metrics
        try:
            timings = (result.get("_timings") or {}) if isinstance(result, dict) else {}
        except Exception:
            timings = {}

        result_dict["job_metrics"] = {
            "job_index": job_index,
            "topic": job.get("topic"),
            "date": str(params["data"]),
            "secao": str(params["secao"]),
            "key1": params["key1"],
            "key2": params["key2"],
            "items": result_dict["items_total"],
            "elapsed_sec": elapsed,
            "timings": timings,
        }

    except Exception as e:
        print(f"[FAIL] Job {job_index}: {e}")
        result_dict["fail"] = 1

    # Apply repeat delay
    delay_ms = params["repeat_delay_ms"]
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    return result_dict
