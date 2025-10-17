from __future__ import annotations

import os


def recommend_parallel(total_jobs: int, prefer_process: bool = True) -> int:
    """Compute a conservative parallelism recommendation for Playwright-based batch jobs.

    Heuristic goals:
    - Avoid thrashing by launching too many Chromium instances
    - Benefit from I/O overlap without exceeding CPU/memory limits
    - Respect environment caps via DOU_PARALLEL_MAX / DOU_PARALLEL_MIN

    Inputs:
    - total_jobs: how many jobs will run (upper bound for parallel)
    - prefer_process: if True, assume process-based pool overhead (more conservative)
    """
    try:
        cores = os.cpu_count() or 4
    except Exception:
        cores = 4

    # Env caps (optional)
    try:
        cap_max = int(os.environ.get("DOU_PARALLEL_MAX", "0") or "0")
        cap_min = int(os.environ.get("DOU_PARALLEL_MIN", "1") or "1")
    except Exception:
        cap_max = 0
        cap_min = 1

    # Base recommendation depends on core count and pool type
    if cores >= 16:
        base = cores - (4 if prefer_process else 2)
    elif cores >= 8:
        base = cores - (2 if prefer_process else 1)
    elif cores >= 4:
        base = cores - (1 if prefer_process else 0)
    else:
        base = max(1, cores)  # very small machines

    # I/O overlap allowance: allow slight over-subscription for I/O wait
    io_bonus = 1 if cores >= 4 else 0
    rec = max(1, base + io_bonus)

    # Global safe hard cap (Chromium is heavy). Allow env override to lift.
    hard_cap = 8
    if cap_max > 0:
        hard_cap = cap_max

    # Never exceed job count or hard cap
    rec = min(rec, max(1, total_jobs), hard_cap)

    # Respect minimum cap
    rec = max(rec, max(1, cap_min))

    return int(rec)
