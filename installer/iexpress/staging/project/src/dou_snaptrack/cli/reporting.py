from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import re
from ..adapters.utils import generate_bulletin as _generate_bulletin
from ..adapters.utils import summarize_text as _summarize_text
from dou_utils.content_fetcher import Fetcher
from dou_utils.log_utils import get_logger

logger = get_logger(__name__)


def consolidate_and_report(
    in_dir: str,
    kind: str,
    out_path: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: Optional[List[str]] = None,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 15,
) -> None:
    import os
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    agg = []
    for f in sorted(Path(in_dir).glob("*.json")):
        try:
            data = __import__('json').loads(f.read_text(encoding="utf-8"))
            items = data.get("itens", [])
            # Normalizar links para absolutos quando possível
            for it in items:
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
            agg.extend(items)
        except Exception:
            pass

    # Deep mode por padrão: enriquecer texto com cache para melhorar qualidade
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines > 0 and not offline and agg:
        logger.info(f"[ENRICH] deep-mode STRICT: items={len(agg)} parallel={fetch_parallel} timeout={fetch_timeout_sec}s overwrite=True")
        # STRICT: sobrescrever texto de todos os itens
        Fetcher(timeout_sec=fetch_timeout_sec).enrich_items(agg, max_workers=fetch_parallel, overwrite=True, min_len=None)  # type: ignore
    else:
        if summary_lines <= 0:
            logger.info("[ENRICH] skipped: summarize disabled (summary_lines=0)")
        elif not enrich_missing:
            logger.info("[ENRICH] skipped: enrich_missing=False")
        elif offline:
            logger.info("[ENRICH] skipped: DOU_OFFLINE_REPORT=1")
        elif not agg:
            logger.info("[ENRICH] skipped: no items")

    # Fallback: se ainda não houver texto, usar título como base mínima para resumo
    if summary_lines > 0 and agg:
        for it in agg:
            if not (it.get("texto") or it.get("ementa")):
                t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                if t:
                    it["texto"] = str(t)

    result: Dict[str, Any] = {
        "data": date_label or "",
        "secao": secao_label or "",
        "total": len(agg),
        "itens": agg,
    }
    summarize = summary_lines > 0
    # Adapt summarizer to expected signature
    def _summarizer(text: str, max_lines: int, mode: str, keywords: Optional[List[str]]):
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


def split_and_report_by_n1(
    in_dir: str,
    kind: str,
    out_root: str,
    pattern: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: Optional[List[str]] = None,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 15,
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
    def _sanitize(name: str) -> str:
        import re
        name = re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", name)
        return (name or "n1").strip(" _")[:120]

    import os
    out_dir = Path(out_root)
    # If a file path is passed (like logs/unused.docx), use its parent as output directory
    if out_dir.suffix:
        out_dir = out_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Agrupar por N1 (selecoes[0])
    groups: Dict[str, List[Dict[str, Any]]] = {}
    date = date_label
    secao = secao_label
    for f in sorted(Path(in_dir).glob("*.json")):
        try:
            data = __import__('json').loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        sel = (data.get("selecoes") or [])
        n1 = None
        if isinstance(sel, list) and len(sel) >= 1 and isinstance(sel[0], dict):
            n1 = sel[0].get("key") or sel[0].get("label") or sel[0].get("type")
        n1 = str(n1 or "N1")
        items = data.get("itens", [])
        # Normalizar links para absolutos quando possível
        for it in items:
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
        groups.setdefault(n1, []).extend(items)
        # Atualiza metadados se faltantes
        if not date:
            date = data.get("data") or date
        if not secao:
            secao = data.get("secao") or secao

    total_files = 0
    # Deep mode por padrão também em agregados por N1
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines > 0 and not offline and groups:
        total_items = sum(len(v) for v in groups.values())
        logger.info(f"[ENRICH] deep-mode STRICT by N1: items={total_items} groups={len(groups)} parallel={fetch_parallel} timeout={fetch_timeout_sec}s overwrite=True")
        fetcher = Fetcher(timeout_sec=fetch_timeout_sec)
        for k, items in groups.items():
            fetcher.enrich_items(items, max_workers=fetch_parallel, overwrite=True, min_len=None)  # type: ignore
    else:
        if summary_lines <= 0:
            logger.info("[ENRICH] skipped by N1: summarize disabled (summary_lines=0)")
        elif not enrich_missing:
            logger.info("[ENRICH] skipped by N1: enrich_missing=False")
        elif offline:
            logger.info("[ENRICH] skipped by N1: DOU_OFFLINE_REPORT=1")
        elif not groups:
            logger.info("[ENRICH] skipped by N1: no groups")

    # Adapt summarizer
    summarize = summary_lines > 0
    def _summarizer(text: str, max_lines: int, mode: str, keywords: Optional[List[str]]):
        if not _summarize_text:
            return text
        return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    for n1, items in groups.items():
        # Fallback: se itens do grupo ainda não tiverem texto, usar título como base mínima para resumo
        if summarize and items:
            for it in items:
                if not (it.get("texto") or it.get("ementa")):
                    t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                    if t:
                        it["texto"] = str(t)
        name = pattern.replace("{n1}", _sanitize(n1)).replace("{date}", _sanitize(date or "")).replace("{secao}", _sanitize(secao or ""))
        out_path = out_dir / name
        # Garantir que a pasta do arquivo exista, mesmo se o padrão incluir subpastas
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result: Dict[str, Any] = {"data": date or "", "secao": secao or "", "total": len(items), "itens": items}
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
def _enrich_missing_texts(*args, **kwargs):
    # Legacy compat: mantido para evitar import breaks; não usado após refactor
    logger.info("[ENRICH] legacy function not used; using dou_utils.content_fetcher.Fetcher instead")
