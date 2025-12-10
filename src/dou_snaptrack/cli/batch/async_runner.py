"""Fast async mode support for batch processing.

This module handles the fast async execution path that uses a single browser
for faster parallel collection.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any


def try_fast_async_mode(
    jobs: list[dict[str, Any]],
    defaults: dict[str, Any],
    out_dir: Path,
    out_pattern: str,
    args,
    cfg: dict[str, Any],
    log_fn: Callable[[str], None],
) -> dict[str, Any] | None:
    """Try to execute batch using fast async mode.

    Fast async mode uses a single browser with multiple contexts for
    2x faster collection compared to multi-browser approach.

    Args:
        jobs: List of jobs to execute
        defaults: Default configuration
        out_dir: Output directory
        out_pattern: Output filename pattern
        args: Command-line arguments
        cfg: Batch configuration
        log_fn: Logging function

    Returns:
        Report dictionary if successful, None if failed or not applicable
    """
    # Check if fast async is enabled
    use_fast_async = os.environ.get("DOU_FAST_ASYNC", "1").strip().lower() in ("1", "true", "yes")
    if hasattr(args, "no_fast_async") and args.no_fast_async:
        use_fast_async = False

    if not use_fast_async:
        return None

    log_fn("[FAST ASYNC] Tentando modo browser único (2x mais rápido)...")

    try:
        # Prepare async input
        async_input = {
            "jobs": jobs,
            "defaults": defaults,
            "out_dir": str(out_dir),
            "out_pattern": out_pattern,
            "max_workers": int(os.environ.get("DOU_MAX_WORKERS", "4") or "4"),
        }

        # Try direct method first
        async_result = _try_direct_async(async_input, log_fn)

        if not async_result:
            return None

        if async_result.get("ok", 0) > 0 or async_result.get("success"):
            # Success! Return formatted report
            report = {
                "total_jobs": len(jobs),
                "ok": async_result.get("ok", 0),
                "fail": async_result.get("fail", 0),
                "items_total": async_result.get("items_total", 0),
                "outputs": async_result.get("outputs", []),
                "metrics": async_result.get("metrics", {}),
                "mode": "fast_async",
            }

            elapsed = async_result.get("elapsed", 0)
            log_fn("[FAST ASYNC] ✓ SUCESSO!")
            log_fn(f"[FAST ASYNC]   Tempo: {elapsed:.1f}s")
            log_fn(f"[FAST ASYNC]   Jobs OK: {report['ok']}/{report['total_jobs']}")
            log_fn(f"[FAST ASYNC]   Jobs FAIL: {report['fail']}/{report['total_jobs']}")
            log_fn(f"[FAST ASYNC]   Items coletados: {report['items_total']}")
            if report['outputs']:
                log_fn(f"[FAST ASYNC]   Arquivos salvos: {len(report['outputs'])}")

            return report
        else:
            error_msg = async_result.get("error", "unknown") if async_result else "no result"
            log_fn(f"[FAST ASYNC] Falhou ({error_msg}), usando fallback...")
            return None

    except Exception as e:
        log_fn(f"[FAST ASYNC] Erro ao importar/executar: {e}, usando fallback...")
        return None


def _try_direct_async(async_input: dict[str, Any], log_fn: Callable[[str], None]) -> dict[str, Any] | None:
    """Try to run async collector directly.

    Args:
        async_input: Input configuration for async collector
        log_fn: Logging function

    Returns:
        Async result or None if failed
    """
    try:
        from ...ui.collectors.dou_parallel import run_parallel_batch

        return run_parallel_batch(async_input)
    except RuntimeError as e:
        if "event loop" in str(e).lower():
            # Event loop is running, use subprocess
            log_fn("[FAST ASYNC] Event loop detectado, usando subprocess...")
            return _run_fast_async_subprocess(async_input, log_fn)
        else:
            raise
    except Exception:
        return None


def _run_fast_async_subprocess(async_input: dict[str, Any], log_fn: Callable[[str], None]) -> dict[str, Any] | None:
    """Run async collector in subprocess.

    Args:
        async_input: Input configuration
        log_fn: Logging function

    Returns:
        Result dictionary or None if failed
    """
    import subprocess
    import sys
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(async_input, f, ensure_ascii=False)
            input_path = f.name

        output_path = input_path.replace(".json", "_result.json")

        py = sys.executable or "python"
        cmd = [py, "-m", "dou_snaptrack.ui.collectors.dou_parallel"]

        # O módulo usa variáveis de ambiente para input/output
        env = os.environ.copy()
        env["INPUT_JSON_PATH"] = input_path
        env["RESULT_JSON_PATH"] = output_path
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)

        output_data = None
        if Path(output_path).exists():
            try:
                with open(output_path, encoding="utf-8") as f:
                    output_data = json.load(f)
            except Exception as read_err:
                log_fn(f"[FAST ASYNC] Falha ao ler resultado: {read_err}")

        # Sempre logar resultado do subprocess para diagnóstico
        log_fn(f"[FAST ASYNC] Subprocess retornou code={result.returncode}")

        if output_data:
            log_fn(
                f"[FAST ASYNC] Resultado: ok={output_data.get('ok')} fail={output_data.get('fail')} "
                f"items={output_data.get('items_total')} elapsed={output_data.get('elapsed', 0):.1f}s"
            )
            if output_data.get("error"):
                log_fn(f"[FAST ASYNC] Erro do coletor: {output_data.get('error')}")
            if output_data.get("traceback"):
                log_fn(f"[FAST ASYNC] Traceback: {output_data.get('traceback')[:500]}")
        else:
            log_fn("[FAST ASYNC] Nenhum output_data encontrado no arquivo de resultado")

        # Mostrar stderr/stdout se houver erro ou se debug estiver ativo
        debug_logs = os.environ.get("DOU_FAST_ASYNC_DEBUG", "0").lower() in ("1", "true", "yes")
        if result.returncode != 0 or debug_logs:
            if result.stderr:
                # Mostrar últimas linhas do stderr (mais útil que as primeiras)
                stderr_lines = result.stderr.strip().split('\n')
                if len(stderr_lines) > 20:
                    log_fn(f"[FAST ASYNC] stderr ({len(stderr_lines)} linhas, últimas 20):")
                    for line in stderr_lines[-20:]:
                        log_fn(f"  {line}")
                else:
                    log_fn("[FAST ASYNC] stderr:")
                    for line in stderr_lines:
                        log_fn(f"  {line}")
            if result.stdout:
                log_fn(f"[FAST ASYNC] stdout: {result.stdout[:800]}")

        # Return whatever the collector produced so the caller can decide if it is usable
        if output_data:
            return output_data

        log_fn("[FAST ASYNC] ERRO: Arquivo de resultado não existe ou está vazio")
        log_fn(f"[FAST ASYNC] Esperado em: {output_path}")
        return None

    except Exception as e:
        log_fn(f"[FAST ASYNC] Subprocess error: {e}")
        return None
    finally:
        keep_tmp = os.environ.get("DOU_KEEP_FAST_ASYNC_TMP", "0").lower() in ("1", "true", "yes")
        if keep_tmp:
            log_fn(f"[FAST ASYNC] Mantendo arquivos temporários: {input_path}, {output_path}")
        else:
            # Cleanup temp files
            try:
                Path(input_path).unlink(missing_ok=True)
                Path(output_path).unlink(missing_ok=True)
            except Exception:
                pass
