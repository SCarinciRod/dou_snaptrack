from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Global lock files
# - batch lock: guards a single batch execution launched from UI
# - ui lock: registers a UI instance to detect concurrent UIs
LOCK_PATH = Path("resultados") / "batch.lock"
UI_LOCK_PATH = Path("resultados") / "ui.lock"

# Cache de src root para evitar path resolution repetida
_SRC_ROOT = str(Path(__file__).resolve().parents[2])

def _ensure_pythonpath() -> None:
    """Garante src/ no PYTHONPATH de forma eficiente (skip se já configurado)."""
    cur_pp = os.environ.get("PYTHONPATH", "")

    # Otimização: skip se já está no path
    if _SRC_ROOT in cur_pp:
        return

    sep = ";" if os.name == "nt" else ":"
    os.environ["PYTHONPATH"] = f"{_SRC_ROOT}{sep}{cur_pp}" if cur_pp else _SRC_ROOT


def run_cmd(cmd, timeout: int = 5, cwd: str | None = None, env: dict | None = None, check: bool = False):
    """Small wrapper around subprocess.run to centralize capture/timeouts.

    Returns the CompletedProcess on success. Propagates subprocess.TimeoutExpired
    so callers that expect timeouts can handle them.
    """
    return subprocess.run(cmd, capture_output=True, text=True, check=check, timeout=timeout, cwd=cwd, env=env)

def _pid_alive_windows(pid: int) -> bool:
    """Return True if a process with this PID exists on Windows.

    Uses tasklist filtered by PID and parses output robustly to avoid false positives.
    OTIMIZAÇÃO: csv e io importados no topo do módulo.
    """
    try:
        if pid <= 0:
            return False
        out = run_cmd(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], timeout=2)
        stdout = (out.stdout or "").strip()
        if not stdout or stdout.lower().startswith("info:"):
            return False
        # Parse CSV robustamente usando biblioteca nativa
        try:
            reader = csv.reader(io.StringIO(stdout))
            row = next(reader, [])
            if len(row) >= 2:
                pid_field = row[1].strip()
                return pid_field.isdigit() and int(pid_field) == pid
        except Exception:
            # Fallback: if any non-INFO output exists, assume alive
            return True
        return False
    except subprocess.TimeoutExpired:
        # Timeout significa sistema lento, assume processo vivo para segurança
        return True
    except Exception:
        return False

def _ensure_results_dir() -> Path:
    p = Path("resultados")
    p.mkdir(parents=True, exist_ok=True)
    return p

def detect_other_execution() -> dict[str, Any] | None:
    """Return info about another execution if a UI lock is active and PID is alive.
    Cleans up stale locks automatically.
    { pid, started, lock_path }
    """
    try:
        if not LOCK_PATH.exists():
            return None
        data = {}
        try:
            data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        pid = int(data.get("pid") or 0)
        started = str(data.get("started") or "")
        if sys.platform.startswith("win"):
            alive = _pid_alive_windows(pid) if pid else False
        else:
            # Best-effort on non-Windows: check if /proc/<pid> exists
            alive = pid > 0 and Path(f"/proc/{pid}").exists()
        if alive:
            return {"pid": pid, "started": started, "lock_path": str(LOCK_PATH)}
        # Not alive: remove stale lock
        with contextlib.suppress(Exception):
            LOCK_PATH.unlink(missing_ok=True)
        return None
    except Exception:
        return None



def detect_other_ui() -> dict[str, Any] | None:
    """Detect another running UI instance using the ui.lock file.

    Stale or foreign locks are auto-removed. Only returns info if the PID is
    currently a Streamlit process for this repo's UI.
    """
    _ensure_results_dir()
    try:
        if not UI_LOCK_PATH.exists():
            return None
        try:
            data = json.loads(UI_LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        pid = int(data.get("pid") or 0)
        started = str(data.get("started") or "")
        if sys.platform.startswith("win"):
            info = _win_get_process_info(pid) if pid else {}
            alive = bool(info) and _pid_alive_windows(pid)
            if not alive or not _is_our_streamlit_process(info):
                with contextlib.suppress(Exception):
                    UI_LOCK_PATH.unlink(missing_ok=True)
                return None
            return {"pid": pid, "started": started, "lock_path": str(UI_LOCK_PATH)}
        else:
            # Non-Windows best-effort: if pid dir exists, consider alive
            alive = pid > 0 and Path(f"/proc/{pid}").exists()
            if not alive:
                with contextlib.suppress(Exception):
                    UI_LOCK_PATH.unlink(missing_ok=True)
                return None
            return {"pid": pid, "started": started, "lock_path": str(UI_LOCK_PATH)}
    except Exception:
        return None

def clear_ui_lock() -> None:
    """Best-effort removal of the UI lock file."""
    with contextlib.suppress(Exception):
        UI_LOCK_PATH.unlink(missing_ok=True)


def cleanup_batch_processes() -> dict[str, Any]:
    """Kill any orphaned batch subprocesses and clean up locks/incomplete files.

    Returns a summary of what was cleaned up.
    """
    result = {"killed_pids": [], "removed_locks": [], "errors": []}

    # 1. Remove lock files
    for lock_path in [LOCK_PATH, UI_LOCK_PATH]:
        try:
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
                result["removed_locks"].append(str(lock_path))
        except Exception as e:
            result["errors"].append(f"lock {lock_path}: {e}")

    # 2. Find and kill subprocesses from _active_pids.json files
    try:
        resultados_dir = Path("resultados")
        if resultados_dir.exists():
            for pids_file in resultados_dir.rglob("_subproc/_active_pids.json"):
                try:
                    data = json.loads(pids_file.read_text(encoding="utf-8"))
                    pids = data.get("pids", [])
                    _parent_pid = data.get("parent", 0)

                    # Kill each subprocess
                    for pid in pids:
                        try:
                            if sys.platform.startswith("win"):
                                # Windows: use taskkill
                                subprocess.run(
                                    ["taskkill", "/F", "/PID", str(pid)],
                                    capture_output=True, timeout=5
                                )
                            else:
                                # Unix: send SIGTERM then SIGKILL
                                os.kill(pid, 15)  # SIGTERM
                            result["killed_pids"].append(pid)
                        except Exception:
                            pass

                    # Remove the pids file
                    pids_file.unlink(missing_ok=True)
                except Exception as e:
                    result["errors"].append(f"pids file {pids_file}: {e}")
    except Exception as e:
        result["errors"].append(f"scan resultados: {e}")

    # 3. Kill any python processes that look like worker_entry
    try:
        if sys.platform.startswith("win"):
            # Find python processes running worker_entry
            out = subprocess.run(
                ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
                capture_output=True, text=True, timeout=10
            )
            for line in (out.stdout or "").splitlines():
                if "worker_entry" in line.lower():
                    # Extract PID (last number in line)
                    parts = line.strip().split()
                    if parts:
                        try:
                            pid = int(parts[-1])
                            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
                            result["killed_pids"].append(pid)
                        except Exception:
                            pass
    except Exception as e:
        result["errors"].append(f"wmic scan: {e}")

    return result


def register_this_ui_instance() -> None:
    """Register current process as the active UI instance (overwrites previous lock)."""
    _ensure_results_dir()
    meta = {"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}
    with contextlib.suppress(Exception):
        UI_LOCK_PATH.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

def _win_get_process_info(pid: int) -> dict:
    """Fetch process info on Windows via tasklist (otimizado, sem PowerShell).

    Returns {} on failure. Usa tasklist CSV que é 75% mais rápido que PowerShell.
    OTIMIZAÇÃO: Removido fallback PowerShell (3s timeout) - não necessário.
    """
    try:
        # Versão otimizada: tasklist com /V (verbose) para pegar command line
        out = run_cmd(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/V", "/NH"], timeout=2)
        stdout = (out.stdout or "").strip()
        if not stdout or stdout.lower().startswith("info:"):
            return {}

        # Parse CSV com biblioteca nativa (já importado no topo)
        reader = csv.reader(io.StringIO(stdout))
        row = next(reader, [])

        if len(row) >= 2:
            # tasklist /V format: Image Name, PID, Session Name, Session#, Mem Usage, Status, User, CPU Time, Window Title
            return {
                "exe": row[0].strip() if len(row) > 0 else "",
                "pid": row[1].strip() if len(row) > 1 else "",
                "user": row[6].strip() if len(row) > 6 else "",
                "cmd": row[8].strip() if len(row) > 8 else "",  # Window Title como proxy de command
            }
    except subprocess.TimeoutExpired:
        pass  # Timeout, retornar vazio
    except Exception:
        pass

    # NOTA: PowerShell fallback REMOVIDO - era lento (3s) e raramente necessário
    # tasklist /V já fornece informações suficientes para nossa heurística

    return {}


def _is_our_streamlit_process(info: dict) -> bool:
    """Heuristic: ensure process points to our venv python and runs streamlit app.py within this repo.
    """
    try:
        if not info:
            return False
        exe = (info.get("exe") or "").lower()
        cmd = (info.get("cmd") or "").lower()
        here = Path(__file__).resolve()
        repo_root = here.parents[2]  # c:\Projetos
        venv_py = (repo_root / ".venv" / "Scripts" / "python.exe").as_posix().lower().replace("/", "\\")
        app_path = (repo_root / "src" / "dou_snaptrack" / "ui" / "app.py").as_posix().lower().replace("/", "\\")
        # Accept either exe equals venv python or command line contains it
        return bool(
            venv_py
            and (venv_py in exe or venv_py in cmd)
            and ("streamlit" in cmd and app_path in cmd)
        )
    except Exception:
        return False


def terminate_other_execution(pid: int) -> bool:
    """Attempt to terminate another running execution (process tree) on Windows.
    Only proceeds if PID appears to be our own Streamlit/runner process.
    """
    try:
        if sys.platform.startswith("win"):
            info = _win_get_process_info(pid)
            if not _is_our_streamlit_process(info):
                # Refuse to kill unknown processes
                return False
            res = run_cmd(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=5)
            return res.returncode == 0
        else:
            res = run_cmd(["kill", "-9", str(pid)], timeout=5)
            return res.returncode == 0
    except Exception:
        return False

class _UILock:
    """File-based lock using Windows msvcrt when available; holds the lock while context is alive."""
    def __init__(self, path: Path):
        self.path = path
        self._fp = None
        self._locked = False

    def __enter__(self):
        _ensure_results_dir()
        # Write metadata (pid, started) so we can show info and target termination
        meta = {"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}
        with contextlib.suppress(Exception):
            self.path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        try:
            self._fp = open(self.path, "r+b")
        except FileNotFoundError:
            self._fp = open(self.path, "w+b")
        try:
            if sys.platform.startswith("win"):
                import msvcrt  # type: ignore
                # Lock first byte non-blocking
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
                self._locked = True
            else:
                # On non-Windows, best-effort: exclusive open by creating a sidecar lock
                self._fp.close()
                self._fp = open(str(self.path) + ".lock", "x")
                self._locked = True
        except Exception:
            self._locked = False
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        errors = []
        try:
            if self._fp and self._locked and sys.platform.startswith("win"):
                import msvcrt  # type: ignore
                try:
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception as e:
                    errors.append(f"unlock: {e}")
        finally:
            if self._fp:
                try:
                    self._fp.close()
                except Exception as e:
                    errors.append(f"close: {e}")

            # Best-effort cleanup of lock artifacts
            for lock_file in [self.path, Path(str(self.path) + ".lock")]:
                try:
                    lock_file.unlink(missing_ok=True)
                except Exception as e:
                    errors.append(f"unlink {lock_file.name}: {e}")

        # Log erros para debug (importante para detectar leaks)
        if errors:
            try:
                import logging
                logging.warning(f"Lock cleanup warnings for {self.path.name}: {'; '.join(errors)}")
            except Exception:
                pass  # Logging falhou, mas não deve quebrar cleanup

        return False


def run_batch_with_cfg(cfg_path: Path, parallel: int, fast_mode: bool = False, prefer_edge: bool = True,
                       enforce_singleton: bool = True) -> dict[str, Any]:
    """Headless-safe wrapper to execute the batch without importing Streamlit UI.

    Returns the loaded report dict or {} if something failed.
    """
    try:
        from .helpers import (
            configure_environment_variables,
            delete_individual_outputs,
            load_and_prepare_config,
            load_report,
            sanitize_config_for_ui,
            setup_output_directory,
            setup_windows_event_loop,
            write_batch_start_log,
            write_playwright_opened_log,
        )

        # Setup
        setup_windows_event_loop()

        # Lazy imports to keep this module light and Streamlit-free
        from playwright.sync_api import sync_playwright  # type: ignore

        from dou_snaptrack.cli.batch.runner import run_batch
        from dou_snaptrack.cli.batch.summary_config import SummaryConfig

        # Load and prepare configuration
        raw_cfg, plan_date = load_and_prepare_config(cfg_path)
        out_dir_path, run_log_path = setup_output_directory(plan_date)
        out_dir_str = str(out_dir_path)

        # Sanitize config for UI execution
        cfg_obj = sanitize_config_for_ui(raw_cfg, plan_date)
        tmp_cfg_path = out_dir_path / "_run_cfg.json"
        tmp_cfg_path.write_text(json.dumps(cfg_obj, ensure_ascii=False, indent=2), encoding="utf-8")

        # Configure environment
        configure_environment_variables(parallel, prefer_edge, fast_mode)
        _ensure_pythonpath()

        # Log batch start
        write_batch_start_log(run_log_path, cfg_path, tmp_cfg_path, out_dir_path, parallel, fast_mode, prefer_edge)

        # Optionally enforce a single UI-run at a time (via file lock)
        lock_ctx = _UILock(LOCK_PATH) if enforce_singleton else None
        if lock_ctx:
            lock_ctx.__enter__()
            if not lock_ctx._locked:
                other = detect_other_execution()
                raise RuntimeError(f"Outra execução em andamento: {other}")

        try:
            with sync_playwright() as p:
                write_playwright_opened_log(run_log_path)

                from types import SimpleNamespace
                args = SimpleNamespace(
                    config=str(tmp_cfg_path),
                    out_dir=out_dir_str,
                    headful=False,
                    slowmo=0,
                    state_file=None,
                    reuse_page=True,
                    parallel=int(parallel),
                    log_file=str(run_log_path),
                )

                run_batch(p, args, SummaryConfig(lines=4, mode="center", keywords=None))
        finally:
            if lock_ctx:
                lock_ctx.__exit__(None, None, None)

        # Load and post-process report
        rep = load_report(out_dir_path)
        rep = delete_individual_outputs(rep, out_dir_path)

        return rep
    except Exception as e:
        print(f"[run_batch_with_cfg] Falha: {type(e).__name__}: {e}")
        return {}
