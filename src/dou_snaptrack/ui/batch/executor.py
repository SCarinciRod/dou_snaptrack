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
    from dou_snaptrack.ui.batch.runner import (
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
        from dou_snaptrack.ui.batch.runner import run_batch_with_cfg as _runner

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
    from .executor_helpers import (
        check_concurrent_execution,
        handle_concurrent_execution_ui,
        estimate_job_count,
        prepare_execution_config,
        write_temp_config,
        show_execution_result,
    )
    
    if not selected_path.exists():
        st.error("Plano não encontrado.")
        return

    # Concurrency guard: check if another execution is running
    batch_funcs = _get_batch_runner()
    other = check_concurrent_execution(batch_funcs)

    if other:
        if not handle_concurrent_execution_ui(other, batch_funcs, st):
            st.stop()

    # Load config and estimate jobs
    cfg = _load_plan_config(selected_path)
    est_jobs = estimate_job_count(cfg)
    parallel = int(recommend_parallel(est_jobs, prefer_process=True))

    # Prepare execution config
    sanitize_fn = _get_sanitize_filename()
    cfg_json = prepare_execution_config(cfg, selected_path, st.session_state, sanitize_fn)
    
    # Write temp config
    override_date = cfg_json["data"]
    pass_cfg_path = write_temp_config(cfg_json, override_date)

    # Execute
    with st.spinner("Executando…"):
        st.caption(f"Iniciando captura… log em resultados/{override_date}/batch_run.log")
        rep = _run_batch_with_cfg(pass_cfg_path, parallel, fast_mode=False, prefer_edge=True)

    # Show result
    show_execution_result(rep, parallel, st.session_state, st)
