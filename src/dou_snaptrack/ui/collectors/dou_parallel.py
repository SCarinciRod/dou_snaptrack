"""
DOU Parallel Batch Collector - Single Browser Mode

Baseado no modelo de sucesso do eagendas_collect_parallel.py:
- Um único browser com múltiplos contexts (4 workers ótimo)
- Async/await com asyncio.run() 
- Subprocess independente para evitar conflitos com event loop

Performance comparada (16 jobs):
- Multi-browser (batch atual): ~85-100s
- Single browser async (4w): ~40s (2x mais rápido)

Recebe via variável de ambiente INPUT_JSON_PATH ou stdin:
{
    "jobs": [...],
    "max_workers": 4,
    "defaults": {...},
    "out_dir": "path",
    "out_pattern": "{topic}_{secao}_{date}_{idx}.json"
}

Escreve resultado em RESULT_JSON_PATH.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Constantes otimizadas baseadas em testes
DEFAULT_WORKERS = 4  # Ótimo baseado em benchmarks (16 jobs em ~40s)
GOTO_TIMEOUT = 60000
SELECT_TIMEOUT = 30000
REPOP_WAIT_MS = 2000
CONTENT_TIMEOUT = 10000


@dataclass
class JobResult:
    """Resultado de um job individual."""
    job_id: str
    job_index: int
    success: bool
    items: list[dict] = field(default_factory=list)
    elapsed: float = 0.0
    error: str | None = None
    timings: dict = field(default_factory=dict)
    
    # Metadata para output file
    date: str = ""
    secao: str = ""
    key1: str = ""
    key2: str = ""
    topic: str = ""


def _write_result(data: dict) -> None:
    """Write result to RESULT_JSON_PATH file (subprocess contract)."""
    result_path = os.environ.get("RESULT_JSON_PATH")
    if result_path:
        Path(result_path).parent.mkdir(parents=True, exist_ok=True)
        Path(result_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(data, ensure_ascii=False))


def _log(msg: str, level: str = "INFO") -> None:
    """Log message to stderr (não interfere com resultado JSON)."""
    print(f"[{level}] {msg}", file=sys.stderr, flush=True)


async def collect_dou_job(
    page,
    job: dict,
    job_index: int,
    worker_id: int,
    defaults: dict
) -> JobResult:
    """
    Coleta links do DOU para um único job usando seletores hierárquicos.
    
    Versão simplificada e otimizada para paralelismo.
    """
    job_id = job.get("id") or job.get("topic") or f"job_{job_index}"
    date_str = job.get("data") or job.get("date") or defaults.get("data", "")
    secao = job.get("secao") or defaults.get("secaoDefault", "DO1")
    key1 = job.get("key1") or ""
    key2 = job.get("key2") or "Todos"
    topic = job.get("topic") or key1
    
    prefix = f"[W{worker_id}]"
    start = time.perf_counter()
    timings = {}
    
    result = JobResult(
        job_id=job_id,
        job_index=job_index,
        success=False,
        date=date_str,
        secao=secao,
        key1=key1,
        key2=key2,
        topic=topic
    )
    
    try:
        # Navegar para página do DOU
        url = f"https://www.in.gov.br/leiturajornal?data={date_str}&secao={secao}"
        _log(f"{prefix} [{job_id}] Navegando para {url}", "DEBUG")
        
        t0 = time.perf_counter()
        await page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
        timings["goto"] = round(time.perf_counter() - t0, 2)
        
        # Aguardar dropdowns carregarem
        t0 = time.perf_counter()
        await page.wait_for_selector("select", timeout=SELECT_TIMEOUT)
        timings["wait_select"] = round(time.perf_counter() - t0, 2)
        
        # Encontrar selects
        selects = await page.query_selector_all("select")
        if len(selects) < 1:
            result.error = "Nenhum select encontrado"
            result.elapsed = time.perf_counter() - start
            return result
        
        # Selecionar ministério/órgão
        t0 = time.perf_counter()
        try:
            await page.select_option("select:first-of-type", label=key1, timeout=10000)
        except Exception:
            # Fallback: procurar match parcial
            select1 = selects[0]
            options = await page.evaluate("""(sel) => {
                return Array.from(sel.options).map(o => ({
                    value: o.value, 
                    text: o.textContent.trim()
                }));
            }""", select1)
            
            target = None
            for opt in options:
                if key1.lower() in opt.get("text", "").lower():
                    target = opt
                    break
            
            if not target:
                # Opção não encontrada - retornar sucesso com 0 itens (não é erro fatal)
                _log(f"{prefix} [{job_id}] Opção não encontrada no dropdown: '{key1}' - retornando 0 itens", "WARN")
                result.success = True
                result.items = []
                result.elapsed = round(time.perf_counter() - start, 2)
                result.timings = timings
                return result
            
            await page.select_option("select:first-of-type", value=target["value"], timeout=10000)
        timings["select"] = round(time.perf_counter() - t0, 2)
        
        # Aguardar repopulação
        t0 = time.perf_counter()
        await page.wait_for_timeout(REPOP_WAIT_MS)
        timings["repop_wait"] = round(time.perf_counter() - t0, 2)
        
        # Aguardar conteúdo carregar
        t0 = time.perf_counter()
        try:
            await page.wait_for_selector("a[href*='/web/dou/']", timeout=CONTENT_TIMEOUT)
        except Exception:
            pass  # Pode não ter resultados
        timings["wait_content"] = round(time.perf_counter() - t0, 2)
        
        # Coletar links
        t0 = time.perf_counter()
        items = await page.evaluate("""() => {
            const links = [];
            const seen = new Set();
            const anchors = document.querySelectorAll("a[href*='/web/dou/']");
            
            for (const a of anchors) {
                const href = a.href;
                if (seen.has(href)) continue;
                seen.add(href);
                
                // Extrair título
                const container = a.closest('article, .card, section, div');
                const titleEl = container?.querySelector('.title, .titulo, h2, h3, h4');
                const title = titleEl?.textContent?.trim() || a.textContent?.trim() || '';
                
                links.push({
                    link: href,
                    titulo: title,
                    detail_url: href
                });
            }
            
            return links;
        }""")
        timings["collect"] = round(time.perf_counter() - t0, 2)
        
        result.success = True
        result.items = items
        result.timings = timings
        result.elapsed = round(time.perf_counter() - start, 2)
        
        timing_str = " ".join(f"{k}={v:.1f}s" for k, v in timings.items())
        _log(f"{prefix} [{job_id}] ✓ {len(items)} items em {result.elapsed:.1f}s ({timing_str})")
        
    except Exception as e:
        result.error = str(e)
        result.elapsed = round(time.perf_counter() - start, 2)
        result.timings = timings
        _log(f"{prefix} [{job_id}] ✗ {e}", "ERROR")
    
    return result


async def worker_task(
    worker_id: int,
    page,
    jobs_with_indices: list[tuple[int, dict]],
    results: list[JobResult],
    lock: asyncio.Lock,
    defaults: dict
):
    """Worker que processa uma lista de jobs sequencialmente."""
    _log(f"[W{worker_id}] Iniciando com {len(jobs_with_indices)} jobs...")
    
    for job_index, job in jobs_with_indices:
        result = await collect_dou_job(page, job, job_index, worker_id, defaults)
        async with lock:
            results.append(result)
    
    _log(f"[W{worker_id}] Finalizado")


def distribute_jobs(jobs_with_indices: list[tuple[int, dict]], num_workers: int) -> list[list[tuple[int, dict]]]:
    """Distribui jobs entre workers de forma round-robin para balanceamento."""
    worker_queues: list[list[tuple[int, dict]]] = [[] for _ in range(num_workers)]
    
    for i, item in enumerate(jobs_with_indices):
        worker_idx = i % num_workers
        worker_queues[worker_idx].append(item)
    
    return worker_queues


async def main_async(input_data: dict) -> dict:
    """Função principal assíncrona."""
    from playwright.async_api import async_playwright
    from .dou_helpers import (
        launch_browser_with_channels,
        create_worker_contexts,
        cleanup_browser_resources,
        calculate_statistics,
        log_final_results,
        save_job_outputs,
        build_final_result,
    )
    
    start_time = time.perf_counter()
    
    jobs = input_data.get("jobs", [])
    max_workers = input_data.get("max_workers", DEFAULT_WORKERS)
    defaults = input_data.get("defaults", {})
    out_dir = input_data.get("out_dir")
    out_pattern = input_data.get("out_pattern", "{topic}_{secao}_{date}_{idx}.json")
    
    if not jobs:
        return {"success": False, "error": "Nenhum job fornecido", "ok": 0, "fail": 0}
    
    actual_workers = min(max_workers, len(jobs))
    
    _log(f"{'='*60}")
    _log("DOU PARALLEL COLLECTOR (Single Browser Async)")
    _log(f"{'='*60}")
    _log(f"Jobs: {len(jobs)}, Workers: {actual_workers}")
    _log(f"{'='*60}")
    
    results: list[JobResult] = []
    lock = asyncio.Lock()
    
    async with async_playwright() as p:
        # Launch browser
        prefer_edge = os.environ.get("DOU_PREFER_EDGE", "").lower() in ("1", "true", "yes")
        browser = await launch_browser_with_channels(p, prefer_edge, _log)
        
        if not browser:
            return {"success": False, "error": "Nenhum browser disponível", "ok": 0, "fail": 0}
        
        # Create contexts and pages for workers
        contexts, pages = await create_worker_contexts(browser, actual_workers, GOTO_TIMEOUT)
        _log(f"✓ {actual_workers} contexts criados")
        
        # Create job list with indices
        jobs_with_indices = [(i + 1, job) for i, job in enumerate(jobs)]
        worker_queues = distribute_jobs(jobs_with_indices, actual_workers)
        
        # Create and execute tasks in parallel
        tasks = []
        for i, worker_jobs in enumerate(worker_queues):
            if worker_jobs:
                task = asyncio.create_task(
                    worker_task(
                        worker_id=i + 1,
                        page=pages[i],
                        jobs_with_indices=worker_jobs,
                        results=results,
                        lock=lock,
                        defaults=defaults
                    )
                )
                tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Cleanup
        await cleanup_browser_resources(contexts, browser)
    
    elapsed = time.perf_counter() - start_time
    
    # Calculate statistics and log results
    stats = calculate_statistics(results)
    log_final_results(stats, len(jobs), elapsed, _log)
    
    # Save outputs if directory provided
    outputs = []
    if out_dir:
        outputs = save_job_outputs(stats["successful"], out_dir, out_pattern)
    
    # Build and return final result
    return build_final_result(stats, outputs, elapsed)


def run_parallel_batch(input_data: dict) -> dict:
    """
    Entry point síncrono para rodar batch paralelo com browser único.
    
    Args:
        input_data: Dict com jobs, defaults, out_dir, out_pattern, max_workers
        
    Returns:
        Dict com ok, fail, items_total, outputs, metrics
    """
    import io
    
    # Garantir encoding UTF-8
    if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    try:
        return asyncio.run(main_async(input_data))
    except RuntimeError as e:
        # asyncio.run() raises RuntimeError if there's already a running event loop
        if "cannot be called from a running event loop" in str(e).lower() or "event loop" in str(e).lower():
            # Propagar para que o batch.py use o subprocess fallback
            raise
        # Outro RuntimeError, tentar retornar erro
        import traceback
        _log(f"Erro fatal (RuntimeError): {e}", "ERROR")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "ok": 0,
            "fail": len(input_data.get("jobs", [])),
            "items_total": 0,
            "outputs": []
        }
    except Exception as e:
        import traceback
        _log(f"Erro fatal: {e}", "ERROR")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "ok": 0,
            "fail": len(input_data.get("jobs", [])),
            "items_total": 0,
            "outputs": []
        }


def main():
    """Entry point para execução via subprocess."""
    import io
    
    # Garantir encoding UTF-8
    if sys.stdin.encoding != 'utf-8':
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    try:
        # Ler input
        input_file = os.environ.get("INPUT_JSON_PATH")
        if input_file and Path(input_file).exists():
            input_data = json.loads(Path(input_file).read_text(encoding="utf-8-sig"))
        else:
            input_data = json.loads(sys.stdin.read())
        
        result = asyncio.run(main_async(input_data))
        # Consider execução parcialmente bem-sucedida como exit 0 se houver itens
        exit_code = 0 if (result.get("success") or result.get("ok", 0) > 0) else 1
        _write_result(result)
        return exit_code
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        _write_result({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "ok": 0,
            "fail": 0
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
