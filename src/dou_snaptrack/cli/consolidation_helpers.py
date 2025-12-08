"""Helper functions for consolidation and reporting.

This module contains extracted functions from consolidate_and_report to reduce complexity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dou_utils.content_fetcher import Fetcher
from dou_utils.log_utils import get_logger

logger = get_logger(__name__)


def load_json_files(in_dir: str) -> list[dict[str, Any]]:
    """Load all JSON files from directory and aggregate items.
    
    Args:
        in_dir: Input directory path
        
    Returns:
        List of aggregated items
    """
    agg = []
    for f in sorted(Path(in_dir).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items = data.get("itens", [])
            normalize_item_urls(items)
            agg.extend(items)
        except Exception:
            pass
    return agg


def normalize_item_urls(items: list[dict[str, Any]]) -> None:
    """Normalize item URLs to absolute URLs.
    
    Args:
        items: List of items to normalize (modified in place)
    """
    for it in items:
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


def should_enrich(summary_lines: int, agg: list[dict[str, Any]]) -> bool:
    """Determine if items should be enriched.
    
    Args:
        summary_lines: Number of summary lines
        agg: List of items
        
    Returns:
        True if should enrich, False otherwise
    """
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    return summary_lines > 0 and not offline and bool(agg)


def enrich_items(
    agg: list[dict[str, Any]],
    fetch_parallel: int,
    fetch_timeout_sec: int,
    fetch_force_refresh: bool,
    fetch_browser_fallback: bool,
    short_len_threshold: int,
) -> None:
    """Enrich items with full text content.
    
    Args:
        agg: List of items to enrich (modified in place)
        fetch_parallel: Number of parallel workers
        fetch_timeout_sec: Timeout in seconds
        fetch_force_refresh: Force refresh flag
        fetch_browser_fallback: Use browser fallback flag
        short_len_threshold: Short length threshold
    """
    logger.info(
        f"[ENRICH] deep-mode STRICT: items={len(agg)} parallel={fetch_parallel} timeout={fetch_timeout_sec}s "
        f"overwrite=True force_refresh={bool(fetch_force_refresh)} browser_fallback={bool(fetch_browser_fallback)} short_len_threshold={int(short_len_threshold)}"
    )
    Fetcher(
        timeout_sec=fetch_timeout_sec,
        force_refresh=bool(fetch_force_refresh),
        use_browser_if_short=bool(fetch_browser_fallback),
        short_len_threshold=int(short_len_threshold),
        browser_timeout_sec=max(20, fetch_timeout_sec),
    ).enrich_items(agg, max_workers=fetch_parallel, overwrite=True, min_len=None)  # type: ignore


def log_enrich_skip_reason(summary_lines: int, enrich_missing: bool, agg: list[dict[str, Any]]) -> None:
    """Log reason for skipping enrichment.
    
    Args:
        summary_lines: Number of summary lines
        enrich_missing: Enrich missing flag
        agg: List of items
    """
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines <= 0:
        logger.info("[ENRICH] skipped: summarize disabled (summary_lines=0)")
    elif not enrich_missing:
        logger.info("[ENRICH] skipped: enrich_missing=False")
    elif offline:
        logger.info("[ENRICH] skipped: DOU_OFFLINE_REPORT=1")
    elif not agg:
        logger.info("[ENRICH] skipped: no items")


def add_title_fallback(agg: list[dict[str, Any]], summary_lines: int) -> None:
    """Add title as fallback text for items without text.
    
    Args:
        agg: List of items (modified in place)
        summary_lines: Number of summary lines
    """
    if summary_lines > 0 and agg:
        for it in agg:
            if not (it.get("texto") or it.get("ementa")):
                t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                if t:
                    it["texto"] = str(t)


def create_result_dict(agg: list[dict[str, Any]], date_label: str, secao_label: str) -> dict[str, Any]:
    """Create result dictionary from aggregated items.
    
    Args:
        agg: List of aggregated items
        date_label: Date label
        secao_label: Section label
        
    Returns:
        Result dictionary
    """
    return {
        "data": date_label or "",
        "secao": secao_label or "",
        "total": len(agg),
        "itens": agg,
    }
