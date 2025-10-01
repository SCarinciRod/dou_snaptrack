from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import hashlib
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

from .summary_config import SummaryConfig, apply_summary_overrides_from_job
from .runner import run_once


def sanitize_filename(name: str) -> str:
    import re
    name = re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", name)
    return name[:180].strip("_ ") or "out"


def render_out_filename(pattern: str, job: Dict[str, Any]) -> str:
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


def expand_batch_config(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
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
                jj_r = dict(jj); jj_r["_repeat"] = r
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
                    jj_r = dict(jj); jj_r["_repeat"] = r
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
                jj_r = dict(jj); jj_r["_repeat"] = r
                jobs.append(jj_r)

    return jobs


def _worker_process(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process-based worker to avoid Playwright sync threading issues."""
    # Ajuste de loop asyncio no Windows antes de importar Playwright (subprocess)
    try:
        import sys as _sys, asyncio as _asyncio
        if _sys.platform.startswith("win"):
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
            _asyncio.set_event_loop(_asyncio.new_event_loop())
    except Exception:
        pass
    from playwright.sync_api import sync_playwright  # type: ignore
    jobs: List[Dict[str, Any]] = payload["jobs"]
    defaults: Dict[str, Any] = payload["defaults"]
    out_dir = Path(payload["out_dir"])  # already exists
    out_pattern: str = payload["out_pattern"]
    headful: bool = bool(payload.get("headful", False))
    slowmo: int = int(payload.get("slowmo", 0))
    state_file: Optional[str] = payload.get("state_file")
    reuse_page: bool = bool(payload.get("reuse_page", False))
    summary: SummaryConfig = SummaryConfig(**(payload.get("summary") or {}))
    indices: List[int] = payload["indices"]

    def _get(job, key, default_key=None, default_value=None):
        if default_key is None:
            default_key = key
        return job.get(key, defaults.get(default_key, default_value))

    report = {"ok": 0, "fail": 0, "items_total": 0, "outputs": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful, slow_mo=slowmo)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
        page_cache: Dict[Tuple[str, str], Any] = {}
        try:
            for j_idx in indices:
                job = jobs[j_idx - 1]
                print(f"\n[PW{os.getpid()}] [Job {j_idx}/{len(jobs)}] {job.get('topic','')}: {job.get('query','')}")
                out_name = render_out_filename(out_pattern, {**job, "_job_index": j_idx})
                out_path = out_dir / out_name

                data = job.get("data")
                secao = job.get("secao", defaults.get("secaoDefault", "DO1"))
                key1_type = job.get("key1_type"); key1 = job.get("key1")
                key2_type = job.get("key2_type"); key2 = job.get("key2")
                label1 = job.get("label1"); label2 = job.get("label2")

                max_links = int(_get(job, "max_links", "max_links", 30))
                do_scrape_detail = bool(_get(job, "scrape_detail", "scrape_detail", True))
                detail_timeout = int(_get(job, "detail_timeout", "detail_timeout", 60_000))
                fallback_date = bool(_get(job, "fallback_date_if_missing", "fallback_date_if_missing", True))

                max_scrolls = int(_get(job, "max_scrolls", "max_scrolls", 40))
                scroll_pause_ms = int(_get(job, "scroll_pause_ms", "scroll_pause_ms", 350))
                stable_rounds = int(_get(job, "stable_rounds", "stable_rounds", 3))
                detail_parallel = int(_get(job, "detail_parallel", "detail_parallel", 1))

                bulletin = job.get("bulletin") or defaults.get("bulletin")
                bulletin_out_pat = job.get("bulletin_out") or defaults.get("bulletin_out") or None
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
                        page.set_default_timeout(60_000)
                        page.set_default_navigation_timeout(60_000)
                        page_cache[k] = page
                    keep_open = True

                try:
                    result = run_once(
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
                        page=page, keep_page_open=keep_open,
                    )
                    report["ok"] += 1
                    report["outputs"].append(str(out_path))
                    report["items_total"] += result.get("total", 0)
                except Exception as e:
                    print(f"[FAIL] Job {j_idx}: {e}")
                    report["fail"] += 1

                delay_ms = int(job.get("repeat_delay_ms", defaults.get("repeat_delay_ms", 0)))
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
        finally:
            # Close cached pages
            for p in page_cache.values():
                try:
                    p.close()
                except Exception:
                    pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    return report


def run_batch(playwright, args, summary: SummaryConfig) -> None:
    cfg_path = Path(args.config)
    # Aceitar UTF-8 com BOM
    txt = cfg_path.read_text(encoding="utf-8-sig")
    cfg = json.loads(txt)
    out_dir = Path(args.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = expand_batch_config(cfg)
    if not jobs:
        print("[Erro] Nenhum job gerado a partir do config.")
        return

    out_pattern = (cfg.get("output") or {}).get("pattern") or "{topic}_{secao}_{date}_{idx}.json"
    report = {"total_jobs": len(jobs), "ok": 0, "fail": 0, "items_total": 0, "outputs": []}

    defaults = cfg.get("defaults") or {}

    def _get(job, key, default_key=None, default_value=None):
        if default_key is None:
            default_key = key
        return job.get(key, defaults.get(default_key, default_value))

    # Dedup global state
    state_file_path = None
    global_seen = set()
    if cfg.get("state_file"):
        state_file_path = Path(cfg["state_file"])
    elif getattr(args, "state_file", None):
        state_file_path = Path(args.state_file)
    if state_file_path and state_file_path.exists():
        try:
            for line in state_file_path.read_text(encoding="utf-8").splitlines():
                try:
                    obj = json.loads(line); h = obj.get("hash")
                    if h: global_seen.add(h)
                except Exception:
                    pass
        except Exception:
            pass

    parallel = int(getattr(args, "parallel", 4) or 4)
    reuse_page = bool(getattr(args, "reuse_page", False))

    # Distribute jobs roughly evenly across workers
    total = len(jobs)
    indices = list(range(1, total + 1))
    buckets: List[List[int]] = [[] for _ in range(max(1, parallel))]
    for i, idx in enumerate(indices):
        buckets[i % len(buckets)].append(idx)

    try:
        with ProcessPoolExecutor(max_workers=max(1, parallel)) as ex:
            futs = []
            for w_id, bucket in enumerate(buckets):
                if not bucket:
                    continue
                payload = {
                    "jobs": jobs,
                    "defaults": defaults,
                    "out_dir": str(out_dir),
                    "out_pattern": out_pattern,
                    "headful": bool(args.headful),
                    "slowmo": int(args.slowmo),
                    "state_file": str(state_file_path) if state_file_path else None,
                    "reuse_page": reuse_page,
                    "summary": {"lines": summary.lines, "mode": summary.mode, "keywords": summary.keywords},
                    "indices": bucket,
                }
                futs.append(ex.submit(_worker_process, payload))
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    report["ok"] += r.get("ok", 0)
                    report["fail"] += r.get("fail", 0)
                    report["items_total"] += r.get("items_total", 0)
                    report["outputs"].extend(r.get("outputs", []))
                except Exception as e:
                    print(f"[Worker FAIL] {e}")
    finally:
        # Nothing to cleanup in parent; workers clean themselves.
        pass

    rep_path = out_dir / (((cfg.get("output", {}) or {}).get("report")) or "batch_report.json")
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}")
