from __future__ import annotations

import json
import os
import sys
import asyncio
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import subprocess

# Global lock files
# - batch lock: guards a single batch execution launched from UI
# - ui lock: registers a UI instance to detect concurrent UIs
LOCK_PATH = Path("resultados") / "batch.lock"
UI_LOCK_PATH = Path("resultados") / "ui.lock"

def _pid_alive_windows(pid: int) -> bool:
    try:
        # Use tasklist to check if PID exists
        out = subprocess.run([
            "tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"
        ], capture_output=True, text=True, check=False)
        txt = (out.stdout or "") + (out.stderr or "")
        # When no tasks are found, tasklist prints "INFO: No tasks are running..."
        return str(pid) in txt and "No tasks" not in txt
    except Exception:
        return False

def _ensure_results_dir() -> Path:
    p = Path("resultados"); p.mkdir(parents=True, exist_ok=True)
    return p

def detect_other_execution() -> Optional[Dict[str, Any]]:
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
        try:
            LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    except Exception:
        return None

def _detect_lock(lock_path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not lock_path.exists():
            return None
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        pid = int(data.get("pid") or 0)
        started = str(data.get("started") or "")
        if sys.platform.startswith("win"):
            alive = _pid_alive_windows(pid) if pid else False
        else:
            alive = pid > 0 and Path(f"/proc/{pid}").exists()
        if alive:
            return {"pid": pid, "started": started, "lock_path": str(lock_path)}
        # cleanup stale
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    except Exception:
        return None

def detect_other_ui() -> Optional[Dict[str, Any]]:
    """Detect another running UI instance using the ui.lock file."""
    _ensure_results_dir()
    return _detect_lock(UI_LOCK_PATH)

def register_this_ui_instance() -> None:
    """Register current process as the active UI instance (overwrites previous lock)."""
    _ensure_results_dir()
    meta = {"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}
    try:
        UI_LOCK_PATH.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def terminate_other_execution(pid: int) -> bool:
    """Attempt to terminate another running execution (process tree) on Windows.
    Returns True if the command succeeded.
    """
    try:
        if sys.platform.startswith("win"):
            res = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
            return res.returncode == 0
        else:
            res = subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
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
        try:
            self.path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
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

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fp and self._locked and sys.platform.startswith("win"):
                import msvcrt  # type: ignore
                try:
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
        finally:
            try:
                if self._fp:
                    self._fp.close()
            except Exception:
                pass
            # Best-effort cleanup of lock artifacts
            try:
                self.path.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                if not sys.platform.startswith("win"):
                    Path(str(self.path) + ".lock").unlink(missing_ok=True)
            except Exception:
                pass
        return False


def run_batch_with_cfg(cfg_path: Path, parallel: int, fast_mode: bool = False, prefer_edge: bool = True,
                       enforce_singleton: bool = True) -> Dict[str, Any]:
    """Headless-safe wrapper to execute the batch without importing Streamlit UI.

    Returns the loaded report dict or {} if something failed.
    """
    try:
        # Ensure Windows has the proper event loop policy for Playwright subprocesses
        if sys.platform.startswith("win"):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception:
                pass

        # Lazy imports to keep this module light and Streamlit-free
        from dou_snaptrack.cli.batch import run_batch
        from dou_snaptrack.cli.summary_config import SummaryConfig
        from playwright.sync_api import sync_playwright  # type: ignore

        # Determine output dir based on plan date
        try:
            raw_cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
            # UI policy: se a data não estiver explícita, usar hoje
            plan_date = (raw_cfg.get("data") or "").strip() or _date.today().strftime("%d-%m-%Y")
        except Exception:
            raw_cfg = {}
            plan_date = _date.today().strftime("%d-%m-%Y")

        out_dir_path = Path("resultados") / plan_date
        out_dir_path.mkdir(parents=True, exist_ok=True)
        out_dir_str = str(out_dir_path)
        run_log_path = out_dir_path / "batch_run.log"

        # UI policy: link capture only (no details, no bulletin) to keep fast and safe
        cfg_obj = json.loads(json.dumps(raw_cfg)) if raw_cfg else {}
        # Se a data não foi definida, forçar hoje (para rodadas recorrentes do UI)
        if not (cfg_obj.get("data") or "").strip():
            cfg_obj["data"] = plan_date
        dfl = dict(cfg_obj.get("defaults") or {})
        dfl.pop("bulletin", None)
        dfl.pop("bulletin_out", None)
        dfl["scrape_detail"] = False
        dfl["detail_parallel"] = 1
        cfg_obj["defaults"] = dfl
        for key in ("jobs", "combos"):
            seq = cfg_obj.get(key)
            if isinstance(seq, list):
                for j in seq:
                    if isinstance(j, dict):
                        j.pop("bulletin", None)
                        j.pop("bulletin_out", None)
                        j["scrape_detail"] = False
                        j["detail_parallel"] = 1

        tmp_cfg_path = out_dir_path / "_run_cfg.json"
        tmp_cfg_path.write_text(json.dumps(cfg_obj, ensure_ascii=False, indent=2), encoding="utf-8")

        # Environment for workers
        # Default to thread pool under UI unless explicitly overridden
        os.environ.setdefault("DOU_POOL", "thread")
        if prefer_edge:
            os.environ["DOU_PREFER_EDGE"] = "1"
        if fast_mode:
            os.environ["DOU_FAST_MODE"] = "1"

        # Ensure PYTHONPATH includes src so workers can import dou_snaptrack on Windows spawn
        src_root = str(Path(__file__).resolve().parents[2])
        cur_pp = os.environ.get("PYTHONPATH") or ""
        if src_root not in (cur_pp.split(";") if os.name == "nt" else cur_pp.split(":")):
            os.environ["PYTHONPATH"] = f"{src_root}{';' if os.name == 'nt' else ':'}{cur_pp}" if cur_pp else src_root

        # Pre-create header and note Playwright opening
        try:
            with open(run_log_path, "a", encoding="utf-8") as _fp:
                _fp.write(f"[UI] batch start: cfg={cfg_path} tmp={tmp_cfg_path} out_dir={out_dir_path} parallel={int(parallel)} fast_mode={bool(fast_mode)} prefer_edge={bool(prefer_edge)}\n")
                _fp.write("[UI] opening Playwright context...\n")
        except Exception:
            pass

        # Optionally enforce a single UI-run at a time (via file lock)
        lock_ctx = _UILock(LOCK_PATH) if enforce_singleton else None
        if lock_ctx:
            lock_ctx.__enter__()
            if not lock_ctx._locked:
                # Someone else holds the lock; surface a clear error so the UI can prompt
                other = detect_other_execution()
                raise RuntimeError(f"Outra execução em andamento: {other}")
        try:
            with sync_playwright() as p:
                # Logged: context opened
                try:
                    with open(run_log_path, "a", encoding="utf-8") as _fp:
                        _fp.write("[UI] Playwright context opened. Scheduling batch...\n")
                except Exception:
                    pass

                from types import SimpleNamespace
                args = SimpleNamespace(
                    config=str(tmp_cfg_path),
                    out_dir=out_dir_str,
                    headful=False,
                    slowmo=0,
                    state_file=None,
                    reuse_page=True,  # reuse a tab per (date,secao)
                    parallel=int(parallel),
                    log_file=str(run_log_path),
                )

                run_batch(p, args, SummaryConfig(lines=4, mode="center", keywords=None))
        finally:
            if lock_ctx:
                lock_ctx.__exit__(None, None, None)

        rep_path = out_dir_path / "batch_report.json"
        return json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
    except Exception as e:
        # Print instead of Streamlit UI feedback to keep this headless-safe
        print(f"[run_batch_with_cfg] Falha: {type(e).__name__}: {e}")
        return {}
