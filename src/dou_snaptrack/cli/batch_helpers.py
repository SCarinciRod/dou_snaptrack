"""Helper functions for batch processing to reduce complexity of batch.py.

This module contains extracted functions that were part of run_batch()
to improve maintainability and testability.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.text import sanitize_filename


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    jobs: list[dict[str, Any]]
    defaults: dict[str, Any]
    out_dir: Path
    out_pattern: str
    state_file_path: Path | None
    headful: bool
    slowmo: int
    reuse_page: bool
    summary: dict[str, Any]
    log_file: str | None


@dataclass
class BatchReport:
    """Batch processing report."""

    total_jobs: int
    ok: int = 0
    fail: int = 0
    items_total: int = 0
    outputs: list[str] = None
    metrics: dict[str, Any] = None
    mode: str = "fallback"

    def __post_init__(self):
        if self.outputs is None:
            self.outputs = []
        if self.metrics is None:
            self.metrics = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "total_jobs": self.total_jobs,
            "ok": self.ok,
            "fail": self.fail,
            "items_total": self.items_total,
            "outputs": self.outputs,
            "metrics": self.metrics,
            "mode": self.mode,
        }


def load_state_file(state_file_path: Path | None) -> set[str]:
    """Load global deduplication state from file.

    Args:
        state_file_path: Path to state file or None

    Returns:
        Set of seen hashes
    """
    global_seen = set()
    if not state_file_path or not state_file_path.exists():
        return global_seen

    try:
        for line in state_file_path.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
                h = obj.get("hash")
                if h:
                    global_seen.add(h)
            except Exception:
                pass
    except Exception:
        pass

    return global_seen


def determine_parallelism(args, jobs_count: int) -> int:
    """Determine the number of parallel workers to use.

    Args:
        args: Command-line arguments
        jobs_count: Number of jobs to process

    Returns:
        Number of parallel workers
    """
    # Check if user specified parallelism
    try:
        user_parallel = getattr(args, "parallel", None)
        if user_parallel is None:
            raise AttributeError
        user_parallel = int(user_parallel)
    except Exception:
        user_parallel = None

    if user_parallel and user_parallel > 0:
        return int(user_parallel)

    # Use automatic recommendation
    try:
        from dou_snaptrack.utils.parallel import recommend_parallel

        pool_pref = os.environ.get("DOU_POOL", "process").strip().lower()
        prefer_process = pool_pref == "process"
        return int(recommend_parallel(jobs_count, prefer_process=prefer_process))
    except Exception:
        return 4


def distribute_jobs_into_buckets(
    jobs: list[dict[str, Any]], cfg: dict[str, Any], parallel: int
) -> tuple[list[list[int]], int]:
    """Distribute jobs into buckets for parallel processing.

    Jobs with the same (date, secao) are grouped together. Large groups
    are split across buckets to maximize parallelism.

    Args:
        jobs: List of job configurations
        cfg: Batch configuration
        parallel: Number of parallel workers

    Returns:
        Tuple of (buckets, desired_size) where buckets is a list of job indices
        and desired_size is the target size per bucket
    """
    # Group jobs by (date, secao)
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, job in enumerate(jobs, start=1):
        d = str(job.get("data") or cfg.get("data") or "")
        s = str(job.get("secao") or cfg.get("secaoDefault") or "")
        groups[(d, s)].append(i)

    min_bucket = max(1, int(os.environ.get("DOU_BUCKET_SIZE_MIN", "2") or "2"))
    max_effective_workers = int(os.environ.get("DOU_MAX_WORKERS", "4") or "4")
    effective_parallel = min(parallel, max_effective_workers)

    unique_groups = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)

    # Strategy: Keep (date, secao) groups intact when possible
    if len(unique_groups) == 1:
        # Single group: split into buckets
        only_group_idxs = unique_groups[0][1]
        ideal_buckets = math.ceil(len(only_group_idxs) / max(2, min_bucket))
        bucket_count = min(effective_parallel, max(1, ideal_buckets))
        desired_size = max(1, math.ceil(len(only_group_idxs) / bucket_count))
        buckets = [
            only_group_idxs[start : start + desired_size] for start in range(0, len(only_group_idxs), desired_size)
        ]
    else:
        # Multiple groups
        if len(unique_groups) <= max(1, effective_parallel):
            buckets = [idxs for (_, idxs) in unique_groups[: max(1, effective_parallel)]]
            desired_size = max(min_bucket, max((len(b) for b in buckets), default=1))
        else:
            bucket_count = max(1, min(effective_parallel, math.ceil(len(jobs) / max(1, min_bucket))))
            desired_size = max(min_bucket, math.ceil(len(jobs) / bucket_count))
            pseudo_groups: list[list[int]] = [
                idxs[start : start + desired_size]
                for _, idxs in unique_groups
                for start in range(0, len(idxs), desired_size)
            ]
            buckets = [[] for _ in range(bucket_count)]
            for gi, chunk in enumerate(pseudo_groups):
                buckets[gi % bucket_count].extend(chunk)

    return buckets, desired_size


def create_worker_payload(
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    state_file_path: Path | None,
    reuse_page: bool,
    summary: dict[str, Any],
    bucket: list[int],
) -> dict[str, Any]:
    """Create payload for a worker process.

    Args:
        jobs: All jobs
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        state_file_path: Path to state file
        reuse_page: Whether to reuse browser page
        summary: Summary configuration
        bucket: List of job indices for this worker

    Returns:
        Worker payload dictionary
    """
    return {
        "jobs": jobs,
        "defaults": defaults,
        "out_dir": str(out_dir),
        "out_pattern": out_pattern,
        "headful": bool(args.headful),
        "slowmo": int(args.slowmo),
        "state_file": str(state_file_path) if state_file_path else None,
        "reuse_page": reuse_page,
        "summary": summary,
        "indices": bucket,
        "log_file": getattr(args, "log_file", None),
    }


def aggregate_report_metrics(report: dict[str, Any]) -> None:
    """Aggregate job metrics into summary statistics.

    Modifies report in place to add metrics.summary section.

    Args:
        report: Batch report dictionary
    """
    try:
        jobs_m = report.get("metrics", {}).get("jobs", [])
        if not jobs_m:
            return

        import statistics as _stats

        elapseds = [m.get("elapsed_sec", 0) or 0 for m in jobs_m]
        items = [m.get("items", 0) or 0 for m in jobs_m]
        rep_sum = {
            "jobs": len(jobs_m),
            "elapsed_sec_total": float(sum(elapseds)),
            "elapsed_sec_avg": float(_stats.mean(elapseds) if elapseds else 0),
            "elapsed_sec_p50": float(_stats.median(elapseds) if elapseds else 0),
            "elapsed_sec_p90": float(sorted(elapseds)[int(0.9 * len(elapseds)) - 1] if len(elapseds) >= 1 else 0),
            "items_total": int(sum(items)),
            "items_avg": float(_stats.mean(items) if items else 0),
        }
        if "metrics" not in report:
            report["metrics"] = {}
        report["metrics"]["summary"] = rep_sum
    except Exception:
        pass


def aggregate_outputs_by_date(paths: list[str], out_dir: Path, plan_name: str) -> list[str]:
    """Aggregate job outputs by date into per-date files.

    Args:
        paths: List of output file paths
        out_dir: Output directory
        plan_name: Plan name for output files

    Returns:
        List of aggregated output file paths
    """
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"data": "", "secao": "", "plan": plan_name, "itens": []}
    )
    secao_any = ""

    for pth in paths or []:
        try:
            data = json.loads(Path(pth).read_text(encoding="utf-8"))
        except Exception:
            continue

        date = str(data.get("data") or "")
        secao = str(data.get("secao") or "")

        if not agg[date]["data"]:
            agg[date]["data"] = date
        if not agg[date]["secao"]:
            agg[date]["secao"] = secao
        if not secao_any and secao:
            secao_any = secao

        items = data.get("itens", []) or []

        # Normalize detail_url (absolute)
        for it in items:
            try:
                durl = it.get("detail_url") or ""
                if not durl:
                    link = it.get("link") or ""
                    if link:
                        if link.startswith("http"):
                            durl = link
                        elif link.startswith("/"):
                            durl = f"https://www.in.gov.br{link}"
                if durl:
                    it["detail_url"] = durl
            except Exception:
                pass

        agg[date]["itens"].extend(items)

    written: list[str] = []
    secao_label = (secao_any or "DO").strip()

    for date, payload in agg.items():
        payload["total"] = len(payload.get("itens", []))
        safe_plan = sanitize_filename(plan_name)
        date_lab = (date or "").replace("/", "-")
        out_name = f"{safe_plan}_{secao_label}_{date_lab}.json"
        out_path = out_dir / out_name
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(out_path))

    return written


def write_report(report: dict[str, Any], out_dir: Path, cfg: dict[str, Any]) -> Path:
    """Write batch report to file.

    Args:
        report: Report dictionary
        out_dir: Output directory
        cfg: Batch configuration

    Returns:
        Path to report file
    """
    report_filename = ((cfg.get("output", {}) or {}).get("report")) or "batch_report.json"
    rep_path = out_dir / report_filename
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep_path


def finalize_with_aggregation(
    report: dict[str, Any], out_dir: Path, cfg: dict[str, Any], rep_path: Path, log_fn
) -> None:
    """Perform plan aggregation if configured.

    Args:
        report: Batch report
        out_dir: Output directory
        cfg: Batch configuration
        rep_path: Path to report file
        log_fn: Logging function
    """
    try:
        plan_name = (cfg.get("plan_name") or (cfg.get("defaults", {}) or {}).get("plan_name") or "").strip()
        if not plan_name:
            return

        prev_outputs = list(report.get("outputs", []))
        agg_files = aggregate_outputs_by_date(prev_outputs, out_dir, plan_name)

        if not agg_files:
            return

        # Delete original per-job outputs
        deleted = []
        for pth in prev_outputs:
            try:
                Path(pth).unlink(missing_ok=True)
                deleted.append(pth)
            except Exception:
                pass

        # Update batch report
        try:
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
        except Exception:
            rep = report

        rep["deleted_outputs"] = deleted
        rep["outputs"] = []
        rep["aggregated"] = agg_files
        rep["aggregated_only"] = True
        rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

        log_fn(
            f"[AGG] {len(agg_files)} arquivo(s) agregado(s) por plano: {plan_name}; removidos {len(deleted)} JSON(s) individuais"
        )
    except Exception as e:
        log_fn(f"[AGG][WARN] Falha ao agregar por plano: {e}")
