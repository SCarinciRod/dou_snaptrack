from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import re
from ..adapters.utils import generate_bulletin as _generate_bulletin
from ..adapters.utils import summarize_text as _summarize_text


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
    fetch_timeout_sec: int = 10,
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

    # Enriquecer com texto (leve) apenas para itens sem texto quando for resumir
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines > 0 and enrich_missing and not offline and agg:
        _enrich_missing_texts(agg, max_workers=fetch_parallel, timeout_sec=fetch_timeout_sec)

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


def report_from_aggregated(
    files: List[str],
    kind: str,
    out_path: str,
    date_label: str = "",
    secao_label: str = "",
    summary_lines: int = 0,
    summary_mode: str = "center",
    summary_keywords: Optional[List[str]] = None,
    order_desc_by_date: bool = True,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 10,
) -> None:
    """Gera boletim a partir de um ou mais arquivos agregados (cada um já contém muitos itens).

    Permite juntar agregados de dias diferentes em um único boletim.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    agg: List[Dict[str, Any]] = []
    date = date_label
    secao = secao_label
    for fp in files:
        try:
            data = __import__('json').loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        items = data.get("itens", [])
        # Normalizar links para absolutos quando possível (para enriquecer texto)
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
        if not date:
            date = data.get("data") or date
        if not secao:
            secao = data.get("secao") or secao
    # Ordena por data_publicacao (desc), quando disponível
    if order_desc_by_date:
        def _key(it: Dict[str, Any]):
            d = it.get("data_publicacao") or ""
            # esperado DD-MM-AAAA; forçar formato comparável AAAA-MM-DD
            try:
                dd, mm, yyyy = d.split("-")
                return f"{yyyy}-{mm}-{dd}"
            except Exception:
                return ""
        agg.sort(key=_key, reverse=True)

    # Enriquecer com texto leve para itens sem texto quando for resumir
    import os
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines > 0 and enrich_missing and not offline and agg:
        _enrich_missing_texts(agg, max_workers=fetch_parallel, timeout_sec=fetch_timeout_sec)

    # Fallback: se ainda não houver texto, usar título como base mínima para resumo
    if summary_lines > 0 and agg:
        for it in agg:
            if not (it.get("texto") or it.get("ementa")):
                t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                if t:
                    it["texto"] = str(t)

    result: Dict[str, Any] = {"data": date or "", "secao": secao or "", "total": len(agg), "itens": agg}
    summarize = summary_lines > 0
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
    print(f"[OK] Boletim (de agregados) gerado: {out_path}")


def find_aggregated_by_plan(in_dir: str, plan_name: str) -> List[str]:
    """Lista arquivos agregados do padrão {plan}_{secao}_{data}.json do plano indicado."""
    plan_safe = re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", plan_name).strip(" _")
    out = []
    for f in sorted(Path(in_dir).glob(f"{plan_safe}_*_*.json")):
        out.append(str(f))
    return out


def aggregate_outputs_by_plan(in_dir: str, plan_name: str) -> List[str]:
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
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"data": "", "secao": "", "plan": plan_name, "itens": []})
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
    written: List[str] = []
    # resultados root = parent of the day folder if named 'resultados'
    target_dir = root.parent if root.parent.name.lower() == "resultados" else root
    secao_label = (secao_any or "DO").strip()
    def _sanitize(name: str) -> str:
        return re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", name).strip(" _")[:180] or "out"
    for date, payload in agg.items():
        payload["total"] = len(payload.get("itens", []))
        safe_plan = _sanitize(plan_name)
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
    summary_keywords: Optional[List[str]] = None,
    enrich_missing: bool = True,
    fetch_parallel: int = 8,
    fetch_timeout_sec: int = 10,
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
    # Opcionalmente enriquecer textos ausentes nos grupos quando for resumir
    offline = (os.environ.get("DOU_OFFLINE_REPORT", "").strip() or "0").lower() in ("1","true","yes")
    if summary_lines > 0 and enrich_missing and not offline and groups:
        for k, items in groups.items():
            _enrich_missing_texts(items, max_workers=fetch_parallel, timeout_sec=fetch_timeout_sec)

    # Adapt summarizer
    summarize = summary_lines > 0
    def _summarizer(text: str, max_lines: int, mode: str, keywords: Optional[List[str]]):
        if not _summarize_text:
            return text
        return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore

    for n1, items in groups.items():
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
def _enrich_missing_texts(items: List[Dict[str, Any]], max_workers: int = 8, timeout_sec: int = 10) -> None:
    """Para cada item sem 'texto' nem 'ementa', faz um GET simples e extrai o corpo da matéria.
    Evita Playwright para não pesar; usa regex/HTML simples. Preenche item['texto'] quando possível.
    """
    targets = []
    for it in items:
        if (it.get("texto") or it.get("ementa")):
            continue
        url = it.get("detail_url") or it.get("link") or ""
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://www.in.gov.br{url}"
        if not url.startswith("http"):
            continue
        targets.append((it, url))

    if not targets:
        return

    def _fetch(url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "close",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                try:
                    return raw.decode("latin-1", errors="ignore")
                except Exception:
                    return ""

    def _extract_text(html: str) -> str:
        if not html:
            return ""
        # Remover scripts/styles
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
        # Tentar article, depois main, depois body
        m = re.search(r"<article[^>]*>([\s\S]*?)</article>", html, flags=re.I)
        if not m:
            m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
        if not m:
            m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.I)
        chunk = m.group(1) if m else html
        # Remover tags
        text = re.sub(r"<[^>]+>", " ", chunk)
        # Normalizar espaços e reduzir tamanho
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch, url): (it, url) for it, url in targets}
        for fut in as_completed(futs):
            it, url = futs[fut]
            try:
                html = fut.result()
                body = _extract_text(html)
                if body:
                    it["texto"] = body
            except (urllib.error.URLError, Exception):
                # se falhar, seguimos sem texto
                continue
