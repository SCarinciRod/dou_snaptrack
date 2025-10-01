from __future__ import annotations

import json
import sys
import asyncio
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st


# ---------------- Helpers ----------------
# Corrigir política do loop no Windows para evitar NotImplementedError com Playwright
if sys.platform.startswith("win"):
    try:
        # No Windows, subprocess (usado pelo Playwright) requer ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
@dataclass
class PlanState:
    date: str
    secao: str
    combos: List[Dict[str, Any]]
    defaults: Dict[str, Any]


def _ensure_state():
    if "plan" not in st.session_state:
        st.session_state.plan = PlanState(
            date=_date.today().strftime("%d-%m-%Y"),
            secao="DO1",
            combos=[],
            defaults={
                "scrape_detail": False,
                "summary_lines": 4,
                "summary_mode": "center",
                "bulletin": "docx",
                "bulletin_out": "boletim_{secao}_{date}_{idx}.docx",
            },
        )


def _load_pairs_file(p: Path) -> Dict[str, List[str]]:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Espera formato {"pairs": {"N1": ["N2", ...]}}
        pairs = data.get("pairs") or {}
        if isinstance(pairs, dict):
            norm = {}
            for k, v in pairs.items():
                if isinstance(v, list):
                    norm[str(k)] = [str(x) for x in v]
            return norm
    except Exception:
        pass
    return {}


def _build_combos(n1: str, n2_list: List[str], key_type: str = "text") -> List[Dict[str, Any]]:
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


def _plan_live_fetch_n2(secao: str, date: str, n1: str, limit2: Optional[int] = 20) -> List[str]:
    # Usa build_plan_live para descobrir pares válidos do dia para um N1 específico
    try:
        import sys as _sys, asyncio as _asyncio
        # Garantir Proactor loop no momento do uso do Playwright (Windows)
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        from playwright.sync_api import sync_playwright  # type: ignore
        from types import SimpleNamespace
        from dou_snaptrack.cli.plan_live import build_plan_live
        with sync_playwright() as p:
            args = SimpleNamespace(
                secao=secao,
                data=date,
                plan_out=None,
                select1=None,
                select2=None,
                select3=None,
                pick1=n1,
                pick2=None,
                pick3=None,
                limit1=None,
                limit2=limit2,
                limit3=None,
                key1_type_default="text",
                key2_type_default="text",
                key3_type_default="text",
                plan_verbose=False,
                query=None,
            )
            cfg = build_plan_live(p, args)
            combos = cfg.get("combos", [])
            n2s = sorted({c.get("key2") for c in combos if c.get("key1") == n1 and c.get("key2")})
            return n2s
    except Exception as e:
        st.error(f"Falha no plan-live: {e}")
        return []


def _plan_live_fetch_n1_options(secao: str, date: str) -> List[str]:
    """Descobre as opções do dropdown N1 diretamente do site (como no combo do DOU)."""
    import traceback
    try:
        import sys as _sys, asyncio as _asyncio
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        from playwright.sync_api import sync_playwright, TimeoutError  # type: ignore
        from dou_snaptrack.utils.browser import build_dou_url, goto, try_visualizar_em_lista
        from dou_snaptrack.utils.dom import find_best_frame
        from dou_snaptrack.cli.plan_live import _collect_dropdown_roots, _read_dropdown_options  # type: ignore

        with sync_playwright() as p:
            # Preferir Chrome do sistema para evitar downloads (SSL restrito)
            import os
            from pathlib import Path
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
            except Exception:
                try:
                    browser = p.chromium.launch(channel="msedge", headless=True)
                except Exception:
                    exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
                    if not exe:
                        for c in (
                            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                        ):
                            if Path(c).exists():
                                exe = c; break
                    if exe and Path(exe).exists():
                        try:
                            browser = p.chromium.launch(executable_path=exe, headless=True)
                        except Exception:
                            browser = p.chromium.launch(headless=True)
                    else:
                        browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
                page = context.new_page()
                url = build_dou_url(date, secao)
                goto(page, url)
                try:
                    try_visualizar_em_lista(page)
                except Exception:
                    pass
                frame = find_best_frame(context)
                roots = _collect_dropdown_roots(frame)
                r1 = roots[0] if roots else None
                if not r1:
                    st.error("[ERRO] Nenhum dropdown N1 detectado. Verifique se há publicações para a data/seção escolhidas.")
                    return []
                opts = _read_dropdown_options(frame, r1)
                if not opts:
                    st.error("[ERRO] Nenhuma opção encontrada no dropdown N1. Pode ser problema de seletores ou página vazia.")
                    return []
                texts = []
                for o in opts:
                    t = (o.get("text") or "").strip()
                    if not t or t.lower() == "todos":
                        continue
                    texts.append(t)
                uniq = sorted({t for t in texts})
                if not uniq:
                    st.error("[ERRO] Lista de N1 está vazia após filtragem. Tente outra data/seção ou revise o site.")
                return uniq
            except TimeoutError:
                st.error("[ERRO] Timeout ao tentar carregar opções N1. Tente novamente ou revise a conexão.")
                return []
            except Exception as e:
                tb = traceback.format_exc(limit=4)
                st.error(f"[ERRO] Falha ao listar N1 ao vivo: {type(e).__name__}: {e}\n\nTraceback:\n{tb}")
                st.info("Possíveis causas: Playwright browsers não instalados, venv não ativado, dependências faltando.\n\nPara instalar browsers, rode:")
                st.code("python -m playwright install", language="powershell")
                return []
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        tb = traceback.format_exc(limit=4)
        st.error(f"[ERRO] Falha Playwright/UI: {type(e).__name__}: {e}\n\nTraceback:\n{tb}")
        st.info("Possíveis causas: Playwright browsers não instalados, venv não ativado, dependências faltando.\n\nPara instalar browsers, rode:")
        st.code("python -m playwright install", language="powershell")
        return []


def _run_batch_with_cfg(cfg_path: Path, parallel: int) -> Dict[str, Any]:
    try:
        import sys as _sys, asyncio as _asyncio
        if _sys.platform.startswith("win"):
            try:
                _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
                _asyncio.set_event_loop(_asyncio.new_event_loop())
            except Exception:
                pass
        from playwright.sync_api import sync_playwright  # type: ignore
        from dou_snaptrack.cli.batch import run_batch
        from dou_snaptrack.cli.summary_config import SummaryConfig
        with sync_playwright() as p:
            class Args:
                config = str(cfg_path)
                out_dir = "."
                headful = False
                slowmo = 0
                state_file = None
                reuse_page = False
                parallel = parallel
            run_batch(p, Args, SummaryConfig(lines=4, mode="center", keywords=None))
        rep = json.loads(Path("batch_report.json").read_text(encoding="utf-8")) if Path("batch_report.json").exists() else {}
        return rep
    except Exception as e:
        st.error(f"Falha ao executar batch: {e}")
        return {}


def _run_report(in_dir: Path, kind: str, out_path: Path, split_by_n1: bool, date_label: str, secao_label: str,
                summary_lines: int, summary_mode: str):
    try:
        if split_by_n1:
            from dou_snaptrack.cli.reporting import split_and_report_by_n1
            split_and_report_by_n1(
                str(in_dir), kind, str(out_path), "boletim_{n1}_{date}.docx",
                date_label=date_label, secao_label=secao_label,
                summary_lines=summary_lines, summary_mode=summary_mode,
            )
        else:
            from dou_snaptrack.cli.reporting import consolidate_and_report
            consolidate_and_report(
                str(in_dir), kind, str(out_path),
                date_label=date_label, secao_label=secao_label,
                summary_lines=summary_lines, summary_mode=summary_mode,
            )
        st.success("Boletim gerado!")
    except Exception as e:
        st.error(f"Falha ao gerar boletim: {e}")


# ---------------- UI ----------------
st.set_page_config(page_title="SnapTrack DOU • UI", layout="wide")
st.title("SnapTrack DOU — Interface")
_ensure_state()

with st.sidebar:
    st.header("Configuração")
    st.session_state.plan.date = st.text_input("Data (DD-MM-AAAA)", st.session_state.plan.date)
    st.session_state.plan.secao = st.selectbox("Seção", ["DO1", "DO2", "DO3"], index=0)
    st.markdown("- Padrão: hoje; altere se necessário.")

    st.info("A execução usa preferencialmente o Chrome/Edge instalados (canal 'chrome'); se indisponível, cai para o Chromium do Playwright.")

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
        except Exception as _e:
            st.write(f"[diag] erro: {_e}")

tab1, tab2, tab3 = st.tabs(["Explorar e montar plano", "Executar plano", "Gerar boletim"])

with tab1:
    st.subheader("Explorar N1/N2 e montar plano")
    source = st.radio("Fonte das opções", ["Arquivo de pares (rápido)", "Descoberta ao vivo (plan-live)"], index=0)
    pairs_map: Dict[str, List[str]] = {}
    if source == "Arquivo de pares (rápido)":
        default_pairs = Path("artefatos/pairs_DO1_full.json")
        pairs_file = st.text_input("Arquivo de pares (JSON)", str(default_pairs if default_pairs.exists() else ""))
        if pairs_file:
            pairs_map = _load_pairs_file(Path(pairs_file))
        n1_list = sorted(pairs_map.keys())
        n1 = st.selectbox("Nível 1 (Órgão)", n1_list) if n1_list else None
        n2_list = pairs_map.get(n1, []) if n1 else []
    else:
        # Descoberta ao vivo: primeiro carrega lista de N1, depois carrega N2 para o N1 selecionado
        if st.button("Carregar N1 (ao vivo)"):
            with st.spinner("Obtendo lista de N1 do DOU…"):
                n1_candidates = _plan_live_fetch_n1_options(str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or ""))
            st.session_state["live_n1"] = n1_candidates

        n1_list = st.session_state.get("live_n1", [])
        if n1_list:
            n1 = st.selectbox("Nível 1 (Órgão)", n1_list, key="sel_n1_live")
        else:
            n1 = None
            st.info("Clique em 'Carregar N1 (ao vivo)' para listar os órgãos.")

        # Carregar N2 conforme N1 escolhido
        n2_list = []
        can_load_n2 = bool(n1)
        if st.button("Carregar N2 para o N1 selecionado") and can_load_n2:
            with st.spinner("Obtendo lista de N2 do DOU…"):
                n2_list = _plan_live_fetch_n2(str(st.session_state.plan.secao or ""), str(st.session_state.plan.date or ""), str(n1))
            st.session_state["live_n2_for_" + str(n1)] = n2_list
        if n1:
            n2_list = st.session_state.get("live_n2_for_" + str(n1), [])

    sel_n2 = st.multiselect("Nível 2 (Unidade)", options=n2_list)
    if st.button("Adicionar ao plano", disabled=not (n1 and sel_n2)):
        add = _build_combos(str(n1), sel_n2)
        st.session_state.plan.combos.extend(add)
        st.success(f"Adicionados {len(add)} combos ao plano.")

    st.write("Plano atual:")
    st.dataframe(st.session_state.plan.combos)

    cols = st.columns(2)
    with cols[0]:
        if st.button("Limpar plano"):
            st.session_state.plan.combos = []
            st.success("Plano limpo.")

    st.divider()
    st.subheader("Salvar plano")
    plan_path = st.text_input("Salvar como (ex.: batch_today.json)", "batch_today.json")
    if st.button("Salvar plano"):
        cfg = {
            "data": st.session_state.plan.date,
            "secaoDefault": st.session_state.plan.secao,
            "defaults": st.session_state.plan.defaults,
            "combos": st.session_state.plan.combos,
            "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"}
        }
        Path(plan_path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Plano salvo em {plan_path}")

with tab2:
    st.subheader("Executar plano (batch)")
    plan_to_run = st.text_input("Arquivo do plano (JSON)", "batch_today.json")
    parallel = st.number_input("Parallel workers", min_value=1, max_value=8, value=4, step=1)
    if st.button("Executar batch"):
        if not Path(plan_to_run).exists():
            st.error("Plano não encontrado.")
        else:
            with st.spinner("Executando…"):
                rep = _run_batch_with_cfg(Path(plan_to_run), int(parallel))
            st.write(rep or {"info": "Sem relatório"})

with tab3:
    st.subheader("Gerar boletim")
    in_dir = st.text_input("Pasta de entrada (JSONs)", "out_batch")
    kind = st.selectbox("Formato", ["docx", "md", "html"], index=0)
    split = st.checkbox("Gerar um arquivo por N1", value=False)
    base_tpl = "logs/boletim_{secao}_{date}.docx" if not split else "logs/run/unused.docx"
    base_tpl = base_tpl.replace("{date}", str(st.session_state.plan.date or "")).replace("{secao}", str(st.session_state.plan.secao or ""))
    out_path = st.text_input("Destino do boletim", base_tpl)
    summary_lines = st.number_input("Resumo: nº de linhas por item (0=desligado)", min_value=0, max_value=10, value=4)
    summary_mode = st.selectbox("Modo do resumo", ["center", "lead", "keywords-first"], index=0)
    if st.button("Gerar boletim"):
        with st.spinner("Gerando…"):
            _run_report(Path(str(in_dir or "")), kind, Path(str(out_path or "")), split, str(st.session_state.plan.date or ""), str(st.session_state.plan.secao or ""),
                        int(summary_lines), str(summary_mode))
