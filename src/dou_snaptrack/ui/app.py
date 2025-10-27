from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import date as _date
from functools import lru_cache
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Garantir que a pasta src/ esteja no PYTHONPATH (execução via streamlit run src/...)
SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# OTIMIZAÇÃO: Lazy imports - só carrega quando necessário
# Streamlit é leve, pode carregar logo
import streamlit as st

# OTIMIZAÇÃO: Imports pesados apenas quando TYPE_CHECKING ou sob demanda
if TYPE_CHECKING:
    from playwright.sync_api import sync_playwright

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
        'clear_ui_lock': clear_ui_lock,
        'detect_other_execution': detect_other_execution,
        'detect_other_ui': detect_other_ui,
        'register_this_ui_instance': register_this_ui_instance,
        'terminate_other_execution': terminate_other_execution,
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
    prefer_edge = (os.environ.get("DOU_PREFER_EDGE", "").strip() or "0").lower() in ("1","true","yes")
    candidates = [
        r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ] if prefer_edge else [
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    ]
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
    out = []
    for n2 in n2_list:
        out.append({
            "key1_type": key_type,
            "key1": n1,
            "key2_type": key_type,
            "key2": n2,
            "key3_type": None,
            "key3": None,
            "label1": "",
            "label2": "",
            "label3": "",
        })
    return out


# REMOVIDO: _get_thread_local_playwright_and_browser() - não mais necessário após migração para async API


@st.cache_data(show_spinner=False, ttl=300)
def _plan_live_fetch_n2(secao: str, date: str, n1: str, limit2: int | None = 20) -> list[str]:
    """Busca opções N2 (organizações subordinadas) para um N1 específico.
    
    VERSÃO ASYNC-COMPATIBLE: Usa plan_live_async com asyncio.run()
    """
    import asyncio
    from types import SimpleNamespace
    from playwright.async_api import async_playwright
    from dou_snaptrack.cli.plan_live_async import build_plan_live_async

    async def fetch_n2_options():
        async with async_playwright() as p:
            args = SimpleNamespace(
                secao=secao,
                data=date,
                plan_out=None,
                select1=None,
                select2=None,
                pick1=n1,
                pick2=None,
                limit1=None,
                limit2=limit2,
                headless=True,
                slowmo=0,
            )
            
            try:
                cfg = await build_plan_live_async(p, args)
                combos = cfg.get("combos", [])
                
                # Extrair lista única de N2 para o N1 escolhido
                n2_set = set()
                for c in combos:
                    k2 = c.get("key2", "")
                    if k2 and k2 != "Todos":
                        n2_set.add(k2)
                
                return sorted(n2_set)
            except Exception:
                return []
    
    try:
        return asyncio.run(fetch_n2_options())
    except Exception:
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
                    context = await browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
                    context.set_default_timeout(90_000)
                    page = await context.new_page()
                    url = build_dou_url(date, secao)
                    await goto_async(page, url)
                    try:
                        await try_visualizar_em_lista_async(page)
                    except Exception:
                        pass
                    frame = await find_best_frame_async(context)
                    try:
                        await page.wait_for_timeout(3000)
                    except Exception:
                        pass
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
                    uniq = sorted({t for t in texts})
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
                    try:
                        await context.close()
                    except Exception:
                        pass
                    try:
                        await browser.close()
                    except Exception:
                        pass
        
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
    import subprocess
    import json
    import tempfile
    from pathlib import Path
    
    # Criar script temporário para executar em processo isolado
    # Passar src_path como argumento porque __file__ não existe em 'python -c'
    src_path = str(SRC_ROOT / "src")
    
    script_content = f'''
import sys

# Add src to path (passado como literal porque __file__ não existe em python -c)
src_root = r"{src_path}"
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
    try:
        result = subprocess.run(
            [sys.executable, "-c", script_content],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent)  # Raiz do projeto
        )
        
        if result.returncode != 0:
            try:
                error_data = json.loads(result.stdout)
                st.error(f"[ERRO] {error_data.get('error', 'Erro desconhecido')}")
            except Exception:
                st.error(f"[ERRO] Falha ao carregar N1: {result.stderr}")
            return []
        
        data = json.loads(result.stdout)
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
        return []


def _run_batch_with_cfg(cfg_path: Path, parallel: int, fast_mode: bool = False, prefer_edge: bool = True) -> dict[str, Any]:
    """Wrapper que delega para o runner livre de Streamlit para permitir uso headless e via UI."""
    try:
        from dou_snaptrack.ui.batch_runner import run_batch_with_cfg as _runner
        return _runner(cfg_path, parallel=int(parallel), fast_mode=bool(fast_mode), prefer_edge=bool(prefer_edge))
    except Exception as e:
        st.error(f"Falha ao executar batch: {e}")
        return {}

def _run_report(in_dir: Path, kind: str, out_dir: Path, base_name: str, split_by_n1: bool, date_label: str, secao_label: str,
                summary_lines: int, summary_mode: str, summary_keywords: list[str] | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if split_by_n1:
            from dou_snaptrack.cli.reporting import split_and_report_by_n1
            # Gravar diretamente dentro de out_dir
            pattern = out_dir / f"boletim_{{n1}}_{date_label}.{kind}"
            split_and_report_by_n1(
                str(in_dir), kind, str(out_dir / "unused"), str(pattern),
                date_label=date_label, secao_label=secao_label,
                summary_lines=summary_lines, summary_mode=summary_mode,
                summary_keywords=summary_keywords,
            )
            files = sorted(out_dir.glob(f"boletim_*_{date_label}.{kind}"))
        else:
            from dou_snaptrack.cli.reporting import consolidate_and_report
            out_path = out_dir / base_name
            consolidate_and_report(
                str(in_dir), kind, str(out_path),
                date_label=date_label, secao_label=secao_label,
                summary_lines=summary_lines, summary_mode=summary_mode,
                summary_keywords=summary_keywords,
            )
            files = [out_path]
        return files
    except Exception as e:
        st.error(f"Falha ao gerar boletim: {e}")
        return []


# ---------------- UI ----------------
st.set_page_config(page_title="SnapTrack DOU ", layout="wide")

# OTIMIZAÇÃO: Lazy load batch_runner apenas quando necessário (startup mais rápido)
# Detect another UI and register this one
batch_funcs = get_batch_runner()
other_ui = batch_funcs['detect_other_ui']()
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
        ok = batch_funcs['terminate_other_execution'](int(other_ui.get("pid") or 0))
        if ok:
            st.success("Outra UI encerrada. Prosseguindo…")
        else:
            st.error("Falha ao encerrar a outra UI. Feche manualmente a janela/processo.")
    elif clear_lock:
        try:
            batch_funcs['clear_ui_lock']()
            st.success("Lock removido. Prosseguindo…")
        except Exception as _e:
            st.error(f"Falha ao remover lock: {_e}")
    elif not ignore_ui:
        st.stop()

# Register this UI instance for future launches
batch_funcs['register_this_ui_instance']()

st.title("SnapTrack DOU — Interface")
_ensure_state()

with st.sidebar:
    st.header("Configuração")
    
    # Date picker visual (calendário) ao invés de text input
    from datetime import datetime, timedelta
    
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
        help="Selecione a data de publicação do DOU para consulta"
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
                        exe_hint = c; break
            st.write({
                "OS": f"{_plat.system()} {_plat.release()}",
                "Python": pyver,
                "Interpreter": exe,
                "EventLoopPolicy": loop_policy,
                "Playwright": pw_ver,
                "Chrome/Edge path": exe_hint or "canal 'chrome' (auto)",
            })
            # Botão para reiniciar recursos Playwright desta thread
            if st.button("Reiniciar navegador (UI)"):
                try:
                    # Fechar e remover quaisquer recursos thread-local desta sessão
                    to_del = []
                    for k, v in list(st.session_state.items()):
                        if isinstance(k, str) and k.startswith("_pw_res_tid_"):
                            try:
                                if hasattr(v, "close"):
                                    v.close()
                            except Exception:
                                pass
                            to_del.append(k)
                    for k in to_del:
                        try:
                            del st.session_state[k]
                        except Exception:
                            pass
                    st.success("Navegador reiniciado para esta sessão.")
                except Exception as _e2:
                    st.error(f"Falha ao reiniciar navegador: {_e2}")
        except Exception as _e:
            st.write(f"[diag] erro: {_e}")

tab1, tab2, tab3 = st.tabs(["Explorar e montar plano", "Executar plano", "Gerar boletim"])

with tab1:
    st.subheader("Monte sua Pesquisa")
    # Descoberta ao vivo: primeiro carrega lista de N1, depois carrega N2 para o N1 selecionado
    if st.button("Carregar"):
        with st.spinner("Obtendo lista de Orgãos do DOU…"):
            n1_candidates = _plan_live_fetch_n1_options(str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or ""))
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
    if st.button("Carregar Organizações Subordinadas") and can_load_n2:
        with st.spinner("Obtendo lista do DOU…"):
            n2_list = _plan_live_fetch_n2(str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or ""), str(n1))
        st.session_state["live_n2_for_" + str(n1)] = n2_list
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
        add_n1_only = (n1 and not n2_list)
        if st.button("Orgão sem Suborganizações", disabled=not add_n1_only):
            add = _build_combos(str(n1), ["Todos"])  # N2='Todos' indica sem filtro de N2
            st.session_state.plan.combos.extend(add)
            st.success("Adicionado N1 com N2='Todos'.")

    st.write("Plano atual:")
    st.dataframe(st.session_state.plan.combos)

    cols = st.columns(2)
    with cols[0]:
        if st.button("Limpar plano"):
            st.session_state.plan.combos = []
            st.success("Plano limpo.")

    st.divider()
    st.subheader("Salvar plano")
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
            "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"}
        }
        # Propagar nome do plano, se informado
        _pname = st.session_state.get("plan_name_ui")
        if isinstance(_pname, str) and _pname.strip():
            cfg["plan_name"] = _pname.strip()
        ppath = Path(plan_path); ppath.parent.mkdir(parents=True, exist_ok=True)
        ppath.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Plano salvo em {plan_path}")

with tab2:
    st.subheader("Escolha o plano de pesquisa")
    # OTIMIZAÇÃO: Criação lazy de diretórios
    plans_dir, _ = _ensure_dirs()
    plan_candidates = []
    try:
        for p in plans_dir.glob("*.json"):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if any(k in txt for k in ('"combos"', '"secaoDefault"', '"output"')):
                    plan_candidates.append(p)
            except Exception:
                pass
    except Exception:
        pass
    plan_candidates = sorted(set(plan_candidates))
    if not plan_candidates:
        st.info("Nenhum plano salvo ainda. Informe um caminho válido abaixo.")
        plan_to_run = st.text_input("Arquivo do plano (JSON)", "batch_today.json")
        selected_path = Path(plan_to_run)
    else:
        labels = [str(p) for p in plan_candidates]
        choice = st.selectbox("Selecione o plano salvo", labels, index=0)
        selected_path = Path(choice)

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
            other = batch_funcs['detect_other_execution']()
            if other:
                st.warning(f"Outra execução detectada (PID={other.get('pid')} iniciada em {other.get('started')}).")
                colx = st.columns(2)
                with colx[0]:
                    kill_it = st.button("Encerrar outra execução (forçar)")
                with colx[1]:
                    proceed_anyway = st.button("Prosseguir sem encerrar")
                if kill_it:
                    ok = batch_funcs['terminate_other_execution'](int(other.get("pid") or 0))
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
                            cand = (c0.get("label1") or c0.get("key1") or "Plano")
                            cfg_json["plan_name"] = sanitize_fn(str(cand))
                    except Exception:
                        cfg_json["plan_name"] = "Plano"
                # Gerar um config temporário para a execução desta sessão, sem modificar o arquivo salvo
                out_dir_tmp = Path("resultados") / override_date
                out_dir_tmp.mkdir(parents=True, exist_ok=True)
                pass_cfg_path = out_dir_tmp / "_run_cfg.from_ui.json"
                try:
                    pass_cfg_path.write_text(json.dumps(cfg_json, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
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
    results_root = Path("resultados"); results_root.mkdir(parents=True, exist_ok=True)
    # Formato e política padronizada de resumo (sem escolhas do usuário)
    # Padrões fixos: summary_lines=7, summary_mode="center", keywords=None
    st.caption("Os resumos são gerados com parâmetros padronizados (modo center, 7 linhas) e captura profunda automática.")
    st.caption("Gere boletim a partir de agregados do dia: {plan}_{secao}_{data}.json (dentro da pasta da data)")

    # Deep-mode: sem opções expostas. Usamos parâmetros fixos e mantemos modo online.

    # Ação auxiliar: agregação manual a partir de uma pasta de dia
    with st.expander("Agregação manual (quando necessário)"):
        day_dirs = []
        try:
            for d in results_root.iterdir():
                if d.is_dir():
                    day_dirs.append(d)
        except Exception:
            pass
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
            manual_plan = st.text_input("Nome do plano (para nome do arquivo agregado)", value=st.session_state.get("plan_name_ui", ""), key="agg_manual_plan")
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
        for d in results_root.iterdir():
            if d.is_dir():
                day_dirs.append(d)
    except Exception:
        pass
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
                    try:
                        os.environ["DOU_OFFLINE_REPORT"] = "0"
                    except Exception:
                        pass
                    report_from_aggregated(
                        [str(p) for p in files], kind2, str(out_path),
                        date_label=str(sel_day), secao_label=secao_label,
                        summary_lines=7, summary_mode="center",
                        summary_keywords=None, order_desc_by_date=True,
                        fetch_parallel=8, fetch_timeout_sec=30,
                        fetch_force_refresh=True, fetch_browser_fallback=True,
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
                        st.download_button("Baixar boletim (plano)", data=data, file_name=out_path.name, key="dl_fallback")
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
                try:
                    del st.session_state[k]
                except Exception:
                    pass


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
                                progress_callback=progress_callback
                            )
                        )
                    except Exception as e:
                        result = {"success": False, "error": f"{type(e).__name__}: {e}"}
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    if result.get("success"):
                        st.success(f"✅ Atualizado! {result.get('n1_count', 0)} órgãos, {result.get('pairs_count', 0)} pares")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")
        
        with col2:
            if st.button("ℹ️ Ver Info", key="info_pairs_btn", use_container_width=True):
                st.json(info, expanded=True)

            st.caption("Arquivo do boletim removido do servidor. Os JSONs permanecem em 'resultados/'.")
