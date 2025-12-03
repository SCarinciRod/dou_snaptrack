"""
Batch execution UI components for DOU SnapTrack.

This module provides the UI components for TAB2 "Executar plano".
"""
from __future__ import annotations

import contextlib
import json
import time
from datetime import date as _date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from dou_snaptrack.ui.plan_editor import _list_saved_plan_files

# Local imports
from dou_snaptrack.ui.state import ensure_dirs

if TYPE_CHECKING:
    pass


# =============================================================================
# LAZY IMPORTS
# =============================================================================
@lru_cache(maxsize=1)
def _get_batch_runner() -> dict:
    """Lazy import of batch_runner module (imports Playwright)."""
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


@lru_cache(maxsize=1)
def _get_sanitize_filename():
    """Lazy import of sanitize_filename from utils.text."""
    from dou_snaptrack.utils.text import sanitize_filename
    return sanitize_filename


@lru_cache(maxsize=1)
def _get_recommend_parallel():
    """Lazy import of recommend_parallel from utils.parallel."""
    from dou_snaptrack.utils.parallel import recommend_parallel
    return recommend_parallel


def _load_plan_config(path: Path) -> dict[str, Any]:
    """Load plan config from file with error handling.
    
    OTIMIZAÇÃO: Esta função é o ponto único de leitura de config,
    evitando múltiplas leituras do mesmo arquivo.
    """
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================
def render_batch_executor() -> None:
    """Render the batch executor UI (TAB2 "Executar plano")."""
    st.subheader("Escolha o plano de pesquisa")

    # OTIMIZAÇÃO: Criação lazy de diretórios
    plans_dir, _ = ensure_dirs()
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
    # OTIMIZAÇÃO: Usar _load_plan_config (leitura única) ao invés de read_text()
    cfg_preview = _load_plan_config(selected_path) if selected_path.exists() else {}
    combos_prev = cfg_preview.get("combos") or []
    topics_prev = cfg_preview.get("topics") or []
    est_jobs_prev = len(combos_prev) * max(1, len(topics_prev) or 1)

    recommend_parallel = _get_recommend_parallel()
    suggested_workers = recommend_parallel(est_jobs_prev, prefer_process=True)
    st.caption(f"Paralelismo recomendado: {suggested_workers} (baseado no hardware e plano)")
    st.caption("A captura do plano é sempre 'link-only' (sem detalhes/boletim); gere o boletim na aba correspondente.")

    if st.button("Pesquisar Agora"):
        _execute_plan(selected_path, recommend_parallel)


def _execute_plan(selected_path: Path, recommend_parallel) -> None:
    """Execute the selected plan with concurrency management."""
    if not selected_path.exists():
        st.error("Plano não encontrado.")
        return

    # Concurrency guard: check if another execution is running
    batch_funcs = _get_batch_runner()
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
    # OTIMIZAÇÃO: Reutilizar cfg_preview carregado anteriormente
    # (a função recebe selected_path, então recarregar é seguro)
    cfg = _load_plan_config(selected_path)
    combos = cfg.get("combos") or []
    topics = cfg.get("topics") or []
    est_jobs = len(combos) * max(1, len(topics) or 1)

    # Calcular recomendação no momento da execução
    parallel = int(recommend_parallel(est_jobs, prefer_process=True))

    with st.spinner("Executando…"):
        # OTIMIZAÇÃO: Reutilizar cfg já carregado (era terceira leitura)
        cfg_json = dict(cfg)  # Cópia para não modificar original

        override_date = str(st.session_state.plan.date or "").strip() or _date.today().strftime("%d-%m-%Y")
        cfg_json["data"] = override_date

        # Injetar plan_name (agregação por plano ao final do batch)
        _pname2 = st.session_state.get("plan_name_ui")
        if isinstance(_pname2, str) and _pname2.strip():
            cfg_json["plan_name"] = _pname2.strip()

        if not cfg_json.get("plan_name"):
            # Fallback 1: nome do arquivo do plano salvo
            sanitize_fn = _get_sanitize_filename()
            try:
                if selected_path and selected_path.exists():
                    base = selected_path.stem
                    if base:
                        cfg_json["plan_name"] = sanitize_fn(base)
            except Exception:
                pass

        if not cfg_json.get("plan_name"):
            # Fallback 2: usar key1/label1 do primeiro combo
            sanitize_fn = _get_sanitize_filename()
            try:
                combos_fallback = cfg_json.get("combos") or []
                if combos_fallback:
                    c0 = combos_fallback[0] or {}
                    cand = c0.get("label1") or c0.get("key1") or "Plano"
                    cfg_json["plan_name"] = sanitize_fn(str(cand))
            except Exception:
                cfg_json["plan_name"] = "Plano"

        # Gerar um config temporário para a execução desta sessão
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
