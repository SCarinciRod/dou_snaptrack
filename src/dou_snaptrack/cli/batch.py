from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import hashlib
import time
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
import subprocess

from .summary_config import SummaryConfig, apply_summary_overrides_from_job


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
    # Optional log redirection: write worker prints to a shared log file
    _log_fp = None
    try:
        log_file = payload.get("log_file")
        # Evitar redirecionar stdout quando rodando inline (thread) no processo principal
        import multiprocessing as _mp
        is_main_proc = (_mp.current_process().name == "MainProcess")
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            _log_fp = open(log_file, "a", encoding="utf-8", buffering=1)
            if not is_main_proc:
                sys.stdout = _log_fp  # type: ignore
                sys.stderr = _log_fp  # type: ignore
            print(f"[Worker {os.getpid()}] logging to {log_file}")
    except Exception:
        _log_fp = None
    # Defer heavy imports until after stdout is redirected
    from playwright.sync_api import sync_playwright  # type: ignore
    from .runner import run_once
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
                        exe = c; break
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
        page_cache: Dict[Tuple[str, str], Any] = {}
        fast_mode = (os.environ.get("DOU_FAST_MODE", "").strip() or "0").lower() in ("1","true","yes")
        try:
            for j_idx in indices:
                job = jobs[j_idx - 1]
                start_ts = time.time()
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

                # Leaner defaults to reduce scrolling effort; fast-mode can cut further
                max_scrolls = int(_get(job, "max_scrolls", "max_scrolls", 20))
                scroll_pause_ms = int(_get(job, "scroll_pause_ms", "scroll_pause_ms", 150))
                stable_rounds = int(_get(job, "stable_rounds", "stable_rounds", 1))
                if fast_mode:
                    max_scrolls = min(max_scrolls, 15)
                    scroll_pause_ms = min(scroll_pause_ms, 150)
                    stable_rounds = min(stable_rounds, 1)
                    do_scrape_detail = False
                detail_parallel = int(_get(job, "detail_parallel", "detail_parallel", 1))

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
                        page.set_default_timeout(20_000)
                        page.set_default_navigation_timeout(20_000)
                        page_cache[k] = page
                    keep_open = True

                def _run_with_retry(cur_page) -> Optional[Dict[str, Any]]:
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
                        except Exception as e:
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
                                        cur_page.set_default_timeout(20_000)
                                        cur_page.set_default_navigation_timeout(20_000)
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
                    print(f"[PW{os.getpid()}] [Job {j_idx}] concluído em {elapsed:.1f}s — itens={0 if not isinstance(result, dict) else result.get('total', 0)}")
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
    # Ensure file buffer is flushed before returning
    try:
        if _log_fp:
            _log_fp.flush()
    except Exception:
        pass
    return report


def _init_worker(log_file: Optional[str] = None) -> None:
    """Initializer for worker processes to confirm spawn and set basic policy early."""
    try:
        import sys as _sys, asyncio as _asyncio, os as _os
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


def run_batch(playwright, args, summary: SummaryConfig) -> None:
    # Simple helper to mirror logs into provided log file (if any)
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
    cfg_path = Path(args.config)
    # Aceitar UTF-8 com BOM
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
    pool_pref = os.environ.get("DOU_POOL", "process").strip().lower() or "process"
    reuse_page = bool(getattr(args, "reuse_page", False))

    # Distribute jobs by (date, secao), but chunk large groups across buckets to keep parallelism
    from collections import defaultdict
    import math
    groups: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, job in enumerate(jobs, start=1):
        d = str(job.get("data") or cfg.get("data") or "")
        s = str(job.get("secao") or cfg.get("secaoDefault") or "")
        groups[(d, s)].append(i)
    min_bucket = int(os.environ.get("DOU_BUCKET_SIZE_MIN", "2") or "2")
    min_bucket = max(1, min_bucket)
    # Strategy: prefer keeping (date,secao) groups intact, but if there is only one group with many jobs,
    # split it into a few buckets to retain some parallelism while reusing pages within each bucket.
    unique_groups = list(sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True))
    if len(unique_groups) == 1:
        only_group_idxs = unique_groups[0][1]
        # Choose 2-3 buckets depending on job count and available parallelism
        bucket_count = min(parallel, max(1, min(3, math.ceil(len(only_group_idxs) / max(2, min_bucket)))))
        desired_size = max(1, math.ceil(len(only_group_idxs) / bucket_count))
        buckets = []
        for start in range(0, len(only_group_idxs), desired_size):
            buckets.append(only_group_idxs[start:start + desired_size])
    else:
        # Multiple groups: keep each group in its own bucket when possible, otherwise chunk large groups
        if len(unique_groups) <= max(1, parallel):
            buckets = [idxs for (_, idxs) in unique_groups[:max(1, parallel)]]
            desired_size = max(min_bucket, max((len(b) for b in buckets), default=1))
        else:
            bucket_count = max(1, min(parallel, math.ceil(len(jobs) / max(1, min_bucket))))
            desired_size = max(min_bucket, math.ceil(len(jobs) / bucket_count))
            pseudo_groups: List[List[int]] = []
            for _, idxs in unique_groups:
                for start in range(0, len(idxs), desired_size):
                    pseudo_groups.append(idxs[start:start + desired_size])
            buckets = [[] for _ in range(bucket_count)]
            for gi, chunk in enumerate(pseudo_groups):
                buckets[gi % bucket_count].extend(chunk)

    _log(f"[Parent] total_jobs={len(jobs)} parallel={parallel} reuse_page={reuse_page}")
    _log(f"[Parent] buckets={len(buckets)} desired_size={desired_size}")
    try:
        if pool_pref == "subprocess" and parallel > 1:
            _log(f"[Parent] Using subprocess pool (workers={parallel})")
            futs = []
            tmp_dir = out_dir / "_subproc"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            for w_id, bucket in enumerate(buckets):
                if not bucket:
                    continue
                _log(f"[Parent] Scheduling (subproc) bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}")
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
                    "log_file": getattr(args, "log_file", None),
                }
                payload_path = (tmp_dir / f"payload_{w_id+1}.json").resolve()
                result_path = (tmp_dir / f"result_{w_id+1}.json").resolve()
                payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                # Build subprocess command using current Python
                py = sys.executable or "python"
                cmd = [py, "-m", "dou_snaptrack.cli.worker_entry", "--payload", str(payload_path), "--out", str(result_path)]
                # Use repository root as CWD to ensure module resolution and relative paths behave as expected
                repo_root = Path(__file__).resolve().parents[3]
                src_dir = (repo_root / "src").resolve()
                env = os.environ.copy()
                existing_pp = env.get("PYTHONPATH", "")
                if str(src_dir) not in (existing_pp.split(";") if os.name == "nt" else existing_pp.split(":")):
                    env["PYTHONPATH"] = (str(src_dir) + (";" if os.name == "nt" else ":") + existing_pp) if existing_pp else str(src_dir)
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(repo_root), env=env)
                futs.append((p, result_path))
            _log(f"[Parent] {len(futs)} subprocesses spawned")
            # Collect results
            for p, result_path in futs:
                try:
                    out = p.communicate(timeout=900)[0].decode("utf-8", errors="ignore") if p.stdout else ""
                except Exception:
                    out = ""
                if out:
                    _log(out.strip())
                if result_path.exists():
                    try:
                        r = json.loads(result_path.read_text(encoding="utf-8"))
                        report["ok"] += r.get("ok", 0)
                        report["fail"] += r.get("fail", 0)
                        report["items_total"] += r.get("items_total", 0)
                        report["outputs"].extend(r.get("outputs", []))
                        _log(f"[Parent] Subproc done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                    except Exception as e:
                        _log(f"[Subproc parse FAIL] {e}")
                else:
                    _log("[Subproc FAIL] result file missing")
        elif pool_pref == "thread" and parallel > 1:
            _log(f"[Parent] Using ThreadPoolExecutor (workers={parallel})")
            with ThreadPoolExecutor(max_workers=max(1, parallel)) as tpex:
                futs = []
                for w_id, bucket in enumerate(buckets):
                    if not bucket:
                        continue
                    _log(f"[Parent] Scheduling (thread) bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}")
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
                        "log_file": getattr(args, "log_file", None),
                    }
                    futs.append(tpex.submit(_worker_process, payload))
                _log(f"[Parent] {len(futs)} thread-futures scheduled")
                for fut in as_completed(futs):
                    try:
                        r = fut.result()
                        report["ok"] += r.get("ok", 0)
                        report["fail"] += r.get("fail", 0)
                        report["items_total"] += r.get("items_total", 0)
                        report["outputs"].extend(r.get("outputs", []))
                        _log(f"[Parent] Thread future done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                    except Exception as e:
                        _log(f"[Worker FAIL thread] {e}")
        elif parallel <= 1:
            # Run inline in a separate thread to avoid Playwright Sync API inside running asyncio loop
            _log("[Parent] Running single bucket inline (thread, no ProcessPool)")
            for w_id, bucket in enumerate(buckets):
                if not bucket:
                    continue
                _log(f"[Parent] Scheduling bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}")
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
                    "log_file": getattr(args, "log_file", None),
                }
                try:
                    with ThreadPoolExecutor(max_workers=1) as tpex:
                        fut = tpex.submit(_worker_process, payload)
                        r = fut.result()
                        report["ok"] += r.get("ok", 0)
                        report["fail"] += r.get("fail", 0)
                        report["items_total"] += r.get("items_total", 0)
                        report["outputs"].extend(r.get("outputs", []))
                        _log(f"[Parent] Inline (thread) done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                except Exception as e:
                    _log(f"[Worker FAIL inline-thread] {e}")
        else:
            ctx = mp.get_context("spawn")
            with ProcessPoolExecutor(max_workers=max(1, parallel), mp_context=ctx, initializer=_init_worker, initargs=(log_file,)) as ex:
                _log("[Parent] ProcessPoolExecutor started")
                futs = []
                for w_id, bucket in enumerate(buckets):
                    if not bucket:
                        continue
                    _log(f"[Parent] Scheduling bucket {w_id+1}/{len(buckets)} size={len(bucket)} first_idx={bucket[0] if bucket else '-'}")
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
                        "log_file": getattr(args, "log_file", None),
                    }
                    futs.append(ex.submit(_worker_process, payload))
                _log(f"[Parent] {len(futs)} futures scheduled")
                try:
                    # Espera algum worker completar em até 60s; caso contrário, fallback inline
                    any_done = False
                    for fut in as_completed(futs, timeout=60):
                        any_done = True
                        try:
                            r = fut.result()
                            report["ok"] += r.get("ok", 0)
                            report["fail"] += r.get("fail", 0)
                            report["items_total"] += r.get("items_total", 0)
                            report["outputs"].extend(r.get("outputs", []))
                            _log(f"[Parent] Future done: ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                        except Exception as e:
                            _log(f"[Worker FAIL] {e}")
                    if not any_done:
                        raise TimeoutError("no worker finished within timeout")
                except TimeoutError:
                    _log("[Parent] Timeout aguardando workers. Fazendo fallback para execução inline…")
                    # Cancelar e cair para thread-pool paralelo
                    try:
                        ex.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
                    with ThreadPoolExecutor(max_workers=max(1, parallel)) as tpex:
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
                                "log_file": getattr(args, "log_file", None),
                            }
                            futs.append(tpex.submit(_worker_process, payload))
                        _log(f"[Parent] {len(futs)} thread-futures scheduled (fallback)")
                        for fut in as_completed(futs):
                            try:
                                r = fut.result()
                                report["ok"] += r.get("ok", 0)
                                report["fail"] += r.get("fail", 0)
                                report["items_total"] += r.get("items_total", 0)
                                report["outputs"].extend(r.get("outputs", []))
                                _log(f"[Parent] Thread future done (fallback): ok={r.get('ok',0)} fail={r.get('fail',0)} items={r.get('items_total',0)}")
                            except Exception as e:
                                _log(f"[Worker FAIL thread fallback] {e}")
    finally:
        # Nothing to cleanup in parent; workers clean themselves.
        pass

    rep_path = out_dir / (((cfg.get("output", {}) or {}).get("report")) or "batch_report.json")
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    final_line = f"[REPORT] {rep_path} — jobs={report['total_jobs']} ok={report['ok']} fail={report['fail']} items={report['items_total']}"
    _log("")
    _log(final_line)
