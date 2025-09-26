from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Callable
from pathlib import Path

from ..page_utils import goto as _goto, try_visualizar_em_lista, find_best_frame
from ..query_utils import apply_query as _apply_query, collect_links as _collect_links
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
    max_scrolls: int = 40
    scroll_pause_ms: int = 350
    stable_rounds: int = 3

    scrape_detail: bool = False
    detail_timeout: int = 60_000
    fallback_date_if_missing: bool = True
    dedup_state_file: Optional[str] = None

    # Summary is usually applied at bulletin generation; keep disabled here by default
    summary: bool = False
    summary_lines: int = 7
    summary_mode: str = "center"
    summary_keywords: Optional[List[str]] = None


class EditionRunnerService:
    def __init__(self, context):
        self.context = context

    def run(self, params: EditionRunParams, summarizer_fn: Optional[Callable] = None) -> Dict[str, Any]:
        page = self.context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        url = f"https://www.in.gov.br/leiturajornal?data={params.date}&secao={params.secao}"
        _goto(page, url)
        try_visualizar_em_lista(page)
        frame = find_best_frame(self.context)

        selector = MultiLevelCascadeSelector(frame)
        selres = selector.run(
            key1=str(params.key1), key1_type=str(params.key1_type),
            key2=str(params.key2), key2_type=str(params.key2_type),
            key3=str(params.key3) if params.key3 else None, key3_type=str(params.key3_type) if params.key3_type else None,
            label1=params.label1, label2=params.label2, label3=params.label3
        )
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
        items = _collect_links(
            frame,
            max_links=params.max_links,
            max_scrolls=params.max_scrolls,
            scroll_pause_ms=params.scroll_pause_ms,
            stable_rounds=params.stable_rounds,
        )

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
                    parallel=1,
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
            result["total"] = len(result["itens"])
            result["enriquecido"] = True
        else:
            result["itens"] = items
            result["total"] = len(items)
            result["enriquecido"] = False

        try:
            page.close()
        except Exception:
            pass
        return result
