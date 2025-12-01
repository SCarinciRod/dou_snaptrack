"""
SnapTrack DOU — Streamlit UI Application.

This is the main UI module for the DOU SnapTrack application.
It provides a web interface for:
- Building and managing DOU scraping plans
- Executing batch scraping jobs
- Generating bulletins from scraped data
- E-Agendas consultation

See MODULE DOCUMENTATION section below for future modularization plan.
"""
from __future__ import annotations  # noqa: I001

# =============================================================================
# SECTION: IMPORTS
# =============================================================================
# Standard library
import asyncio
import atexit
import contextlib
import json
import logging
import os
import sys
import time
import traceback
from datetime import date as _date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Third-party
import streamlit as st

# Local imports (new modular structure)
from dou_snaptrack.ui.state import (
    PlanState,
    SessionManager,
    ensure_dirs,
    ensure_eagendas_state,
    ensure_state,
)
from dou_snaptrack.ui.subprocess_utils import execute_script_and_read_result
from dou_snaptrack.ui.dou_fetch import (
    fetch_n1_options as _plan_live_fetch_n1_options,
    fetch_n2_options as _plan_live_fetch_n2,
)
from dou_snaptrack.ui.eagendas_fetch import (
    fetch_hierarchy as _eagendas_fetch_hierarchy,
)
from dou_snaptrack.ui.plan_editor import (
    _build_combos,
    _list_saved_plan_files,
    _resolve_combo_label,
    render_plan_discovery,
    render_plan_loader,
    render_plan_editor_table,
    render_plan_saver,
    PlanEditorSession,
)
from dou_snaptrack.ui.eagendas_ui import (
    render_hierarchy_selector,
    render_date_period_selector,
    render_query_manager,
    render_lista_manager,
    render_saved_queries_list,
    render_execution_section,
    render_document_generator,
    render_document_download,
    EAgendasSession,
)
from dou_snaptrack.ui.sidebar import render_sidebar
from dou_snaptrack.ui.batch_executor import render_batch_executor
from dou_snaptrack.ui.report_generator import render_report_generator

# =============================================================================
# SECTION: PATH SETUP
# =============================================================================
# Garantir que a pasta src/ esteja no PYTHONPATH (execução via streamlit run src/...)
SRC_ROOT = Path(__file__).resolve().parents[2]
CWD_ROOT = str(SRC_ROOT)  # Pre-computed for subprocess cwd
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# OTIMIZAÇÃO: Imports pesados apenas quando TYPE_CHECKING ou sob demanda
if TYPE_CHECKING:  # pragma: no cover - apenas para type checkers
    pass


# =============================================================================
# SECTION: LOGGING CONFIGURATION
# =============================================================================
# Logging setup
LOG_DIR = Path("logs")
with contextlib.suppress(Exception):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("dou_snaptrack.ui")
if not logger.handlers:
    with contextlib.suppress(Exception):
        _fh = logging.FileHandler(LOG_DIR / "ui_app.log", encoding="utf-8")
        _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(_fh)

_LOG_LEVEL = os.environ.get("DOU_UI_LOG_LEVEL", "INFO")
logger.setLevel(getattr(logging, _LOG_LEVEL.upper(), logging.INFO))


# =============================================================================
# SECTION: CLEANUP ON EXIT
# =============================================================================
def _cleanup_on_exit():
    """Cleanup function called when UI process exits.
    
    Kills orphaned batch subprocesses and removes lock files.
    """
    try:
        from dou_snaptrack.ui.batch_runner import cleanup_batch_processes, clear_ui_lock
        cleanup_batch_processes()
        clear_ui_lock()
        logger.info("UI cleanup completed on exit")
    except Exception as e:
        logger.warning(f"UI cleanup on exit failed: {e}")

# Register cleanup to run on exit
atexit.register(_cleanup_on_exit)


# =============================================================================
# SECTION: LAZY IMPORTS (Performance optimization)
# Using @lru_cache for cleaner implementation than manual global caching
# =============================================================================
@lru_cache(maxsize=1)
def get_batch_runner() -> dict:
    """Lazy import of batch_runner module (imports Playwright)."""
    from dou_snaptrack.ui.batch_runner import (
        clear_ui_lock,
        cleanup_batch_processes,
        detect_other_execution,
        detect_other_ui,
        register_this_ui_instance,
        terminate_other_execution,
    )
    return {
        "clear_ui_lock": clear_ui_lock,
        "cleanup_batch_processes": cleanup_batch_processes,
        "detect_other_execution": detect_other_execution,
        "detect_other_ui": detect_other_ui,
        "register_this_ui_instance": register_this_ui_instance,
        "terminate_other_execution": terminate_other_execution,
    }


@lru_cache(maxsize=1)
def get_sanitize_filename():
    """Lazy import of sanitize_filename from utils.text."""
    from dou_snaptrack.utils.text import sanitize_filename
    return sanitize_filename


@lru_cache(maxsize=1)
def get_plan_live_eagendas():
    """Lazy import of plan_live_eagendas_async module."""
    from dou_snaptrack.cli import plan_live_eagendas_async
    return plan_live_eagendas_async


@lru_cache(maxsize=1)
def get_eagendas_calendar():
    """Lazy import of eagendas_calendar module."""
    from dou_snaptrack.utils import eagendas_calendar
    return eagendas_calendar


# =============================================================================
# SECTION: PLAN FILE UTILITIES - Moved to plan_editor.py
# =============================================================================
# _plan_metadata and _list_saved_plan_files moved to plan_editor.py and imported above


# =============================================================================
# SECTION: BACKWARD COMPATIBILITY ALIASES
# =============================================================================
# These aliases maintain compatibility with existing code while using new modules
_ensure_state = ensure_state
_ensure_eagendas_state = ensure_eagendas_state
_ensure_dirs = ensure_dirs
_execute_script_and_read_result = execute_script_and_read_result

# Note: SessionManager moved to state.py; SubprocessManager was unused and removed


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


# _find_system_browser_exe moved to dou_fetch.py and imported as _find_system_browser_exe


@st.cache_data(show_spinner=False, ttl=3600)  # Cache por 1 hora - previne dados obsoletos
def _load_pairs_file_cached(path_str: str) -> dict[str, list[str]]:
    """Cached wrapper around _load_pairs_file for UI flows."""
    try:
        return _load_pairs_file(Path(path_str))
    except Exception:
        return {}


# _build_combos moved to plan_editor.py and imported above


# _plan_live_fetch_n2 moved to dou_fetch.py and imported as _plan_live_fetch_n2

# =============================================================================
# SECTION: E-AGENDAS FETCH
# Functions extracted to: dou_snaptrack.ui.eagendas_fetch
# Imports: _eagendas_fetch_hierarchy
# =============================================================================


# _run_batch_with_cfg and _run_report moved to batch_executor.py and report_generator.py


# =============================================================================
# SECTION: STREAMLIT PAGE CONFIGURATION
# =============================================================================
st.set_page_config(page_title="SnapTrack DOU ", layout="wide")

# Theme diagnostic: show current Streamlit theme options and config file contents
try:
    with st.sidebar.expander("Diagnóstico do tema", expanded=False):
        try:
            theme_opts = st.get_option("theme")
        except Exception:
            theme_opts = None
        st.write("Streamlit theme options:")
        st.json(theme_opts or {})

        cfg_path = Path(".streamlit/config.toml")
        if cfg_path.exists():
            try:
                cfg_txt = cfg_path.read_text(encoding="utf-8")
                st.markdown("`.streamlit/config.toml` contents:")
                st.code(cfg_txt, language="toml")
            except Exception as e:
                st.warning(f"Não foi possível ler .streamlit/config.toml: {e}")
        else:
            st.caption("Arquivo `.streamlit/config.toml` não encontrado no diretório atual.")
        st.caption("Reinicie o app com `streamlit run` se alterou o arquivo de config.")
except Exception:
    # Non-fatal: if Streamlit not ready show nothing
    pass


def _resolve_logo_path() -> Path | None:
    """Resolve the logo path from environment or default locations."""
    # Check environment variable first
    env_logo = os.environ.get("DOU_UI_LOGO_PATH")
    if env_logo:
        p = Path(env_logo)
        if p.exists():
            return p
    
    # Default locations
    candidates = [
        Path("assets/logo.png"),
        Path("assets/logo.jpg"),
        Path("src/dou_snaptrack/ui/assets/logo.png"),
        SRC_ROOT / "dou_snaptrack" / "ui" / "assets" / "logo.png",
    ]
    
    for c in candidates:
        if c.exists():
            return c
    
    return None


# _resolve_combo_label moved to plan_editor.py and imported above


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
    placement = os.environ.get("DOU_UI_LOGO_MODE", "corner").strip().lower()
    if placement == "sidebar":
        logo_path = _resolve_logo_path()
        if logo_path:
            try:
                sidebar_width = int(os.environ.get("DOU_UI_LOGO_SIDEBAR_WIDTH", "160"))
            except Exception:
                sidebar_width = 160
            try:
                st.image(str(logo_path), width=sidebar_width)
            except Exception:
                pass

    st.header("Configuração")

    # Date picker visual (calendário) ao invés de text input
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
    SessionManager.set_plan_date(selected_date.strftime("%d-%m-%Y"))

    secao_choice = st.selectbox("Seção", ["DO1", "DO2", "DO3"], index=0)
    SessionManager.set_plan_secao(secao_choice)
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
                    # Atualizar token para invalidar caches que usam refresh_token
                    st.session_state["plan_fetch_refresh_token"] = time.time()
                    st.success("Cache limpo.")
                except Exception as _e3:
                    st.warning(f"Falha ao limpar cache: {_e3}")
        except Exception as _e:
            st.write(f"[diag] erro: {_e}")


# =============================================================================
# SECTION: TAB DOU - Plan Builder and Executor (Future: ui/plan_editor.py)
# =============================================================================

with main_tab_dou:
    tab1, tab2, tab3 = st.tabs(["Explorar e montar plano", "Executar plano", "Gerar boletim"])

with tab1:
    # TAB1: Explorar e montar plano - usa funções render de plan_editor.py
    render_plan_discovery()
    
    st.divider()
    st.subheader("📝 Gerenciar Plano")
    
    render_plan_loader()
    render_plan_editor_table()
    render_plan_saver()

with tab2:
    # TAB2: Executar plano - usa render_batch_executor de batch_executor.py
    render_batch_executor()

with tab3:
    # TAB3: Gerar boletim - usa render_report_generator de report_generator.py
    render_report_generator()


# =============================================================================
# SECTION: TAB E-AGENDAS - Using modular eagendas_ui components
# =============================================================================

with main_tab_eagendas:
    st.subheader("E-Agendas — Consulta de Agendas de Servidores Públicos")

    # Seção 1: Seleção de Órgão/Agente (N1/N2)
    # Modelo simplificado: Órgão → Agente (direto, sem cargo intermediário)
    st.markdown("### 1️⃣ Selecione o Servidor Público")

    col_n1, col_n2 = st.columns(2)

    with col_n1:
        render_hierarchy_selector(
            title="Órgão",
            load_button_text="Carregar Órgãos",
            load_key="eagendas_load_n1",
            options_key="eagendas_n1_options",
            select_key="eagendas_sel_n1",
            current_key="eagendas.current_n1",
            label_key="eagendas_current_n1_label",
            level=1,
        )

    with col_n2:
        n1_selected = st.session_state.eagendas.current_n1
        n1_label = st.session_state.get("eagendas_current_n1_label", "Órgão")
        render_hierarchy_selector(
            title="Agente",
            load_button_text="Carregar Agentes",
            load_key="eagendas_load_n2",
            options_key="eagendas_n2_options",
            select_key="eagendas_sel_n2",
            current_key="eagendas.current_n2",
            label_key="eagendas_current_n2_label",
            level=2,
            parent_value=n1_selected,
            parent_label=n1_label,
        )

    st.divider()

    # Seção 2: Período de Pesquisa (usando função modular)
    date_start, date_end = render_date_period_selector()

    st.divider()

    # Seção 3: Gerenciamento de Consultas Salvas
    render_query_manager()

    # Sub-seção: Salvar/Carregar Listas de Agentes
    render_lista_manager()

    # Mostrar lista de consultas salvas
    render_saved_queries_list()

    st.divider()

    # Seção 4: Execução
    render_execution_section(date_start, date_end)

    st.divider()

    # Seção 5: Geração de Documento
    render_document_generator(date_start, date_end)

    # Download separado de documento gerado anteriormente
    render_document_download()


# =============================================================================
# SECTION: SIDEBAR - Using modular sidebar components
# =============================================================================

render_sidebar()
