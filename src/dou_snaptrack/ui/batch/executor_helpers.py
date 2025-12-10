"""Helper functions for batch executor.

This module contains extracted functions from _execute_plan to reduce complexity.
"""

from __future__ import annotations

import contextlib
import json
from datetime import date as _date
from pathlib import Path
from typing import Any


def check_concurrent_execution(batch_funcs: dict) -> dict[str, Any] | None:
    """Check if another execution is running.

    Args:
        batch_funcs: Dictionary of batch runner functions

    Returns:
        Info about other execution or None
    """
    return batch_funcs["detect_other_execution"]()


def handle_concurrent_execution_ui(other: dict[str, Any], batch_funcs: dict, st_module) -> bool:
    """Handle UI for concurrent execution scenario.

    Args:
        other: Info about other execution
        batch_funcs: Dictionary of batch runner functions
        st_module: Streamlit module

    Returns:
        True if should proceed, False if should stop
    """
    st_module.warning(f"Outra execução detectada (PID={other.get('pid')} iniciada em {other.get('started')}).")
    colx = st_module.columns(2)

    with colx[0]:
        kill_it = st_module.button("Encerrar outra execução (forçar)")
    with colx[1]:
        proceed_anyway = st_module.button("Prosseguir sem encerrar")

    if kill_it:
        ok = batch_funcs["terminate_other_execution"](int(other.get("pid") or 0))
        if ok:
            st_module.success("Outra execução encerrada. Prosseguindo…")
            return True
        else:
            st_module.error("Falha ao encerrar a outra execução. Tente novamente manualmente.")
            return False
    elif not proceed_anyway:
        return False

    return True


def estimate_job_count(cfg: dict[str, Any]) -> int:
    """Estimate number of jobs from config.

    Args:
        cfg: Configuration dictionary

    Returns:
        Estimated job count
    """
    combos = cfg.get("combos") or []
    topics = cfg.get("topics") or []
    return len(combos) * max(1, len(topics) or 1)


def prepare_execution_config(
    cfg: dict[str, Any],
    selected_path: Path,
    st_session_state,
    sanitize_fn
) -> dict[str, Any]:
    """Prepare configuration for execution.

    Args:
        cfg: Base configuration
        selected_path: Path to selected plan
        st_session_state: Streamlit session state
        sanitize_fn: Function to sanitize filenames

    Returns:
        Prepared configuration dictionary
    """
    cfg_json = dict(cfg)

    # Override date
    override_date = str(st_session_state.plan.date or "").strip() or _date.today().strftime("%d-%m-%Y")
    cfg_json["data"] = override_date

    # Inject plan_name
    plan_name = determine_plan_name(cfg_json, selected_path, st_session_state, sanitize_fn)
    cfg_json["plan_name"] = plan_name

    return cfg_json


def determine_plan_name(
    cfg_json: dict[str, Any],
    selected_path: Path,
    st_session_state,
    sanitize_fn
) -> str:
    """Determine plan name from various sources.

    Args:
        cfg_json: Configuration dictionary
        selected_path: Path to selected plan
        st_session_state: Streamlit session state
        sanitize_fn: Function to sanitize filenames

    Returns:
        Plan name string
    """
    # Try session state first
    _pname2 = st_session_state.get("plan_name_ui")
    if isinstance(_pname2, str) and _pname2.strip():
        return _pname2.strip()

    # Fallback 1: filename
    try:
        if selected_path and selected_path.exists():
            base = selected_path.stem
            if base:
                return sanitize_fn(base)
    except Exception:
        pass

    # Fallback 2: first combo key1/label1
    try:
        combos_fallback = cfg_json.get("combos") or []
        if combos_fallback:
            c0 = combos_fallback[0] or {}
            cand = c0.get("label1") or c0.get("key1") or "Plano"
            return sanitize_fn(str(cand))
    except Exception:
        pass

    return "Plano"


def write_temp_config(cfg_json: dict[str, Any], override_date: str) -> Path:
    """Write temporary configuration file.

    Args:
        cfg_json: Configuration dictionary
        override_date: Date string for output directory

    Returns:
        Path to temporary config file
    """
    out_dir_tmp = Path("resultados") / override_date
    out_dir_tmp.mkdir(parents=True, exist_ok=True)
    pass_cfg_path = out_dir_tmp / "_run_cfg.from_ui.json"

    with contextlib.suppress(Exception):
        pass_cfg_path.write_text(json.dumps(cfg_json, ensure_ascii=False, indent=2), encoding="utf-8")

    return pass_cfg_path


def show_execution_result(rep: dict[str, Any] | None, parallel: int, st_session_state, st_module) -> None:
    """Show execution result in UI.

    Args:
        rep: Report dictionary
        parallel: Number of parallel workers
        st_session_state: Streamlit session state
        st_module: Streamlit module
    """
    st_module.write(rep or {"info": "Sem relatório"})

    # Hint on where to find detailed run logs
    out_date = str(st_session_state.plan.date or "").strip() or _date.today().strftime("%d-%m-%Y")
    log_hint = Path("resultados") / out_date / "batch_run.log"

    if log_hint.exists():
        st_module.caption(f"Execução concluída com {parallel} workers automáticos. Log detalhado em: {log_hint}")
    else:
        st_module.caption(f"Execução concluída com {parallel} workers automáticos.")
