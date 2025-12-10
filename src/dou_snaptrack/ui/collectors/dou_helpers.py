"""Helper functions for parallel DOU collection.

This module contains extracted functions from main_async to reduce complexity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


async def launch_browser_with_channels(p, prefer_edge: bool, log_fn) -> Any | None:
    """Launch browser trying different channels.

    Args:
        p: Playwright instance
        prefer_edge: Whether to prefer Edge over Chrome
        log_fn: Logging function

    Returns:
        Browser instance or None
    """
    channels = ("msedge", "chrome") if prefer_edge else ("chrome", "msedge")

    for channel in channels:
        try:
            browser = await p.chromium.launch(
                channel=channel,
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                ]
            )
            log_fn(f"✓ Browser {channel} iniciado")
            return browser
        except Exception:
            continue

    return None


async def create_worker_contexts(browser, actual_workers: int, goto_timeout: int) -> tuple[list, list]:
    """Create browser contexts and pages for workers.

    Args:
        browser: Browser instance
        actual_workers: Number of workers
        goto_timeout: Timeout for navigation

    Returns:
        Tuple of (contexts, pages)
    """
    contexts = []
    pages = []

    for _ in range(actual_workers):
        ctx = await browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1280, 'height': 900}
        )
        ctx.set_default_timeout(goto_timeout)

        # Block heavy resources
        await ctx.route("**/*.{png,jpg,jpeg,gif,webp,mp4,woff,woff2,ttf,otf}", lambda route: route.abort())
        await ctx.route("**/*analytics*", lambda route: route.abort())
        await ctx.route("**/*googletagmanager*", lambda route: route.abort())

        page = await ctx.new_page()
        contexts.append(ctx)
        pages.append(page)

    return contexts, pages


async def cleanup_browser_resources(contexts: list, browser) -> None:
    """Clean up browser contexts and browser.

    Args:
        contexts: List of browser contexts
        browser: Browser instance
    """
    for ctx in contexts:
        await ctx.close()
    await browser.close()


def calculate_statistics(results: list) -> dict[str, Any]:
    """Calculate statistics from results.

    Args:
        results: List of JobResult objects

    Returns:
        Dictionary with statistics
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    total_items = sum(len(r.items) for r in successful)

    return {
        "successful": successful,
        "failed": failed,
        "total_items": total_items,
    }


def log_final_results(stats: dict[str, Any], jobs_count: int, elapsed: float, log_fn) -> None:
    """Log final execution results.

    Args:
        stats: Statistics dictionary
        jobs_count: Total number of jobs
        elapsed: Elapsed time
        log_fn: Logging function
    """
    log_fn(f"{'='*60}")
    log_fn("RESULTADO FINAL (Single Browser Async)")
    log_fn(f"{'='*60}")
    log_fn(f"Jobs OK: {len(stats['successful'])}/{jobs_count}")
    log_fn(f"Jobs FAIL: {len(stats['failed'])}/{jobs_count}")
    log_fn(f"Total items coletados: {stats['total_items']}")
    log_fn(f"Tempo total: {elapsed:.1f}s")

    # Listar jobs que falharam
    if stats['failed']:
        log_fn("Jobs com falha:")
        for r in stats['failed']:
            log_fn(f"  - {r.job_id}: {r.error}")

    # Resumo dos jobs bem sucedidos
    if stats['successful']:
        log_fn("Jobs bem sucedidos:")
        for r in stats['successful']:
            log_fn(f"  - {r.job_id}: {len(r.items)} items em {r.elapsed:.1f}s")

    log_fn(f"{'='*60}")


def save_job_outputs(successful_results: list, out_dir: str, out_pattern: str) -> list[str]:
    """Save individual job outputs to files.

    Args:
        successful_results: List of successful JobResult objects
        out_dir: Output directory
        out_pattern: Output filename pattern

    Returns:
        List of output file paths
    """
    outputs = []
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Import sanitize_filename with fallback
    try:
        from dou_snaptrack.utils.text import sanitize_filename
    except ImportError:
        import re
        def sanitize_filename(s: str) -> str:
            return re.sub(r'[<>:"/\\|?*]', '_', str(s or ''))

    for r in successful_results:
        # Build filename
        tokens = {
            "topic": r.topic or "job",
            "secao": r.secao or "DO",
            "date": (r.date or "").replace("/", "-"),
            "idx": str(r.job_index),
            "key1": r.key1 or "",
            "key2": r.key2 or "",
        }
        name = out_pattern
        for k, v in tokens.items():
            name = name.replace("{" + k + "}", sanitize_filename(str(v)))

        file_path = out_path / name
        output_data = {
            "data": r.date,
            "secao": r.secao,
            "key1": r.key1,
            "key2": r.key2,
            "topic": r.topic,
            "total": len(r.items),
            "itens": r.items,
            "_timings": r.timings
        }
        file_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append(str(file_path))

    return outputs


def build_final_result(stats: dict[str, Any], outputs: list[str], elapsed: float) -> dict[str, Any]:
    """Build final result dictionary.

    Args:
        stats: Statistics dictionary
        outputs: List of output file paths
        elapsed: Elapsed time

    Returns:
        Final result dictionary
    """
    # Considerar sucesso se pelo menos um job foi bem sucedido
    # (partial success é aceitável para batch processing)
    has_successes = len(stats["successful"]) > 0
    all_success = len(stats["failed"]) == 0

    return {
        "success": has_successes,  # True se há pelo menos um sucesso
        "all_success": all_success,  # True somente se todos foram ok
        "ok": len(stats["successful"]),
        "fail": len(stats["failed"]),
        "items_total": stats["total_items"],
        "outputs": outputs,
        "elapsed": round(elapsed, 1),
        "metrics": {
            "jobs": [
                {
                    "job_index": r.job_index,
                    "topic": r.topic,
                    "date": r.date,
                    "secao": r.secao,
                    "key1": r.key1,
                    "key2": r.key2,
                    "items": len(r.items),
                    "elapsed_sec": r.elapsed,
                    "timings": r.timings,
                }
                for r in stats["successful"]
            ],
            "summary": {}
        }
    }
