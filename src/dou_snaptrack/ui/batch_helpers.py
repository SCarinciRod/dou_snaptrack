"""Helper functions for UI batch execution.

This module contains extracted functions from run_batch_with_cfg to reduce complexity.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date
from pathlib import Path
from typing import Any


def setup_windows_event_loop() -> None:
    """Configure asyncio event loop for Windows platform."""
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass


def load_and_prepare_config(cfg_path: str | Path) -> tuple[dict[str, Any], str]:
    """Load configuration file and determine plan date.
    
    Args:
        cfg_path: Path to configuration file
        
    Returns:
        Tuple of (config_dict, plan_date_str)
    """
    try:
        raw_cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
        # UI policy: se a data não estiver explícita, usar hoje
        plan_date = (raw_cfg.get("data") or "").strip() or _date.today().strftime("%d-%m-%Y")
    except Exception:
        raw_cfg = {}
        plan_date = _date.today().strftime("%d-%m-%Y")
    
    return raw_cfg, plan_date


def setup_output_directory(plan_date: str) -> tuple[Path, Path]:
    """Create output directory structure.
    
    Args:
        plan_date: Plan date string
        
    Returns:
        Tuple of (output_dir_path, run_log_path)
    """
    out_dir_path = Path("resultados") / plan_date
    out_dir_path.mkdir(parents=True, exist_ok=True)
    run_log_path = out_dir_path / "batch_run.log"
    return out_dir_path, run_log_path


def sanitize_config_for_ui(raw_cfg: dict[str, Any], plan_date: str) -> dict[str, Any]:
    """Sanitize config for UI execution (disable details and bulletins).
    
    Args:
        raw_cfg: Raw configuration dictionary
        plan_date: Plan date string
        
    Returns:
        Sanitized configuration dictionary
    """
    cfg_obj = json.loads(json.dumps(raw_cfg)) if raw_cfg else {}
    
    # Se a data não foi definida, forçar hoje (para rodadas recorrentes do UI)
    if not (cfg_obj.get("data") or "").strip():
        cfg_obj["data"] = plan_date
    
    # Update defaults
    dfl = dict(cfg_obj.get("defaults") or {})
    dfl.pop("bulletin", None)
    dfl.pop("bulletin_out", None)
    dfl["scrape_detail"] = False
    dfl["detail_parallel"] = 1
    cfg_obj["defaults"] = dfl
    
    # Update jobs and combos
    for key in ("jobs", "combos"):
        seq = cfg_obj.get(key)
        if isinstance(seq, list):
            for j in seq:
                if isinstance(j, dict):
                    j.pop("bulletin", None)
                    j.pop("bulletin_out", None)
                    j["scrape_detail"] = False
                    j["detail_parallel"] = 1
    
    return cfg_obj


def configure_environment_variables(parallel: int, prefer_edge: bool, fast_mode: bool) -> None:
    """Configure environment variables for batch execution.
    
    Args:
        parallel: Number of parallel workers
        prefer_edge: Whether to prefer Edge browser
        fast_mode: Whether to enable fast mode
    """
    # Prefer subprocess pool when there is real parallelism
    try:
        if int(parallel) > 1:
            os.environ["DOU_POOL"] = "subprocess"
        else:
            os.environ["DOU_POOL"] = "thread"
    except Exception:
        os.environ.setdefault("DOU_POOL", "thread")
    
    if prefer_edge:
        os.environ["DOU_PREFER_EDGE"] = "1"
    if fast_mode:
        os.environ["DOU_FAST_MODE"] = "1"


def write_batch_start_log(run_log_path: Path, cfg_path: Path, tmp_cfg_path: Path, 
                          out_dir_path: Path, parallel: int, fast_mode: bool, prefer_edge: bool) -> None:
    """Write batch execution start to log file.
    
    Args:
        run_log_path: Path to log file
        cfg_path: Original config path
        tmp_cfg_path: Temporary config path
        out_dir_path: Output directory path
        parallel: Number of parallel workers
        fast_mode: Fast mode flag
        prefer_edge: Prefer Edge flag
    """
    try:
        with open(run_log_path, "a", encoding="utf-8") as _fp:
            _fp.write(
                f"[UI] batch start: cfg={cfg_path} tmp={tmp_cfg_path} out_dir={out_dir_path} "
                f"parallel={int(parallel)} fast_mode={bool(fast_mode)} prefer_edge={bool(prefer_edge)}\n"
            )
            _fp.write("[UI] opening Playwright context...\n")
    except Exception:
        pass


def write_playwright_opened_log(run_log_path: Path) -> None:
    """Write Playwright context opened message to log.
    
    Args:
        run_log_path: Path to log file
    """
    try:
        with open(run_log_path, "a", encoding="utf-8") as _fp:
            _fp.write("[UI] Playwright context opened. Scheduling batch...\n")
    except Exception:
        pass


def delete_individual_outputs(rep: dict[str, Any], out_dir_path: Path) -> dict[str, Any]:
    """Delete individual JSON outputs after aggregation.
    
    Args:
        rep: Report dictionary
        out_dir_path: Output directory path
        
    Returns:
        Updated report dictionary
    """
    try:
        agg = rep.get("aggregated") if isinstance(rep, dict) else None
        outs = rep.get("outputs") if isinstance(rep, dict) else None
        
        if not (agg and isinstance(agg, list) and outs and isinstance(outs, list) and len(outs) > 0):
            return rep
        
        # Deletar em paralelo para performance (3-5x mais rápido)
        def _safe_delete(path: str) -> tuple[str, bool]:
            """Delete file and return (path, success)."""
            try:
                Path(path).unlink(missing_ok=True)
                return (path, True)
            except Exception:
                return (path, False)
        
        # Max 4 workers para I/O (sweet spot)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(_safe_delete, outs))
        
        deleted = [p for p, success in results if success]
        
        # Update report on disk
        rep_path = out_dir_path / "batch_report.json"
        if rep_path.exists() and deleted:
            try:
                rep["deleted_outputs"] = deleted
                rep["outputs"] = []
                rep["aggregated_only"] = True
                rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass
    
    return rep


def load_report(out_dir_path: Path) -> dict[str, Any]:
    """Load batch report from output directory.
    
    Args:
        out_dir_path: Output directory path
        
    Returns:
        Report dictionary or empty dict if not found
    """
    rep_path = out_dir_path / "batch_report.json"
    return json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
