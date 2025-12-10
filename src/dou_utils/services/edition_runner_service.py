from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..page_utils import find_best_frame


@dataclass
class EditionRunParams:
    date: str
    secao: str
    key1: str
    key1_type: str
    key2: str
    key2_type: str
    key3: str | None = None
    key3_type: str | None = None
    label1: str | None = None
    label2: str | None = None
    label3: str | None = None

    query: str | None = None
    max_links: int = 100
    max_scrolls: int = 30
    scroll_pause_ms: int = 250
    stable_rounds: int = 2

    scrape_detail: bool = False
    detail_timeout: int = 60_000
    fallback_date_if_missing: bool = True
    dedup_state_file: str | None = None
    detail_parallel: int = 1

    # Summary is usually applied at bulletin generation; keep disabled here by default
    summary: bool = False
    summary_lines: int = 7
    summary_mode: str = "center"
    summary_keywords: list[str] | None = None


class EditionRunnerService:
    def __init__(self, context):
        self.context = context
        # Optional hooks for page reuse (set by caller)
        self._precreated_page = None
        self._keep_page_open = False
        # When True and a precreated page is provided, avoid navigation if already on same edition
        self._allow_inpage_reuse = False
        # Install a global route on the context to block heavy resources (images, media, fonts)
        try:
            def _route_block_heavy(route):
                try:
                    req = route.request
                    rtype = getattr(req, "resource_type", lambda: "")()
                    # Não bloquear stylesheet para evitar quebra de dropdown/renderização dinâmica
                    if rtype in ("image", "media", "font"):
                        return route.abort()
                    url = req.url
                    if any(url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".woff", ".woff2")):
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()
            self.context.route("**/*", _route_block_heavy)
        except Exception:
            pass

    def run(self, params: EditionRunParams, summarizer_fn: Callable | None = None) -> dict[str, Any]:
        import time

        from .edition_execution_helpers import (
            build_base_result,
            build_edition_url,
            build_error_result,
            build_timings,
            collect_edition_links,
            enrich_items_with_detail,
            log_execution_summary,
            navigate_to_edition,
            normalize_items_without_detail,
            retry_selection_with_reload,
            run_multilevel_selection,
            should_reuse_inpage,
        )

        # Setup page
        page = self._precreated_page or self.context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        # Determine navigation strategy
        url = build_edition_url(params.date, params.secao)
        inpage = should_reuse_inpage(
            self._precreated_page,
            self._allow_inpage_reuse,
            params.date,
            params.secao
        )
        do_nav = not inpage

        # Navigate and prepare view
        nav_times = navigate_to_edition(page, url, do_nav, inpage)
        frame = find_best_frame(self.context)
        t_after_view = time.time()

        # Run selection with retry on failure
        selres = run_multilevel_selection(frame, params)
        if not selres.get("ok") and inpage:
            selres = retry_selection_with_reload(page, self.context, params, inpage)

        if not selres.get("ok"):
            with contextlib.suppress(Exception):
                page.close()
            return build_error_result(params, selres)

        # Collect links
        t_after_select = time.time()
        items = collect_edition_links(frame, params)
        t_after_collect = time.time()

        # Build result
        result = build_base_result(params)

        if params.scrape_detail:
            enriched_items, enriched = enrich_items_with_detail(
                self.context, page, frame, url, items, params, summarizer_fn
            )
            result["itens"] = enriched_items
            result["total"] = len(enriched_items)
            result["enriquecido"] = enriched
        else:
            normalized_items, enriched = normalize_items_without_detail(page, items, params)
            result["itens"] = normalized_items
            result["total"] = len(items)
            result["enriquecido"] = enriched

        # Cleanup
        if not self._keep_page_open:
            with contextlib.suppress(Exception):
                page.close()

        # Add timings and log
        timings = build_timings(
            nav_times['t0'], nav_times['t_after_nav'], t_after_view,
            t_after_select, t_after_collect, inpage
        )
        with contextlib.suppress(Exception):
            result["_timings"] = timings

        log_execution_summary(params, timings)
        return result
