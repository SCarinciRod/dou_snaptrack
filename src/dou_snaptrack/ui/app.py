from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import time
import traceback  # Certificar que está no escopo global
from dataclasses import dataclass
from datetime import date as _date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

# Garantir que a pasta src/ esteja no PYTHONPATH (execução via streamlit run src/...)
SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# OTIMIZAÇÃO: Lazy imports - só carrega quando necessário
# Streamlit é leve, pode carregar logo

# OTIMIZAÇÃO: Imports pesados apenas quando TYPE_CHECKING ou sob demanda
if TYPE_CHECKING:
    pass


# Funções lazy loading para imports pesados
def _lazy_import_batch_runner():
    """Lazy import do batch_runner (importa Playwright)."""
    from dou_snaptrack.ui.batch_runner import (
        clear_ui_lock,
        detect_other_execution,
        detect_other_ui,
        register_this_ui_instance,
        terminate_other_execution,
    )

    return {
        "clear_ui_lock": clear_ui_lock,
        "detect_other_execution": detect_other_execution,
        "detect_other_ui": detect_other_ui,
        "register_this_ui_instance": register_this_ui_instance,
        "terminate_other_execution": terminate_other_execution,
    }


def _lazy_import_text():
    """Lazy import de utils.text."""
    from dou_snaptrack.utils.text import sanitize_filename

    return sanitize_filename


# Cache de lazy imports para evitar reimport
_BATCH_RUNNER_CACHE = None
_SANITIZE_FILENAME_CACHE = None


def get_batch_runner():
    """Retorna batch_runner (cached)."""
    global _BATCH_RUNNER_CACHE
    if _BATCH_RUNNER_CACHE is None:
        _BATCH_RUNNER_CACHE = _lazy_import_batch_runner()
    return _BATCH_RUNNER_CACHE


def get_sanitize_filename():
    """Retorna sanitize_filename (cached)."""
    global _SANITIZE_FILENAME_CACHE
    if _SANITIZE_FILENAME_CACHE is None:
        _SANITIZE_FILENAME_CACHE = _lazy_import_text()
    return _SANITIZE_FILENAME_CACHE


# Cache para módulos e-agendas
_PLAN_LIVE_EAGENDAS_CACHE = None
_EAGENDAS_CALENDAR_CACHE = None


def _resolve_combo_label(combo: dict[str, Any], label_field: str, key_field: str) -> str:
    """Resolve o texto exibido no editor evitando strings vazias do arquivo."""
    value = combo.get(label_field)
    if not value:
        value = combo.get(key_field)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


@lru_cache(maxsize=128)
def _plan_metadata(path_str: str, stamp: float | None) -> dict[str, Any]:
    """Extrai metadados leves de um plano para evitar reprocessar JSON a cada rerun."""
    # stamp participa apenas da chave do cache para invalidar quando o arquivo muda
    _ = stamp
    path = Path(path_str)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"path": path_str, "stem": path.stem, "combos": 0, "data": None, "secao": None}

    combos = cfg.get("combos") or []
    return {
        "path": path_str,
        "stem": path.stem,
        "combos": len(combos),
        "data": cfg.get("data"),
        "secao": cfg.get("secaoDefault"),
    }


@st.cache_data(show_spinner=False, ttl=30)
def _list_saved_plan_files(refresh_token: float = 0.0) -> list[dict[str, Any]]:
    """Lista planos salvos com cache curto para evitar travamento por I/O repetido."""
    plans_dir = Path("planos")
    if not plans_dir.exists():
        return []

    entries: list[dict[str, Any]] = []
    for plan_path in plans_dir.glob("*.json"):
        with contextlib.suppress(Exception):
            stat = plan_path.stat()
            meta = _plan_metadata(str(plan_path), stat.st_mtime)
            meta["mtime"] = stat.st_mtime
            meta["size_kb"] = round(stat.st_size / 1024, 1)
            entries.append(meta)

    entries.sort(key=lambda item: item["stem"].lower())
    return entries


def _lazy_import_plan_live_eagendas():
    """Lazy import do módulo plan_live_eagendas_async."""
    from dou_snaptrack.cli import plan_live_eagendas_async

    return plan_live_eagendas_async


def _lazy_import_eagendas_calendar():
    """Lazy import do módulo eagendas_calendar."""
    from dou_snaptrack.utils import eagendas_calendar

    return eagendas_calendar


def get_plan_live_eagendas():
    """Retorna plan_live_eagendas_async module (cached)."""
    global _PLAN_LIVE_EAGENDAS_CACHE
    if _PLAN_LIVE_EAGENDAS_CACHE is None:
        _PLAN_LIVE_EAGENDAS_CACHE = _lazy_import_plan_live_eagendas()
    return _PLAN_LIVE_EAGENDAS_CACHE


def get_eagendas_calendar():
    """Retorna eagendas_calendar module (cached)."""
    global _EAGENDAS_CALENDAR_CACHE
    if _EAGENDAS_CALENDAR_CACHE is None:
        _EAGENDAS_CALENDAR_CACHE = _lazy_import_eagendas_calendar()
    return _EAGENDAS_CALENDAR_CACHE


# ---------------- Helpers ----------------
# CORREÇÃO CRÍTICA: NÃO configurar asyncio no topo do módulo!
# Streamlit gerencia seu próprio event loop e configurá-lo aqui causa conflito:
# "Error: It looks like you are using Playwright Sync API inside the asyncio loop"
# A configuração agora é feita APENAS dentro de threads que precisam de Playwright.
# Ref: https://github.com/microsoft/playwright-python/issues/178


@dataclass
class PlanState:
    date: str
    secao: str
    combos: list[dict[str, Any]]
    defaults: dict[str, Any]


@dataclass
class EAgendasState:
    """Estado da tab E-Agendas."""

    saved_queries: list[
        dict[str, Any]
    ]  # Lista de queries salvas: [{n1_label, n1_value, n2_label, n2_value, n3_label, n3_value, person_label}]
    current_n1: str | None
    current_n2: str | None
    current_n3: str | None
    date_start: str  # Formato DD-MM-YYYY
    date_end: str  # Formato DD-MM-YYYY


def _ensure_state():
    # OTIMIZAÇÃO: Lazy directory creation - apenas cria quando necessário
    # (evita I/O no startup se pastas já existem)
    if "plan" not in st.session_state:
        st.session_state.plan = PlanState(
            date=_date.today().strftime("%d-%m-%Y"),
            secao="DO1",
            combos=[],
            defaults={
                "scrape_detail": False,
                "summary_lines": 0,
                "summary_mode": "center",
            },
        )


def _ensure_eagendas_state():
    """Garante que o estado da tab E-Agendas está inicializado."""
    if "eagendas" not in st.session_state:
        st.session_state.eagendas = EAgendasState(
            saved_queries=[],
            current_n1=None,
            current_n2=None,
            current_n3=None,
            date_start=_date.today().strftime("%d-%m-%Y"),
            date_end=_date.today().strftime("%d-%m-%Y"),
        )


def _ensure_dirs():
    """Cria diretórios base apenas quando necessário (lazy)."""
    PLANS_DIR = Path("planos")
    RESULTS_DIR = Path("resultados")
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return PLANS_DIR, RESULTS_DIR


def _load_pairs_file(p: Path) -> dict[str, list[str]]:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Espera formato {"pairs": {"N1": ["N2", ...]}}
        pairs = data.get("pairs") or {}
        if isinstance(pairs, dict):
            norm: dict[str, list[str]] = {}
            for k, v in pairs.items():
                if isinstance(v, list):
                    norm[str(k)] = [str(x) for x in v]
            return norm
    except Exception:
        pass
    return {}


@lru_cache(maxsize=4)  # Cobre múltiplas versões (Edge/Chrome 32/64-bit)
def _find_system_browser_exe() -> str | None:
    """Resolve a system Chrome/Edge executable once and cache the result."""
    from pathlib import Path as _P

    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if exe and _P(exe).exists():
        return exe
    prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1", "true", "yes")
    candidates = (
        [
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
        if prefer_edge
        else [
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
    )
    for c in candidates:
        if _P(c).exists():
            return c
    return None


@st.cache_data(show_spinner=False, ttl=3600)  # Cache por 1 hora - previne dados obsoletos
def _load_pairs_file_cached(path_str: str) -> dict[str, list[str]]:
    """Cached wrapper around _load_pairs_file for UI flows."""
    try:
        return _load_pairs_file(Path(path_str))
    except Exception:
        return {}


def _build_combos(n1: str, n2_list: list[str], key_type: str = "text") -> list[dict[str, Any]]:
    return [
        {
            "key1_type": key_type,
            "key1": n1,
            "key2_type": key_type,
            "key2": n2,
            "key3_type": None,
            "key3": None,
            "label1": n1,  # Usar key como label inicial (usuário pode editar depois)
            "label2": n2,  # Usar key como label inicial
            "label3": "",
        }
        for n2 in n2_list
    ]


# REMOVIDO: _get_thread_local_playwright_and_browser() - não mais necessário após migração para async API


@st.cache_data(show_spinner=False, ttl=300)
def _plan_live_fetch_n2(secao: str, date: str, n1: str, limit2: int | None = None) -> list[str]:
    """Descobre as opções do dropdown N2 diretamente do site (como no combo do DOU).

    Ajuste: limit2 padrão agora é None para evitar truncar lista de N2 (antes 20).
    Se quiser limitar por performance, passe explicitamente um inteiro.
    """
    import json
    import re
    import subprocess
    import sys
    from pathlib import Path

    # Se limit2 é None, passar literal None (não aplicar corte no builder)
    _limit2_literal = "None" if limit2 in (None, 0) else str(int(limit2))

    # IMPORTANTE: quando N1 contém vírgulas (ex.: "Ministério da Ciência, Tecnologia e Inovação"),
    # usar select1 com regex ancorada para evitar split por vírgula em pick1.
    _select1_pattern = "^" + re.escape(str(n1)) + "$"
    _select1_literal = json.dumps(_select1_pattern, ensure_ascii=False)

    script_content = f'''
import json
import sys
from playwright.async_api import async_playwright
from types import SimpleNamespace
from dou_snaptrack.cli.plan_live_async import build_plan_live_async

try:
    async def fetch_n2_options():
        async with async_playwright() as p:
            args = SimpleNamespace(
                secao="{secao}",
                data="{date}",
                plan_out=None,
                select1={_select1_literal},
                select2=None,
                pick1=None,
                pick2=None,
                limit1=None,
                limit2={_limit2_literal},
                headless=True,
                slowmo=0,
            )

            cfg = await build_plan_live_async(p, args)
            combos = cfg.get("combos", [])
            n2_set = set()
            for c in combos:
                k1 = c.get("key1")
                k2 = c.get("key2")
                if k1 == "{n1}" and k2 and k2 != "Todos":
                    n2_set.add(k2)
            return sorted(n2_set)

    import asyncio
    result = asyncio.run(fetch_n2_options())
    print(json.dumps({{"success": True, "options": result}}))
except Exception as e:
    print(json.dumps({{"error": f"{{type(e).__name__}}: {{e}}"}}))
    sys.exit(1)
'''

    try:
        result = subprocess.run(
            [sys.executable, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent),  # Raiz do projeto
        )

        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        json_line = stdout_lines[-1] if stdout_lines else ""

        if result.returncode != 0:
            try:
                error_data = json.loads(json_line)
                st.error(f"[ERRO] {error_data.get('error', 'Erro desconhecido')}")
            except json.JSONDecodeError:
                st.error(f"[ERRO] Falha ao carregar N2. Return code: {result.returncode}")
                if result.stderr:
                    st.error(f"STDERR: {result.stderr[:300]}")
            return []

        try:
            data = json.loads(json_line)
        except json.JSONDecodeError as je:
            st.error(f"[ERRO] JSON inválido: {je}")
            st.error(f"Saída completa: {result.stdout[:500]}")
            return []

        if data.get("success"):
            return data.get("options", [])
        else:
            st.error(f"[ERRO] {data.get('error', 'Erro desconhecido')}")
            return []

    except subprocess.TimeoutExpired:
        st.error("[ERRO] Timeout ao carregar opções N2 (>2 minutos)")
        return []
    except Exception as e:
        st.error(f"[ERRO] Falha ao executar subprocess: {type(e).__name__}: {e}")
        st.error(f"Traceback: {traceback.format_exc()[:500]}")
        return []


def _plan_live_fetch_n1_options_worker(secao: str, date: str) -> list[str]:
    """Worker que usa async API do Playwright - compatível com asyncio loop do Streamlit.
    MIGRAÇÃO ASYNC: Usa playwright.async_api + asyncio.run() para evitar conflito.
    """
    import asyncio
    import traceback

    try:

        async def fetch_n1_options():
            from playwright.async_api import TimeoutError, async_playwright  # type: ignore

            from dou_snaptrack.cli.plan_live_async import (  # type: ignore
                _collect_dropdown_roots_async,
                _read_dropdown_options_async,
                _select_roots_async,
            )
            from dou_snaptrack.utils.browser import build_dou_url, goto_async, try_visualizar_em_lista_async
            from dou_snaptrack.utils.dom import find_best_frame_async

            async with async_playwright() as p:
                browser = await p.chromium.launch(channel="chrome", headless=True)
                try:
                    context = await browser.new_context(
                        ignore_https_errors=True, viewport={"width": 1366, "height": 900}
                    )
                    context.set_default_timeout(90_000)
                    page = await context.new_page()
                    url = build_dou_url(date, secao)
                    await goto_async(page, url)
                    with contextlib.suppress(Exception):
                        await try_visualizar_em_lista_async(page)
                    frame = await find_best_frame_async(context)
                    with contextlib.suppress(Exception):
                        await page.wait_for_timeout(3000)
                    try:
                        r1, _r2 = await _select_roots_async(frame)
                    except Exception:
                        r1 = None
                    if not r1:
                        roots = await _collect_dropdown_roots_async(frame)
                        r1 = roots[0] if roots else None
                    if not r1:
                        return []
                    opts = await _read_dropdown_options_async(frame, r1)
                    if not opts:
                        return []
                    texts = []
                    for o in opts:
                        t = (o.get("text") or "").strip()
                        nt = (t or "").strip().lower()
                        if not t or nt == "todos" or nt.startswith("selecionar ") or nt.startswith("selecione "):
                            continue
                        texts.append(t)
                    uniq = sorted(set(texts))
                    return uniq
                except TimeoutError as te:
                    st.error(f"[ERRO] Timeout ao tentar carregar opções N1 ({te}).")
                    st.warning("⏱️ O site do DOU pode estar lento. Tente novamente em alguns segundos.")
                    return []
                except Exception as e:
                    tb = traceback.format_exc(limit=4)
                    st.error(f"[ERRO] Falha ao listar N1: {type(e).__name__}: {e}\n\n{tb}")
                    return []
                finally:
                    with contextlib.suppress(Exception):
                        await context.close()
                    with contextlib.suppress(Exception):
                        await browser.close()

        # Executar função async
        return asyncio.run(fetch_n1_options())

    except Exception as e:
        tb = traceback.format_exc(limit=4)
        st.error(f"[ERRO] Falha Playwright/UI: {type(e).__name__}: {e}\n\n{tb}")
        return []


@st.cache_data(show_spinner=False, ttl=300)
def _plan_live_fetch_n1_options(secao: str, date: str) -> list[str]:
    """Descobre as opções do dropdown N1 diretamente do site (como no combo do DOU).

    CORREÇÃO: Executa worker em thread separada para evitar conflito com asyncio loop do Streamlit.
    A thread cria um novo process isolado sem loop asyncio.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    try:
        # Criar script temporário para executar em processo isolado
        src_path = str(SRC_ROOT / "src").replace("\\", "\\\\")  # Escapar barras para Windows

        script_content = f'''
import sys

# Add src to path (passado como literal porque __file__ não existe em python -c)
src_root = "{src_path}"
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from dou_snaptrack.cli.plan_live import _collect_dropdown_roots, _read_dropdown_options, _select_roots
from dou_snaptrack.utils.browser import build_dou_url, goto, try_visualizar_em_lista
from dou_snaptrack.utils.dom import find_best_frame
from playwright.sync_api import sync_playwright, TimeoutError
import json

try:
    with sync_playwright() as p:
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

        frame = find_best_frame(context)
        page.wait_for_timeout(3000)

        try:
            r1, _r2 = _select_roots(frame)
        except Exception:
            r1 = None

        if not r1:
            roots = _collect_dropdown_roots(frame)
            r1 = roots[0] if roots else None

        if not r1:
            print(json.dumps({{"error": "Nenhum dropdown N1 detectado"}}))
            sys.exit(1)

        opts = _read_dropdown_options(frame, r1)

        if not opts:
            print(json.dumps({{"error": "Nenhuma opção encontrada no dropdown N1"}}))
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
    print(json.dumps({{"error": f"Timeout: {{te}}"}}))
    sys.exit(1)
except Exception as e:
    print(json.dumps({{"error": f"{{type(e).__name__}}: {{e}}"}}))
    sys.exit(1)
'''

        # Executar em subprocess isolado (sem asyncio loop)
        result = subprocess.run(
            [sys.executable, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent),  # Raiz do projeto
        )

        # Extrair apenas a última linha do stdout (JSON), ignorando logs anteriores
        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        json_line = stdout_lines[-1] if stdout_lines else ""

        if result.returncode != 0:
            try:
                error_data = json.loads(json_line)
                st.error(f"[ERRO] {error_data.get('error', 'Erro desconhecido')}")
            except json.JSONDecodeError:
                st.error(f"[ERRO] Falha ao carregar N1. Return code: {result.returncode}")
                if result.stderr:
                    st.error(f"STDERR: {result.stderr[:300]}")
            return []

        try:
            data = json.loads(json_line)
        except json.JSONDecodeError as je:
            st.error(f"[ERRO] JSON inválido: {je}")
            st.error(f"Saída completa: {result.stdout[:500]}")
            return []

        if data.get("success"):
            return data.get("options", [])
        else:
            st.error(f"[ERRO] {data.get('error', 'Erro desconhecido')}")
            return []

    except subprocess.TimeoutExpired:
        st.error("[ERRO] Timeout ao carregar opções N1 (>2 minutos)")
        return []
    except Exception as e:
        st.error(f"[ERRO] Falha ao executar subprocess: {type(e).__name__}: {e}")
        st.error(f"Traceback: {traceback.format_exc()[:500]}")
        return []
    return []  # Garantir retorno de lista em todos os caminhos


# ======================== E-AGENDAS: Funções de Fetch ========================


@st.cache_data(show_spinner=False, ttl=600)
def _eagendas_fetch_hierarchy(
    level: int = 1, n1_value: str | None = None, n2_value: str | None = None
) -> dict[str, Any]:
    """Busca opções de N1, N2 ou N3 do E-Agendas usando build_plan_eagendas_async.
    IMPLEMENTAÇÃO LEVE: Em vez de construir plano completo (antes chamava build_plan_eagendas_async,
    causando demora >3min), abrir a página, acessar diretamente a API JavaScript do Selectize e ler opções.

    Args:
        level: 1=Órgãos, 2=Cargos, 3=Agentes
        n1_value: Value do órgão (para level 2 e 3)
        n2_value: Value do cargo (para level 3)

    Returns:
        dict: {"success": bool, "options": [{"label","value"}], "error": str}
    """
    import json
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    if level not in (1, 2, 3):
        return {"success": False, "options": [], "error": f"Level inválido: {level}"}
    if level >= 2 and not n1_value:
        return {"success": False, "options": [], "error": "N1 value necessário"}
    if level == 3 and (not n1_value or not n2_value):
        return {"success": False, "options": [], "error": "N1 e N2 values necessários"}

    # IDs fixos dos elementos Selectize (documentados em plan_live_eagendas_async)
    DD_ORGAO_ID = "filtro_orgao_entidade"
    DD_CARGO_ID = "filtro_cargo"
    DD_AGENTE_ID = "filtro_servidor"

    # SRC_ROOT já aponta para C:\Projetos, não adicionar /src novamente
    src_path = str(SRC_ROOT).replace("\\", "\\\\")

    # Script isolado usando Playwright SYNC (evita PermissionError no Windows subprocess)
    script_parts = [
        "import sys, json, os",
        f"src_root = '{src_path}'",
        "if src_root not in sys.path: sys.path.insert(0, src_root)",
        "# DEBUG: Verificar ambiente",
        "print(f'[ENV] PLAYWRIGHT_BROWSERS_PATH={os.environ.get(\"PLAYWRIGHT_BROWSERS_PATH\", \"NOT_SET\")}', file=sys.stderr, flush=True)",
        "print(f'[ENV] src_root={src_root}', file=sys.stderr, flush=True)",
        "from playwright.sync_api import sync_playwright",
        "from pathlib import Path",
        f"DD_ORGAO_ID = '{DD_ORGAO_ID}'",
        f"DD_CARGO_ID = '{DD_CARGO_ID}'",
        f"DD_AGENTE_ID = '{DD_AGENTE_ID}'",
        f"LEVEL = {level}",
        f"N1V = {json.dumps(n1_value or '')}",
        f"N2V = {json.dumps(n2_value or '')}",
        # JavaScript evaluation helpers
        "def get_selectize_options(page, element_id: str):\n    return page.evaluate(\"(id) => {\\n        const el = document.getElementById(id);\\n        if (!el || !el.selectize) return [];\\n        const s = el.selectize;\\n        const out = [];\\n        const opts = s.options || {};\\n        for (const [val, raw] of Object.entries(opts)) {\\n            const v = String(val ?? '');\\n            const t = (raw && (raw.text || raw.label || raw.nome || raw.name)) || v;\\n            if (!t) continue;\\n            out.push({ value: v, text: String(t) });\\n        }\\n        return out;\\n    }\", element_id)",
        "def set_selectize_value(page, element_id: str, value: str):\n    return page.evaluate(\"(args) => {\\n        const { id, value } = args;\\n        const el = document.getElementById(id);\\n        if (!el || !el.selectize) return false;\\n        el.selectize.setValue(String(value), false);\\n        el.dispatchEvent(new Event('change', { bubbles: true }));\\n        el.dispatchEvent(new Event('input', { bubbles: true }));\\n        return true;\\n    }\", { 'id': element_id, 'value': value })",
        """def main():
    import sys
    import os
    from pathlib import Path
    import time
    diagnostics = {'console_errors': [], 'network_errors': [], 'dom_checks': {}}
    with sync_playwright() as p:
        browser = None
        # Usar mesma estratégia do plan_live_async.py: tentar channels primeiro, depois fallback para executável
        try:
            print('[DEBUG] Tentando channel=chrome...', file=sys.stderr, flush=True)
            browser = p.chromium.launch(channel='chrome', headless=True)
            print('[DEBUG] ✓ channel=chrome OK', file=sys.stderr, flush=True)
        except Exception as e1:
            print(f'[DEBUG] ✗ channel=chrome falhou: {e1}', file=sys.stderr, flush=True)
            try:
                print('[DEBUG] Tentando channel=msedge...', file=sys.stderr, flush=True)
                browser = p.chromium.launch(channel='msedge', headless=True)
                print('[DEBUG] ✓ channel=msedge OK', file=sys.stderr, flush=True)
            except Exception as e2:
                print(f'[DEBUG] ✗ channel=msedge falhou: {e2}', file=sys.stderr, flush=True)
                # Fallback: buscar executável explícito (evita PermissionError em ambientes restritos)
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
                    print(f'[DEBUG] Tentando executable_path={exe}...', file=sys.stderr, flush=True)
                    browser = p.chromium.launch(executable_path=exe, headless=True)
                    print(f'[DEBUG] ✓ executable_path OK', file=sys.stderr, flush=True)
        # Se ainda não conseguiu, tentar download padrão (último recurso)
        if not browser:
            print('[DEBUG] Tentando launch padrão...', file=sys.stderr, flush=True)
            browser = p.chromium.launch(headless=True)
            print('[DEBUG] ✓ launch padrão OK', file=sys.stderr, flush=True)
        context = browser.new_context(ignore_https_errors=True, viewport={'width':1280,'height':900})
        context.set_default_timeout(60000)
        page = context.new_page()
        page.on('console', lambda msg: diagnostics['console_errors'].append(msg.text) if msg.type in ['error','warning'] else None)
        page.on('requestfailed', lambda req: diagnostics['network_errors'].append(req.url))
        print('[DEBUG] Navegando para eagendas.cgu.gov.br...', file=sys.stderr, flush=True)
        page.goto('https://eagendas.cgu.gov.br/', wait_until='domcontentloaded')
        print('[DEBUG] Página carregada, verificando DOM...', file=sys.stderr, flush=True)
        diagnostics['dom_checks']['element_exists'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')")
        diagnostics['dom_checks']['has_selectize_class'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')?.classList.contains('selectized')")
        diagnostics['dom_checks']['selectize_obj'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')?.selectize")
        try:
            print('[DEBUG] Aguardando selectize inicializar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return !!(el && el.selectize); }}", timeout=20000)
            print('[DEBUG] ✓ Selectize inicializado', file=sys.stderr, flush=True)
        except Exception as e:
            diagnostics['wait_error'] = str(e)
            print(f'[DEBUG] ✗ Selectize não inicializou: {e}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return []
        if LEVEL == 1:
            print('[DEBUG] Esperando selectize com >5 opções...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}", timeout=15000)
            print('[DEBUG] Wait concluído, lendo options_count...', file=sys.stderr, flush=True)
            options_count = page.evaluate(f"Object.keys(document.getElementById('{DD_ORGAO_ID}')?.selectize?.options || {{}}).length")
            diagnostics['dom_checks']['options_count'] = options_count
            print(f'[DEBUG] options_count={options_count}, chamando get_selectize_options...', file=sys.stderr, flush=True)
            orgs = get_selectize_options(page, DD_ORGAO_ID)
            print(f'[DEBUG] get_selectize_options retornou {len(orgs)} items', file=sys.stderr, flush=True)
            out = [o for o in orgs if 'selecione' not in o['text'].lower()]
            diagnostics['result_count'] = len(out)
            diagnostics['raw_orgs_sample'] = orgs[:3] if orgs else []
            if len(out) == 0:
                diagnostics['screenshot'] = page.screenshot(type='png', full_page=False)
            print(f'[DIAG] {json.dumps(diagnostics, default=str, ensure_ascii=False)}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return out
        print(f'[DEBUG] Selecionando N1={N1V}...', file=sys.stderr, flush=True)
        set_selectize_value(page, DD_ORGAO_ID, N1V)
        page.wait_for_timeout(1000)
        try:
            print('[DEBUG] Aguardando N2 carregar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_CARGO_ID}'); return !!(el && el.selectize); }}", timeout=10000)
        except Exception:
            pass
        if LEVEL == 2:
            cargos = get_selectize_options(page, DD_CARGO_ID)
            out = [o for o in cargos if 'selecione' not in o['text'].lower()]
            print(f'[DEBUG] N2 retornou {len(out)} cargos', file=sys.stderr, flush=True)
            # Se N2 vazio, tentar N3 como fallback
            if len(out) == 0:
                print('[DEBUG] N2 vazio, tentando N3 (agentes) como fallback...', file=sys.stderr, flush=True)
                try:
                    page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return !!(el && el.selectize); }}", timeout=10000)
                    agentes = get_selectize_options(page, DD_AGENTE_ID)
                    out = [o for o in agentes if o.get('value') != '-1' and 'selecione' not in o['text'].lower() and 'todos os ocupantes' not in o['text'].lower()]
                    print(f'[DEBUG] N3 fallback retornou {len(out)} agentes', file=sys.stderr, flush=True)
                except Exception as e:
                    print(f'[DEBUG] N3 fallback falhou: {e}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return out
        print(f'[DEBUG] Selecionando N2={N2V}...', file=sys.stderr, flush=True)
        set_selectize_value(page, DD_CARGO_ID, N2V)
        page.wait_for_timeout(1000)
        try:
            print('[DEBUG] Aguardando N3 carregar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return !!(el && el.selectize); }}", timeout=10000)
        except Exception:
            pass
        agentes = get_selectize_options(page, DD_AGENTE_ID)
        out = [o for o in agentes if o.get('value') != '-1' and 'selecione' not in o['text'].lower() and 'todos os ocupantes' not in o['text'].lower()]
        print(f'[DEBUG] N3 retornou {len(out)} agentes', file=sys.stderr, flush=True)
        context.close()
        browser.close()
        return out""",
    "try:\n    data = main()\n    print(json.dumps({'success': True, 'options': data}))\nexcept Exception as e:\n    import traceback\n    print(json.dumps({'success': False, 'error': str(type(e).__name__) + ': ' + str(e), 'traceback': traceback.format_exc()[:400]}))",
    ]
    script_content = "\n".join(script_parts)

    # Ambiente para evitar tentativas de download
    env = os.environ.copy()
    env['PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD'] = '1'
    env['PYTHONUNBUFFERED'] = '1'  # Forçar output imediato (sem buffer)
    venv_browsers = Path(sys.executable).parent.parent / 'pw-browsers'
    if venv_browsers.exists():
        env['PLAYWRIGHT_BROWSERS_PATH'] = str(venv_browsers)
    # SSL corporativo (usar somente nesta chamada)
    env['NODE_TLS_REJECT_UNAUTHORIZED'] = '0'

    try:
        # Salvar script para debug (não deletar)
        debug_script = Path(__file__).parent / f"_eagendas_debug_level{level}.py"
        with open(debug_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        print(f"[DEBUG] Script salvo em: {debug_script}")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp:
            tmp.write(script_content)
            tmp_script = tmp.name
        try:
            result = subprocess.run(
                [sys.executable, tmp_script],
                capture_output=True,
                text=True,
                timeout=90 if level == 1 else 110,
                cwd=str(Path(__file__).parent.parent.parent),
                env=env,
            )
        finally:
            with contextlib.suppress(Exception):
                Path(tmp_script).unlink()

        # DEBUG: Log stdout e stderr completos
        print(f"\n[E-AGENDAS DEBUG] Level={level} returncode={result.returncode}")
        print(f"[STDOUT] {result.stdout[:500] if result.stdout else '(empty)'}")
        print(f"[STDERR len={len(result.stderr)}] {result.stderr[:1000] if result.stderr else '(empty)'}")

        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        json_line = stdout_lines[-1] if stdout_lines else ''
        if result.returncode != 0:
            try:
                err_data = json.loads(json_line)
                return {"success": False, "options": [], "error": err_data.get('error','Erro desconhecido')}
            except Exception:
                return {"success": False, "options": [], "error": f"Falha subprocess ({result.returncode})"}
        try:
            data = json.loads(json_line)
        except json.JSONDecodeError as je:
            return {"success": False, "options": [], "error": f"JSON inválido: {je}"}
        if not data.get('success'):
            return {"success": False, "options": [], "error": data.get('error','Erro desconhecido')}
        raw_opts = data.get('options') or []
        # Normalizar saída
        norm = []
        for o in raw_opts:
            lbl = (o.get('text') or o.get('label') or '').strip()
            val = (o.get('value') or '').strip()
            if not lbl or not val:
                continue
            norm.append({'label': lbl, 'value': val})
        # Ordenar por label
        norm = sorted(norm, key=lambda x: x['label'].lower())
        return {"success": True, "options": norm, "error": ""}
    except subprocess.TimeoutExpired:
        return {"success": False, "options": [], "error": "Timeout (>90/110s)"}
    except Exception as e:
        return {"success": False, "options": [], "error": f"{type(e).__name__}: {e}"}


def _run_batch_with_cfg(
    cfg_path: Path, parallel: int, fast_mode: bool = False, prefer_edge: bool = True
) -> dict[str, Any]:
    """Wrapper que delega para o runner livre de Streamlit para permitir uso headless e via UI."""
    try:
        from dou_snaptrack.ui.batch_runner import run_batch_with_cfg as _runner

        return _runner(cfg_path, parallel=int(parallel), fast_mode=bool(fast_mode), prefer_edge=bool(prefer_edge))
    except Exception as e:
        st.error(f"Falha ao executar batch: {e}")
        return {}


def _run_report(
    in_dir: Path,
    kind: str,
    out_dir: Path,
    base_name: str,
    split_by_n1: bool,
    date_label: str,
    secao_label: str,
    summary_lines: int,
    summary_mode: str,
    summary_keywords: list[str] | None = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if split_by_n1:
            from dou_snaptrack.cli.reporting import split_and_report_by_n1

            # Gravar diretamente dentro de out_dir
            pattern = out_dir / f"boletim_{{n1}}_{date_label}.{kind}"
            split_and_report_by_n1(
                str(in_dir),
                kind,
                str(out_dir / "unused"),
                str(pattern),
                date_label=date_label,
                secao_label=secao_label,
                summary_lines=summary_lines,
                summary_mode=summary_mode,
                summary_keywords=summary_keywords,
            )
            files = sorted(out_dir.glob(f"boletim_*_{date_label}.{kind}"))
        else:
            from dou_snaptrack.cli.reporting import consolidate_and_report

            out_path = out_dir / base_name
            consolidate_and_report(
                str(in_dir),
                kind,
                str(out_path),
                date_label=date_label,
                secao_label=secao_label,
                summary_lines=summary_lines,
                summary_mode=summary_mode,
                summary_keywords=summary_keywords,
            )
            files = [out_path]
        return files
    except Exception as e:
        st.error(f"Falha ao gerar boletim: {e}")
        return []


# ---------------- UI ----------------
st.set_page_config(page_title="SnapTrack DOU ", layout="wide")

# OTIMIZAÇÃO: Lazy load batch_runner apenas quando necessário
# Detect another UI and register this one
batch_funcs = get_batch_runner()
other_ui = batch_funcs["detect_other_ui"]()
if other_ui and int(other_ui.get("pid") or 0) != os.getpid():
    st.warning(f"Outra instância da UI detectada (PID={other_ui.get('pid')} iniciada em {other_ui.get('started')}).")
    col_ui = st.columns(3)
    with col_ui[0]:
        kill_ui = st.button("Encerrar a outra UI (forçar)")
    with col_ui[1]:
        ignore_ui = st.button("Ignorar e continuar")
    with col_ui[2]:
        clear_lock = st.button("Limpar lock e continuar")
    if kill_ui:
        ok = batch_funcs["terminate_other_execution"](int(other_ui.get("pid") or 0))
        if ok:
            st.success("Outra UI encerrada. Prosseguindo…")
        else:
            st.error("Falha ao encerrar a outra UI. Feche manualmente a janela/processo.")
    elif clear_lock:
        try:
            batch_funcs["clear_ui_lock"]()
            st.success("Lock removido. Prosseguindo…")
        except Exception as _e:
            st.error(f"Falha ao remover lock: {_e}")
    elif not ignore_ui:
        st.stop()

# Register this UI instance for future launches
batch_funcs["register_this_ui_instance"]()

st.title("SnapTrack DOU — Interface")
_ensure_state()
_ensure_eagendas_state()

# Tabs principais: DOU e E-Agendas
main_tab_dou, main_tab_eagendas = st.tabs(["📰 DOU", "📅 E-Agendas"])

with st.sidebar:
    st.header("Configuração")

    # Date picker visual (calendário) ao invés de text input
    from datetime import timedelta

    # Converter data string DD-MM-YYYY para date object (se válida)
    current_date_str = st.session_state.plan.date
    try:
        # Parse DD-MM-YYYY
        parts = current_date_str.split("-")
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            current_date_obj = _date(year, month, day)
        else:
            current_date_obj = _date.today()
    except Exception:
        current_date_obj = _date.today()

    # Date picker com calendário visual
    selected_date = st.date_input(
        "Data de publicação",
        value=current_date_obj,
        min_value=_date(2000, 1, 1),  # DOU digital começou em 2000
        max_value=_date.today() + timedelta(days=7),  # Permitir até 7 dias no futuro
        format="DD/MM/YYYY",
        help="Selecione a data de publicação do DOU para consulta",
    )

    # Converter de volta para string DD-MM-YYYY (formato esperado pelo backend)
    st.session_state.plan.date = selected_date.strftime("%d-%m-%Y")

    st.session_state.plan.secao = st.selectbox("Seção", ["DO1", "DO2", "DO3"], index=0)
    st.markdown("💡 **Dica**: Use o calendário para selecionar a data facilmente.")
    plan_name_ui = st.text_input("Nome do plano (para agregação)", value=st.session_state.get("plan_name_ui", ""))
    st.session_state["plan_name_ui"] = plan_name_ui

    with st.expander("Diagnóstico do ambiente"):
        try:
            import platform as _plat

            pyver = sys.version.split(" ")[0]
            exe = sys.executable
            loop_policy = type(asyncio.get_event_loop_policy()).__name__
            try:
                import playwright  # type: ignore

                pw_ver = getattr(playwright, "__version__", "?")
            except Exception:
                pw_ver = "não importado"
            # detectar Chrome/Edge
            import os
            from pathlib import Path

            exe_hint = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
            if not exe_hint:
                for c in (
                    r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                ):
                    if Path(c).exists():
                        exe_hint = c
                        break
            st.write(
                {
                    "OS": f"{_plat.system()} {_plat.release()}",
                    "Python": pyver,
                    "Interpreter": exe,
                    "EventLoopPolicy": loop_policy,
                    "Playwright": pw_ver,
                    "Chrome/Edge path": exe_hint or "canal 'chrome' (auto)",
                }
            )
            # Botão para reiniciar recursos Playwright desta thread
            if st.button("Reiniciar navegador (UI)"):
                try:
                    # Fechar e remover quaisquer recursos thread-local desta sessão
                    to_del = []
                    for k, v in list(st.session_state.items()):
                        if isinstance(k, str) and k.startswith("_pw_res_tid_"):
                            with contextlib.suppress(Exception):
                                if hasattr(v, "close"):
                                    v.close()
                            to_del.append(k)
                    for k in to_del:
                        # Remover silenciosamente se existir
                        st.session_state.pop(k, None)
                    st.success("Navegador reiniciado para esta sessão.")
                except Exception as _e2:
                    st.error(f"Falha ao reiniciar navegador: {_e2}")
            # Limpar cache de dados (inclui resultados de N1/N2)
            if st.button("Limpar cache de dados (N1/N2)"):
                try:
                    st.cache_data.clear()
                    st.success("Cache limpo.")
                except Exception as _e3:
                    st.warning(f"Falha ao limpar cache: {_e3}")
        except Exception as _e:
            st.write(f"[diag] erro: {_e}")

# ======================== TAB PRINCIPAL: DOU ========================
with main_tab_dou:
    tab1, tab2, tab3 = st.tabs(["Explorar e montar plano", "Executar plano", "Gerar boletim"])

with tab1:
    st.subheader("Monte sua Pesquisa")
    # Descoberta ao vivo: primeiro carrega lista de N1, depois carrega N2 para o N1 selecionado
    if st.button("Carregar"):
        with st.spinner("Obtendo lista de Orgãos do DOU…"):
            n1_candidates = _plan_live_fetch_n1_options(
                str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or "")
            )
        st.session_state["live_n1"] = n1_candidates

    n1_list = st.session_state.get("live_n1", [])
    if n1_list:
        n1 = st.selectbox("Órgão", n1_list, key="sel_n1_live")
    else:
        n1 = None
        st.info("Clique em 'Carregar' para listar os órgãos.")

    # Carregar N2 conforme N1 escolhido
    n2_list: list[str] = []
    can_load_n2 = bool(n1)
    if st.button("Carregar Organizações Subordinadas (todas)") and can_load_n2:
        with st.spinner("Obtendo lista completa do DOU…"):
            # Sem limite: pode ser grande em DO3 (centenas). Cache evita repetição.
            n2_list = _plan_live_fetch_n2(
                str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or ""), str(n1), limit2=None
            )
        st.session_state["live_n2_for_" + str(n1)] = n2_list
        st.caption(f"{len(n2_list)} suborganizações encontradas para '{n1}'.")
    if n1:
        n2_list = st.session_state.get("live_n2_for_" + str(n1), [])

    sel_n2 = st.multiselect("Organização Subordinada", options=n2_list)
    cols_add = st.columns(2)
    with cols_add[0]:
        if st.button("Adicionar ao plano", disabled=not (n1 and sel_n2)):
            add = _build_combos(str(n1), sel_n2)
            st.session_state.plan.combos.extend(add)
            st.success(f"Adicionados {len(add)} combos ao plano.")
    with cols_add[1]:
        # Caso não haja N2 disponíveis, permitir adicionar somente N1 usando N2='Todos'
        add_n1_only = n1 and not n2_list
        if st.button("Orgão sem Suborganizações", disabled=not add_n1_only):
            add = _build_combos(str(n1), ["Todos"])  # N2='Todos' indica sem filtro de N2
            st.session_state.plan.combos.extend(add)
            st.success("Adicionado N1 com N2='Todos'.")

    st.divider()
    st.subheader("📝 Gerenciar Plano")

    # Sub-seção: Carregar plano existente para edição
    with st.expander("📂 Carregar Plano Salvo para Editar"):
        plans_dir, _ = _ensure_dirs()
        refresh_token = st.session_state.get("plan_list_refresh_token", 0.0)
        head_actions = st.columns([3, 1])
        with head_actions[1]:
            if st.button("↻ Atualizar", key="refresh_plan_editor", help="Recarrega a lista de planos salvos"):
                st.session_state["plan_list_refresh_token"] = time.time()
                st.rerun()

        plan_entries = _list_saved_plan_files(refresh_token)

        if not plan_entries:
            st.info("Nenhum plano salvo disponível.")
        else:
            labels = [
                f"{entry['stem']} ({entry['combos']} combos)"
                for entry in plan_entries
            ]

            selected_idx = st.selectbox(
                "Selecione um plano para editar:",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key="edit_plan_selector"
            )

            col_load, col_info = st.columns([1, 2])
            with col_load:
                if st.button("📥 Carregar para Edição", use_container_width=True):
                    try:
                        selected_plan = Path(plan_entries[selected_idx]["path"])
                        cfg = json.loads(selected_plan.read_text(encoding="utf-8"))

                        # Carregar dados do plano para o estado da sessão
                        st.session_state.plan.date = cfg.get("data", _date.today().strftime("%d-%m-%Y"))
                        st.session_state.plan.secao = cfg.get("secaoDefault", "DO1")
                        st.session_state.plan.combos = cfg.get("combos", [])
                        st.session_state.plan.defaults = cfg.get("defaults", {
                            "scrape_detail": False,
                            "summary_lines": 0,
                            "summary_mode": "center",
                        })

                        # Salvar nome do plano para facilitar resalvar
                        plan_name = cfg.get("plan_name", selected_plan.stem)
                        st.session_state["plan_name_ui"] = plan_name
                        st.session_state["loaded_plan_path"] = str(selected_plan)

                        st.success(f"✅ Plano '{selected_plan.stem}' carregado com {len(st.session_state.plan.combos)} combos!")
                        # Removido st.rerun() para evitar travamento - o estado atualiza automaticamente
                    except Exception as e:
                        st.error(f"❌ Erro ao carregar plano: {e}")

            with col_info:
                meta = plan_entries[selected_idx]
                st.caption(f"📅 Data: {meta.get('data') or 'N/A'}")
                st.caption(f"📰 Seção: {meta.get('secao') or 'N/A'}")
                st.caption(f"📦 Combos: {meta.get('combos', 0)}")
                size_kb = meta.get("size_kb")
                if size_kb is not None:
                    st.caption(f"💾 Tamanho: {size_kb} KB")

    # Visualização e edição do plano atual
    st.markdown("#### 📋 Plano Atual")

    if not st.session_state.plan.combos:
        st.info("📭 Nenhum combo no plano. Use as opções acima para adicionar combos ou carregar um plano salvo.")
    else:
        num_combos = len(st.session_state.plan.combos)
        st.caption(f"Total: **{num_combos} combos**")

        # Verificar se há muitos combos que podem causar lentidão/travamento
        MAX_COMBOS_SAFE = 200
        if num_combos > MAX_COMBOS_SAFE:
            st.warning(f"⚠️ **Plano grande detectado ({num_combos} combos)**")
            st.info("💡 Planos com muitos combos podem causar lentidão na edição. Considere dividir em planos menores ou usar a linha de comando para execução.")
            # Permitir edição mesmo assim, mas com aviso

        # Criar DataFrame com checkbox para seleção
        import pandas as pd

        # Extrair labels com checkbox para marcar remoção
        display_data = []
        for i, combo in enumerate(st.session_state.plan.combos):
            orgao_label = _resolve_combo_label(combo, "label1", "key1")
            sub_label = _resolve_combo_label(combo, "label2", "key2")
            display_data.append({
                "Remover?": False,
                "ID": i,
                "Órgão": orgao_label,
                "Sub-órgão": sub_label,
            })

        df_display = pd.DataFrame(display_data)

        # Tabela editável com checkbox
        editor_key = f"plan_combos_editor_{st.session_state.get('loaded_plan_path', 'new')}_{len(st.session_state.plan.combos)}"
        edited_df = st.data_editor(
            df_display,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Remover?": st.column_config.CheckboxColumn(
                    "Remover?",
                    help="Marque para remover este combo",
                    default=False,
                    width="small"
                ),
                "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "Órgão": st.column_config.TextColumn("Órgão", width="large"),
                "Sub-órgão": st.column_config.TextColumn("Sub-órgão", width="large"),
            },
            hide_index=True,
            key=editor_key,
            disabled=["ID"]
        )

        # Botões de ação
        st.markdown("**Ações:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("💾 Salvar Edições", use_container_width=True, type="primary",
                        help="Aplica as mudanças de texto"):
                for i, combo in enumerate(st.session_state.plan.combos):
                    if i < len(edited_df):
                        new_orgao = edited_df.iloc[i]["Órgão"]
                        new_sub = edited_df.iloc[i]["Sub-órgão"]
                        combo["label1"] = new_orgao
                        combo["label2"] = new_sub
                # Salvar de volta no arquivo carregado, se existir
                loaded_path = st.session_state.get("loaded_plan_path")
                if loaded_path:
                    try:
                        cfg_to_save = {
                            "data": st.session_state.plan.date,
                            "secaoDefault": st.session_state.plan.secao,
                            "defaults": st.session_state.plan.defaults,
                            "combos": st.session_state.plan.combos,
                            "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"},
                        }
                        _pname = st.session_state.get("plan_name_ui")
                        if isinstance(_pname, str) and _pname.strip():
                            cfg_to_save["plan_name"] = _pname.strip()
                        Path(loaded_path).write_text(json.dumps(cfg_to_save, ensure_ascii=False, indent=2), encoding="utf-8")
                        st.success("✅ Edições salvas no arquivo!")
                        st.session_state["plan_list_refresh_token"] = time.time()  # Refresh cache
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar no arquivo: {e}")
                else:
                    st.success("✅ Edições salvas (em memória)! Use 'Salvar plano' para persistir em arquivo.")
                st.rerun()

        with col2:
            selected_count = int(edited_df["Remover?"].sum())
            btn_label = f"🗑️ Remover Marcados ({selected_count})"
            if st.button(btn_label, use_container_width=True, disabled=selected_count == 0,
                        help="Remove combos marcados"):
                new_combos = []
                for i, combo in enumerate(st.session_state.plan.combos):
                    if i < len(edited_df) and not edited_df.iloc[i]["Remover?"]:
                        new_combos.append(combo)
                st.session_state.plan.combos = new_combos
                st.success(f"✅ {selected_count} combo(s) removido(s)")
                st.rerun()

        with col3:
            if st.button("🗑️ Limpar Tudo", use_container_width=True,
                        help="Remove TODOS os combos"):
                st.session_state.plan.combos = []
                st.success("🗑️ Plano limpo")
                st.rerun()

    st.divider()
    st.subheader("💾 Salvar Plano")
    # OTIMIZAÇÃO: Criação lazy de diretórios apenas quando necessário
    plans_dir, _ = _ensure_dirs()
    suggested = plans_dir / f"plan_{str(st.session_state.plan.date or '').replace('/', '-').replace(' ', '_')}.json"
    plan_path = st.text_input("Salvar como", str(suggested))
    if st.button("Salvar plano"):
        cfg = {
            "data": st.session_state.plan.date,
            "secaoDefault": st.session_state.plan.secao,
            "defaults": st.session_state.plan.defaults,
            "combos": st.session_state.plan.combos,
            "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"},
        }
        # Propagar nome do plano, se informado
        _pname = st.session_state.get("plan_name_ui")
        if isinstance(_pname, str) and _pname.strip():
            cfg["plan_name"] = _pname.strip()
        ppath = Path(plan_path)
        ppath.parent.mkdir(parents=True, exist_ok=True)
        ppath.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Plano salvo em {plan_path}")
        st.session_state["plan_list_refresh_token"] = time.time()

with tab2:
    st.subheader("Escolha o plano de pesquisa")
    # OTIMIZAÇÃO: Criação lazy de diretórios
    plans_dir, _ = _ensure_dirs()
    refresh_token = st.session_state.get("plan_list_refresh_token", 0.0)
    header_cols = st.columns([3, 1])
    with header_cols[1]:
        if st.button("↻ Atualizar", key="refresh_plan_runner", help="Recarrega lista de planos"):
            st.session_state["plan_list_refresh_token"] = time.time()
            st.rerun()

    plan_entries = _list_saved_plan_files(refresh_token)

    if not plan_entries:
        st.info("Nenhum plano salvo ainda. Informe um caminho válido abaixo.")
        plan_to_run = st.text_input("Arquivo do plano (JSON)", "batch_today.json")
        selected_path = Path(plan_to_run)
    else:
        labels = [f"{entry['stem']} ({entry['combos']} combos)" for entry in plan_entries]
        choice_idx = st.selectbox(
            "Selecione o plano salvo",
            range(len(labels)),
            format_func=lambda i: labels[i],
            index=0,
        )
        selected_path = Path(plan_entries[choice_idx]["path"])

    # Paralelismo adaptativo (heurística baseada em CPU e nº de jobs)
    # OTIMIZAÇÃO: Import lazy apenas quando necessário (não carrega no startup)
    try:
        cfg_preview = json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else {}
        combos_prev = cfg_preview.get("combos") or []
        topics_prev = cfg_preview.get("topics") or []
        est_jobs_prev = len(combos_prev) * max(1, len(topics_prev) or 1)
    except Exception:
        est_jobs_prev = 1

    # Lazy import apenas quando realmente usado
    from dou_snaptrack.utils.parallel import recommend_parallel

    suggested_workers = recommend_parallel(est_jobs_prev, prefer_process=True)
    st.caption(f"Paralelismo recomendado: {suggested_workers} (baseado no hardware e plano)")
    st.caption("A captura do plano é sempre 'link-only' (sem detalhes/boletim); gere o boletim na aba correspondente.")

    if st.button("Pesquisar Agora"):
        if not selected_path.exists():
            st.error("Plano não encontrado.")
        else:
            # Concurrency guard: check if another execution is running
            # OTIMIZAÇÃO: Lazy load batch_runner apenas quando botão for clicado
            batch_funcs = get_batch_runner()
            other = batch_funcs["detect_other_execution"]()
            if other:
                st.warning(f"Outra execução detectada (PID={other.get('pid')} iniciada em {other.get('started')}).")
                colx = st.columns(2)
                with colx[0]:
                    kill_it = st.button("Encerrar outra execução (forçar)")
                with colx[1]:
                    proceed_anyway = st.button("Prosseguir sem encerrar")
                if kill_it:
                    ok = batch_funcs["terminate_other_execution"](int(other.get("pid") or 0))
                    if ok:
                        st.success("Outra execução encerrada. Prosseguindo…")
                    else:
                        st.error("Falha ao encerrar a outra execução. Tente novamente manualmente.")
                elif not proceed_anyway:
                    st.stop()
            # Descobrir número de jobs do plano
            try:
                cfg = json.loads(selected_path.read_text(encoding="utf-8"))
                combos = cfg.get("combos") or []
                topics = cfg.get("topics") or []
                # Estimação rápida de jobs (sem repetir): se houver topics, cada combo cruza com topic
                est_jobs = len(combos) * max(1, len(topics) or 1)
            except Exception:
                est_jobs = 1

            # Calcular recomendação no momento da execução (pode mudar conforme data/plan_name)
            parallel = int(recommend_parallel(est_jobs, prefer_process=True))
            with st.spinner("Executando…"):
                # Forçar execução para a data atual selecionada no UI (padrão: hoje)
                try:
                    cfg_json = json.loads(selected_path.read_text(encoding="utf-8"))
                except Exception:
                    cfg_json = {}
                override_date = str(st.session_state.plan.date or "").strip() or _date.today().strftime("%d-%m-%Y")
                cfg_json["data"] = override_date
                # Injetar plan_name (agregação por plano ao final do batch)
                _pname2 = st.session_state.get("plan_name_ui")
                if isinstance(_pname2, str) and _pname2.strip():
                    cfg_json["plan_name"] = _pname2.strip()
                if not cfg_json.get("plan_name"):
                    # Fallback 1: nome do arquivo do plano salvo
                    # OTIMIZAÇÃO: Lazy load sanitize_filename apenas quando necessário
                    sanitize_fn = get_sanitize_filename()
                    try:
                        if selected_path and selected_path.exists():
                            base = selected_path.stem
                            if base:
                                cfg_json["plan_name"] = sanitize_fn(base)
                    except Exception:
                        pass
                if not cfg_json.get("plan_name"):
                    # Fallback 2: usar key1/label1 do primeiro combo
                    sanitize_fn = get_sanitize_filename()
                    try:
                        combos_fallback = cfg_json.get("combos") or []
                        if combos_fallback:
                            c0 = combos_fallback[0] or {}
                            cand = c0.get("label1") or c0.get("key1") or "Plano"
                            cfg_json["plan_name"] = sanitize_fn(str(cand))
                    except Exception:
                        cfg_json["plan_name"] = "Plano"
                # Gerar um config temporário para a execução desta sessão, sem modificar o arquivo salvo
                out_dir_tmp = Path("resultados") / override_date
                out_dir_tmp.mkdir(parents=True, exist_ok=True)
                pass_cfg_path = out_dir_tmp / "_run_cfg.from_ui.json"
                with contextlib.suppress(Exception):
                    pass_cfg_path.write_text(json.dumps(cfg_json, ensure_ascii=False, indent=2), encoding="utf-8")
                st.caption(f"Iniciando captura… log em resultados/{override_date}/batch_run.log")
                rep = _run_batch_with_cfg(pass_cfg_path, parallel, fast_mode=False, prefer_edge=True)
            st.write(rep or {"info": "Sem relatório"})
            # Hint on where to find detailed run logs
            out_date = str(st.session_state.plan.date or "").strip() or _date.today().strftime("%d-%m-%Y")
            log_hint = Path("resultados") / out_date / "batch_run.log"
            if log_hint.exists():
                st.caption(f"Execução concluída com {parallel} workers automáticos. Log detalhado em: {log_hint}")
            else:
                st.caption(f"Execução concluída com {parallel} workers automáticos.")

with tab3:
    st.subheader("Boletim por Plano (agregados)")
    results_root = Path("resultados")
    results_root.mkdir(parents=True, exist_ok=True)
    # Formato e política padronizada de resumo (sem escolhas do usuário)
    # Padrões fixos: summary_lines=7, summary_mode="center", keywords=None
    st.caption(
        "Os resumos são gerados com parâmetros padronizados (modo center, 7 linhas) e captura profunda automática."
    )
    st.caption("Gere boletim a partir de agregados do dia: {plan}_{secao}_{data}.json (dentro da pasta da data)")

    # Deep-mode: sem opções expostas. Usamos parâmetros fixos e mantemos modo online.

    # Ação auxiliar: agregação manual a partir de uma pasta de dia
    with st.expander("Agregação manual (quando necessário)"):
        day_dirs = []
        try:
            day_dirs = [d for d in results_root.iterdir() if d.is_dir()]
        except Exception:
            day_dirs = []
        day_dirs = sorted(day_dirs, key=lambda p: p.name, reverse=True)
        if not day_dirs:
            st.info("Nenhuma pasta encontrada em 'resultados'. Execute um plano para gerar uma pasta do dia.")
        else:
            labels = [p.name for p in day_dirs]
            choice = st.selectbox("Pasta do dia para agregar", labels, index=0, key="agg_day_choice")
            choice_str = str(choice) if isinstance(choice, str) and choice else str(labels[0])
            chosen_dir = results_root / choice_str
            help_txt = "Use esta opção se a execução terminou sem gerar os arquivos agregados. Informe o nome do plano e agregue os JSONs da pasta escolhida."
            st.write(help_txt)
            manual_plan = st.text_input(
                "Nome do plano (para nome do arquivo agregado)",
                value=st.session_state.get("plan_name_ui", ""),
                key="agg_manual_plan",
            )
            if st.button("Gerar agregados agora", key="agg_manual_btn"):
                _mp = manual_plan or ""
                if not _mp.strip():
                    st.warning("Informe o nome do plano.")
                else:
                    try:
                        from dou_snaptrack.cli.reporting import aggregate_outputs_by_plan

                        written = aggregate_outputs_by_plan(str(chosen_dir), _mp.strip())
                        if written:
                            st.success(f"Gerados {len(written)} agregado(s):")
                            for w in written:
                                st.write(w)
                        else:
                            st.info("Nenhum arquivo de job encontrado para agregar.")
                    except Exception as e:
                        st.error(f"Falha ao agregar: {e}")

    # Seletor 1: escolher a pasta da data (resultados/<data>)
    day_dirs: list[Path] = []
    try:
        day_dirs = [d for d in results_root.iterdir() if d.is_dir()]
    except Exception:
        day_dirs = []
    day_dirs = sorted(day_dirs, key=lambda p: p.name, reverse=True)
    if not day_dirs:
        st.info("Nenhuma pasta encontrada em 'resultados'. Execute um plano com 'Nome do plano' para gerar agregados.")
    else:
        day_labels = [p.name for p in day_dirs]
        sel_day = st.selectbox("Data (pasta em resultados)", day_labels, index=0, key="agg_day_select")
        chosen_dir = results_root / str(sel_day)

        # Indexar agregados dentro da pasta escolhida
        def _index_aggregates_in_day(day_dir: Path) -> dict[str, list[Path]]:
            idx: dict[str, list[Path]] = {}
            try:
                for f in day_dir.glob("*_DO?_*.json"):
                    name = f.name
                    try:
                        parts = name[:-5].split("_")  # drop .json
                        if len(parts) < 3:
                            continue
                        sec = parts[-2]
                        date = parts[-1]
                        plan = "_".join(parts[:-2])
                        if not sec.upper().startswith("DO"):
                            continue
                        # conferir se bate com a pasta (sanidade)
                        if date != day_dir.name:
                            continue
                    except Exception:
                        continue
                    idx.setdefault(plan, []).append(f)
            except Exception:
                pass
            return idx

        day_idx = _index_aggregates_in_day(chosen_dir)
        plan_names = sorted(day_idx.keys())
        if not plan_names:
            st.info("Nenhum agregado encontrado nessa data. Verifique se o plano foi executado com 'Nome do plano'.")
        else:
            # Seletor 2: escolher o plano dentro da pasta do dia
            sel_plan = st.selectbox("Plano (encontrado na data)", plan_names, index=0, key="agg_plan_select")
            files = day_idx.get(sel_plan, [])
            kind2 = st.selectbox("Formato (agregados)", ["docx", "md", "html"], index=1, key="kind_agg")
            out_name2 = st.text_input("Nome do arquivo de saída", f"boletim_{sel_plan}_{sel_day}.{kind2}")
            if st.button("Gerar boletim do plano (data selecionada)"):
                try:
                    from dou_snaptrack.cli.reporting import report_from_aggregated

                    out_path = results_root / out_name2
                    # Detectar seção a partir do primeiro arquivo
                    secao_label = ""
                    if files:
                        try:
                            parts = files[0].stem.split("_")
                            if len(parts) >= 2:
                                secao_label = parts[-2]
                        except Exception:
                            pass
                    # Garantir deep-mode ligado para relatório (não offline)
                    os.environ["DOU_OFFLINE_REPORT"] = "0"
                    report_from_aggregated(
                        [str(p) for p in files],
                        kind2,
                        str(out_path),
                        date_label=str(sel_day),
                        secao_label=secao_label,
                        summary_lines=7,
                        summary_mode="center",
                        summary_keywords=None,
                        order_desc_by_date=True,
                        fetch_parallel=8,
                        fetch_timeout_sec=30,
                        fetch_force_refresh=True,
                        fetch_browser_fallback=True,
                        short_len_threshold=800,
                    )
                    data = out_path.read_bytes()
                    st.success(f"Boletim gerado: {out_path}")
                    # Guardar em memória para download e remoção posterior do arquivo físico
                    try:
                        st.session_state["last_bulletin_data"] = data
                        st.session_state["last_bulletin_name"] = out_path.name
                        st.session_state["last_bulletin_path"] = str(out_path)
                        st.info("Use o botão abaixo para baixar; o arquivo local será removido após o download.")
                    except Exception:
                        # Fallback: se sessão não aceitar, manter botão direto (sem remoção automática)
                        st.download_button(
                            "Baixar boletim (plano)", data=data, file_name=out_path.name, key="dl_fallback"
                        )
                except Exception as e:
                    st.error(f"Falha ao gerar boletim por plano: {e}")

    # Se houver um boletim recém-gerado, oferecer download e remover arquivo após clique
    lb_data = st.session_state.get("last_bulletin_data")
    lb_name = st.session_state.get("last_bulletin_name")
    lb_path = st.session_state.get("last_bulletin_path")
    if lb_data and lb_name:
        clicked = st.download_button(
            "Baixar último boletim gerado", data=lb_data, file_name=str(lb_name), key="dl_last_bulletin"
        )
        if clicked:
            # Remover arquivo gerado no servidor após o download
            try:
                if lb_path:
                    from pathlib import Path as _P

                    p = _P(str(lb_path))
                    if p.exists():
                        p.unlink()
            except Exception as _e:
                st.warning(f"Não foi possível remover o arquivo local: {lb_path} — {_e}")
            # Limpar dados da sessão para evitar re-download e liberar memória
            for k in ("last_bulletin_data", "last_bulletin_name", "last_bulletin_path"):
                st.session_state.pop(k, None)


# ======================== TAB PRINCIPAL: E-AGENDAS ========================
with main_tab_eagendas:
    st.subheader("E-Agendas — Consulta de Agendas de Servidores Públicos")

    # Seção 1: Seleção de Órgão/Cargo/Agente (N1/N2/N3)
    st.markdown("### 1️⃣ Selecione o Servidor Público")

    col_n1, col_n2, col_n3 = st.columns(3)

    with col_n1:
        st.markdown("**Órgão (N1)**")
        if st.button("Carregar Órgãos", key="eagendas_load_n1"):
            with st.spinner("Obtendo lista de órgãos do E-Agendas..."):
                result = _eagendas_fetch_hierarchy(level=1)
                if result["success"]:
                    st.session_state["eagendas_n1_options"] = result["options"]
                    st.success(f"✅ {len(result['options'])} órgãos carregados")
                else:
                    st.error(f"❌ Erro ao carregar órgãos: {result['error']}")
                    st.session_state["eagendas_n1_options"] = []

        n1_options = st.session_state.get("eagendas_n1_options", [])
        if n1_options:
            n1_labels = [opt["label"] for opt in n1_options]
            selected_n1_label = st.selectbox("Selecione o órgão:", n1_labels, key="eagendas_sel_n1")
            # Encontrar o value correspondente
            selected_n1_value = next((opt["value"] for opt in n1_options if opt["label"] == selected_n1_label), None)
            st.session_state.eagendas.current_n1 = selected_n1_value
            st.session_state["eagendas_current_n1_label"] = selected_n1_label
        else:
            st.info("Clique em 'Carregar Órgãos' para começar")

    with col_n2:
        st.markdown("**Cargo (N2)**")
        n1_selected = st.session_state.eagendas.current_n1
        if n1_selected and st.button("Carregar Cargos", key="eagendas_load_n2"):
            n1_label = st.session_state.get("eagendas_current_n1_label", "N1")
            with st.spinner(f"Obtendo cargos para '{n1_label}'..."):
                result = _eagendas_fetch_hierarchy(level=2, n1_value=n1_selected)
                if result["success"]:
                    st.session_state["eagendas_n2_options"] = result["options"]
                    st.success(f"✅ {len(result['options'])} cargos carregados")
                else:
                    st.error(f"❌ Erro ao carregar cargos: {result['error']}")
                    st.session_state["eagendas_n2_options"] = []

        n2_options = st.session_state.get("eagendas_n2_options", [])
        if n2_options:
            n2_labels = [opt["label"] for opt in n2_options]
            selected_n2_label = st.selectbox("Selecione o cargo:", n2_labels, key="eagendas_sel_n2")
            # Encontrar o value correspondente
            selected_n2_value = next((opt["value"] for opt in n2_options if opt["label"] == selected_n2_label), None)
            st.session_state.eagendas.current_n2 = selected_n2_value
            st.session_state["eagendas_current_n2_label"] = selected_n2_label
        elif n1_selected:
            st.info("Clique em 'Carregar Cargos'")
        else:
            st.caption("Selecione um órgão primeiro")

    with col_n3:
        st.markdown("**Agente (N3)**")
        n2_selected = st.session_state.eagendas.current_n2
        n1_selected = st.session_state.eagendas.current_n1
        if n2_selected and st.button("Carregar Agentes", key="eagendas_load_n3"):
            n2_label = st.session_state.get("eagendas_current_n2_label", "N2")
            with st.spinner(f"Obtendo agentes para '{n2_label}'..."):
                result = _eagendas_fetch_hierarchy(level=3, n1_value=n1_selected, n2_value=n2_selected)
                if result["success"]:
                    st.session_state["eagendas_n3_options"] = result["options"]
                    st.success(f"✅ {len(result['options'])} agentes carregados")
                else:
                    st.error(f"❌ Erro ao carregar agentes: {result['error']}")
                    st.session_state["eagendas_n3_options"] = []

        n3_options = st.session_state.get("eagendas_n3_options", [])
        if n3_options:
            n3_labels = [opt["label"] for opt in n3_options]
            selected_n3_label = st.selectbox("Selecione o agente:", n3_labels, key="eagendas_sel_n3")
            # Encontrar o value correspondente
            selected_n3_value = next((opt["value"] for opt in n3_options if opt["label"] == selected_n3_label), None)
            st.session_state.eagendas.current_n3 = selected_n3_value
            st.session_state["eagendas_current_n3_label"] = selected_n3_label
        elif n2_selected:
            st.info("Clique em 'Carregar Agentes'")
        else:
            st.caption("Selecione um cargo primeiro")

    st.divider()

    # Seção 2: Período de Pesquisa
    st.markdown("### 2️⃣ Defina o Período de Pesquisa")
    st.caption("⚠️ O período deve ser definido a cada execução (não é salvo nas consultas)")

    col_date1, col_date2 = st.columns(2)

    with col_date1:
        # Parse data inicial
        try:
            parts = st.session_state.eagendas.date_start.split("-")
            start_obj = _date(int(parts[2]), int(parts[1]), int(parts[0]))
        except Exception:
            start_obj = _date.today()

        date_start = st.date_input("Data de início:", value=start_obj, format="DD/MM/YYYY", key="eagendas_date_start")
        st.session_state.eagendas.date_start = date_start.strftime("%d-%m-%Y")

    with col_date2:
        # Parse data final
        try:
            parts = st.session_state.eagendas.date_end.split("-")
            end_obj = _date(int(parts[2]), int(parts[1]), int(parts[0]))
        except Exception:
            end_obj = _date.today()

        date_end = st.date_input("Data de término:", value=end_obj, format="DD/MM/YYYY", key="eagendas_date_end")
        st.session_state.eagendas.date_end = date_end.strftime("%d-%m-%Y")

    # Validação de período
    if date_start > date_end:
        st.error("⚠️ A data de início deve ser anterior ou igual à data de término!")
    else:
        days_diff = (date_end - date_start).days
        st.caption(f"✅ Período selecionado: {days_diff + 1} dia(s)")

    st.divider()

    # Seção 3: Gerenciamento de Consultas Salvas
    st.markdown("### 3️⃣ Consultas Salvas")
    st.caption("Salve combinações de servidores para executar múltiplas pesquisas")

    col_add, col_clear = st.columns([3, 1])

    with col_add:
        can_add = all(
            [
                st.session_state.eagendas.current_n1,
                st.session_state.eagendas.current_n2,
                st.session_state.eagendas.current_n3,
            ]
        )
        if st.button("+ Adicionar Consulta Atual", disabled=not can_add, use_container_width=True):
            # Criar query com labels e values reais
            n1_label = st.session_state.get("eagendas_current_n1_label", "")
            n2_label = st.session_state.get("eagendas_current_n2_label", "")
            n3_label = st.session_state.get("eagendas_current_n3_label", "")

            query = {
                "n1_label": n1_label,
                "n1_value": st.session_state.eagendas.current_n1,
                "n2_label": n2_label,
                "n2_value": st.session_state.eagendas.current_n2,
                "n3_label": n3_label,
                "n3_value": st.session_state.eagendas.current_n3,
                "person_label": f"{n3_label} ({n2_label})",
            }
            st.session_state.eagendas.saved_queries.append(query)
            st.success("✅ Consulta adicionada!")
            st.rerun()

    with col_clear:
        if st.button("🗑️ Limpar Todas", use_container_width=True):
            st.session_state.eagendas.saved_queries = []
            st.success("🗑️ Consultas removidas")
            st.rerun()

    # Sub-seção: Salvar/Carregar Listas de Agentes
    st.markdown("#### 💾 Gerenciar Listas de Agentes")

    listas_dir = Path("planos") / "eagendas_listas"
    listas_dir.mkdir(parents=True, exist_ok=True)

    col_save, col_load = st.columns(2)

    with col_save:
        st.caption("💾 Salvar lista atual")
        lista_name = st.text_input(
            "Nome da lista:",
            placeholder="Ex: Ministros_CADE",
            key="eagendas_lista_name",
            help="Nome para identificar esta lista de agentes"
        )

        can_save = len(st.session_state.eagendas.saved_queries) > 0 and lista_name.strip()
        if st.button("💾 Salvar Lista", disabled=not can_save, use_container_width=True):
            # Sanitizar nome do arquivo
            safe_name = "".join(c if c.isalnum() or c in "_ -" else "_" for c in lista_name.strip())
            file_path = listas_dir / f"{safe_name}.json"

            # Preparar dados para salvar
            lista_data = {
                "nome": lista_name.strip(),
                "criado_em": _date.today().strftime("%Y-%m-%d"),
                "total_agentes": len(st.session_state.eagendas.saved_queries),
                "queries": st.session_state.eagendas.saved_queries
            }

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(lista_data, f, indent=2, ensure_ascii=False)
                st.success(f"✅ Lista '{lista_name}' salva com sucesso!")
                st.caption(f"📁 {file_path}")
            except Exception as e:
                st.error(f"❌ Erro ao salvar lista: {e}")

    with col_load:
        st.caption("📂 Carregar lista salva")

        # Listar arquivos JSON disponíveis
        lista_files = sorted(listas_dir.glob("*.json"))

        if lista_files:
            # Ler metadados das listas
            lista_options = []
            for file_path in lista_files:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)
                    nome = data.get("nome", file_path.stem)
                    total = data.get("total_agentes", len(data.get("queries", [])))
                    criado = data.get("criado_em", "")
                    lista_options.append({
                        "label": f"{nome} ({total} agentes) - {criado}",
                        "path": file_path,
                        "data": data
                    })
                except Exception:
                    # Ignorar arquivos corrompidos
                    continue

            if lista_options:
                selected_lista_label = st.selectbox(
                    "Selecione uma lista:",
                    [opt["label"] for opt in lista_options],
                    key="eagendas_lista_select"
                )

                col_load_btn, col_del_btn = st.columns(2)

                with col_load_btn:
                    if st.button("📂 Carregar", use_container_width=True):
                        # Encontrar a lista selecionada
                        selected_opt = next((opt for opt in lista_options if opt["label"] == selected_lista_label), None)
                        if selected_opt:
                            st.session_state.eagendas.saved_queries = selected_opt["data"]["queries"]
                            st.success(f"✅ Lista carregada: {selected_opt['data']['total_agentes']} agentes")
                            st.rerun()

                with col_del_btn:
                    if st.button("🗑️ Excluir", use_container_width=True, type="secondary"):
                        # Confirmar exclusão
                        selected_opt = next((opt for opt in lista_options if opt["label"] == selected_lista_label), None)
                        if selected_opt:
                            try:
                                selected_opt["path"].unlink()
                                st.success("🗑️ Lista excluída")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao excluir: {e}")
            else:
                st.info("Nenhuma lista disponível")
        else:
            st.info("Nenhuma lista salva ainda")

    # Mostrar lista de consultas salvas
    queries = st.session_state.eagendas.saved_queries
    if queries:
        st.metric("Total de consultas", len(queries))
        with st.expander(f"📋 Ver todas ({len(queries)} consultas)", expanded=True):
            for idx, q in enumerate(queries):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{idx + 1}. {q['person_label']}")
                    st.caption(f"   Órgão: {q['n1_label']} | Cargo: {q['n2_label']}")
                with col2:
                    if st.button("❌", key=f"del_query_{idx}"):
                        st.session_state.eagendas.saved_queries.pop(idx)
                        st.rerun()
    else:
        st.info("Nenhuma consulta salva. Selecione um servidor e clique em 'Adicionar Consulta Atual'")

    st.divider()

    # Seção 4: Execução
    st.markdown("### 4️⃣ Executar Pesquisa")

    can_execute = len(st.session_state.eagendas.saved_queries) > 0 and date_start <= date_end

    if st.button("🚀 Executar Todas as Consultas", disabled=not can_execute, use_container_width=True):
        from datetime import datetime as dt

        # Preparar estrutura de dados
        periodo_iso = {
            "inicio": date_start.strftime("%Y-%m-%d"),
            "fim": date_end.strftime("%Y-%m-%d")
        }

        queries = st.session_state.eagendas.saved_queries

        # Criar progress bar
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        status_text.text("🚀 Iniciando coleta de eventos via Playwright...")

        try:
            # Preparar input para subprocess
            subprocess_input = {
                "queries": queries,
                "periodo": periodo_iso
            }

            # Caminho do script de coleta
            script_path = Path(__file__).parent / "eagendas_collect_subprocess.py"

            # Executar subprocess
            progress_bar.progress(0.1)
            status_text.text("🌐 Navegando no E-Agendas...")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                input=json.dumps(subprocess_input),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos timeout
            )

            # Processar resultado
            if result.returncode != 0:
                # Erro no subprocess
                try:
                    error_data = json.loads(result.stdout)
                    error_msg = error_data.get("error", "Erro desconhecido")
                except Exception:
                    error_msg = result.stderr or "Erro ao executar coleta"

                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Erro durante coleta: {error_msg}")

                # Logs de debug
                if result.stderr:
                    with st.expander("🔍 Logs do processo"):
                        st.code(result.stderr)
            else:
                # Parsear resultado JSON
                try:
                    response = json.loads(result.stdout)
                except json.JSONDecodeError:
                    progress_bar.empty()
                    status_text.empty()
                    st.error("❌ Erro ao parsear resposta do subprocess")
                    with st.expander("🔍 Output raw"):
                        st.code(result.stdout)
                else:
                    if not response.get("success"):
                        progress_bar.empty()
                        status_text.empty()
                        st.error(f"❌ Coleta falhou: {response.get('error', 'Erro desconhecido')}")
                        if "traceback" in response:
                            with st.expander("🔍 Traceback"):
                                st.code(response["traceback"])
                    else:
                        # Extrair dados
                        events_data = response.get("data", {})
                        agentes_data = events_data.get("agentes", [])
                        total_eventos = events_data.get("metadata", {}).get("total_eventos", 0)

                        # Finalizar progresso
                        progress_bar.progress(1.0)
                        status_text.text("✅ Coleta concluída!")

                        # Salvar JSON
                        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
                        json_path = Path("resultados") / f"eagendas_eventos_{periodo_iso['inicio']}_{periodo_iso['fim']}_{timestamp}.json"
                        json_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(events_data, f, indent=2, ensure_ascii=False)

                        # Exibir resultados
                        st.success(f"✅ Coleta concluída! {len(agentes_data)} agentes processados")
                        col_r1, col_r2, col_r3 = st.columns(3)
                        with col_r1:
                            st.metric("Agentes", len(agentes_data))
                        with col_r2:
                            st.metric("Eventos", total_eventos)
                        with col_r3:
                            st.metric("Período", f"{(date_end - date_start).days + 1} dias")

                        st.info(f"📁 Dados salvos em: `{json_path.name}`")

                        # Armazenar caminho no session_state para geração de documento
                        st.session_state["last_eagendas_json"] = str(json_path)

                        # Mostrar logs do processo se houver
                        if result.stderr:
                            with st.expander("📋 Logs da coleta"):
                                st.text(result.stderr)

        except subprocess.TimeoutExpired:
            progress_bar.empty()
            status_text.empty()
            st.error("❌ Timeout: A coleta demorou mais de 5 minutos")
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Erro durante execução: {e}")
            import traceback
            with st.expander("🔍 Detalhes do erro"):
                st.code(traceback.format_exc())

    if not can_execute:
        if len(st.session_state.eagendas.saved_queries) == 0:
            st.warning("⚠️ Adicione pelo menos uma consulta para executar")
        if date_start > date_end:
            st.warning("⚠️ Corrija o período de pesquisa")

    st.divider()

    # Seção 5: Geração de Documento
    st.markdown("### 5️⃣ Gerar Documento DOCX")
    st.caption("Gere um documento Word com as agendas coletadas, organizadas por agente")

    # Verificar se há arquivo JSON recém-coletado ou de exemplo
    from pathlib import Path
    json_to_use = None
    is_example = False

    # Priorizar último JSON coletado
    if "last_eagendas_json" in st.session_state:
        last_json = Path(st.session_state["last_eagendas_json"])
        if last_json.exists():
            json_to_use = last_json
        else:
            # Limpar referência se arquivo não existe mais
            del st.session_state["last_eagendas_json"]

    # Fallback para exemplo
    if json_to_use is None:
        json_example = Path("resultados") / "eagendas_eventos_exemplo.json"
        if json_example.exists():
            json_to_use = json_example
            is_example = True

    if json_to_use:
        col_doc1, col_doc2 = st.columns([3, 1])

        with col_doc1:
            if is_example:
                st.info("📝 Dados de exemplo disponíveis para teste")
            else:
                st.success(f"📊 Dados coletados prontos: `{json_to_use.name}`")

        with col_doc2:
            btn_label = "📄 Gerar Documento" if is_example else "📄 Gerar DOCX"
            if st.button(btn_label, key="gen_doc_btn", use_container_width=True):
                # Import via adapter (padrão usado pelo DOU) - falha silenciosa se lxml corrompido
                from dou_snaptrack.adapters.eagendas_adapter import generate_eagendas_document_from_json

                if generate_eagendas_document_from_json is None:
                    st.error("❌ **Módulo python-docx não encontrado ou corrompido**")
                    st.warning("🔧 Este é um problema comum no Windows com lxml corrompido")

                    with st.expander("🔍 Detalhes do erro"):
                        st.code("O módulo eagendas_document não pôde ser carregado (lxml corrompido)", language="text")
                        st.code(f"Python: {sys.executable}", language="text")

                    st.divider()
                    st.markdown("**💡 Solução recomendada:**")
                    fix_cmd = f'"{sys.executable}" -m pip uninstall -y lxml python-docx\n"{sys.executable}" -m pip install --no-cache-dir lxml python-docx'
                    st.code(fix_cmd, language="powershell")
                    st.caption("Execute os comandos acima no PowerShell, reinicie a UI e tente novamente")
                else:
                    try:
                        # Gerar nome do documento
                        if is_example:
                            out_path = Path("resultados") / "eagendas_agentes_exemplo.docx"
                            doc_title = "Agendas de Agentes Públicos - Exemplo"
                        else:
                            out_path = json_to_use.with_suffix(".docx")
                            doc_title = f"Agendas E-Agendas - {date_start.strftime('%d/%m/%Y')} a {date_end.strftime('%d/%m/%Y')}"

                        with st.spinner("Gerando documento DOCX..."):
                            result = generate_eagendas_document_from_json(
                                json_path=json_to_use,
                                out_path=out_path,
                                include_metadata=True,
                                title=doc_title
                            )

                        st.success("✅ Documento gerado com sucesso!")
                        st.metric("Agentes", result["agents"])
                        st.metric("Eventos", result["events"])
                        st.caption(result["period"])

                        # Oferecer download
                        with open(out_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Baixar Documento DOCX",
                                data=f,
                                file_name=out_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                        # Persistir em sessão para permitir download separado e remoção posterior
                        try:
                            with open(out_path, "rb") as _df:
                                st.session_state["last_eagendas_doc_bytes"] = _df.read()
                            st.session_state["last_eagendas_doc_name"] = out_path.name
                            st.session_state["last_eagendas_doc_path"] = str(out_path)
                        except Exception:
                            pass

                    except Exception as e:
                        st.error(f"❌ Erro ao gerar documento: {e}")
                        with st.expander("🔍 Traceback completo"):
                            import traceback
                            st.code(traceback.format_exc())
    else:
        st.info("💡 Execute a coleta de eventos primeiro ou use o script de teste para gerar dados de exemplo")
        st.code("python scripts/test_eagendas_document.py", language="bash")

    # Download separado de documento gerado anteriormente (padrão usado pelo boletim DOU)
    _doc_bytes = st.session_state.get("last_eagendas_doc_bytes")
    _doc_name = st.session_state.get("last_eagendas_doc_name")
    _doc_path = st.session_state.get("last_eagendas_doc_path")

    if _doc_bytes and _doc_name:
        st.divider()
        dl_clicked = st.download_button(
            label="⬇️ Baixar último DOCX gerado",
            data=_doc_bytes,
            file_name=_doc_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="dl_last_eagendas_doc"
        )
        if dl_clicked:
            # Remover arquivo gerado no servidor após o download
            try:
                if _doc_path:
                    from pathlib import Path as _P
                    p = _P(str(_doc_path))
                    if p.exists():
                        p.unlink(missing_ok=True)
                        st.toast("🗑️ Arquivo DOCX removido do servidor")
            except Exception as _e:
                st.warning(f"Não foi possível remover o arquivo local: {_doc_path} — {_e}")

            # Remover também o JSON de origem se existir
            try:
                if "last_eagendas_json" in st.session_state:
                    json_path_str = st.session_state["last_eagendas_json"]
                    from pathlib import Path as _P
                    json_p = _P(json_path_str)
                    if json_p.exists():
                        json_p.unlink(missing_ok=True)
                        st.toast(f"🗑️ JSON de dados ({json_p.name}) removido")
                    st.session_state.pop("last_eagendas_json", None)
            except Exception as _e:
                # Falha silenciosa - JSON não é crítico
                pass

            # Limpar dados da sessão para evitar re-download e liberar memória
            for k in ("last_eagendas_doc_bytes", "last_eagendas_doc_name", "last_eagendas_doc_path"):
                st.session_state.pop(k, None)


# ======================== TAB 4: Manutenção do Artefato de Pares ========================
with st.sidebar:
    st.divider()
    with st.expander("🔧 Manutenção do Artefato", expanded=False):
        st.caption("Gerenciar pairs_DO1_full.json")

        from dou_snaptrack.utils.pairs_updater import get_pairs_file_info, update_pairs_file_async

        info = get_pairs_file_info()

        if info["exists"]:
            st.metric("Status", "✅ Existe" if not info["is_stale"] else "⚠️ Obsoleto")
            if info["age_days"] is not None:
                st.metric("Idade", f"{info['age_days']:.1f} dias")
            if info["n1_count"]:
                st.metric("Órgãos (N1)", info["n1_count"])
            if info["pairs_count"]:
                st.metric("Pares (N1→N2)", info["pairs_count"])
            if info["last_update"]:
                st.caption(f"Última atualização: {info['last_update'][:19]}")
        else:
            st.warning("⚠️ Arquivo não encontrado")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Atualizar Agora", key="update_pairs_btn", use_container_width=True):
                with st.spinner("Scraping DOU para atualizar pares..."):
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    # MIGRAÇÃO ASYNC: Usar update_pairs_file_async com asyncio.run()
                    import asyncio

                    def progress_callback(pct: float, msg: str):
                        progress_bar.progress(pct)
                        status_text.text(msg)

                    try:
                        result = asyncio.run(
                            update_pairs_file_async(
                                limit1=5,  # Limitar para teste rápido
                                progress_callback=progress_callback,
                            )
                        )
                    except Exception as e:
                        result = {"success": False, "error": f"{type(e).__name__}: {e}"}

                    progress_bar.empty()
                    status_text.empty()

                    if result.get("success"):
                        st.success(
                            f"✅ Atualizado! {result.get('n1_count', 0)} órgãos, {result.get('pairs_count', 0)} pares"
                        )
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")

        with col2:
            if st.button("Info", key="info_pairs_btn", use_container_width=True):
                st.json(info, expanded=True)

            st.caption("Arquivo do boletim removido do servidor. Os JSONs permanecem em 'resultados/'.")
