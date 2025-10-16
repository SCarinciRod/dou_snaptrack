from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Callable
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from ..page_utils import goto as _goto, try_visualizar_em_lista, find_best_frame
from ..detail_utils import abs_url as _abs_url
from ..query_utils import apply_query as _apply_query, collect_links as _collect_links
from ..enrich_utils import enrich_items_friendly_titles as _enrich_titles
from ..services.multi_level_cascade_service import MultiLevelCascadeSelector
from ..services.cascade_service import CascadeService, CascadeParams
from ..bulletin_utils import generate_bulletin as _generate_bulletin  # optional, used by caller typically


@dataclass
class EditionRunParams:
    date: str
    secao: str
    key1: str
    key1_type: str
    key2: str
    key2_type: str
    key3: Optional[str] = None
    key3_type: Optional[str] = None
    label1: Optional[str] = None
    label2: Optional[str] = None
    label3: Optional[str] = None

    query: Optional[str] = None
    max_links: int = 30
    max_scrolls: int = 30
    scroll_pause_ms: int = 250
    stable_rounds: int = 2

    scrape_detail: bool = False
    detail_timeout: int = 60_000
    fallback_date_if_missing: bool = True
    dedup_state_file: Optional[str] = None
    detail_parallel: int = 1

    # Summary is usually applied at bulletin generation; keep disabled here by default
    summary: bool = False
    summary_lines: int = 7
    summary_mode: str = "center"
    summary_keywords: Optional[List[str]] = None


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
                    if rtype in ("image", "media", "font", "stylesheet"):
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

    def run(self, params: EditionRunParams, summarizer_fn: Optional[Callable] = None) -> Dict[str, Any]:
        import time
        t0 = time.time()
        page = self._precreated_page or self.context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        url = f"https://www.in.gov.br/leiturajornal?data={params.date}&secao={params.secao}"
        # Decide whether to navigate or reuse current edition page
        do_nav = True
        inpage = False
        try:
            if self._precreated_page is not None and self._allow_inpage_reuse and not page.is_closed():
                cur = page.url or ""
                if cur:
                    pu = urlparse(cur)
                    qu = parse_qs(pu.query or "")
                    # compare edition by query params (string equality on first values)
                    same_date = (qu.get("data", [None])[0] == str(params.date))
                    same_secao = (qu.get("secao", [None])[0] == str(params.secao))
                    if same_date and same_secao:
                        do_nav = False
                        inpage = True
        except Exception:
            pass

        if do_nav:
            _goto(page, url)
        t_after_nav = time.time()
        # Garantir visão em lista mesmo em reuso in-page (idempotente)
        try_visualizar_em_lista(page)
        frame = find_best_frame(self.context)
        t_after_view = time.time()

        def _run_selection(_frame):
            selector = MultiLevelCascadeSelector(_frame)
            return selector.run(
                key1=str(params.key1), key1_type=str(params.key1_type),
                key2=str(params.key2), key2_type=str(params.key2_type),
                key3=str(params.key3) if params.key3 else None, key3_type=str(params.key3_type) if params.key3_type else None,
                label1=params.label1, label2=params.label2, label3=params.label3
            )

        selres = _run_selection(frame)
        # If selection failed while trying in-page reuse, do a single hard refresh and retry
        if not selres.get("ok") and inpage:
            try:
                page.reload(wait_until="domcontentloaded", timeout=60_000)
                try_visualizar_em_lista(page)
                frame = find_best_frame(self.context)
                selres = _run_selection(frame)
            except Exception:
                pass
        if not selres.get("ok"):
            try:
                page.close()
            except Exception:
                pass
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

        _apply_query(frame, params.query or "")
        t_after_select = time.time()
        items = _collect_links(
            frame,
            max_links=params.max_links,
            max_scrolls=params.max_scrolls,
            scroll_pause_ms=params.scroll_pause_ms,
            stable_rounds=params.stable_rounds,
        )
        t_after_collect = time.time()

        result: Dict[str, Any] = {
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

        if params.scrape_detail:
            svc = CascadeService(self.context, page, frame, summarize_fn=summarizer_fn)
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
            result["itens"] = out.get("itens", [])
            # Ensure each enriched item carries the originating N1 (orgão) metadata
            for it in result.get("itens", []):
                try:
                    if not it.get("orgao"):
                        # prefer label when available
                        it["orgao"] = params.label1 or params.key1
                except Exception:
                    pass
            result["total"] = len(result["itens"])
            result["enriquecido"] = True
        else:
            # Sem enriquecimento: normalize links relativos e gere títulos amigáveis heurísticos
            norm_items = []
            for it in items:
                try:
                    link = it.get("link") or ""
                    durl = _abs_url(page.url, link) if link else ""
                    if durl:
                        it = {**it, "detail_url": durl}
                    # Attach originating N1 (orgão) so downstream bulletin can group by it
                    try:
                        it["orgao"] = params.label1 or params.key1
                    except Exception:
                        pass
                except Exception:
                    pass
                norm_items.append(it)
            try:
                result["itens"] = _enrich_titles(norm_items, date=params.date, secao=params.secao)
            except Exception:
                result["itens"] = norm_items
            result["total"] = len(items)
            result["enriquecido"] = False

        if not self._keep_page_open:
            try:
                page.close()
            except Exception:
                pass
        total_elapsed = time.time() - t0
        print(
            f"[EditionRunner] data={params.date} secao={params.secao} k1={params.key1} k2={params.key2} inpage={int(inpage)} "
            f"timings: nav={t_after_nav - t0:.1f}s view={t_after_view - t_after_nav:.1f}s "
            f"select={t_after_select - t_after_view:.1f}s collect={t_after_collect - t_after_select:.1f}s total={total_elapsed:.1f}s"
        )
        return result
