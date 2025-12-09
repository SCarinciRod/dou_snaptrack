"""Helper functions for batch configuration expansion.

This module contains functions extracted from expand_batch_config to reduce complexity.
"""

from __future__ import annotations

from typing import Any


def apply_base_config(job: dict[str, Any], base_data: str | None, base_secao: str | None) -> None:
    """Apply base data and secao to job if not already set.

    Args:
        job: Job dictionary (modified in place)
        base_data: Base data value
        base_secao: Base secao value
    """
    if base_data and not job.get("data"):
        job["data"] = base_data
    if base_secao and not job.get("secao"):
        job["secao"] = base_secao


def apply_topic_summary_config(job: dict[str, Any], topic: dict[str, Any]) -> None:
    """Apply topic-level summary configuration to job.

    Args:
        job: Job dictionary (modified in place)
        topic: Topic configuration
    """
    t_summary_kws = topic.get("summary_keywords")
    t_summary_lines = topic.get("summary_lines")
    t_summary_mode = topic.get("summary_mode")

    if t_summary_kws is not None:
        job["summary_keywords"] = t_summary_kws
    if t_summary_lines is not None:
        job["summary_lines"] = t_summary_lines
    if t_summary_mode is not None:
        job["summary_mode"] = t_summary_mode


def create_repeated_jobs(base_job: dict[str, Any], repeat_count: int) -> list[dict[str, Any]]:
    """Create repeated job instances.

    Args:
        base_job: Base job configuration
        repeat_count: Number of repetitions

    Returns:
        List of repeated job dictionaries
    """
    jobs = []
    for r in range(1, repeat_count + 1):
        job_copy = dict(base_job)
        job_copy["_repeat"] = r
        jobs.append(job_copy)
    return jobs


def expand_simple_jobs(
    cfg: dict[str, Any], defaults: dict[str, Any], base_data: str | None, base_secao: str | None
) -> list[dict[str, Any]]:
    """Expand simple jobs from cfg['jobs'].

    Args:
        cfg: Batch configuration
        defaults: Default configuration
        base_data: Base data value
        base_secao: Base secao value

    Returns:
        List of expanded job dictionaries
    """
    jobs: list[dict[str, Any]] = []

    def merge_defaults(job):
        out = dict(defaults)
        out.update(job or {})
        return out

    for j in cfg.get("jobs", []):
        jj = merge_defaults(j)
        apply_base_config(jj, base_data, base_secao)
        repeat_count = max(1, int(jj.get("repeat", cfg.get("repeat", 1))))
        jobs.extend(create_repeated_jobs(jj, repeat_count))

    return jobs


def expand_topic_combo_jobs(
    cfg: dict[str, Any], defaults: dict[str, Any], base_data: str | None, base_secao: str | None
) -> list[dict[str, Any]]:
    """Expand jobs from topics and combos.

    Args:
        cfg: Batch configuration
        defaults: Default configuration
        base_data: Base data value
        base_secao: Base secao value

    Returns:
        List of expanded job dictionaries
    """
    jobs: list[dict[str, Any]] = []

    def merge_defaults(job):
        out = dict(defaults)
        out.update(job or {})
        return out

    topics = cfg.get("topics", [])
    combos = cfg.get("combos", [])

    for t in topics:
        topic_name = t.get("name") or "topic"
        topic_query = t.get("query") or ""
        topic_repeat = int(t.get("repeat", cfg.get("repeat", 1)))

        for idx, c in enumerate(combos, 1):
            jj = merge_defaults(c)
            apply_base_config(jj, base_data, base_secao)

            # Set topic-specific fields
            jj["topic"] = topic_name
            jj["query"] = jj.get("query", topic_query)
            jj["_combo_index"] = idx

            # Apply topic-level summary config
            apply_topic_summary_config(jj, t)

            # Create repeated jobs
            repeat_count = max(1, int(jj.get("repeat", topic_repeat)))
            jobs.extend(create_repeated_jobs(jj, repeat_count))

    return jobs


def expand_combo_only_jobs(
    cfg: dict[str, Any], defaults: dict[str, Any], base_data: str | None, base_secao: str | None
) -> list[dict[str, Any]]:
    """Expand jobs from combos only (no topics).

    Args:
        cfg: Batch configuration
        defaults: Default configuration
        base_data: Base data value
        base_secao: Base secao value

    Returns:
        List of expanded job dictionaries
    """
    jobs: list[dict[str, Any]] = []

    def merge_defaults(job):
        out = dict(defaults)
        out.update(job or {})
        return out

    combos = cfg.get("combos", [])

    for idx, c in enumerate(combos, 1):
        jj = merge_defaults(c)
        apply_base_config(jj, base_data, base_secao)

        # Set default topic if not provided
        jj["topic"] = jj.get("topic") or f"job{idx}"
        jj["query"] = jj.get("query", defaults.get("query", "") if isinstance(defaults, dict) else "")
        jj["_combo_index"] = idx

        # Create repeated jobs
        repeat_count = max(1, int(jj.get("repeat", cfg.get("repeat", 1))))
        jobs.extend(create_repeated_jobs(jj, repeat_count))

    return jobs
