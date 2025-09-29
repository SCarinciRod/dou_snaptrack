from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable

from ..cli.summary_config import SummaryConfig
from ..adapters.services import get_edition_runner
from ..adapters.utils import generate_bulletin as _generate_bulletin, summarize_text as _summarize_text


def _make_summarizer(summary: SummaryConfig) -> Optional[Callable[[str, int, str, Optional[List[str]]], str]]:
    if not _summarize_text:
        return None

    def _adapter(text: str, max_lines: int, mode: str, keywords: Optional[List[str]] = None) -> str:
        # _summarize_text is guaranteed not None here due to guard above
        return (_summarize_text or (lambda t, **_: t))(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    return _adapter


def run_once(context, date: str, secao: str,
             key1: str, key1_type: str,
             key2: str, key2_type: str,
             key3: Optional[str], key3_type: Optional[str],
             query: Optional[str], max_links: int, out_path: str,
             scrape_details: bool, detail_timeout: int, fallback_date_if_missing: bool,
             label1: Optional[str], label2: Optional[str], label3: Optional[str],
             max_scrolls: int, scroll_pause_ms: int, stable_rounds: int,
             state_file: Optional[str], bulletin: Optional[str], bulletin_out: Optional[str],
             summary: SummaryConfig,
             page=None, keep_page_open: bool = False) -> Dict[str, Any]:

    try:
        EditionRunnerService, EditionRunParams = get_edition_runner()
    except Exception as e:
        raise RuntimeError(str(e))

    summarizer = _make_summarizer(summary)
    runner = EditionRunnerService(context)
    params = EditionRunParams(
        date=str(date), secao=str(secao),
        key1=str(key1), key1_type=str(key1_type),
        key2=str(key2), key2_type=str(key2_type),
        key3=str(key3) if key3 else None, key3_type=str(key3_type) if key3_type else None,
        label1=label1, label2=label2, label3=label3,
        query=query or "",
        max_links=int(max_links),
        max_scrolls=int(max_scrolls), scroll_pause_ms=int(scroll_pause_ms), stable_rounds=int(stable_rounds),
        scrape_detail=bool(scrape_details), detail_timeout=int(detail_timeout),
        fallback_date_if_missing=bool(fallback_date_if_missing),
        dedup_state_file=state_file,
        summary=bool(summary.lines and summary.lines > 0),
        summary_lines=int(summary.lines), summary_mode=str(summary.mode), summary_keywords=summary.keywords,
    )

    # If page reuse is requested, inject the existing page into the service if it supports it.
    # Our EditionRunnerService opens/closes its own page; to reuse, we can set a duck-typed attribute the service checks.
    if page is not None:
        try:
            setattr(runner, "_precreated_page", page)
            setattr(runner, "_keep_page_open", bool(keep_page_open))
        except Exception:
            pass
    result = runner.run(params, summarizer_fn=summarizer)

    # Persist JSON
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(__import__('json').dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Links salvos em: {out_path} (total={result.get('total', 0)})")

    # Optional bulletin
    if bulletin and bulletin_out and _generate_bulletin:
        try:
            _generate_bulletin(
                result,
                bulletin_out,
                kind=bulletin,
                summarize=bool(summary.lines and summary.lines > 0),
                summarizer=summarizer,
                keywords=summary.keywords,
                max_lines=summary.lines or 0,
                mode=summary.mode,
            )
            print(f"[OK] Boletim gerado: {bulletin_out}")
        except Exception as e:
            print(f"[Aviso] Falha ao gerar boletim: {e}")

    return result
