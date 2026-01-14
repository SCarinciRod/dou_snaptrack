"""
DOU Live Fetch module for SnapTrack UI.

This module provides functions to fetch N1 (Órgão) and N2 (Sub-órgão) dropdown
options from the DOU website using Playwright in subprocess mode.

Uses the same approach as the Nov 19 working version:
- N1: sync_playwright with direct DOM operations
- N2: async_playwright with build_plan_live_async
- Communication: stdout (last line JSON) instead of temp files
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import traceback
from functools import lru_cache
from pathlib import Path

import streamlit as st

from dou_snaptrack.constants import CACHE_TTL_MEDIUM

# Module-level constants
SRC_ROOT = Path(__file__).resolve().parents[2]
CWD_ROOT = str(SRC_ROOT)

# Logger
logger = logging.getLogger("dou_snaptrack.ui.dou_fetch")


def _get_venv_python() -> str:
    """Get the Python executable from the venv if available.

    This ensures we use the venv's Playwright (which has working permissions)
    rather than a global installation that may have permission issues.
    """
    # Check common venv locations relative to SRC_ROOT (which is src/)
    # Project root is one level up from src/
    project_root = SRC_ROOT.parent

    # Try project root .venv first
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)

    # Try src/.venv (less common but possible)
    venv_python = SRC_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)

    # Fallback: check if current executable is from a venv
    if "venv" in sys.executable.lower() or ".venv" in sys.executable.lower():
        return sys.executable

    # Check parent paths for venv
    try:
        exe_path = Path(sys.executable)
        for parent in exe_path.parents:
            venv_candidate = parent / ".venv" / "Scripts" / "python.exe"
            if venv_candidate.exists():
                return str(venv_candidate)
    except Exception:
        pass

    # Last resort: use current executable
    return sys.executable


@lru_cache(maxsize=4)
def find_system_browser_exe() -> str | None:
    """Resolve a system Chrome/Edge executable once and cache the result."""
    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if exe and Path(exe).exists():
        return exe
    prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1", "true", "yes")
    candidates = (
        [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        if prefer_edge
        else [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    )
    for c in candidates:
        if Path(c).exists():
            return c
    return None


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_MEDIUM)
def fetch_n1_options(secao: str, date: str, refresh_token: float = 0.0) -> list[str]:
    """Fetch N1 (Órgão) dropdown options from DOU website.

    Uses subprocess with sync_playwright for direct DOM operations.
    This approach is more reliable than async_playwright with build_plan_live_async.

    Args:
        secao: Section code (e.g., "DO1", "DO2", "DO3")
        date: Date in DD-MM-YYYY format
        refresh_token: Cache busting token (change to force refresh)

    Returns:
        List of N1 option strings
    """
    _ = refresh_token

    logger.info("[N1-SUBPROCESS] Iniciando fetch N1 para secao=%s date=%s", secao, date)

    # Escapar path para Windows (barras invertidas)
    src_path = str(SRC_ROOT).replace("\\", "\\\\")

    # Script usando sync_playwright com operações DOM diretas (abordagem Nov 19)
    # Inclui estratégia de fallback: channel=chrome -> channel=msedge -> executable_path
    script_content = f'''
import sys
import json
import os
import time
from pathlib import Path

# Add src to path
src_root = "{src_path}"
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from dou_snaptrack.cli.plan.live import _collect_dropdown_roots, _read_dropdown_options, _select_roots
from dou_snaptrack.utils.browser import build_dou_url, goto, try_visualizar_em_lista
from dou_snaptrack.utils.dom import find_best_frame
from playwright.sync_api import sync_playwright, TimeoutError


def _pick_ready_frame(context, timeout_s: float = 12.0):
    """Pick the most likely frame containing DOU controls.

    The DOU UI frequently renders dropdowns inside an iframe; if we pick the frame too early
    we may end up on main_frame and fail to detect N1.
    """
    page = context.pages[0]
    deadline = time.time() + max(1.0, float(timeout_s))
    probe_sel = "#slcOrgs, select, [role=combobox], .selectize-input"

    while time.time() < deadline:
        # 1) Best-frame heuristic
        fr = find_best_frame(context)
        try:
            if fr and fr.locator(probe_sel).count() > 0:
                return fr
        except Exception:
            pass

        # 2) Direct scan across frames (more robust)
        for cand in page.frames:
            try:
                if cand.locator(probe_sel).count() > 0:
                    return cand
            except Exception:
                continue

        page.wait_for_timeout(250)

    return find_best_frame(context)

try:
    with sync_playwright() as p:
        browser = None
        # Estratégia de fallback: channel=chrome -> channel=msedge -> executable_path -> default
        try:
            browser = p.chromium.launch(channel='chrome', headless=True)
        except Exception as e1:
            try:
                browser = p.chromium.launch(channel='msedge', headless=True)
            except Exception as e2:
                # Fallback: buscar executável explícito
                exe = os.environ.get('PLAYWRIGHT_CHROME_PATH') or os.environ.get('CHROME_PATH')
                if not exe:
                    for c in (
                        r'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                        r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                        r'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
                        r'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
                    ):
                        if Path(c).exists():
                            exe = c
                            break
                if exe and Path(exe).exists():
                    browser = p.chromium.launch(executable_path=exe, headless=True)
        # Último recurso: tentar launch padrão
        if not browser:
            browser = p.chromium.launch(headless=True)

        context = browser.new_context(ignore_https_errors=True, viewport={{"width": 1366, "height": 900}})
        context.set_default_timeout(90_000)
        page = context.new_page()

        url = build_dou_url("{date}", "{secao}")
        goto(page, url)

        try:
            try_visualizar_em_lista(page)
        except Exception:
            pass

        # Escolher/aguardar o frame correto (DOU costuma renderizar dentro de iframe)
        frame = _pick_ready_frame(context, timeout_s=12.0)

        # Aguarda sinais mínimos de dropdown no frame escolhido (sem depender do main document)
        try:
            frame.wait_for_selector("#slcOrgs, select, [role=combobox], .selectize-input", timeout=8_000)
        except Exception:
            pass

        try:
            r1, _r2 = _select_roots(frame)
        except Exception:
            r1 = None

        if not r1:
            roots = _collect_dropdown_roots(frame)
            r1 = roots[0] if roots else None

        if not r1:
            # Debug info (compact) to help diagnose iframe/layout changes
            try:
                frame_url = frame.url
            except Exception:
                frame_url = None
            try:
                sel_cnt = frame.locator("select").count()
            except Exception:
                sel_cnt = None
            print(
                json.dumps(
                    {{
                        "success": False,
                        "error": "Nenhum dropdown N1 detectado",
                        "debug": {{"frame_url": frame_url, "select_count": sel_cnt}},
                    }}
                )
            )
            context.close()
            browser.close()
            sys.exit(1)

        opts = _read_dropdown_options(frame, r1)

        if not opts:
            print(json.dumps({{"success": False, "error": "Nenhuma opção encontrada no dropdown N1"}}))
            context.close()
            browser.close()
            sys.exit(1)

        texts = []
        for o in opts:
            t = (o.get("text") or "").strip()
            nt = (t or "").strip().lower()
            if not t or nt == "todos" or nt.startswith("selecionar ") or nt.startswith("selecione "):
                continue
            texts.append(t)

        uniq = sorted(set(texts))
        print(json.dumps({{"success": True, "options": uniq}}))

        context.close()
        browser.close()

except TimeoutError as te:
    print(json.dumps({{"success": False, "error": f"Timeout: {{te}}"}}))
    sys.exit(1)
except Exception as e:
    print(json.dumps({{"success": False, "error": f"{{type(e).__name__}}: {{e}}"}}))
    sys.exit(1)
'''

    try:
        logger.info("[N1-SUBPROCESS] Executando script sync_playwright em subprocess...")
        # Executar em subprocess isolado usando Python do venv (evita problemas de permissão)
        python_exe = _get_venv_python()
        logger.debug("[N1-SUBPROCESS] Usando Python: %s", python_exe)
        result = subprocess.run(
            [python_exe, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=CWD_ROOT,
        )

        # Extrair apenas a última linha do stdout (JSON), ignorando logs anteriores
        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        json_line = stdout_lines[-1] if stdout_lines else ""

        logger.info("[N1-SUBPROCESS] Subprocess retornou. returncode=%s", result.returncode)
        if result.stderr:
            logger.debug("[N1-SUBPROCESS] STDERR:\n%s", result.stderr[:1000])

        if result.returncode != 0:
            try:
                error_data = json.loads(json_line)
                logger.error("[N1-SUBPROCESS] Erro: %s", error_data.get("error"))
                st.error(f"[ERRO] {error_data.get('error', 'Erro desconhecido')}")
            except json.JSONDecodeError:
                logger.error("[N1-SUBPROCESS] Falha ao carregar N1. Return code: %s", result.returncode)
                st.error(f"[ERRO] Falha ao carregar N1. Return code: {result.returncode}")
                if result.stderr:
                    st.error(f"STDERR: {result.stderr[:300]}")
            return []

        try:
            data = json.loads(json_line)
        except json.JSONDecodeError as je:
            logger.error("[N1-SUBPROCESS] JSON inválido: %s", je)
            st.error(f"[ERRO] JSON inválido: {je}")
            st.error(f"Saída completa: {result.stdout[:500]}")
            return []

        if data.get("success"):
            opts = data.get("options", [])
            logger.info("[N1-SUBPROCESS] Sucesso! %s opções retornadas", len(opts))
            return opts
        else:
            logger.error("[N1-SUBPROCESS] Erro retornado: %s", data.get("error"))
            st.error(f"[ERRO] {data.get('error', 'Erro desconhecido')}")
            return []

    except subprocess.TimeoutExpired:
        logger.error("[N1-SUBPROCESS] Timeout!")
        st.error("[ERRO] Timeout ao carregar opções N1 (>2 minutos)")
        return []
    except Exception as exc:
        logger.exception("[N1-SUBPROCESS] Exceção ao executar subprocess")
        st.error(f"[ERRO] Falha ao executar subprocess de N1: {type(exc).__name__}: {exc}")
        st.error(f"Traceback: {traceback.format_exc()[:500]}")
        return []


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_MEDIUM)
def fetch_n2_options(secao: str, date: str, n1: str, limit2: int | None = None, refresh_token: float = 0.0) -> list[str]:
    """Fetch N2 (Sub-órgão) dropdown options from DOU website.

    Uses subprocess with async_playwright via build_plan_live_async.
    Communication via stdout (last line JSON) for reliability.

    Args:
        secao: Section code (e.g., "DO1", "DO2", "DO3")
        date: Date in DD-MM-YYYY format
        n1: Selected N1 (Órgão) value
        limit2: Optional limit on N2 results (None = no limit)
        refresh_token: Cache busting token (change to force refresh)

    Returns:
        List of N2 option strings
    """
    _ = refresh_token

    logger.info("[N2-SUBPROCESS] Iniciando fetch N2 para secao=%s date=%s n1=%s", secao, date, n1)

    # Se limit2 é None, não aplicar corte
    _limit2_int = None if limit2 in (None, 0) else int(limit2)
    _limit2_literal = "None" if _limit2_int is None else str(_limit2_int)

    # Script usando sync_playwright: seleciona somente o N1 escolhido e lê N2
    # (muito mais rápido do que gerar combos via build_plan_live_async)
    src_path = str(SRC_ROOT).replace("\\", "\\\\")
    _n1_literal = json.dumps(str(n1), ensure_ascii=False)

    script_content = f'''
import sys
import json
import os
import time
from pathlib import Path

src_root = "{src_path}"
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from dou_snaptrack.cli.plan.live import _collect_dropdown_roots, _read_dropdown_options, _select_by_text, _select_roots
from dou_snaptrack.utils.browser import build_dou_url, goto, try_visualizar_em_lista
from dou_snaptrack.utils.dom import find_best_frame, is_select, read_select_options
from playwright.sync_api import sync_playwright, TimeoutError


def _pick_ready_frame(context, timeout_s: float = 12.0):
    page = context.pages[0]
    deadline = time.time() + max(1.0, float(timeout_s))
    probe_sel = "#slcOrgs, #slcOrgsSubs, select, [role=combobox], .selectize-input"
    while time.time() < deadline:
        fr = find_best_frame(context)
        try:
            if fr and fr.locator(probe_sel).count() > 0:
                return fr
        except Exception:
            pass
        for cand in page.frames:
            try:
                if cand.locator(probe_sel).count() > 0:
                    return cand
            except Exception:
                continue
        page.wait_for_timeout(250)
    return find_best_frame(context)


def _filter_texts(opts):
    texts = []
    for o in opts or []:
        t = (o.get("text") or "").strip()
        nt = t.lower().strip()
        if not t or nt == "todos" or nt.startswith("selecionar ") or nt.startswith("selecione "):
            continue
        texts.append(t)
    return texts


def _wait_n2_ready(frame, r2, timeout_ms: int = 15_000):
    start = time.time()
    h = r2.get("handle") if r2 else None
    if not h:
        return

    # Native <select>: wait for options length to be > 1 (typically includes placeholder)
    if is_select(h):
        while (time.time() - start) * 1000 < timeout_ms:
            try:
                cur = len(read_select_options(h) or [])
                if cur >= 2:
                    return
            except Exception:
                pass
            frame.page.wait_for_timeout(200)
        return

    # Custom dropdown: open and wait until at least 1 option is visible
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            # Try to read options using robust helper
            # This helper handles open -> wait -> read -> close (escape) sequence
            current = _read_dropdown_options(frame, r2)
            valid = _filter_texts(current)
            
            # If we found valid options (not just "Selecione..."), we are ready
            if len(valid) >= 1:
                return
        except Exception:
            pass
        
        # Wait before retrying
        frame.page.wait_for_timeout(500)


try:
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(channel='chrome', headless=True)
        except Exception:
            try:
                browser = p.chromium.launch(channel='msedge', headless=True)
            except Exception:
                exe = os.environ.get('PLAYWRIGHT_CHROME_PATH') or os.environ.get('CHROME_PATH')
                if not exe:
                    for c in (
                        r'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                        r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                        r'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
                        r'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
                    ):
                        if Path(c).exists():
                            exe = c
                            break
                if exe and Path(exe).exists():
                    browser = p.chromium.launch(executable_path=exe, headless=True)

        if not browser:
            browser = p.chromium.launch(headless=True)

        context = browser.new_context(ignore_https_errors=True, viewport={{"width": 1366, "height": 900}})
        context.set_default_timeout(90_000)
        page = context.new_page()

        url = build_dou_url("{date}", "{secao}")
        goto(page, url)
        try:
            try_visualizar_em_lista(page)
        except Exception:
            pass

        frame = _pick_ready_frame(context, timeout_s=12.0)
        try:
            frame.wait_for_selector("#slcOrgs, #slcOrgsSubs, select, [role=combobox], .selectize-input", timeout=8_000)
        except Exception:
            pass

        r1, r2 = None, None
        try:
            r1, r2 = _select_roots(frame)
        except Exception:
            r1, r2 = None, None
        if not r1 or not r2:
            roots = _collect_dropdown_roots(frame)
            r1 = r1 or (roots[0] if roots else None)
            r2 = r2 or (roots[1] if roots and len(roots) > 1 else None)

        if not r1:
            print(json.dumps({{"success": False, "error": "Dropdown N1 não encontrado"}}))
            context.close(); browser.close(); sys.exit(1)
        if not r2:
            print(json.dumps({{"success": False, "error": "Dropdown N2 não encontrado"}}))
            context.close(); browser.close(); sys.exit(1)

        n1_text = {_n1_literal}
        if not _select_by_text(frame, r1, n1_text):
            print(json.dumps({{"success": False, "error": "Falha ao selecionar N1"}}))
            context.close(); browser.close(); sys.exit(1)

        # Re-resolve roots after selection (DOM may re-render)
        try:
            _r1b, r2b = _select_roots(frame)
            if r2b:
                r2 = r2b
        except Exception:
            pass

        _wait_n2_ready(frame, r2, timeout_ms=15_000)

        # Read N2 options
        opts = _read_dropdown_options(frame, r2)
        texts = _filter_texts(opts)
        uniq = sorted(set(texts))
        limit2 = {_limit2_literal}
        if isinstance(limit2, int) and limit2 > 0:
            uniq = uniq[:limit2]

        print(json.dumps({{"success": True, "options": uniq}}))
        context.close(); browser.close()

except TimeoutError as te:
    print(json.dumps({{"success": False, "error": f"Timeout: {{te}}"}}))
    sys.exit(1)
except Exception as e:
    print(json.dumps({{"success": False, "error": f"{{type(e).__name__}}: {{e}}"}}))
    sys.exit(1)
'''

    try:
        logger.info("[N2-SUBPROCESS] Executando script async_playwright em subprocess...")
        # Usar Python do venv (evita problemas de permissão com Playwright global)
        python_exe = _get_venv_python()
        logger.debug("[N2-SUBPROCESS] Usando Python: %s", python_exe)
        result = subprocess.run(
            [python_exe, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=CWD_ROOT,
        )

        # Extrair apenas a última linha do stdout (JSON), ignorando logs anteriores
        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        json_line = stdout_lines[-1] if stdout_lines else ""

        logger.info("[N2-SUBPROCESS] Subprocess retornou. returncode=%s", result.returncode)
        if result.stderr:
            logger.debug("[N2-SUBPROCESS] STDERR:\n%s", result.stderr[:1000])

        if result.returncode != 0:
            try:
                error_data = json.loads(json_line)
                logger.error("[N2-SUBPROCESS] Erro: %s", error_data.get("error"))
                st.error(f"[ERRO] {error_data.get('error', 'Erro desconhecido')}")
            except json.JSONDecodeError:
                logger.error("[N2-SUBPROCESS] Falha ao carregar N2. Return code: %s", result.returncode)
                st.error(f"[ERRO] Falha ao carregar N2. Return code: {result.returncode}")
                if result.stderr:
                    st.error(f"STDERR: {result.stderr[:300]}")
            return []

        try:
            data = json.loads(json_line)
        except json.JSONDecodeError as je:
            logger.error("[N2-SUBPROCESS] JSON inválido: %s", je)
            st.error(f"[ERRO] JSON inválido: {je}")
            st.error(f"Saída completa: {result.stdout[:500]}")
            return []

        if data.get("success"):
            opts = data.get("options", [])
            logger.info("[N2-SUBPROCESS] Sucesso! %s opções retornadas", len(opts))
            return opts
        else:
            logger.error("[N2-SUBPROCESS] Erro retornado: %s", data.get("error"))
            st.error(f"[ERRO] {data.get('error', 'Erro desconhecido')}")
            return []

    except subprocess.TimeoutExpired:
        logger.error("[N2-SUBPROCESS] Timeout!")
        st.error("[ERRO] Timeout ao carregar opções N2 (>2 minutos)")
        return []
    except Exception as exc:
        logger.exception("[N2-SUBPROCESS] Exceção ao executar subprocess")
        st.error(f"[ERRO] Falha ao executar subprocess de N2: {type(exc).__name__}: {exc}")
        st.error(f"Traceback: {traceback.format_exc()[:500]}")
        return []


# Backward compatibility aliases
_plan_live_fetch_n1_options = fetch_n1_options
_plan_live_fetch_n2 = fetch_n2_options
_find_system_browser_exe = find_system_browser_exe
