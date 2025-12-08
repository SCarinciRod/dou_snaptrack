"""Helper functions for build_plan_live to reduce complexity."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from ..utils.browser import fmt_date, goto
from ..utils.dom import find_best_frame, label_for_control
from ..utils.wait_utils import wait_for_condition


def launch_browser_with_fallbacks(pctx, headful: bool, slowmo: int):
    """Launch browser with multiple fallback strategies.
    
    Tries in order:
    1. Chrome channel
    2. Edge channel
    3. Executable path from environment or common locations
    4. Default Chromium
    """
    # Try Chrome channel
    try:
        return pctx.chromium.launch(channel="chrome", headless=not headful, slow_mo=slowmo)
    except Exception:
        pass
    
    # Try Edge channel
    try:
        return pctx.chromium.launch(channel="msedge", headless=not headful, slow_mo=slowmo)
    except Exception:
        pass
    
    # Try executable path
    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if not exe:
        for c in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ):
            if Path(c).exists():
                exe = c
                break
    
    if exe and Path(exe).exists():
        try:
            return pctx.chromium.launch(executable_path=exe, headless=not headful, slow_mo=slowmo)
        except Exception:
            pass
    
    # Last resort: default Chromium
    return pctx.chromium.launch(headless=not headful, slow_mo=slowmo)


def setup_browser_and_page(browser, args):
    """Create browser context and page with DOU settings."""
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
    page = context.new_page()
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)
    
    data = fmt_date(args.data)
    goto(page, f"https://www.in.gov.br/leiturajornal?data={data}&secao={args.secao}")
    frame = find_best_frame(context)
    
    return context, page, frame


def wait_after_selection(page, frame):
    """Wait for page to settle after dropdown selection."""
    with contextlib.suppress(Exception):
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
    with contextlib.suppress(Exception):
        wait_for_condition(frame, lambda: page.is_visible("body"), timeout_ms=200, poll_ms=50)


def collect_n1_candidates(frame, r1, args, verbose: bool):
    """Collect and filter N1 dropdown options."""
    from .plan_live import _read_dropdown_options, _filter_opts, _build_keys
    
    o1 = _read_dropdown_options(frame, r1)
    o1 = _filter_opts(o1, getattr(args, "select1", None), getattr(args, "pick1", None), getattr(args, "limit1", None))
    k1_list = _build_keys(o1, getattr(args, "key1_type_default", "text"))
    
    if not k1_list:
        raise RuntimeError("Após filtros, N1 ficou sem opções (ajuste --select1/--pick1/--limit1).")
    
    if verbose:
        print(f"[plan-live] N1 candidatos: {len(k1_list)}")
    
    return k1_list


def collect_n2_for_n1(frame, r2, args, k1, verbose: bool):
    """Collect and filter N2 dropdown options for a given N1."""
    from .plan_live import _read_dropdown_options, _filter_opts, _build_keys
    
    if not r2:
        return []
    
    o2 = _read_dropdown_options(frame, r2)
    o2 = _filter_opts(o2, getattr(args, "select2", None), getattr(args, "pick2", None), getattr(args, "limit2", None))
    k2_list = _build_keys(o2, getattr(args, "key2_type_default", "text"))
    
    if verbose:
        print(f"[plan-live] N1='{k1}' => N2 válidos: {len(k2_list)}")
    
    return k2_list


def create_combo_with_n2(args, k1, k2, frame, r1, r2):
    """Create a combo dict for N1+N2."""
    return {
        "key1_type": getattr(args, "key1_type_default", "text"),
        "key1": k1,
        "key2_type": getattr(args, "key2_type_default", "text"),
        "key2": k2,
        "key3_type": None,
        "key3": None,
        "label1": label_for_control(frame, r1.get("handle")) or "",
        "label2": (label_for_control(frame, r2.get("handle")) or "") if r2 else "",
        "label3": "",
    }


def create_combo_n1_only(args, k1, frame, r1):
    """Create a combo dict for N1 only."""
    return {
        "key1_type": getattr(args, "key1_type_default", "text"),
        "key1": k1,
        "key2_type": None,
        "key2": None,
        "key3_type": None,
        "key3": None,
        "label1": label_for_control(frame, r1.get("handle")) or "",
        "label2": "",
        "label3": "",
    }


def build_plan_config_dict(args, data, combos):
    """Build the plan configuration dictionary."""
    cfg = {
        "data": data,
        "secaoDefault": args.secao or "DO1",
        "defaults": {
            "scrape_detail": bool(getattr(args, "scrape_detail", False)),
            "fallback_date_if_missing": bool(getattr(args, "fallback_date_if_missing", False)),
            "max_links": int(getattr(args, "max_links", 30)),
            "max_scrolls": int(getattr(args, "max_scrolls", 30)),
            "scroll_pause_ms": int(getattr(args, "scroll_pause_ms", 250)),
            "stable_rounds": int(getattr(args, "stable_rounds", 2)),
            "label1": getattr(args, "label1", None),
            "label2": getattr(args, "label2", None),
            "label3": None,
            "debug_dump": bool(getattr(args, "debug_dump", False)),
            "summary_lines": int(getattr(args, "summary_lines", 3)) if getattr(args, "summary_lines", None) else None,
            "summary_mode": getattr(args, "summary_mode", "center"),
        },
        "combos": combos,
        "output": {"pattern": "{secao}_{date}_{idx}.json", "report": "batch_report.json"},
    }
    
    # Optional plan name
    plan_name = getattr(args, "plan_name", None) or getattr(args, "nome_plano", None)
    if plan_name:
        cfg["plan_name"] = str(plan_name)
    
    # Optional topic query
    if getattr(args, "query", None):
        cfg["topics"] = [{"name": "Topic", "query": args.query}]
    
    # Optional state file
    if getattr(args, "state_file", None):
        cfg["state_file"] = args.state_file
    
    # Optional bulletin output
    if getattr(args, "bulletin", None):
        ext = "docx" if args.bulletin == "docx" else args.bulletin
        out_b = args.bulletin_out or f"boletim_{{secao}}_{{date}}_{{idx}}.{ext}"
        cfg["output"]["bulletin"] = out_b
        cfg["defaults"]["bulletin"] = args.bulletin
        cfg["defaults"]["bulletin_out"] = out_b
    
    return cfg


def ensure_n1_root(frame, verbose: bool):
    """Ensure N1 dropdown root is available, with fallback lookup.
    
    Returns:
        N1 root dict, or None if not found
    """
    from .plan_live import _select_roots, _collect_dropdown_roots
    
    r1, _ = _select_roots(frame)
    if not r1:
        roots_tmp = _collect_dropdown_roots(frame)
        r1 = roots_tmp[0] if roots_tmp else None
    
    if not r1 and verbose:
        print("[plan-live][skip] N1 não encontrado após atualização do DOM.")
    
    return r1


def try_select_n1(frame, r1, k1, verbose: bool):
    """Try to select N1 option by text.
    
    Returns:
        True if successful, False otherwise
    """
    from .plan_live import _select_by_text
    
    if not _select_by_text(frame, r1, k1):
        if verbose:
            print(f"[plan-live][skip] N1 '{k1}' não pôde ser selecionado.")
        return False
    return True


def generate_combos_for_n1(k1, k2_list, args, frame, r1, r2, maxc, current_count: int):
    """Generate combos for a given N1 selection.
    
    Returns:
        List of new combos
    """
    combos = []
    
    if k2_list:
        for k2 in k2_list:
            combos.append(create_combo_with_n2(args, k1, k2, frame, r1, r2))
            if maxc and (current_count + len(combos)) >= maxc:
                break
    else:
        combos.append(create_combo_n1_only(args, k1, frame, r1))
    
    return combos


def cleanup_browser_context(context, browser, must_close_browser, pctx_mgr):
    """Clean up browser context and optionally browser and playwright context."""
    if context is not None:
        with contextlib.suppress(Exception):
            context.close()
    
    if must_close_browser and browser is not None:
        with contextlib.suppress(Exception):
            browser.close()
    
    if pctx_mgr is not None:
        with contextlib.suppress(Exception):
            pctx_mgr.__exit__(None, None, None)
