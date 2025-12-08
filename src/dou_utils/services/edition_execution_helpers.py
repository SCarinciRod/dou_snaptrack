"""Helper functions for EditionRunnerService.run to reduce complexity.

This module contains extracted functions from EditionRunnerService.run().
"""

from __future__ import annotations

import contextlib
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..detail_utils import abs_url as _abs_url
from ..enrich_utils import enrich_items_friendly_titles as _enrich_titles
from ..page_utils import find_best_frame, goto as _goto, try_visualizar_em_lista
from ..query_utils import apply_query as _apply_query, collect_links as _collect_links
from ..services.cascade_service import CascadeParams, CascadeService
from ..services.multi_level_cascade_service import MultiLevelCascadeSelector


def build_edition_url(date: str, secao: str) -> str:
    """Build edition URL from date and secao."""
    return f"https://www.in.gov.br/leiturajornal?data={date}&secao={secao}"


def should_reuse_inpage(page, allow_inpage_reuse: bool, date: str, secao: str) -> bool:
    """Check if current page can be reused for this edition.
    
    Args:
        page: Playwright page (can be None)
        allow_inpage_reuse: Whether in-page reuse is allowed
        date: Target date
        secao: Target secao
        
    Returns:
        True if page can be reused
    """
    if not allow_inpage_reuse or page is None:
        return False
    
    try:
        if page.is_closed():
            return False
        
        cur = page.url or ""
        if not cur:
            return False
        
        pu = urlparse(cur)
        qu = parse_qs(pu.query or "")
        
        # Compare edition by query params
        same_date = (qu.get("data", [None])[0] == str(date))
        same_secao = (qu.get("secao", [None])[0] == str(secao))
        
        return same_date and same_secao
    except Exception:
        return False


def navigate_to_edition(page, url: str, do_nav: bool, inpage: bool) -> dict[str, float]:
    """Navigate to edition and prepare view.
    
    Args:
        page: Playwright page
        url: Edition URL
        do_nav: Whether to navigate
        inpage: Whether reusing in-page
        
    Returns:
        Dict with timing info: {'t0', 't_after_nav'}
    """
    t0 = time.time()
    
    # Reset t0 if reusing in-page to avoid accumulating idle time
    if inpage:
        t0 = time.time()
    
    if do_nav:
        _goto(page, url)
    
    t_after_nav = time.time()
    
    # Ensure list view (idempotent even for in-page reuse)
    try_visualizar_em_lista(page)
    
    return {'t0': t0, 't_after_nav': t_after_nav}


def run_multilevel_selection(frame, params) -> dict[str, Any]:
    """Run multi-level cascade selection.
    
    Args:
        frame: Playwright frame
        params: EditionRunParams
        
    Returns:
        Selection result dict
    """
    selector = MultiLevelCascadeSelector(frame)
    return selector.run(
        key1=str(params.key1), key1_type=str(params.key1_type),
        key2=str(params.key2), key2_type=str(params.key2_type),
        key3=str(params.key3) if params.key3 else None,
        key3_type=str(params.key3_type) if params.key3_type else None,
        label1=params.label1, label2=params.label2, label3=params.label3
    )


def retry_selection_with_reload(page, context, params, inpage: bool) -> dict[str, Any]:
    """Retry selection after hard refresh if in-page reuse failed.
    
    Args:
        page: Playwright page
        context: Browser context
        params: EditionRunParams
        inpage: Whether was using in-page reuse
        
    Returns:
        Selection result dict
    """
    if not inpage:
        return {"ok": False}
    
    try:
        page.reload(wait_until="domcontentloaded", timeout=60_000)
        try_visualizar_em_lista(page)
        frame = find_best_frame(context)
        return run_multilevel_selection(frame, params)
    except Exception:
        return {"ok": False}


def build_error_result(params, selres: dict) -> dict[str, Any]:
    """Build error result when selection fails.
    
    Args:
        params: EditionRunParams
        selres: Selection result with error info
        
    Returns:
        Error result dict
    """
    return {
        "data": params.date,
        "secao": params.secao,
        "selecoes": [
            {"level": 1, "type": params.key1_type, "key": params.key1},
            {"level": 2, "type": params.key2_type, "key": params.key2},
            {"level": 3, "type": params.key3_type, "key": params.key3},
        ],
        "query": params.query,
        "total": 0,
        "itens": [],
        "enriquecido": False,
        "_error": f"selection_failed_level_{selres.get('level_fail')}"
    }


def collect_edition_links(frame, params) -> list[dict]:
    """Collect links from edition after query application.
    
    Args:
        frame: Playwright frame
        params: EditionRunParams
        
    Returns:
        List of collected items
    """
    _apply_query(frame, params.query or "")
    
    return _collect_links(
        frame,
        max_links=params.max_links,
        max_scrolls=params.max_scrolls,
        scroll_pause_ms=params.scroll_pause_ms,
        stable_rounds=params.stable_rounds,
    )


def build_base_result(params) -> dict[str, Any]:
    """Build base result structure.
    
    Args:
        params: EditionRunParams
        
    Returns:
        Base result dict
    """
    return {
        "data": params.date,
        "secao": params.secao,
        "selecoes": [
            {"level": 1, "type": params.key1_type, "key": params.key1},
            {"level": 2, "type": params.key2_type, "key": params.key2},
            {"level": 3, "type": params.key3_type, "key": params.key3},
        ],
        "query": params.query,
        "total": 0,
        "itens": [],
        "enriquecido": False,
    }


def enrich_items_with_detail(context, page, frame, url: str, items: list, params, summarizer_fn) -> tuple[list, bool]:
    """Enrich items with detailed information.
    
    Args:
        context: Browser context
        page: Playwright page
        frame: Playwright frame
        url: Edition URL
        items: Items to enrich
        params: EditionRunParams
        summarizer_fn: Summarizer function
        
    Returns:
        Tuple of (enriched_items, enriched_flag)
    """
    svc = CascadeService(context, page, frame, summarize_fn=summarizer_fn)
    out = svc.run(
        items,
        CascadeParams(
            url=url,
            date=params.date,
            secao=params.secao,
            query=params.query,
            max_links=params.max_links,
            scrape_detail=True,
            detail_timeout=params.detail_timeout,
            parallel=max(1, int(getattr(params, "detail_parallel", 1) or 1)),
            summary=params.summary,
            summary_lines=params.summary_lines,
            summary_mode=params.summary_mode,
            summary_keywords=params.summary_keywords,
            advanced_detail=False,
            fallback_date_if_missing=params.fallback_date_if_missing,
            dedup_state_file=params.dedup_state_file,
        )
    )
    
    enriched_items = out.get("itens", [])
    
    # Attach orgao metadata
    for it in enriched_items:
        with contextlib.suppress(Exception):
            if not it.get("orgao"):
                it["orgao"] = params.label1 or params.key1
    
    return enriched_items, True


def normalize_items_without_detail(page, items: list, params) -> tuple[list, bool]:
    """Normalize items without detail scraping.
    
    Args:
        page: Playwright page
        items: Items to normalize
        params: EditionRunParams
        
    Returns:
        Tuple of (normalized_items, enriched_flag)
    """
    norm_items = []
    for it in items:
        try:
            link = it.get("link") or ""
            durl = _abs_url(page.url, link) if link else ""
            if durl:
                it = {**it, "detail_url": durl}
            
            # Attach orgao metadata
            with contextlib.suppress(Exception):
                it["orgao"] = params.label1 or params.key1
        except Exception:
            pass
        norm_items.append(it)
    
    try:
        enriched = _enrich_titles(norm_items, date=params.date, secao=params.secao)
        return enriched, False
    except Exception:
        return norm_items, False


def build_timings(t0: float, t_after_nav: float, t_after_view: float, 
                  t_after_select: float, t_after_collect: float, inpage: bool) -> dict[str, Any]:
    """Build timing metrics.
    
    Args:
        t0: Start time
        t_after_nav: Time after navigation
        t_after_view: Time after view setup
        t_after_select: Time after selection
        t_after_collect: Time after collection
        inpage: Whether in-page reuse was used
        
    Returns:
        Timing metrics dict
    """
    total_elapsed = time.time() - t0
    return {
        "nav_sec": round(t_after_nav - t0, 3),
        "view_sec": round(t_after_view - t_after_nav, 3),
        "select_sec": round(t_after_select - t_after_view, 3),
        "collect_sec": round(t_after_collect - t_after_select, 3),
        "total_sec": round(total_elapsed, 3),
        "inpage_reuse": bool(inpage),
    }


def log_execution_summary(params, timings: dict):
    """Log execution summary.
    
    Args:
        params: EditionRunParams
        timings: Timing metrics
    """
    print(
        f"[EditionRunner] data={params.date} secao={params.secao} k1={params.key1} k2={params.key2} "
        f"inpage={int(timings['inpage_reuse'])} timings: nav={timings['nav_sec']:.1f}s "
        f"view={timings['view_sec']:.1f}s select={timings['select_sec']:.1f}s "
        f"collect={timings['collect_sec']:.1f}s total={timings['total_sec']:.1f}s"
    )
