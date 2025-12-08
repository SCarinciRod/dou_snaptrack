from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# CRÍTICO: Aplicar patch para corrigir bug de texto cortado em resumos
import dou_utils.bulletin_patch  # noqa: F401
from dou_utils.content_fetcher import Fetcher
from dou_utils.log_utils import get_logger
from dou_utils.summarize import summarize_text as _summarize_text

from ..adapters.utils import generate_bulletin as _generate_bulletin
from ..utils.text import sanitize_filename

logger = get_logger(__name__)


def consolidate_and_report(
    in_dir: str,
    kind: str,
    out_path: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: list[str] | None = None,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 15,
    fetch_force_refresh: bool = True,
    fetch_browser_fallback: bool = True,
    short_len_threshold: int = 800,
) -> None:
    from .consolidation_helpers import (
        load_json_files,
        should_enrich,
        enrich_items,
        log_enrich_skip_reason,
        add_title_fallback,
        create_result_dict,
    )
    
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Load and normalize items
    agg = load_json_files(in_dir)

    # Enrich items if appropriate
    if should_enrich(summary_lines, agg):
        enrich_items(agg, fetch_parallel, fetch_timeout_sec, fetch_force_refresh, 
                    fetch_browser_fallback, short_len_threshold)
    else:
        log_enrich_skip_reason(summary_lines, enrich_missing, agg)

    # Add fallback text from title
    add_title_fallback(agg, summary_lines)

    # Create result and generate bulletin
    result = create_result_dict(agg, date_label, secao_label)
    summarize = summary_lines > 0
    
    def _summarizer(text: str, max_lines: int, mode: str, keywords: list[str] | None):
        if not _summarize_text:
            return text
        return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    _generate_bulletin(
        result,
        out_path,
        kind=kind,
        summarize=summarize,
        summarizer=_summarizer if summarize else None,
        keywords=summary_keywords,
        max_lines=summary_lines or 0,
        mode=summary_mode,
    )
    print(f"[OK] Boletim consolidado gerado: {out_path}")


def report_from_aggregated(
    files: list[str],
    kind: str,
    out_path: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: list[str] | None = None,
    order_desc_by_date: bool = True,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 15,
    fetch_force_refresh: bool = True,
    fetch_browser_fallback: bool = True,
    short_len_threshold: int = 800,
) -> None:
    """Gera boletim a partir de um ou mais arquivos agregados (cada um já contém muitos itens).

    Permite juntar agregados de dias diferentes em um único boletim.
    """
    from .reporting_helpers import (
        load_aggregated_files,
        sort_items_by_date_desc,
        should_enrich_items,
        enrich_items_with_fetcher,
        clean_enriched_items,
        log_enrichment_debug_info,
        log_enrichment_skip_reason,
        fallback_add_title_as_text,
    )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Load and merge files
    agg, date, secao = load_aggregated_files(files)
    date = date or date_label
    secao = secao or secao_label

    # Sort by publication date if requested
    if order_desc_by_date:
        sort_items_by_date_desc(agg)

    # Enrich items with deep mode if appropriate
    if should_enrich_items(summary_lines, enrich_missing, agg):
        enrich_items_with_fetcher(
            agg,
            fetch_parallel,
            fetch_timeout_sec,
            fetch_force_refresh,
            fetch_browser_fallback,
            short_len_threshold,
        )
        clean_enriched_items(agg)
        log_enrichment_debug_info(agg)
    else:
        offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1", "true", "yes")
        log_enrichment_skip_reason(summary_lines, enrich_missing, offline, bool(agg))

    # Fallback: use title as base for summary if text is missing
    fallback_add_title_as_text(agg, summary_lines)

    # Generate bulletin
    result: dict[str, Any] = {"data": date or "", "secao": secao or "", "total": len(agg), "itens": agg}
    summarize = summary_lines > 0

    def _summarizer(text: str, max_lines: int, mode: str, keywords: list[str] | None):
        if not _summarize_text:
            return text
        return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    _generate_bulletin(
        result,
        out_path,
        kind=kind,
        summarize=summarize,
        summarizer=_summarizer if summarize else None,
        keywords=summary_keywords,
        max_lines=summary_lines or 0,
        mode=summary_mode,
    )
    print(f"[OK] Boletim (de agregados) gerado: {out_path}")


def find_aggregated_by_plan(in_dir: str, plan_name: str) -> list[str]:
    """Lista arquivos agregados do padrão {plan}_{secao}_{data}.json do plano indicado."""
    plan_safe = re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", plan_name).strip(" _")
    return [str(f) for f in sorted(Path(in_dir).glob(f"{plan_safe}_*_*_.json"))]


def aggregate_outputs_by_plan(in_dir: str, plan_name: str) -> list[str]:
    """Aggregate all job JSON outputs inside a day-folder into a single per-date
    file at the resultados root, named {plan}_paginadoDOU_{date}.json.

    Returns the list of aggregated files written.
    """
    root = Path(in_dir)
    if root.is_file():
        root = root.parent
    # Detect date and secao from any job file
    jobs = [p for p in root.glob("*.json") if p.name.lower().endswith(".json") and not p.name.lower().startswith("batch_report") and not p.name.startswith("_")]
    if not jobs:
        return []
    from collections import defaultdict
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"data": "", "secao": "", "plan": plan_name, "itens": []})
    secao_any = ""
    for jf in jobs:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        date = str(data.get("data") or "")
        secao = str(data.get("secao") or "")
        if not agg[date]["data"]:
            agg[date]["data"] = date
        if not agg[date]["secao"]:
            agg[date]["secao"] = secao
        if not secao_any and secao:
            secao_any = secao
        items = data.get("itens", []) or []
        # Normalize detail_url absolute
        for it in items:
            try:
                durl = it.get("detail_url") or ""
                if not durl:
                    link = it.get("link") or ""
                    if link:
                        if link.startswith("http"):
                            durl = link
                        elif link.startswith("/"):
                            durl = f"https://www.in.gov.br{link}"
                if durl:
                    it["detail_url"] = durl
            except Exception:
                pass
        agg[date]["itens"].extend(items)
    written: list[str] = []
    # resultados root = parent of the day folder if named 'resultados'
    target_dir = root.parent if root.parent.name.lower() == "resultados" else root
    secao_label = (secao_any or "DO").strip()
    for date, payload in agg.items():
        payload["total"] = len(payload.get("itens", []))
        safe_plan = sanitize_filename(plan_name)
        date_lab = (date or "").replace("/", "-")
        out_name = f"{safe_plan}_{secao_label}_{date_lab}.json"
        out_path = target_dir / out_name
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(out_path))
    return written


def split_and_report_by_n1(
    in_dir: str,
    kind: str,
    out_root: str,
    pattern: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: list[str] | None = None,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 15,
    fetch_force_refresh: bool = True,
    fetch_browser_fallback: bool = True,
    short_len_threshold: int = 800,
) -> None:
    """Gera múltiplos boletins, um por N1 (primeiro nível da seleção).

    Args:
        in_dir: pasta com JSONs de saída dos jobs
        kind: docx|md|html
        out_root: diretório base de saída (será criado)
        pattern: padrão do nome do arquivo, com placeholders {n1},{date},{secao}
        date_label: rótulo de data (opcional)
        secao_label: rótulo de seção (opcional)
    """
    from .reporting_helpers import (
        load_and_group_by_n1,
        enrich_groups_with_fetcher,
        log_enrichment_skip_reason,
        fallback_add_title_as_text,
    )

    # Prepare output directory
    out_dir = Path(out_root)
    if out_dir.suffix:  # If a file path is passed, use its parent
        out_dir = out_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load and group items by N1
    groups, date, secao = load_and_group_by_n1(in_dir)
    date = date or date_label
    secao = secao or secao_label

    # Enrich items with deep mode if appropriate
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1", "true", "yes")
    if summary_lines > 0 and not offline and enrich_missing and groups:
        enrich_groups_with_fetcher(
            groups,
            fetch_parallel,
            fetch_timeout_sec,
            fetch_force_refresh,
            fetch_browser_fallback,
            short_len_threshold,
        )
    else:
        log_enrichment_skip_reason(summary_lines, enrich_missing, offline, bool(groups), context="by N1")

    # Create summarizer
    summarize = summary_lines > 0

    def _summarizer(text: str, max_lines: int, mode: str, keywords: list[str] | None):
        if not _summarize_text:
            return text
        return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    # Generate bulletin for each group
    total_files = 0
    for n1, items in groups.items():
        # Fallback: use title as text if missing
        fallback_add_title_as_text(items, summary_lines)

        # Generate output filename
        name = (
            pattern.replace("{n1}", sanitize_filename(n1, max_len=120))
            .replace("{date}", sanitize_filename(date or "", max_len=120))
            .replace("{secao}", sanitize_filename(secao or "", max_len=120))
        )
        out_path = out_dir / name
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate bulletin
        result: dict[str, Any] = {"data": date or "", "secao": secao or "", "total": len(items), "itens": items}
        _generate_bulletin(
            result,
            str(out_path),
            kind=kind,
            summarize=summarize,
            summarizer=_summarizer if summarize else None,
            keywords=summary_keywords,
            max_lines=summary_lines or 0,
            mode=summary_mode,
        )
        print(f"[OK] Boletim N1 gerado: {out_path} (itens={len(items)})")
        total_files += 1

    print(f"[REPORT] Gerados {total_files} arquivos por N1 em: {out_dir}")


# ----------------- helpers -----------------
def _enrich_missing_texts(*args, **_kwargs):
    # Legacy compat: mantido para evitar import breaks; não usado após refactor
    logger.info("[ENRICH] legacy function not used; using dou_utils.content_fetcher.Fetcher instead")
