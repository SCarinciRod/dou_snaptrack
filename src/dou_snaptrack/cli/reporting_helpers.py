"""Helper functions for reporting to reduce complexity.

This module contains functions extracted from reporting.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


def normalize_item_detail_url(item: dict[str, Any]) -> None:
    """Normalize detail_url to absolute URL for item.

    Args:
        item: Item dictionary (modified in place)
    """
    durl = item.get("detail_url") or ""
    if not durl:
        link = item.get("link") or ""
        if link:
            if link.startswith("http"):
                durl = link
            elif link.startswith("/"):
                durl = f"https://www.in.gov.br{link}"
    if durl:
        item["detail_url"] = durl


def load_aggregated_files(files: list[str]) -> tuple[list[dict[str, Any]], str, str]:
    """Load and merge aggregated files.

    Args:
        files: List of file paths to load

    Returns:
        Tuple of (items, date, secao)
    """
    agg: list[dict[str, Any]] = []
    date = ""
    secao = ""

    for fp in files:
        try:
            data = __import__('json').loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue

        items = data.get("itens", [])

        # Normalize URLs
        for it in items:
            normalize_item_detail_url(it)

        agg.extend(items)

        if not date:
            date = data.get("data") or date
        if not secao:
            secao = data.get("secao") or secao

    return agg, date, secao


def sort_items_by_date_desc(items: list[dict[str, Any]]) -> None:
    """Sort items by publication date in descending order.

    Args:
        items: List of items (sorted in place)
    """

    def _key(it: dict[str, Any]):
        d = it.get("data_publicacao") or ""
        # Expected DD-MM-YYYY; convert to comparable YYYY-MM-DD format
        try:
            dd, mm, yyyy = d.split("-")
            return f"{yyyy}-{mm}-{dd}"
        except Exception:
            return ""

    items.sort(key=_key, reverse=True)


def should_enrich_items(
    summary_lines: int, enrich_missing: bool, items: list[dict[str, Any]]
) -> bool:
    """Determine if items should be enriched with deep mode.

    Args:
        summary_lines: Number of summary lines requested
        enrich_missing: Whether enrichment is enabled
        items: List of items

    Returns:
        True if items should be enriched
    """
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1", "true", "yes")
    return summary_lines > 0 and not offline and enrich_missing and bool(items)


def enrich_items_with_fetcher(
    items: list[dict[str, Any]],
    fetch_parallel: int,
    fetch_timeout_sec: int,
    fetch_force_refresh: bool,
    fetch_browser_fallback: bool,
    short_len_threshold: int,
) -> None:
    """Enrich items with full text using Fetcher.

    Args:
        items: List of items (modified in place)
        fetch_parallel: Number of parallel workers
        fetch_timeout_sec: Timeout in seconds
        fetch_force_refresh: Force refresh flag
        fetch_browser_fallback: Use browser fallback flag
        short_len_threshold: Short length threshold
    """
    from dou_snaptrack.utils.fetcher import Fetcher

    logger.info(
        f"[ENRICH] deep-mode STRICT: items={len(items)} parallel={fetch_parallel} timeout={fetch_timeout_sec}s "
        f"overwrite=True force_refresh={bool(fetch_force_refresh)} browser_fallback={bool(fetch_browser_fallback)} short_len_threshold={int(short_len_threshold)}"
    )

    Fetcher(
        timeout_sec=fetch_timeout_sec,
        force_refresh=bool(fetch_force_refresh),
        use_browser_if_short=bool(fetch_browser_fallback),
        short_len_threshold=int(short_len_threshold),
        browser_timeout_sec=max(20, fetch_timeout_sec),
    ).enrich_items(items, max_workers=fetch_parallel, overwrite=True, min_len=None)  # type: ignore


def clean_enriched_items(items: list[dict[str, Any]]) -> None:
    """Clean DOU headers from enriched items.

    The fetcher saves complete HTML with "Brasão do Brasil... Diário Oficial..."
    We need to clean BEFORE summarization to avoid headers in summaries.

    Args:
        items: List of items (modified in place)
    """
    from dou_utils.summary_utils import clean_text_for_summary

    for it in items:
        texto_bruto = it.get("texto") or ""
        if texto_bruto:
            it["texto"] = clean_text_for_summary(texto_bruto)


def log_enrichment_debug_info(items: list[dict[str, Any]]) -> None:
    """Log debug information about enrichment results.

    Args:
        items: List of items
    """
    with_texto = sum(1 for i in items if i.get("texto"))
    logger.info(f"[DEBUG] Após enrich+limpeza: {with_texto}/{len(items)} items com 'texto'")

    if items:
        sample_idx = min(2, len(items) - 1)
        sample_text = items[sample_idx].get("texto", "")
        logger.info(f"[DEBUG] Item[{sample_idx}] titulo: {items[sample_idx].get('titulo', '')[:50]}")
        logger.info(
            f"[DEBUG] Item[{sample_idx}] texto length: {len(sample_text)}, primeiros 200: {sample_text[:200]}"
        )


def log_enrichment_skip_reason(
    summary_lines: int, enrich_missing: bool, offline: bool, has_items: bool
) -> None:
    """Log why enrichment was skipped.

    Args:
        summary_lines: Number of summary lines
        enrich_missing: Whether enrichment is enabled
        offline: Whether offline mode is enabled
        has_items: Whether there are items
    """
    if summary_lines <= 0:
        logger.info("[ENRICH] skipped: summarize disabled (summary_lines=0)")
    elif not enrich_missing:
        logger.info("[ENRICH] skipped: enrich_missing=False")
    elif offline:
        logger.info("[ENRICH] skipped: DOU_OFFLINE_REPORT=1")
    elif not has_items:
        logger.info("[ENRICH] skipped: no items")


def fallback_add_title_as_text(items: list[dict[str, Any]], summary_lines: int) -> None:
    """Add title as text fallback when text is missing.

    Args:
        items: List of items (modified in place)
        summary_lines: Number of summary lines (used to check if summarization is enabled)
    """
    if summary_lines > 0 and items:
        for it in items:
            if not (it.get("texto") or it.get("ementa")):
                t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                if t:
                    it["texto"] = str(t)
