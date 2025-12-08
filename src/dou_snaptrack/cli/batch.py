from __future__ import annotations

import contextlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..constants import TIMEOUT_PAGE_DEFAULT, TIMEOUT_SUBPROCESS_LONG
from ..utils.text import sanitize_filename
from .summary_config import SummaryConfig, apply_summary_overrides_from_job


def render_out_filename(pattern: str, job: dict[str, Any]) -> str:
    date_str = job.get("data") or ""
    tokens = {
        "topic": job.get("topic") or "job",
        "secao": job.get("secao") or "DO",
        "date": (date_str or "").replace("/", "-"),
        "idx": str(job.get("_combo_index") or job.get("_job_index") or ""),
        "rep": str(job.get("_repeat") or ""),
        "key1": job.get("key1") or "",
        "key2": job.get("key2") or "",
        "key3": job.get("key3") or "",
    }
    name = pattern
    for k, v in tokens.items():
        name = name.replace("{" + k + "}", sanitize_filename(str(v)))
    return name


def expand_batch_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    defaults = cfg.get("defaults", {})
    base_data = cfg.get("data")
    base_secao = cfg.get("secaoDefault")

    def merge_defaults(job):
        out = dict(defaults)
        out.update(job or {})
        return out

    if cfg.get("jobs"):
        for j in cfg["jobs"]:
            jj = merge_defaults(j)
            if base_data and not jj.get("data"):
                jj["data"] = base_data
            if base_secao and not jj.get("secao"):
                jj["secao"] = base_secao
            rep = max(1, int(jj.get("repeat", cfg.get("repeat", 1))))
            for r in range(1, rep + 1):
                jj_r = dict(jj)
                jj_r["_repeat"] = r
                jobs.append(jj_r)

    topics = cfg.get("topics") or []
    combos = cfg.get("combos") or []
    if topics and combos:
        for t in topics:
            topic_name = t.get("name") or "topic"
            topic_query = t.get("query") or ""
            topic_repeat = int(t.get("repeat", cfg.get("repeat", 1)))
            t_summary_kws = t.get("summary_keywords")
            t_summary_lines = t.get("summary_lines", (defaults.get("summary_lines") if isinstance(defaults, dict) else None))
            t_summary_mode = t.get("summary_mode", (defaults.get("summary_mode") if isinstance(defaults, dict) else None))
            for idx, c in enumerate(combos, 1):
                jj = merge_defaults(c)
                if base_data and not jj.get("data"):
                    jj["data"] = base_data
                if base_secao and not jj.get("secao"):
                    jj["secao"] = base_secao
                jj["topic"] = topic_name
                jj["query"] = jj.get("query", topic_query)
                jj["_combo_index"] = idx
                if t_summary_kws is not None:
                    jj["summary_keywords"] = t_summary_kws
                if t_summary_lines is not None:
                    jj["summary_lines"] = t_summary_lines
                if t_summary_mode is not None:
                    jj["summary_mode"] = t_summary_mode
                rep = max(1, int(jj.get("repeat", topic_repeat)))
                for r in range(1, rep + 1):
                    jj_r = dict(jj)
                    jj_r["_repeat"] = r
                    jobs.append(jj_r)

    if not topics and combos:
        for idx, c in enumerate(combos, 1):
            jj = merge_defaults(c)
            if base_data and not jj.get("data"):
                jj["data"] = base_data
            if base_secao and not jj.get("secao"):
                jj["secao"] = base_secao
            jj["topic"] = jj.get("topic") or f"job{idx}"
            jj["query"] = jj.get("query", defaults.get("query", "") if isinstance(defaults, dict) else "")
            jj["_combo_index"] = idx
            rep = max(1, int(jj.get("repeat", cfg.get("repeat", 1))))
            for r in range(1, rep + 1):
                jj_r = dict(jj)
                jj_r["_repeat"] = r
                jobs.append(jj_r)

    return jobs


def _worker_process(payload: dict[str, Any]) -> dict[str, Any]:
    """Process-based worker to avoid Playwright sync threading issues."""
    # Ajuste de loop asyncio no Windows antes de importar Playwright (subprocess)
    try:
        import asyncio as _asyncio
        import sys as _sys
        if _sys.platform.startswith("win"):
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
            _asyncio.set_event_loop(_asyncio.new_event_loop())
    except Exception:
        pass
    # Optional log redirection: write worker prints to a shared log file
    _log_fp = None
    try:
        log_file = payload.get("log_file")
        # Evitar redirecionar stdout quando rodando inline (thread) no processo principal
        import multiprocessing as _mp
        is_main_proc = (_mp.current_process().name == "MainProcess")
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            _log_fp = open(log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - keep handle open for worker lifetime
            if not is_main_proc:
                sys.stdout = _log_fp  # type: ignore
                sys.stderr = _log_fp  # type: ignore
            print(f"[Worker {os.getpid()}] logging to {log_file}")
    except Exception:
        _log_fp = None
    # Defer heavy imports until after stdout is redirected
    from playwright.sync_api import sync_playwright  # type: ignore

    from .runner import run_once
    jobs: list[dict[str, Any]] = payload["jobs"]
    defaults: dict[str, Any] = payload["defaults"]
    out_dir = Path(payload["out_dir"])  # already exists
    out_pattern: str = payload["out_pattern"]
    headful: bool = bool(payload.get("headful", False))
    slowmo: int = int(payload.get("slowmo", 0))
    state_file: str | None = payload.get("state_file")
    reuse_page: bool = bool(payload.get("reuse_page", False))
    summary: SummaryConfig = SummaryConfig(**(payload.get("summary") or {}))
    indices: list[int] = payload["indices"]

    def _get(job, key, default_key=None, default_value=None):
        if default_key is None:
            default_key = key
        return job.get(key, defaults.get(default_key, default_value))

    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": [], "metrics": {"jobs": [], "summary": {}}}

    with sync_playwright() as p:
        # Prefer system Chrome/Edge (order can respect DOU_PREFER_EDGE) to avoid downloads (faster startup)
        prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1","true","yes")
        channels = ("msedge","chrome") if prefer_edge else ("chrome","msedge")
        browser = None
        launch_opts = {
            "headless": not headful,
            "slow_mo": slowmo,
            "args": [
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-features=Translate,BackForwardCache",
            ],
        }
        for ch in channels:
            try:
                browser = p.chromium.launch(channel=ch, **launch_opts)
                break
            except Exception:
                browser = None
        if browser is None:
            exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
            if not exe:
                for c in (
                    r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                ) if prefer_edge else (
                    r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                ):
                    if Path(c).exists():
                        exe = c
                        break
            if exe:
                try:
                    browser = p.chromium.launch(executable_path=exe, **launch_opts)
                except Exception:
                    browser = p.chromium.launch(**launch_opts)
            else:
                browser = p.chromium.launch(**launch_opts)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1024, "height": 768})
        # Block heavy resources to accelerate navigation and scrolling (keep stylesheets to avoid breaking selectors)
        try:
            def _route_block_heavy(route):
                try:
                    req = route.request
                    rtype = getattr(req, "resource_type", lambda: "")()
                    if rtype in ("image", "media", "font"):
                        return route.abort()
                    url = req.url
                    ul = url.lower()
                    # Block common static heavy types and trackers/analytics
                    if any(ul.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mp3", ".avi", ".mov", ".woff", ".woff2", ".ttf", ".otf")):
                        return route.abort()
                    if any(host in ul for host in ("googletagmanager.com", "google-analytics.com", "doubleclick.net", "hotjar.com", "facebook.com/tr", "stats.g.doubleclick.net")):
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()
            context.route("**/*", _route_block_heavy)
        except Exception:
            pass
        page_cache: dict[tuple[str, str], Any] = {}
        fast_mode = (os.environ.get("DOU_FAST_MODE", "").strip() or "0").lower() in ("1","true","yes")
        try:
            for j_idx in indices:
                job = jobs[j_idx - 1]
                start_ts = time.time()
                print(f"\n[PW{os.getpid()}] [Job {j_idx}/{len(jobs)}] {job.get('topic','')}: {job.get('query','')}")
                print(f"[DEBUG] Job {j_idx} start_ts={start_ts:.3f}")
                out_name = render_out_filename(out_pattern, {**job, "_job_index": j_idx})
                out_path = out_dir / out_name

                data = job.get("data")
                secao = job.get("secao", defaults.get("secaoDefault", "DO1"))
                # key1_type/key2_type default to "text" for compatibility with plans that only have key1/key2
                key1_type = job.get("key1_type") or defaults.get("key1_type") or "text"
                key1 = job.get("key1")
                key2_type = job.get("key2_type") or defaults.get("key2_type") or "text"
                key2 = job.get("key2")
                label1 = job.get("label1")
                label2 = job.get("label2")

                max_links = int(_get(job, "max_links", "max_links", 30) or 30)
                do_scrape_detail = bool(_get(job, "scrape_detail", "scrape_detail", True))
                detail_timeout = int(_get(job, "detail_timeout", "detail_timeout", 60_000) or 60_000)
                fallback_date = bool(_get(job, "fallback_date_if_missing", "fallback_date_if_missing", True))

                # Leaner defaults to reduce scrolling effort; fast-mode can cut further
                max_scrolls = int(_get(job, "max_scrolls", "max_scrolls", 20) or 20)
                scroll_pause_ms = int(_get(job, "scroll_pause_ms", "scroll_pause_ms", 150) or 150)
                stable_rounds = int(_get(job, "stable_rounds", "stable_rounds", 1) or 1)
                if fast_mode:
                    max_scrolls = min(max_scrolls, 15)
                    scroll_pause_ms = min(scroll_pause_ms, 150)
                    stable_rounds = min(stable_rounds, 1)
                    do_scrape_detail = False
                detail_parallel = int(_get(job, "detail_parallel", "detail_parallel", 1) or 1)

                bulletin = job.get("bulletin") or defaults.get("bulletin")
                bulletin_out_pat = job.get("bulletin_out") or defaults.get("bulletin_out") or None
                if fast_mode:
                    bulletin = None
                    bulletin_out_pat = None
                bulletin_out = str(out_dir / render_out_filename(bulletin_out_pat, {**job, "_job_index": j_idx})) if (bulletin and bulletin_out_pat) else None

                if not key1 or not key1_type or not key2 or not key2_type:
                    print(f"[FAIL] Job {j_idx}: parâmetros faltando (key1/key2)")
                    report["fail"] += 1
                    continue

                # Per-job summary overrides
                s_cfg = apply_summary_overrides_from_job(summary, job)

                # Optional page reuse per (date, secao)
                page = None
                keep_open = False
                if reuse_page:
                    k = (str(data), str(secao))
                    page = page_cache.get(k)
                    if page is None:
                        page = context.new_page()
                        page.set_default_timeout(TIMEOUT_PAGE_DEFAULT)
                        page.set_default_navigation_timeout(TIMEOUT_PAGE_DEFAULT)
                        page_cache[k] = page
                    keep_open = True

                def _run_with_retry(
                    cur_page,
                    *,
                    data=data,
                    secao=secao,
                    key1=key1,
                    key1_type=key1_type,
                    key2=key2,
                    key2_type=key2_type,
                    job=job,
                    max_links=max_links,
                    out_path=out_path,
                    do_scrape_detail=do_scrape_detail,
                    detail_timeout=detail_timeout,
                    fallback_date=fallback_date,
                    label1=label1,
                    label2=label2,
                    max_scrolls=max_scrolls,
                    scroll_pause_ms=scroll_pause_ms,
                    stable_rounds=stable_rounds,
                    bulletin=bulletin,
                    bulletin_out=bulletin_out,
                    s_cfg=s_cfg,
                    detail_parallel=detail_parallel,
                    keep_open=keep_open,
                ) -> dict[str, Any] | None:
                    # Single retry path in case of closed page/context issues during reuse
                    for attempt in (1, 2):
                        try:
                            return run_once(
                                context,
                                date=str(data), secao=str(secao),
                                key1=str(key1), key1_type=str(key1_type),
                                key2=str(key2), key2_type=str(key2_type),
                                key3=None, key3_type=None,
                                query=job.get("query", ""), max_links=max_links, out_path=str(out_path),
                                scrape_details=do_scrape_detail, detail_timeout=detail_timeout, fallback_date_if_missing=fallback_date,
                                label1=label1, label2=label2, label3=None,
                                max_scrolls=max_scrolls, scroll_pause_ms=scroll_pause_ms, stable_rounds=stable_rounds,
                                state_file=state_file,
                                bulletin=bulletin, bulletin_out=bulletin_out,
                                summary=SummaryConfig(lines=s_cfg.lines, mode=s_cfg.mode, keywords=s_cfg.keywords),
                                detail_parallel=detail_parallel,
                                page=cur_page, keep_page_open=keep_open,
                            )
                        except Exception:
                            # On first failure, recreate page and retry once
                            if attempt == 1:
                                try:
                                    if reuse_page:
                                        # drop broken page
                                        try:
                                            if cur_page:
                                                cur_page.close()
                                        except Exception:
                                            pass
                                        cur_page = context.new_page()
                                        cur_page.set_default_timeout(TIMEOUT_PAGE_DEFAULT)
                                        cur_page.set_default_navigation_timeout(TIMEOUT_PAGE_DEFAULT)
                                        page_cache[(str(data), str(secao))] = cur_page
                                        continue
                                except Exception:
                                    pass
                            # If retry also fails or not reusing page, raise
                            raise

                try:
                    result = _run_with_retry(page)
                    report["ok"] += 1
                    report["outputs"].append(str(out_path))
                    report["items_total"] += (result.get("total", 0) if isinstance(result, dict) else 0)
                    elapsed = time.time() - start_ts
                    items_count = 0 if not isinstance(result, dict) else result.get('total', 0)
                    print(f"[PW{os.getpid()}] [Job {j_idx}] concluído em {elapsed:.1f}s — itens={items_count}")
                    # DEBUG: Compare wall-clock time vs reported timings
                    try:
                        if isinstance(result, dict):
                            reported_total = result.get("_timings", {}).get("total_sec", 0)
                            if reported_total > 0:
                                diff = abs(elapsed - reported_total)
                                if diff > 5:  # More than 5s difference
                                    print(f"[TIMING WARN] Job {j_idx}: wall-clock={elapsed:.1f}s vs reported={reported_total:.1f}s (diff={diff:.1f}s)")
                    except Exception:
                        pass
                    # Telemetria por job
                    try:
                        timings = (result.get("_timings") or {}) if isinstance(result, dict) else {}
                    except Exception:
                        timings = {}
                    job_metrics = {
                        "job_index": j_idx,
                        "topic": job.get("topic"),
                        "date": str(data),
                        "secao": str(secao),
                        "key1": key1,
                        "key2": key2,
                        "items": (result.get("total", 0) if isinstance(result, dict) else 0),
                        "elapsed_sec": elapsed,
                        "timings": timings,
                    }
                    with contextlib.suppress(Exception):
                        report["metrics"]["jobs"].append(job_metrics)
                except Exception as e:
                    print(f"[FAIL] Job {j_idx}: {e}")
                    report["fail"] += 1

                delay_ms = int(job.get("repeat_delay_ms", defaults.get("repeat_delay_ms", 0)))
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
        finally:
            # Close cached pages
            for p in page_cache.values():
                with contextlib.suppress(Exception):
                    p.close()
            with contextlib.suppress(Exception):
                context.close()
            with contextlib.suppress(Exception):
                browser.close()
    # Ensure file buffer is flushed before returning
    try:
        if _log_fp:
            _log_fp.flush()
    except Exception:
        pass
    return report


def _init_worker(log_file: str | None = None) -> None:
    """Initializer for worker processes to confirm spawn and set basic policy early."""
    try:
        import asyncio as _asyncio
        import os as _os
        import sys as _sys
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        if log_file:
            try:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(f"[Init {_os.getpid()}] worker process spawned\n")
            except Exception:
                pass
    except Exception:
        pass


def _run_fast_async_subprocess(async_input: dict, _log) -> dict:
    """
    Executa o collector async via subprocess (para evitar conflitos de event loop).
    
    Similar ao padrão usado em eagendas_collect_parallel.
    """
    import tempfile
    
    try:
        # Escrever input em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(async_input, f, ensure_ascii=False)
            input_path = f.name
        
        # Escrever resultado em arquivo temporário
        result_path = input_path.replace('.json', '_result.json')
        
        # Encontrar script
        script_path = Path(__file__).parent.parent / "ui" / "dou_collect_parallel.py"
        if not script_path.exists():
            _log(f"[FAST ASYNC SUBPROCESS] Script não encontrado: {script_path}")
            return {"success": False, "error": f"Script não encontrado: {script_path}"}
        
        # Executar subprocess
        env = os.environ.copy()
        env["INPUT_JSON_PATH"] = input_path
        env["RESULT_JSON_PATH"] = result_path
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            capture_output=True,
            timeout=600,  # 10 min timeout
            text=True
        )
        
        # Ler resultado
        if Path(result_path).exists():
            result = json.loads(Path(result_path).read_text(encoding='utf-8'))
        else:
            # Tentar parsear stdout
            try:
                result = json.loads(proc.stdout)
            except Exception:
                result = {"success": False, "error": proc.stderr or "No output"}
        
        # Cleanup
        try:
            Path(input_path).unlink(missing_ok=True)
            Path(result_path).unlink(missing_ok=True)
        except Exception:
            pass
        
        return result
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Subprocess timeout (10 min)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_plan_aggregation(cfg: dict, report: dict, out_dir: Path, _log) -> None:
    """Agregação de outputs por plano (extraída para evitar duplicação)."""
    try:
        plan_name = (cfg.get("plan_name") or (cfg.get("defaults", {}) or {}).get("plan_name") or "").strip()
        if not plan_name:
            return
        
        from collections import defaultdict
        
        def _aggregate_outputs_by_date(paths: list[str], out_dir_p: Path, plan: str) -> list[str]:
            agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"data": "", "secao": "", "plan": plan, "itens": []})
            secao_any = ""
            for pth in paths or []:
                try:
                    data = json.loads(Path(pth).read_text(encoding="utf-8"))
                except Exception:
                    continue
                date = str(data.get("data") or "")
                secao = str(data.get("secao") or "")
                if not agg[date]["data"]:
                    agg[date]["data"] = date
                if not agg[date]["secao"]:
                    agg[date]["secao"] = secao
                if not secao_any and secao:
                    secao_any = secao
                items = data.get("itens", []) or []
                # Normalize detail_url (absolute)
                for it in items:
                    try:
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
                    except Exception:
                        pass
                agg[date]["itens"].extend(items)
            written: list[str] = []
            secao_label = (secao_any or "DO").strip()
            for date, payload in agg.items():
                payload["total"] = len(payload.get("itens", []))
                safe_plan = sanitize_filename(plan)
                date_lab = (date or "").replace("/", "-")
                out_name = f"{safe_plan}_{secao_label}_{date_lab}.json"
                out_path_f = out_dir_p / out_name
                out_path_f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                written.append(str(out_path_f))
            return written

        prev_outputs = list(report.get("outputs", []))
        agg_files = _aggregate_outputs_by_date(prev_outputs, out_dir, plan_name)
        if agg_files:
            deleted = []
            for pth in prev_outputs:
                try:
                    Path(pth).unlink(missing_ok=True)
                    deleted.append(pth)
                except Exception:
                    pass
            report["deleted_outputs"] = deleted
            report["outputs"] = []
            report["aggregated"] = agg_files
            report["aggregated_only"] = True
            # Re-write report with aggregation info
            rep_path = out_dir / (((cfg.get("output", {}) or {}).get("report")) or "batch_report.json")
            rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            _log(f"[AGG] {len(agg_files)} arquivo(s) agregado(s) por plano: {plan_name}; removidos {len(deleted)} JSON(s) individuais")
    except Exception as e:
        _log(f"[AGG][WARN] Falha ao agregar por plano: {e}")


def run_batch(playwright, args, summary: SummaryConfig) -> None:
    """Execute batch processing with optional fast async mode.
    
    This function coordinates batch execution with multiple strategies:
    1. Fast async mode (single browser, multiple contexts) - fastest
    2. Multi-browser fallback modes (subprocess, thread, or process pool)
    
    Args:
        playwright: Playwright instance (may be unused if fast async succeeds)
        args: Command-line arguments
        summary: Summary configuration
    """
    # Setup logging
    log_file = getattr(args, "log_file", None)
    def _log(msg: str) -> None:
        try:
            print(msg)
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(str(msg) + "\n")
        except Exception:
            pass
    
    # Load and parse configuration
    cfg_path = Path(args.config)
    txt = cfg_path.read_text(encoding="utf-8-sig")
    cfg = json.loads(txt)
    out_dir = Path(args.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = expand_batch_config(cfg)
    if not jobs:
        _log("[Erro] Nenhum job gerado a partir do config.")
        return

    out_pattern = (cfg.get("output") or {}).get("pattern") or "{topic}_{secao}_{date}_{idx}.json"
    report = {"total_jobs": len(jobs), "ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    defaults = cfg.get("defaults") or {}

    # ============================================================================
    # FAST ASYNC MODE: Try single-browser async collector first (2x faster)
    # ============================================================================
    from .batch_async import try_fast_async_mode
    
    async_report = try_fast_async_mode(jobs, defaults, out_dir, out_pattern, args, cfg, _log)
    if async_report:
        # Fast async succeeded! Write report and finish
        report = async_report
        from .batch_helpers import write_report, finalize_with_aggregation
        
        rep_path = write_report(report, out_dir, cfg)
        _log(f"\n[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")
        
        finalize_with_aggregation(report, out_dir, cfg, rep_path, _log)


def _init_worker(log_file: str | None = None) -> None:
    """Initializer for worker processes to confirm spawn and set basic policy early."""
    try:
        import asyncio as _asyncio
        import os as _os
        import sys as _sys
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        if log_file:
            try:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(f"[Init {_os.getpid()}] worker process spawned\n")
            except Exception:
                pass
    except Exception:
        pass


def _run_fast_async_subprocess(async_input: dict, _log) -> dict:
    """
    Executa o collector async via subprocess (para evitar conflitos de event loop).
    
    Similar ao padrão usado em eagendas_collect_parallel.
    """
    import tempfile
    
    try:
        # Escrever input em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(async_input, f, ensure_ascii=False)
            input_path = f.name
        
        # Escrever resultado em arquivo temporário
        result_path = input_path.replace('.json', '_result.json')
        
        # Encontrar script
        script_path = Path(__file__).parent.parent / "ui" / "dou_collect_parallel.py"
        if not script_path.exists():
            _log(f"[FAST ASYNC SUBPROCESS] Script não encontrado: {script_path}")
            return {"success": False, "error": f"Script não encontrado: {script_path}"}
        
        # Executar subprocess
        env = os.environ.copy()
        env["INPUT_JSON_PATH"] = input_path
        env["RESULT_JSON_PATH"] = result_path
        env["PYTHONIOENCODING"] = "utf-8"
        
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            capture_output=True,
            timeout=600,  # 10 min timeout
            text=True
        )
        
        # Ler resultado
        if Path(result_path).exists():
            result = json.loads(Path(result_path).read_text(encoding='utf-8'))
        else:
            # Tentar parsear stdout
            try:
                result = json.loads(proc.stdout)
            except Exception:
                result = {"success": False, "error": proc.stderr or "No output"}
        
        # Cleanup
        try:
            Path(input_path).unlink(missing_ok=True)
            Path(result_path).unlink(missing_ok=True)
        except Exception:
            pass
        
        return result
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Subprocess timeout (10 min)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_plan_aggregation(cfg: dict, report: dict, out_dir: Path, _log) -> None:
    """Agregação de outputs por plano (extraída para evitar duplicação)."""
    try:
        plan_name = (cfg.get("plan_name") or (cfg.get("defaults", {}) or {}).get("plan_name") or "").strip()
        if not plan_name:
            return
        
        from collections import defaultdict
        
        def _aggregate_outputs_by_date(paths: list[str], out_dir_p: Path, plan: str) -> list[str]:
            agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"data": "", "secao": "", "plan": plan, "itens": []})
            secao_any = ""
            for pth in paths or []:
                try:
                    data = json.loads(Path(pth).read_text(encoding="utf-8"))
                except Exception:
                    continue
                date = str(data.get("data") or "")
                secao = str(data.get("secao") or "")
                if not agg[date]["data"]:
                    agg[date]["data"] = date
                if not agg[date]["secao"]:
                    agg[date]["secao"] = secao
                if not secao_any and secao:
                    secao_any = secao
                items = data.get("itens", []) or []
                # Normalize detail_url (absolute)
                for it in items:
                    try:
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
                    except Exception:
                        pass
                agg[date]["itens"].extend(items)
            written: list[str] = []
            secao_label = (secao_any or "DO").strip()
            for date, payload in agg.items():
                payload["total"] = len(payload.get("itens", []))
                safe_plan = sanitize_filename(plan)
                date_lab = (date or "").replace("/", "-")
                out_name = f"{safe_plan}_{secao_label}_{date_lab}.json"
                out_path_f = out_dir_p / out_name
                out_path_f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                written.append(str(out_path_f))
            return written

        prev_outputs = list(report.get("outputs", []))
        agg_files = _aggregate_outputs_by_date(prev_outputs, out_dir, plan_name)
        if agg_files:
            deleted = []
            for pth in prev_outputs:
                try:
                    Path(pth).unlink(missing_ok=True)
                    deleted.append(pth)
                except Exception:
                    pass
            report["deleted_outputs"] = deleted
            report["outputs"] = []
            report["aggregated"] = agg_files
            report["aggregated_only"] = True
            # Re-write report with aggregation info
            rep_path = out_dir / (((cfg.get("output", {}) or {}).get("report")) or "batch_report.json")
            rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            _log(f"[AGG] {len(agg_files)} arquivo(s) agregado(s) por plano: {plan_name}; removidos {len(deleted)} JSON(s) individuais")
    except Exception as e:
        _log(f"[AGG][WARN] Falha ao agregar por plano: {e}")


def run_batch(playwright, args, summary: SummaryConfig) -> None:
    """Execute batch processing with optional fast async mode.
    
    This function coordinates batch execution with multiple strategies:
    1. Fast async mode (single browser, multiple contexts) - fastest
    2. Multi-browser fallback modes (subprocess, thread, or process pool)
    
    Args:
        playwright: Playwright instance (may be unused if fast async succeeds)
        args: Command-line arguments
        summary: Summary configuration
    """
    # Setup logging
    log_file = getattr(args, "log_file", None)
    def _log(msg: str) -> None:
        try:
            print(msg)
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as _fp:
                    _fp.write(str(msg) + "\n")
        except Exception:
            pass
    
    # Load and parse configuration
    cfg_path = Path(args.config)
    txt = cfg_path.read_text(encoding="utf-8-sig")
    cfg = json.loads(txt)
    out_dir = Path(args.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = expand_batch_config(cfg)
    if not jobs:
        _log("[Erro] Nenhum job gerado a partir do config.")
        return

    out_pattern = (cfg.get("output") or {}).get("pattern") or "{topic}_{secao}_{date}_{idx}.json"
    report = {"total_jobs": len(jobs), "ok": 0, "fail": 0, "items_total": 0, "outputs": []}
    defaults = cfg.get("defaults") or {}

    # ============================================================================
    # FAST ASYNC MODE: Try single-browser async collector first (2x faster)
    # ============================================================================
    from .batch_async import try_fast_async_mode
    
    async_report = try_fast_async_mode(jobs, defaults, out_dir, out_pattern, args, cfg, _log)
    if async_report:
        # Fast async succeeded! Write report and finish
        report = async_report
        from .batch_helpers import write_report, finalize_with_aggregation
        
        rep_path = write_report(report, out_dir, cfg)
        _log(f"\n[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")
        
        finalize_with_aggregation(report, out_dir, cfg, rep_path, _log)
        return

    # ============================================================================
    # FALLBACK: Multi-browser approach (slower but robust)
    # ============================================================================
    _log("[FALLBACK] Usando método multi-browser original...")

    # Import helper functions
    from .batch_helpers import (
        load_state_file,
        determine_parallelism,
        distribute_jobs_into_buckets,
        aggregate_report_metrics,
        write_report,
        finalize_with_aggregation,
    )
    from .batch_executor import (
        execute_with_subprocess,
        execute_with_threads,
        execute_inline_with_threads,
        execute_with_process_pool,
    )

    # Load deduplication state
    state_file_path = None
    if cfg.get("state_file"):
        state_file_path = Path(cfg["state_file"])
    elif getattr(args, "state_file", None):
        state_file_path = Path(args.state_file)
    
    global_seen = load_state_file(state_file_path)

    # Determine parallelism
    parallel = determine_parallelism(args, len(jobs))
    pool_pref = os.environ.get("DOU_POOL", "process").strip().lower() or "process"
    reuse_page = bool(getattr(args, "reuse_page", False))

    # Distribute jobs into buckets
    buckets, desired_size = distribute_jobs_into_buckets(jobs, cfg, parallel)
    
    effective_parallel = min(parallel, int(os.environ.get("DOU_MAX_WORKERS", "4") or "4"))
    _log(f"[Parent] total_jobs={len(jobs)} parallel={parallel} (effective={effective_parallel}) reuse_page={reuse_page}")
    _log(f"[Parent] buckets={len(buckets)} desired_size={desired_size}")

    # Prepare summary config for workers
    summary_dict = {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords}

    # Execute batch with appropriate strategy
    try:
        if pool_pref == "subprocess" and parallel > 1:
            exec_report = execute_with_subprocess(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log
            )
        elif pool_pref == "thread" and parallel > 1:
            exec_report = execute_with_threads(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log, _worker_process
            )
        elif parallel <= 1:
            exec_report = execute_inline_with_threads(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, _log, _worker_process
            )
        else:
            exec_report = execute_with_process_pool(
                buckets, jobs, defaults, out_dir, out_pattern,
                args, state_file_path, reuse_page, summary, parallel, _log,
                _worker_process, _init_worker, log_file
            )
        
        # Update report with execution results
        report.update(exec_report)
    finally:
        pass

    # Aggregate metrics
    aggregate_report_metrics(report)

    # Write report
    rep_path = write_report(report, out_dir, cfg)
    _log("")
    _log(f"[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")

    # Perform plan aggregation if configured
    finalize_with_aggregation(report, out_dir, cfg, rep_path, _log)
