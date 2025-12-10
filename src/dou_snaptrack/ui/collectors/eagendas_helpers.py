"""Helper functions for E-Agendas subprocess collection.

This module contains extracted functions from main() to reduce complexity.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any


def parse_input_and_periodo(input_data: dict[str, Any]) -> tuple[list, date, date]:
    """Parse input data and period.

    Args:
        input_data: Input dictionary

    Returns:
        Tuple of (queries, start_date, end_date)
    """
    queries = input_data.get("queries", [])
    periodo = input_data.get("periodo", {})

    start_date = date.fromisoformat(periodo["inicio"])
    end_date = date.fromisoformat(periodo["fim"])

    return queries, start_date, end_date


def setup_playwright_env():
    """Set up Playwright environment variables."""
    pw_browsers_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "pw-browsers"
    if pw_browsers_path.exists():
        import os
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers_path)


def launch_browser_with_channels(p, launch_args: list[str]):
    """Launch browser trying different channels.

    Args:
        p: Playwright instance
        launch_args: Launch arguments

    Returns:
        Browser instance or None
    """
    for channel in ['chrome', 'msedge']:
        try:
            print(f"[DEBUG] Tentando channel={channel}...", file=sys.stderr)
            browser = p.chromium.launch(channel=channel, headless=True, args=launch_args)
            print(f"[DEBUG] ✓ {channel} (headless) OK", file=sys.stderr)
            return browser
        except Exception as e:
            print(f"[DEBUG] ✗ {channel} falhou: {e}", file=sys.stderr)

    return None


def launch_browser_with_exe_paths(p, launch_args: list[str]):
    """Launch browser with executable paths.

    Args:
        p: Playwright instance
        launch_args: Launch arguments

    Returns:
        Browser instance or None
    """
    exe_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]

    for exe_path in exe_paths:
        if Path(exe_path).exists():
            try:
                browser = p.chromium.launch(executable_path=exe_path, headless=True, args=launch_args)
                print("[DEBUG] ✓ executable_path (headless) OK", file=sys.stderr)
                return browser
            except Exception:
                continue

    return None


def create_browser_context(browser):
    """Create browser context with settings.

    Args:
        browser: Browser instance

    Returns:
        Tuple of (context, page)
    """
    context = browser.new_context(
        ignore_https_errors=True,
        viewport={'width': 1280, 'height': 900},
        permissions=[],
        geolocation=None,
    )
    context.set_default_timeout(60000)
    page = context.new_page()
    return context, page


def wait_for_angular_and_selectize(page, dd_orgao_id: str) -> bool:
    """Wait for AngularJS and Selectize to initialize.

    Args:
        page: Playwright page
        dd_orgao_id: Dropdown orgao ID

    Returns:
        True if successful
    """
    # Wait for AngularJS
    angular_ready_js = "() => document.querySelector('[ng-app]') !== null"
    try:
        page.wait_for_function(angular_ready_js, timeout=5000)
        print("[DEBUG] ✓ AngularJS ready", file=sys.stderr)
    except Exception:
        print("[DEBUG] AngularJS timeout, continuando...", file=sys.stderr)

    # Wait for Selectize
    wait_orgao_js = f"() => {{ const el = document.getElementById('{dd_orgao_id}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}"
    try:
        page.wait_for_function(wait_orgao_js, timeout=20000)
        print("[DEBUG] ✓ Selectize inicializado", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[ERROR] Selectize não inicializou: {e}", file=sys.stderr)
        return False


def select_orgao_and_agente(page, orgao_value: str, orgao_label: str, agente_value: str, agente_label: str, dd_orgao_id: str, dd_agente_id: str, set_selectize_fn) -> bool:
    """Select orgao and agente in dropdowns.

    Args:
        page: Playwright page
        orgao_value: Orgao value
        orgao_label: Orgao label
        agente_value: Agente value
        agente_label: Agente label
        dd_orgao_id: Dropdown orgao ID
        dd_agente_id: Dropdown agente ID
        set_selectize_fn: Function to set selectize value

    Returns:
        True if successful
    """
    # Select orgao
    print(f"[DEBUG] Selecionando órgão: {orgao_label} (ID: {orgao_value})", file=sys.stderr)
    if not set_selectize_fn(page, dd_orgao_id, orgao_value):
        print("[ERROR] Não foi possível selecionar órgão", file=sys.stderr)
        return False

    page.wait_for_timeout(2000)

    # Select agente
    print(f"[DEBUG] Selecionando agente: {agente_label} (ID: {agente_value})", file=sys.stderr)
    if not set_selectize_fn(page, dd_agente_id, agente_value):
        print("[ERROR] Não foi possível selecionar agente", file=sys.stderr)
        return False

    page.wait_for_timeout(2000)
    return True


def click_mostrar_agenda(page) -> bool:
    """Click 'Mostrar agenda' button.

    Args:
        page: Playwright page

    Returns:
        True if successful
    """
    # Remove cookie bar
    try:
        page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
    except Exception:
        pass

    # Click button
    print("[DEBUG] Clicando em 'Mostrar agenda'...", file=sys.stderr)
    try:
        with page.expect_navigation(wait_until='networkidle', timeout=120000):
            page.evaluate("""() => document.querySelector('button[ng-click*="submit"]').click()""")
        print("[DEBUG] ✓ Navegação completa", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[DEBUG] Clique/navegação falhou: {e}", file=sys.stderr)
        page.wait_for_timeout(15000)
        return True  # Continue anyway


def extract_query_info(query: dict[str, Any]) -> tuple[str, str, str, str]:
    """Extract query information.

    Args:
        query: Query dictionary

    Returns:
        Tuple of (agente_label, agente_value, orgao_label, orgao_value)
    """
    agente_label = query.get('n3_label') or query.get('person_label', 'Agente')
    agente_value = query.get('n3_value', '')
    orgao_label = query.get('n1_label', 'Órgão')
    orgao_value = query.get('n1_value', '')
    return agente_label, agente_value, orgao_label, orgao_value
