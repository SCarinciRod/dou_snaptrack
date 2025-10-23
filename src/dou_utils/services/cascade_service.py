"""
cascade_service.py (Refatorado)
Serviço de execução de cascade (coleta -> detalhes -> dedup -> resumo).

Melhorias:
- Abstração da dependência do Playwright
- Logging mais estruturado
- Funções menores e mais focadas
- Tratamento de erros mais específico
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Protocol

from ..dedup_state import DedupState
from ..detail_utils import abs_url, scrape_detail_structured
from ..hash_utils import stable_sha1
from ..log_utils import get_logger

logger = get_logger(__name__)


class BrowserContext(Protocol):
    """Protocolo que define a interface mínima esperada para o contexto do navegador"""
    def new_page(self) -> Any:
        ...


@dataclass
class CascadeParams:
    url: str
    date: str
    secao: str
    query: str | None
    max_links: int
    scrape_detail: bool
    detail_timeout: int
    parallel: int = 1
    summary: bool = False
    summary_lines: int = 5
    summary_mode: str = "center"
    summary_field: str = "resumo"
    advanced_detail: bool = False
    fallback_date_if_missing: bool = True
    dedup_state_file: str | None = None
    summary_keywords: list[str] | None = None


class CascadeService:
    def __init__(self, context: BrowserContext, page, frame,
                 summarize_fn: Callable | None = None):
        self.context = context
        self.page = page
        self.frame = frame
        self.summarize_fn = summarize_fn

    def run(self, raw_items: list[dict[str, Any]], params: CascadeParams) -> dict[str, Any]:
        """
        Executa o processo de cascade completo para os itens fornecidos.
        
        Args:
            raw_items: Lista de dicionários contendo pelo menos 'link'
            params: Parâmetros de configuração do cascade
        
        Returns:
            Dicionário com estatísticas e itens processados
        """
        t0 = time.time()

        # Inicializa estado de deduplicação se necessário
        dedup = DedupState(params.dedup_state_file) if params.dedup_state_file else None

        # Determina o modo de scraping (paralelo ou sequencial)
        if params.scrape_detail and params.parallel > 1:
            # Cap workers to avoid oversubscription that slows down Playwright+CPU
            if params.parallel > 8:
                params.parallel = 8
            detail_items, failures = self._scrape_parallel(raw_items, params, dedup)
        elif params.scrape_detail:
            detail_items, failures = self._scrape_sequential(raw_items, params, dedup)
        else:
            detail_items, failures = raw_items, 0

        # Adiciona resumos se configurado
        if params.summary and self.summarize_fn and detail_items:
            self._add_summaries(detail_items, params)

        duration = round(time.time() - t0, 2)
        return {
            "stats": {
                "total": len(detail_items),
                "detailFailures": failures,
                "scrapedDetails": bool(params.scrape_detail),
                "parallel": params.parallel,
                "durationSec": duration,
            },
            "itens": detail_items
        }

    def _add_summaries(self, items: list[dict[str, Any]], params: CascadeParams) -> None:
        """Adiciona resumos aos itens"""
        for item in items:
            base_text = item.get("texto") or item.get("ementa") or ""
            if not base_text:
                continue

            try:
                snippet = self._invoke_summarizer(
                    base_text,
                    params.summary_lines,
                    params.summary_mode,
                    params.summary_keywords
                )
                if snippet:
                    item[params.summary_field] = snippet
            except Exception as e:
                logger.warning("Falha ao resumir texto", extra={"err": str(e), "item": item.get("link")})

    def _invoke_summarizer(self, text: str, lines: int, mode: str, keywords: list[str] | None):
        """Invoca a função de resumo com compatibilidade para diferentes assinaturas"""
        if not self.summarize_fn:
            return None
        try:
            return self.summarize_fn(text, lines, mode, keywords)
        except TypeError:
            # Fallback para assinatura reduzida
            logger.debug("Usando assinatura reduzida para summarize_fn")
            return self.summarize_fn(text, lines, mode)

    def _scrape_sequential(self, raw_items: list[dict[str, Any]], params: CascadeParams,
                           dedup: DedupState | None) -> tuple[list, int]:
        """Scraping sequencial de detalhes"""
        out = []
        failures = 0

        for item in raw_items:
            raw_link = item.get("link") or ""
            detail_url = abs_url(self.page.url, raw_link) if raw_link else ""
            fallback_date = params.date if params.fallback_date_if_missing else None

            try:
                # Coleta detalhes estruturados da página
                detail = self._fetch_detail(detail_url, params, fallback_date)

                # Mescla item original com detalhes
                record = {**item, **detail.to_dict()}
                # Garantir detail_url absoluto no item final
                if detail_url:
                    record["detail_url"] = detail_url

                # Calcula hash para deduplicação
                item_hash = record.get("meta", {}).get("hash") or stable_sha1(detail_url)
                record["hash"] = item_hash
                record["data_publicacao_fallback"] = (record.get("meta") or {}).get("data_publicacao_fallback", False)

                # Verifica duplicação se habilitado
                if dedup and dedup.has(item_hash):
                    logger.debug("Item duplicado ignorado", extra={"url": detail_url, "hash": item_hash})
                    continue

                if dedup:
                    dedup.add(item_hash)

                out.append(record)
            except Exception as e:
                failures += 1
                logger.warning("Falha no scrape de detalhes", extra={"url": detail_url, "err": str(e)})

        return out, failures

    def _fetch_detail(self, url: str, params: CascadeParams, fallback_date: str | None = None):
        """Abstrai o processo de fetch de detalhes para reuso"""
        return scrape_detail_structured(
            self.context,
            url,
            timeout_ms=params.detail_timeout,
            advanced=params.advanced_detail,
            fallback_date=fallback_date,
            compute_hash=True
        )

    def _scrape_parallel(self, raw_items: list[dict[str, Any]], params: CascadeParams,
                          dedup: DedupState | None) -> tuple[list, int]:
        """Scraping paralelo de detalhes"""
        out = []
        failures = 0
        item_count = len(raw_items)

        # Reduz workers para não sobrecarregar o browser
        effective_workers = min(params.parallel, item_count, 10)

        if effective_workers < params.parallel:
            logger.info(f"Ajustando workers para {effective_workers} (original: {params.parallel})")

        def _job(item):
            raw_link = item.get("link") or ""
            detail_url = abs_url(self.page.url, raw_link) if raw_link else ""
            fallback_date = params.date if params.fallback_date_if_missing else None

            detail = self._fetch_detail(detail_url, params, fallback_date)
            record = {**item, **detail.to_dict()}
            if detail_url:
                record["detail_url"] = detail_url

            h = record.get("meta", {}).get("hash") or stable_sha1(detail_url)
            record["hash"] = h
            record["data_publicacao_fallback"] = (record.get("meta") or {}).get("data_publicacao_fallback", False)

            return record

        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
            futures = [pool.submit(_job, item) for item in raw_items]

            for fut in as_completed(futures):
                try:
                    rec = fut.result()
                    item_hash = rec.get("hash")

                    if dedup and item_hash and dedup.has(item_hash):
                        continue

                    if dedup and item_hash:
                        dedup.add(item_hash)

                    out.append(rec)
                except Exception as e:
                    failures += 1
                    logger.warning("Falha em detalhes paralelos", extra={"err": str(e)})

        return out, failures
