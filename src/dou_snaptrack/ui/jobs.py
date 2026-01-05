"""Subprocess job helpers for the Streamlit UI.

This module provides a tiny, file-based job status protocol so the UI can:
- run long operations outside the Streamlit process
- persist logs and a status JSON to disk

It does not add new UI surfaces; it is meant to be used behind existing buttons.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class JobResult:
    job_id: str
    ok: bool
    returncode: int
    elapsed_sec: float
    status_path: Path
    log_path: Path
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class RunningJob:
    job_id: str
    proc: subprocess.Popen[str]
    started_perf: float
    status_path: Path
    log_path: Path
    _log_handle: Any


def _ensure_jobs_dir(results_root: Path) -> Path:
    d = results_root / "_jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tail_text(s: str, max_chars: int = 5000) -> str:
    if not s:
        return ""
    return s[-max_chars:]


def run_subprocess_job(
    *,
    results_root: Path,
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 900,
    meta: dict[str, Any] | None = None,
) -> JobResult:
    """Run a subprocess, writing status + log files under resultados/_jobs/."""
    jobs_dir = _ensure_jobs_dir(results_root)
    job_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    status_path = jobs_dir / f"{job_id}.json"
    log_path = jobs_dir / f"{job_id}.log"

    status: dict[str, Any] = {
        "job_id": job_id,
        "started_at": time.time(),
        "cmd": cmd,
        "cwd": str(cwd) if cwd else None,
        "timeout_sec": int(timeout_sec),
        "meta": meta or {},
        "state": "running",
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    start = time.perf_counter()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=merged_env,
            cwd=str(cwd) if cwd else None,
            timeout=timeout_sec,
        )
        elapsed = time.perf_counter() - start

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        log_path.write_text(stdout + "\n\n" + stderr, encoding="utf-8", errors="ignore")

        ok = proc.returncode == 0
        status.update(
            {
                "state": "done" if ok else "failed",
                "finished_at": time.time(),
                "elapsed_sec": elapsed,
                "returncode": proc.returncode,
            }
        )
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

        return JobResult(
            job_id=job_id,
            ok=ok,
            returncode=proc.returncode,
            elapsed_sec=elapsed,
            status_path=status_path,
            log_path=log_path,
            stdout_tail=_tail_text(stdout),
            stderr_tail=_tail_text(stderr),
        )

    except subprocess.TimeoutExpired as e:
        elapsed = time.perf_counter() - start
        stdout = getattr(e, "stdout", "") or ""
        stderr = getattr(e, "stderr", "") or ""
        log_path.write_text(stdout + "\n\n" + stderr, encoding="utf-8", errors="ignore")

        status.update(
            {
                "state": "timeout",
                "finished_at": time.time(),
                "elapsed_sec": elapsed,
                "returncode": -1,
            }
        )
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

        return JobResult(
            job_id=job_id,
            ok=False,
            returncode=-1,
            elapsed_sec=elapsed,
            status_path=status_path,
            log_path=log_path,
            stdout_tail=_tail_text(stdout),
            stderr_tail=_tail_text(stderr),
        )


def python_module_cmd(module: str, args: list[str] | None = None) -> list[str]:
    """Build a 'python -m <module> ...' command using the current interpreter."""
    return [sys.executable or "python", "-m", module, *(args or [])]


def _read_file_tail(path: Path, max_bytes: int = 16_384) -> str:
    try:
        if not path.exists():
            return ""
        size = path.stat().st_size
        if size <= 0:
            return ""
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def start_subprocess_job(
    *,
    results_root: Path,
    cmd: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 900,
    meta: dict[str, Any] | None = None,
) -> RunningJob:
    """Start a subprocess job and stream stdout/stderr into a log file.

    The caller is responsible for polling `proc.poll()` and finalizing.
    """
    jobs_dir = _ensure_jobs_dir(results_root)
    job_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    status_path = jobs_dir / f"{job_id}.json"
    log_path = jobs_dir / f"{job_id}.log"

    status: dict[str, Any] = {
        "job_id": job_id,
        "started_at": time.time(),
        "cmd": cmd,
        "cwd": str(cwd) if cwd else None,
        "timeout_sec": int(timeout_sec),
        "meta": meta or {},
        "state": "running",
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    log_handle = log_path.open("w", encoding="utf-8", errors="ignore")
    started_perf = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Update status with pid
    status["pid"] = proc.pid
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    return RunningJob(
        job_id=job_id,
        proc=proc,
        started_perf=started_perf,
        status_path=status_path,
        log_path=log_path,
        _log_handle=log_handle,
    )


def finalize_subprocess_job(job: RunningJob) -> JobResult:
    """Finalize a running job: close logs, write final status, return summary."""
    rc = job.proc.returncode if job.proc.returncode is not None else -1
    elapsed = time.perf_counter() - job.started_perf
    with suppress(Exception):
        with suppress(Exception):
            job._log_handle.flush()
        job._log_handle.close()

    ok = rc == 0
    try:
        loaded = json.loads(job.status_path.read_text(encoding="utf-8"))
        status: dict[str, Any] = loaded if isinstance(loaded, dict) else {"job_id": job.job_id}
    except Exception:
        status = {"job_id": job.job_id}

    status.update(
        {
            "state": "done" if ok else "failed",
            "finished_at": time.time(),
            "elapsed_sec": elapsed,
            "returncode": rc,
        }
    )
    job.status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    tail = _read_file_tail(job.log_path, max_bytes=16_384)
    return JobResult(
        job_id=job.job_id,
        ok=ok,
        returncode=rc,
        elapsed_sec=elapsed,
        status_path=job.status_path,
        log_path=job.log_path,
        stdout_tail=_tail_text(tail),
        stderr_tail="",
    )


def read_job_log_tail(job: RunningJob, max_bytes: int = 16_384) -> str:
    """Read the last chunk of the job log (merged stdout/stderr)."""
    with suppress(Exception):
        with suppress(Exception):
            job._log_handle.flush()
        return _read_file_tail(job.log_path, max_bytes=max_bytes)
    return ""
