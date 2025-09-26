#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cascade modular com expansão dinâmica de N2.

Fluxos suportados:
1) Modo estático tradicional (combos já possuem key1+key2 [+key3]).
2) Modo dynamic N2:
   - batchConfig traz apenas N1 (e opcionalmente flag "_dynamicN2": true)
   - Durante a execução cada N1 é selecionado e o script coleta as opções reais de N2
     (filtrando sentinelas) e gera subresultados separados.

Principais flags adicionais:
  --keep-sentinels      (não filtra combos sentinela)
  --sentinel-regex      (regex extra para detectar sentinelas)
  --debug-combos        (loga combos antes/depois filtro)
"""

from __future__ import annotations
import argparse
import asyncio
import json
import re
import inspect
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Union

from playwright.async_api import async_playwright, Page, Frame, Playwright, Browser, BrowserContext

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------
try:
    from dou_utils.log_utils import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)
logger = get_logger(__name__)

# ------------------------------------------------------------------
# Selection utilities
# ------------------------------------------------------------------
try:
    from dou_utils.selection_utils import select_level, is_sentinel as su_is_sentinel
except ImportError:
    # Implementação fallback para select_level
    async def select_level(frame: Frame, level: int, value: Optional[str], label: Optional[str],
                           wait_ms: int = 300, logger=None, selector: str = "select",
                           sentinel_regex: Optional[str] = None) -> bool:
        if logger:
            logger.warning(f"Fallback select_level em uso para nível {level} (instale selection_utils).")
        return True
    
    # Implementação fallback para is_sentinel
    def su_is_sentinel(value: Optional[str], label: Optional[str], extra_pattern=None) -> bool:
        value_lower = (value or "").strip().lower()
        label_lower = (label or "").strip().lower()
        
        if not value_lower and not label_lower:
            return True
            
        if value_lower.startswith("selecionar ") or label_lower.startswith("selecionar "):
            return True
            
        if extra_pattern and (re.search(extra_pattern, value_lower) or re.search(extra_pattern, label_lower)):
            return True
            
        return False

# ------------------------------------------------------------------
# Detail utils
# ------------------------------------------------------------------
try:
    from dou_utils.detail_utils import scrape_detail as real_scrape_detail
except ImportError:
    logger.warning("Fallback scrape_detail será usado (instale detail_utils para funcionalidade completa)")
    async def real_scrape_detail(page: Page, url: str, **kwargs) -> Dict[str, Any]:
        """Implementação fallback mínima para scrape_detail."""
        return {"url": url, "content": "(detail not implemented)", "fallback": True}

# ------------------------------------------------------------------
# Batch config loaders
# ------------------------------------------------------------------
try:
    from dou_utils.batch_utils import load_batch_config, expand_batch_config as expand_jobs_modern
    MODERN_EXPAND = True
except ImportError:
    logger.warning("Usando implementação fallback para batch_utils (funcionalidade limitada)")
    MODERN_EXPAND = False
    
    def load_batch_config(path: str | Path) -> Dict[str, Any]:
        """Carrega configuração de batch de um arquivo JSON."""
        return json.loads(Path(path).read_text(encoding="utf-8"))
    
    def expand_jobs_modern(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback mínimo para expansão de jobs."""
        combos = cfg.get("combos") or []
        out = []
        for i, c in enumerate(combos, 1):
            merged = dict(c)
            merged["_combo_index"] = i
            out.append(merged)
        return out

# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------
@dataclass
class CascadeConfig:
    """Configuração para execução de cascade."""
    mode_batch: bool = False
    batch_config: Optional[str] = None
    out: Optional[str] = None
    out_pattern: Optional[str] = None
    data: Optional[str] = None
    secao: Optional[str] = None
    query: Optional[str] = None
    scrape_detail: bool = False
    max_links: Optional[int] = None
    summary: bool = False
    summary_advanced: bool = False
    summary_keywords: Optional[str] = None
    reuse_page: bool = False
    nav_timeout: int = 60000
    headful: bool = False
    slow_mo: int = 0
    dropdown_selector: str = "select"
    accept_consent: bool = False
    keep_sentinels: bool = False
    sentinel_regex: Optional[str] = None
    debug_combos: bool = False
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "CascadeConfig":
        """Cria uma instância de CascadeConfig a partir dos argumentos da linha de comando."""
        return cls(
            mode_batch=args.batch_config is not None,
            batch_config=args.batch_config,
            out=args.out,
            out_pattern=args.out_pattern,
            data=args.data,
            secao=args.secao,
            query=args.query,
            scrape_detail=args.scrape_detail,
            max_links=args.max_links,
            summary=args.summary,
            summary_advanced=args.summary_advanced,
            summary_keywords=args.summary_keywords,
            reuse_page=args.reuse_page,
            nav_timeout=args.nav_timeout,
            headful=args.headful,
            slow_mo=args.slow_mo,
            dropdown_selector=args.dropdown_selector,
            accept_consent=args.accept_consent,
            keep_sentinels=args.keep_sentinels,
            sentinel_regex=args.sentinel_regex,
            debug_combos=args.debug_combos
        )


@dataclass
class JobParams:
    """Parâmetros de um job."""
    key1: Optional[str] = None
    key2: Optional[str] = None
    key3: Optional[str] = None
    label1: Optional[str] = None
    label2: Optional[str] = None
    label3: Optional[str] = None
    dynamic_n2: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobParams":
        """Cria uma instância de JobParams a partir de um dicionário."""
        return cls(
            key1=data.get("key1"),
            key2=data.get("key2"),
            key3=data.get("key3"),
            label1=data.get("label1"),
            label2=data.get("label2"),
            label3=data.get("label3"),
            dynamic_n2=bool(data.get("_dynamicN2"))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        result = {}
        for key, value in asdict(self).items():
            if key != "dynamic_n2" and value is not None:
                result[key] = value
        if self.dynamic_n2:
            result["_dynamicN2"] = True
        return result


@dataclass
class BaseParams:
    """Parâmetros base para execução de cascade."""
    run_id: str
    data: Optional[str] = None
    secao: Optional[str] = None
    query: Optional[str] = None
    
    @classmethod
    def create_default(cls, data: Optional[str] = None, secao: Optional[str] = None, 
                      query: Optional[str] = None) -> "BaseParams":
        """Cria parâmetros base padrão com ID de execução único."""
        return cls(
            run_id=datetime.now().strftime("%Y%m%dT%H%M%SZ"),
            data=data,
            secao=secao,
            query=query
        )


@dataclass
class JobResult:
    """Resultado de um job de cascade."""
    schema: Dict[str, Any]
    run_id: str
    generated_at: str
    params: Dict[str, Any]
    items: List[Dict[str, Any]]
    stats: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário no formato esperado para salvar em arquivo."""
        return {
            "schema": self.schema,
            "runId": self.run_id,
            "generatedAt": self.generated_at,
            "params": self.params,
            "itens": self.items,
            "stats": self.stats
        }


class CascadeJobProcessor:
    """Processador de jobs de cascade."""
    
    def __init__(self, config: CascadeConfig):
        self.config = config
        self.summary_keywords_list = self._parse_summary_keywords()
    
    def _parse_summary_keywords(self) -> Optional[List[str]]:
        """Converte a string de keywords em uma lista."""
        if not self.config.summary_keywords:
            return None
        return [k.strip() for k in self.config.summary_keywords.split(";") if k.strip()]
    
    async def process_job(self, page: Page, base_params: BaseParams, 
                         job_params: JobParams) -> List[JobResult]:
        """
        Processa um job e retorna os resultados.
        
        No modo estático, retorna uma lista com um único resultado.
        No modo dinâmico, retorna uma lista com múltiplos resultados (um por N2).
        """
        frame = page.main_frame
        
        # Seleciona N1
        if job_params.key1 is not None or job_params.label1 is not None:
            await select_level(
                frame, 1, job_params.key1, job_params.label1,
                logger=logger, selector=self.config.dropdown_selector,
                sentinel_regex=self.config.sentinel_regex
            )
        
        # Modo dinâmico: expandir N2 agora
        if job_params.dynamic_n2 or (job_params.key2 is None and job_params.label2 is None):
            return await self._process_dynamic_n2(page, frame, base_params, job_params)
        
        # Modo estático: usar key2 fornecido
        return await self._process_static(page, frame, base_params, job_params)
    
    async def _process_dynamic_n2(self, page: Page, frame: Frame, 
                                 base_params: BaseParams, 
                                 job_params: JobParams) -> List[JobResult]:
        """Processa um job no modo dinâmico (N2 expandido durante a execução)."""
        n2_options = await self._collect_level2_options(frame)
        
        logger.info(f"Dynamic N2: encontrados {len(n2_options)} options para N1={job_params.label1 or job_params.key1}")
        
        results: List[JobResult] = []
        for n2_option in n2_options:
            # Seleciona N2
            await select_level(
                frame, 2, n2_option["value"], n2_option["text"],
                logger=logger, selector=self.config.dropdown_selector,
                sentinel_regex=self.config.sentinel_regex
            )
            
            # Tenta aplicar N3 se fornecido
            if job_params.key3 is not None or job_params.label3 is not None:
                await select_level(
                    frame, 3, job_params.key3, job_params.label3,
                    logger=logger, selector=self.config.dropdown_selector,
                    sentinel_regex=self.config.sentinel_regex
                )
            
            # Coleta e processa itens
            items = await self._collect_and_process_items(page, frame, base_params.query)
            
            # Monta parâmetros do combo
            combo_params = {
                "key1": job_params.key1, 
                "label1": job_params.label1,
                "key2": n2_option["value"], 
                "label2": n2_option["text"]
            }
            
            if job_params.key3 is not None or job_params.label3 is not None:
                combo_params.update({"key3": job_params.key3, "label3": job_params.label3})
            
            results.append(self._create_job_result(base_params, combo_params, items))
            
        return results
    
    async def _process_static(self, page: Page, frame: Frame, 
                             base_params: BaseParams, 
                             job_params: JobParams) -> List[JobResult]:
        """Processa um job no modo estático (key2 já fornecido)."""
        # Seleciona N2 se presente
        if job_params.key2 is not None or job_params.label2 is not None:
            await select_level(
                frame, 2, job_params.key2, job_params.label2,
                logger=logger, selector=self.config.dropdown_selector,
                sentinel_regex=self.config.sentinel_regex
            )
        
        # Seleciona N3 se presente
        if job_params.key3 is not None or job_params.label3 is not None:
            await select_level(
                frame, 3, job_params.key3, job_params.label3,
                logger=logger, selector=self.config.dropdown_selector,
                sentinel_regex=self.config.sentinel_regex
            )
        
        # Coleta e processa itens
        items = await self._collect_and_process_items(page, frame, base_params.query)
        
        # Monta parâmetros do combo
        combo_params = {}
        for field, value in [
            ("key1", job_params.key1),
            ("key2", job_params.key2),
            ("key3", job_params.key3),
            ("label1", job_params.label1),
            ("label2", job_params.label2),
            ("label3", job_params.label3)
        ]:
            if value is not None:
                combo_params[field] = value
        
        return [self._create_job_result(base_params, combo_params, items)]
    
    async def _collect_level2_options(self, frame: Frame) -> List[Dict[str, str]]:
        """Coleta as opções do segundo dropdown e filtra sentinelas."""
        sentinel_regex = re.compile(self.config.sentinel_regex, re.IGNORECASE) if self.config.sentinel_regex else None
        
        try:
            dropdowns = await frame.query_selector_all(self.config.dropdown_selector)
            if len(dropdowns) < 2:
                logger.warning("Não foi possível encontrar o segundo dropdown")
                return []
                
            ddl2 = dropdowns[1]
            options = await ddl2.query_selector_all("option")
            
            result = []
            for option in options:
                value = (await option.get_attribute("value")) or ""
                text = (await option.text_content()) or ""
                value = value.strip()
                text = text.strip()
                
                if not text:
                    continue
                    
                if not self.config.keep_sentinels and su_is_sentinel(value, text, sentinel_regex):
                    continue
                    
                result.append({"value": value or text, "text": text})
                
            return result
        except Exception as e:
            logger.error(f"Erro ao coletar opções N2: {e}")
            return []
    
    async def _collect_and_process_items(self, page: Page, frame: Frame, 
                                        query: Optional[str]) -> List[Dict[str, Any]]:
        """Coleta itens da listagem e adiciona detalhes se necessário."""
        listing_items = await self._scrape_listing(frame, query)
        
        if not self.config.scrape_detail:
            return listing_items
            
        enriched_items = []
        for item in listing_items:
            enriched_items.append(
                await self._enrich_with_detail(page, item)
            )
            
        return enriched_items
    
    async def _scrape_listing(self, frame: Frame, query: Optional[str]) -> List[Dict[str, Any]]:
        """Coleta links da listagem atual."""
        try:
            anchors = await frame.query_selector_all("a")
            result = []
            
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if not href or "/" not in href:  # Ignora âncoras vazias ou de navegação
                    continue
                    
                text = (await anchor.text_content() or "").strip()
                if not text:
                    continue
                    
                if query and query.lower() not in text.lower():
                    continue
                    
                result.append({"title": text, "url": href, "meta": {}})
                
                if self.config.max_links and len(result) >= self.config.max_links:
                    break
                    
            return result
        except Exception as e:
            logger.error(f"Erro ao coletar links: {e}")
            return []
    
    async def _enrich_with_detail(self, page: Page, item: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona detalhes a um item da listagem."""
        url = item.get("url")
        if not url:
            return item
            
        try:
            detail = await self._safe_scrape_detail(page, url)
            item["detail"] = detail
        except Exception as e:
            logger.error(f"Erro ao obter detalhes para {url}: {e}")
            item["detail"] = {"error": str(e)}
            
        return item
    
    async def _safe_scrape_detail(self, page: Page, url: str) -> Dict[str, Any]:
        """Wrapper seguro para scrape_detail que lida com diferentes assinaturas."""
        # Prepara os parâmetros aceitos pelo scrape_detail
        parameters = {}
        
        if self.config.summary:
            parameters["summary"] = True
            
        if self.config.summary_advanced:
            parameters["summary_advanced"] = True
            
        if self.summary_keywords_list:
            parameters["summary_keywords"] = self.summary_keywords_list
            
        try:
            # Verifica quais parâmetros a implementação real aceita
            signature = inspect.signature(real_scrape_detail)
            accepted_params = {}
            
            for param_name in signature.parameters:
                if param_name == "page" or param_name == "url":
                    continue
                if param_name in parameters:
                    accepted_params[param_name] = parameters[param_name]
                    
            # Chama a implementação com os parâmetros aceitos
            return await real_scrape_detail(page, url=url, **accepted_params)
            
        except Exception as e:
            logger.warning(f"Erro ao usar scrape_detail: {e}")
            
            # Fallback: tentar navegar para a página e obter o conteúdo
            try:
                new_page = await page.context.new_page()
                await new_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                html = await new_page.content()
                await new_page.close()
                return {
                    "url": url,
                    "rawHtml": html[:20000],  # Limita o tamanho para evitar problemas com memória
                    "fallback": True
                }
            except Exception as e2:
                logger.error(f"Fallback também falhou: {e2}")
                return {"url": url, "error": str(e2), "fallback": True}
    
    def _create_job_result(self, base_params: BaseParams, 
                          combo_params: Dict[str, Any], 
                          items: List[Dict[str, Any]]) -> JobResult:
        """Cria um objeto JobResult a partir dos parâmetros e itens coletados."""
        return JobResult(
            schema={"name": "cascadeResult", "version": "1.0"},
            run_id=base_params.run_id,
            generated_at=datetime.now().isoformat(),
            params={
                "data": base_params.data,
                "secao": base_params.secao,
                "query": base_params.query,
                "combo": combo_params
            },
            items=items,
            stats={
                "total": len(items),
                "detailEnabled": self.config.scrape_detail,
                "summary": self.config.summary,
                "summaryAdvanced": self.config.summary_advanced
            }
        )


class CascadeRunner:
    """Executor principal de cascade."""
    
    def __init__(self, config: CascadeConfig):
        self.config = config
        self.processor = CascadeJobProcessor(config)
    
    async def run(self):
        """Executa o cascade de acordo com a configuração."""
        if self.config.mode_batch:
            await self._run_batch_mode()
        else:
            await self._run_single_mode()
    
    async def _run_batch_mode(self):
        """Executa o cascade em modo batch (múltiplos jobs)."""
        if not self.config.batch_config:
            raise ValueError("Modo batch requer --batch-config.")
            
        # Configura diretório de saída
        out_dir = Path(self.config.out or "artefatos/cascade_batch")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Carrega e prepara os jobs
        batch_config = load_batch_config(self.config.batch_config)
        jobs = expand_jobs_modern(batch_config)
        jobs = self._filter_jobs(jobs)
        
        if not jobs:
            logger.warning("Nenhum job após filtragem.")
            return
        
        # Parâmetros base
        base_params = BaseParams.create_default(
            data=batch_config.get("data"),
            secao=batch_config.get("secaoDefault") or "DO1",
            query=batch_config.get("query")
        )
        
        logger.info(f"Jobs finais (lógicos): {len(jobs)}")
        
        # Executa os jobs
        async with self._create_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=not self.config.headful,
                slow_mo=self.config.slow_mo if self.config.headful else 0
            )
            
            shared_page = None
            if self.config.reuse_page:
                shared_page = await browser.new_page()
                await self._navigate_to_base(shared_page, base_params.data, base_params.secao)
            
            for idx, job_dict in enumerate(jobs, 1):
                page = shared_page or await browser.new_page()
                
                if not shared_page:
                    await self._navigate_to_base(page, base_params.data, base_params.secao)
                
                job_params = JobParams.from_dict(job_dict)
                
                try:
                    results = await self.processor.process_job(page, base_params, job_params)
                except Exception as e:
                    logger.exception(f"Erro job lógico {idx}: {e}")
                    if not shared_page:
                        await page.close()
                    continue
                
                # Salva os resultados
                for subidx, result in enumerate(results, 1):
                    out_path = self._compute_output_path(
                        result.params.get("combo", {}), 
                        out_dir, 
                        self.config.out_pattern, 
                        idx, 
                        subidx if len(results) > 1 else None
                    )
                    self._write_job_result(result, out_path)
                
                if not shared_page:
                    await page.close()
            
            if shared_page:
                await shared_page.close()
                
            if self.config.headful:
                logger.info("Execução completa. Pausa final de 5s (headful mode)")
                await asyncio.sleep(5)
                
        logger.info("Batch cascade completo.")
    
    async def _run_single_mode(self):
        """Executa o cascade em modo single (job único)."""
        if not self.config.data or not self.config.secao:
            raise ValueError("Modo single requer --data e --secao.")
            
        out_file = Path(self.config.out or "artefatos/cascade_single.json")
        base_params = BaseParams.create_default(
            data=self.config.data,
            secao=self.config.secao,
            query=self.config.query
        )
        
        async with self._create_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=not self.config.headful,
                slow_mo=self.config.slow_mo if self.config.headful else 0
            )
            
            page = await browser.new_page()
            await self._navigate_to_base(page, base_params.data, base_params.secao)
            
            # No modo single, usamos um job vazio
            job_params = JobParams()
            
            try:
                results = await self.processor.process_job(page, base_params, job_params)
                if results:
                    self._write_job_result(results[0], out_file)
            except Exception as e:
                logger.exception(f"Erro no job single: {e}")
            
            if self.config.headful:
                logger.info("Pausa 4s (headful).")
                await asyncio.sleep(4)
                
        logger.info("Single cascade completo.")
    
    def _filter_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra jobs inválidos ou sentinelas."""
        if self.config.debug_combos:
            logger.info(f"Combos originais: {len(jobs)}")
            
        if self.config.keep_sentinels:
            return jobs
            
        sentinel_regex = re.compile(self.config.sentinel_regex, re.IGNORECASE) if self.config.sentinel_regex else None
        filtered_jobs = []
        removed_count = 0
        
        for job in jobs:
            if self._is_sentinel_job(job, sentinel_regex):
                removed_count += 1
                continue
            filtered_jobs.append(job)
            
        if removed_count > 0:
            logger.info(f"Removidos {removed_count} combos sentinela/placeholder.")
            
        if self.config.debug_combos:
            logger.info(f"Combos após filtro: {len(filtered_jobs)}")
            
        return filtered_jobs
    
    def _is_sentinel_job(self, job: Dict[str, Any], sentinel_regex: Optional[re.Pattern]) -> bool:
        """Verifica se um job contém valores sentinela."""
        for key_field, label_field in [("key1", "label1"), ("key2", "label2"), ("key3", "label3")]:
            if su_is_sentinel(job.get(key_field), job.get(label_field), sentinel_regex):
                return True
        return False
    
    async def _navigate_to_base(self, page: Page, data: Optional[str], secao: Optional[str]):
        """Navega para a página base do DOU."""
        if not data or not secao:
            logger.warning("Data ou seção não especificadas para navegação")
            return
            
        url = f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
        logger.info(f"[Navegando] {url}")
        
        # Tenta até 3 vezes com retry
        for attempt in range(1, 4):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.config.nav_timeout)
                break
            except Exception as e:
                if attempt < 3:
                    logger.warning(f"Tentativa {attempt} falhou: {e}")
                    await asyncio.sleep(2 * attempt)  # Backoff exponencial
                else:
                    logger.error(f"Falha na navegação após {attempt} tentativas: {e}")
                    raise
        
        # Aceita consentimento se configurado
        if self.config.accept_consent:
            await self._accept_consent(page)
    
    async def _accept_consent(self, page: Page):
        """Aceita o banner de consentimento se presente."""
        try:
            consent_selectors = [
                "button:has-text('Aceitar')", 
                "button:has-text('Aceito')", 
                "button:has-text('Concordo')",
                "button:has-text('Ok')",
                "button:has-text('Entendi')"
            ]
            
            for selector in consent_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(400)
                        logger.info("Banner de consentimento aceito.")
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Erro ao processar consentimento: {e}")
    
    async def _create_playwright(self) -> Playwright:
        """Cria e configura uma instância do Playwright."""
        return await async_playwright().start()
    
    def _compute_output_path(self, job: Dict[str, Any], out_dir: Path, pattern: Optional[str], 
                            index: int, subindex: Optional[int] = None) -> Path:
        """Calcula o caminho de saída para um resultado de job."""
        name = pattern or "{_job_index}_{key1}_{key2}"
        
        # Substituições básicas
        for token in ("key1", "key2", "key3"):
            placeholder = "{" + token + "}"
            if placeholder in name:
                value = sanitize_filename(str(job.get(token) or "NA"))
                name = name.replace(placeholder, value)
        
        # job index
        name = name.replace("{_job_index}", str(index))
        
        # subindex para multiple results
        if "{_sub}" in name:
            sub_value = str(subindex) if subindex is not None else "0"
            name = name.replace("{_sub}", sub_value)
        elif subindex is not None:
            # Se não houver placeholder, anexa _sub se aplicável
            stem, dot, ext = name.partition(".json")
            name = f"{stem}_{subindex}.json" if dot else f"{stem}_{subindex}"
        
        if not name.endswith(".json"):
            name += ".json"
            
        return out_dir / name
    
    def _write_job_result(self, result: JobResult, out_file: Path):
        """Escreve um resultado de job em um arquivo JSON."""
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"[OUT] {out_file}")


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Sanitiza um nome de arquivo para uso em caminhos de arquivo."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", name)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    if not cleaned:
        cleaned = "out"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def create_arg_parser() -> argparse.ArgumentParser:
    """Cria e configura o parser de argumentos."""
    parser = argparse.ArgumentParser(description="Cascade modular com expansão dinâmica de N2.")
    parser.add_argument("--batch-config", help="Arquivo de configuração de batch")
    parser.add_argument("--out", help="Arquivo de saída (modo single) ou diretório (modo batch)")
    parser.add_argument("--out-pattern", help="Padrão para nomes de arquivos de saída em modo batch")
    parser.add_argument("--data", help="Data no formato DD-MM-AAAA")
    parser.add_argument("--secao", help="Seção do DOU (ex: DO1)")
    parser.add_argument("--query", help="Filtro de busca")
    parser.add_argument("--scrape-detail", action="store_true", help="Habilita scraping de detalhe")
    parser.add_argument("--max-links", type=int, help="Máx. links (listing) por job.")
    parser.add_argument("--summary", action="store_true", help="Habilita geração de resumo")
    parser.add_argument("--summary-advanced", action="store_true", help="Habilita resumo avançado")
    parser.add_argument("--summary-keywords", help="Keywords para resumo (separadas por ;)")
    parser.add_argument("--reuse-page", action="store_
