"""Helper functions for e-agendas plan building.

This module contains functions extracted from plan_live_eagendas_async.py to reduce complexity.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path
from typing import Any


# Constants
DD_ORGAO_ID = "filtro_orgao_entidade"
DD_CARGO_ID = "filtro_cargo"
DD_AGENTE_ID = "filtro_servidor"

LAUNCH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--ignore-certificate-errors',
    '--disable-dev-shm-usage'
]


async def launch_browser_with_fallbacks(playwright, headful: bool, slowmo: int):
    """Launch browser with multiple fallback strategies.
    
    Args:
        playwright: Playwright instance
        headful: Whether to show browser window
        slowmo: Slow motion delay in ms
        
    Returns:
        Browser instance
        
    Raises:
        RuntimeError: If no browser could be launched
    """
    use_headless = not headful
    browser = None
    
    # Try channel=chrome
    try:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=use_headless,
            slow_mo=slowmo,
            args=LAUNCH_ARGS
        )
        return browser
    except Exception:
        pass
    
    # Try channel=msedge
    try:
        browser = await playwright.chromium.launch(
            channel="msedge",
            headless=use_headless,
            slow_mo=slowmo,
            args=LAUNCH_ARGS
        )
        return browser
    except Exception:
        pass
    
    # Try explicit executable paths
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
        browser = await playwright.chromium.launch(
            executable_path=exe,
            headless=use_headless,
            slow_mo=slowmo,
            args=LAUNCH_ARGS
        )
        return browser
    
    # No browser found
    msg = (
        "Nenhum browser disponível. Tentativas:\n"
        "  1. channel='chrome' falhou\n"
        "  2. channel='msedge' falhou\n"
        "  3. Não encontrou Chrome/Edge em caminhos padrão\n"
        "Certifique-se de ter Chrome ou Edge instalado."
    )
    raise RuntimeError(msg)


async def initialize_page_and_wait(page, url: str) -> tuple[bool, bool]:
    """Navigate to URL and wait for Angular and Selectize to be ready.
    
    Args:
        page: Playwright page instance
        url: URL to navigate to
        
    Returns:
        Tuple of (angular_ready, selectize_ready)
    """
    await page.goto(url, wait_until="commit", timeout=60_000)
    
    # Wait for AngularJS
    angular_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => document.querySelector('[ng-app]') !== null",
            timeout=10_000
        )
        angular_ready = True
    
    # Wait for Selectize to be populated
    selectize_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => { const el = document.getElementById('filtro_orgao_entidade'); return el?.selectize && Object.keys(el.selectize.options || {}).length > 5; }",
            timeout=15_000
        )
        selectize_ready = True
    
    # Fallback if conditional waits failed
    if not angular_ready or not selectize_ready:
        await page.wait_for_timeout(1000)
    
    return angular_ready, selectize_ready


async def get_selectize_options_js(frame, element_id: str) -> list[dict[str, Any]]:
    """Get options from Selectize via JavaScript API.
    
    Args:
        frame: Playwright frame
        element_id: HTML element ID
        
    Returns:
        List of option dictionaries with 'value' and 'text' keys
    """
    try:
        opts = await frame.evaluate(
            """
            (id) => {
                const el = document.getElementById(id);
                if (!el || !el.selectize) return [];

                const s = el.selectize;
                const out = [];

                if (s.options) {
                    for (const [val, raw] of Object.entries(s.options)) {
                        const v = String(val ?? '');
                        const t = raw?.text || raw?.label || raw?.nome || raw?.name || v;
                        out.push({ value: v, text: String(t) });
                    }
                }

                return out;
            }
            """,
            element_id,
        )
        return opts or []
    except Exception:
        return []


async def set_selectize_value_js(frame, element_id: str, value: str) -> bool:
    """Set value in Selectize via JavaScript API.
    
    Args:
        frame: Playwright frame
        element_id: HTML element ID
        value: Value to set
        
    Returns:
        True if successful, False otherwise
    """
    try:
        success = await frame.evaluate(
            """
            (args) => {
                const { id, value } = args;
                const el = document.getElementById(id);
                if (!el || !el.selectize) return false;

                el.selectize.setValue(String(value), false);

                // Trigger events
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('input', { bubbles: true }));

                return true;
            }
            """,
            {"id": element_id, "value": value},
        )
        return bool(success)
    except Exception:
        return False


async def wait_for_selectize_repopulate(page, element_id: str, timeout_ms: int = 10_000, fallback_ms: int = 500) -> bool:
    """Wait for Selectize dropdown to repopulate with options.
    
    Args:
        page: Playwright page
        element_id: HTML element ID
        timeout_ms: Timeout for wait_for_function in milliseconds
        fallback_ms: Fallback timeout in milliseconds
        
    Returns:
        True if ready, False if fallback was used
    """
    ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            f"() => {{ const el = document.getElementById('{element_id}'); return el?.selectize && Object.keys(el.selectize.options || {{}}).length > 0; }}",
            timeout=timeout_ms
        )
        ready = True
    
    if not ready:
        await page.wait_for_timeout(fallback_ms)
    
    return ready


def filter_placeholder_options(options: list[dict[str, Any]], additional_filters: list[str] | None = None) -> list[dict[str, Any]]:
    """Filter out placeholder and unwanted options.
    
    Args:
        options: List of option dictionaries
        additional_filters: Additional text patterns to filter out (case-insensitive)
        
    Returns:
        Filtered list of options
    """
    filters = ["selecione"]
    if additional_filters:
        filters.extend([f.lower() for f in additional_filters])
    
    # OTIMIZAÇÃO: compilar regex uma vez em vez de O(options * filters) substring checks
    filter_pattern = "|".join(re.escape(f) for f in filters)
    filter_rx = re.compile(filter_pattern, re.I)
    
    return [
        o for o in options
        if o.get("text") and not filter_rx.search(o["text"])
    ]


def create_combo(org_text: str, org_value: str, cargo_text: str = "Todos", cargo_value: str = "Todos",
                 agente_text: str = "Todos", agente_value: str = "Todos") -> dict[str, Any]:
    """Create a combo dictionary.
    
    Args:
        org_text: Organization label
        org_value: Organization value
        cargo_text: Position label
        cargo_value: Position value
        agente_text: Agent label
        agente_value: Agent value
        
    Returns:
        Combo dictionary
    """
    return {
        "orgao_label": org_text,
        "orgao_value": org_value,
        "cargo_label": cargo_text,
        "cargo_value": cargo_value,
        "agente_label": agente_text,
        "agente_value": agente_value,
    }


def build_config_dict(url: str, args, combos: list[dict[str, Any]], stats: dict[str, int]) -> dict[str, Any]:
    """Build final configuration dictionary.
    
    Args:
        url: Source URL
        args: Arguments namespace
        combos: List of combos
        stats: Statistics dictionary
        
    Returns:
        Configuration dictionary
    """
    return {
        "source": "e-agendas",
        "url": url,
        "filters": {
            "select1": getattr(args, "select1", None),
            "pick1": getattr(args, "pick1", None),
            "limit1": getattr(args, "limit1", None),
            "select2": getattr(args, "select2", None),
            "pick2": getattr(args, "pick2", None),
            "limit2": getattr(args, "limit2", None),
            "select3": getattr(args, "select3", None),
            "pick3": getattr(args, "pick3", None),
            "limit3": getattr(args, "limit3", None),
        },
        "combos": combos,
        "stats": {
            "total_orgaos": stats["total_orgaos"],
            "total_cargos": stats["total_cargos"],
            "total_agentes": stats["total_agentes"],
            "total_combos": len(combos),
        },
    }


def save_plan(cfg: dict[str, Any], plan_out: str | None, verbose: bool = False) -> None:
    """Save plan configuration to JSON file.
    
    Args:
        cfg: Configuration dictionary
        plan_out: Output file path
        verbose: Whether to print confirmation message
    """
    if not plan_out:
        return
    
    import json
    
    Path(plan_out).parent.mkdir(parents=True, exist_ok=True)
    Path(plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    
    if verbose:
        print(f"\n[plan-eagendas-async] ✅ Plan salvo: {plan_out}")
