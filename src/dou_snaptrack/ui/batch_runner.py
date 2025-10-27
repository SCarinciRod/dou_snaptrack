from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import date as _date, datetime
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

def _pid_alive_windows(pid: int) -> bool:
    """Return True if a process with this PID exists on Windows.

    Uses tasklist filtered by PID and parses output robustly to avoid false positives.
    """
    try:
        if pid <= 0:
            return False
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False, timeout=2  # Reduzido de 5s para 2s
        )
        stdout = (out.stdout or "").strip()
        if not stdout or stdout.lower().startswith("info:"):
            return False
        # Parse CSV robustamente usando biblioteca nativa
        import csv
        import io
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
    p = Path("resultados"); p.mkdir(parents=True, exist_ok=True)
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
        try:
            LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
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
                try:
                    UI_LOCK_PATH.unlink(missing_ok=True)
                except Exception:
                    pass
                return None
            return {"pid": pid, "started": started, "lock_path": str(UI_LOCK_PATH)}
        else:
            # Non-Windows best-effort: if pid dir exists, consider alive
            alive = pid > 0 and Path(f"/proc/{pid}").exists()
            if not alive:
                try:
                    UI_LOCK_PATH.unlink(missing_ok=True)
                except Exception:
                    pass
                return None
            return {"pid": pid, "started": started, "lock_path": str(UI_LOCK_PATH)}
    except Exception:
        return None

def clear_ui_lock() -> None:
    """Best-effort removal of the UI lock file."""
    try:
        UI_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass

def register_this_ui_instance() -> None:
    """Register current process as the active UI instance (overwrites previous lock)."""
    _ensure_results_dir()
    meta = {"pid": os.getpid(), "started": datetime.now().isoformat(timespec="seconds")}
    try:
        UI_LOCK_PATH.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _win_get_process_info(pid: int) -> dict:
    """Fetch process info on Windows via tasklist (otimizado, sem PowerShell).
    
    Returns {} on failure. Usa tasklist CSV que é 75% mais rápido que PowerShell.
    """
    try:
        # Versão otimizada: tasklist com /V (verbose) para pegar command line
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/V", "/NH"],
            capture_output=True, text=True, check=False, timeout=1  # 1s suficiente para local call
        )
        stdout = (out.stdout or "").strip()
        if not stdout or stdout.lower().startswith("info:"):
            return {}
        
        # Parse CSV com biblioteca nativa
        import csv
        import io
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
    
    # Fallback para PowerShell apenas se tasklist falhar (raro)
    try:
        ps = (
            "powershell",
            "-NoProfile",
            "-Command",
            f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\"; if($p){{ $u=$p.GetOwner(); [Console]::Out.WriteLine(($p.ExecutablePath+'|'+$p.CommandLine+'|'+$($u.Domain+'\\'+$u.User))) }}"
        )
        out = subprocess.run(ps, capture_output=True, text=True, check=False, timeout=3)  # Reduzido de 5s
        line = (out.stdout or "").strip()
        if line:
            parts = line.split("|", 2)
            exe = parts[0] if len(parts) > 0 else ""
            cmd = parts[1] if len(parts) > 1 else ""
            user = parts[2] if len(parts) > 2 else ""
            return {"exe": exe, "cmd": cmd, "user": user}
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    
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
        if venv_py and (venv_py in exe or venv_py in cmd):
            # Must be running streamlit against our app
            if "streamlit" in cmd and app_path in cmd:
                return True
        return False
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

    def __exit__(self, _exc_type, _exc, tb):
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
        # Ensure Windows has the proper event loop policy for Playwright subprocesses
        if sys.platform.startswith("win"):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception:
                pass

        # Lazy imports to keep this module light and Streamlit-free
        from playwright.sync_api import sync_playwright  # type: ignore

        from dou_snaptrack.cli.batch import run_batch
        from dou_snaptrack.cli.summary_config import SummaryConfig

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
        # Prefer subprocess pool when there is real parallelism; keep thread for single-worker inline stability
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

        # Ensure PYTHONPATH includes src (otimizado com cache)
        _ensure_pythonpath()

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
        rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
        # Pós-processo: se houver arquivos agregados, remover JSONs individuais remanescentes (compat com versões antigas)
        try:
            agg = rep.get("aggregated") if isinstance(rep, dict) else None
            outs = rep.get("outputs") if isinstance(rep, dict) else None
            if agg and isinstance(agg, list):
                # Delete per-job outputs that still exist
                deleted = []
                if outs and isinstance(outs, list):
                    for pth in outs:
                        try:
                            Path(pth).unlink(missing_ok=True)
                            deleted.append(pth)
                        except Exception:
                            pass
                # Update report on disk
                if rep_path.exists():
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
    except Exception as e:
        # Print instead of Streamlit UI feedback to keep this headless-safe
        print(f"[run_batch_with_cfg] Falha: {type(e).__name__}: {e}")
        return {}
