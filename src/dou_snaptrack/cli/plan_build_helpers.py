"""Helper functions for async plan building.

This module contains extracted functions from build_plan_live_async to reduce complexity.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any


async def launch_browser_with_fallbacks(p, headful: bool, slowmo: int):
    """Launch browser with multiple fallback strategies.
    
    Args:
        p: Playwright instance
        headful: Whether to run in headful mode
        slowmo: Slow motion delay
        
    Returns:
        Browser instance
    """
    browser = None
    
    # Try Chrome channel
    try:
        browser = await p.chromium.launch(channel="chrome", headless=not headful, slow_mo=slowmo)
        return browser
    except Exception:
        pass
    
    # Try Edge channel
    try:
        browser = await p.chromium.launch(channel="msedge", headless=not headful, slow_mo=slowmo)
        return browser
    except Exception:
        pass
    
    # Try executable path
    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if not exe:
        for c in (
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        ):
            if Path(c).exists():
                exe = c
                break
    
    if exe and Path(exe).exists():
        browser = await p.chromium.launch(executable_path=exe, headless=not headful, slow_mo=slowmo)
        return browser
    
    # Final fallback
    return await p.chromium.launch(headless=not headful, slow_mo=slowmo)


async def setup_browser_context(browser):
    """Set up browser context and page.
    
    Args:
        browser: Browser instance
        
    Returns:
        Tuple of (context, page)
    """
    context = await browser.new_context(ignore_https_errors=True)
    context.set_default_timeout(90_000)
    page = await context.new_page()
    return context, page


async def wait_for_dropdown_ready(page) -> bool:
    """Wait for dropdown to be populated.
    
    Args:
        page: Playwright page
        
    Returns:
        True if dropdown is ready
    """
    dropdown_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => document.querySelector('#slcOrgs')?.options?.length > 2",
            timeout=15000
        )
        dropdown_ready = True
    
    if not dropdown_ready:
        await page.wait_for_timeout(2000)
    
    return dropdown_ready


async def detect_dropdown_roots(frame, select_roots_fn, collect_roots_fn):
    """Detect N1/N2 dropdown roots.
    
    Args:
        frame: Playwright frame
        select_roots_fn: Function to select roots
        collect_roots_fn: Function to collect roots
        
    Returns:
        Tuple of (r1, r2)
    """
    try:
        r1, r2 = await select_roots_fn(frame)
    except Exception:
        roots = await collect_roots_fn(frame)
        r1 = roots[0] if roots else None
        r2 = roots[1] if len(roots) > 1 else None
    
    return r1, r2


async def process_n1_option(frame, r1, r2, k1, page, read_opts_fn, select_fn, count_opts_fn, wait_repop_fn, select_roots_fn, filter_fn, build_keys_fn, args, verbose: bool) -> list[str]:
    """Process a single N1 option and return N2 keys.
    
    Args:
        frame: Playwright frame
        r1: N1 dropdown root
        r2: N2 dropdown root
        k1: N1 key
        page: Playwright page
        read_opts_fn: Function to read options
        select_fn: Function to select option
        count_opts_fn: Function to count options
        wait_repop_fn: Function to wait for repopulation
        select_roots_fn: Function to select roots
        filter_fn: Function to filter options
        build_keys_fn: Function to build keys
        args: Command line arguments
        verbose: Verbose flag
        
    Returns:
        List of N2 keys
    """
    # Count previous N2 options
    prev_n2_count = 0
    if r2:
        prev_n2_count = await count_opts_fn(frame, r2)
    
    # Select N1
    await select_fn(frame, r1, k1)
    
    # Wait for AJAX
    await page.wait_for_load_state("domcontentloaded", timeout=30_000)
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=5_000)
    
    # Re-detect N2
    try:
        _, r2_new = await select_roots_fn(frame)
        if r2_new:
            r2 = r2_new
    except Exception:
        pass
    
    # Read N2 options
    if r2:
        with contextlib.suppress(Exception):
            await wait_repop_fn(frame, r2, prev_n2_count, timeout_ms=25_000, poll_ms=150)
        
        opts2 = await read_opts_fn(frame, r2)
        opts2 = filter_fn(
            opts2,
            getattr(args, "select2", None),
            getattr(args, "pick2", None),
            getattr(args, "limit2", None)
        )
        k2_list = build_keys_fn(opts2, getattr(args, "key2_type_default", "text"))
        
        if verbose:
            print(f"[plan-live-async] N1='{k1}' => N2 válidos: {len(k2_list)}")
        
        return k2_list
    
    return []


def build_combos_from_keys(k1: str, k2_list: list[str]) -> list[dict[str, Any]]:
    """Build combo dictionaries from N1 and N2 keys.
    
    Args:
        k1: N1 key
        k2_list: List of N2 keys
        
    Returns:
        List of combo dictionaries
    """
    if k2_list:
        return [
            {
                "key1": k1,
                "label1": k1,
                "key2": k2,
                "label2": k2,
            }
            for k2 in k2_list
        ]
    else:
        return [{
            "key1": k1,
            "label1": k1,
            "key2": "Todos",
            "label2": "Todos",
        }]


def build_config(data: str, secao: str, combos: list[dict[str, Any]], defaults: dict[str, Any]) -> dict[str, Any]:
    """Build configuration dictionary.
    
    Args:
        data: Date string
        secao: Section
        combos: List of combos
        defaults: Default values
        
    Returns:
        Configuration dictionary
    """
    return {
        "data": data or "",
        "secaoDefault": secao,
        "defaults": defaults,
        "combos": combos,
        "output": {
            "pattern": "{topic}_{secao}_{date}_{idx}.json",
            "report": "batch_report.json"
        }
    }


def save_plan_if_requested(cfg: dict[str, Any], plan_out: str | None, verbose: bool) -> None:
    """Save plan to file if requested.
    
    Args:
        cfg: Configuration dictionary
        plan_out: Output path
        verbose: Verbose flag
    """
    if plan_out:
        import json
        Path(plan_out).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            print(f"[plan-live-async] Plano salvo: {plan_out}")
