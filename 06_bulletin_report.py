#!/usr/bin/env python
# 06_bulletin_report.py
#
# Fase 0: adicionar schema / generatedAt / source para meta de boletim.
# Gera boletim (docx/md/html) + JSON meta opcional com padrão <out>.meta.json

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List
from dou_utils.bulletin_utils import generate_bulletin
from dou_utils.advanced_summary import summarize_advanced
from dou_utils.log_utils import get_logger
from dou_utils.constants import schema_block, utc_now_iso, SOURCES

logger = get_logger(__name__)


def _collect_items(in_dir: Path) -> List[dict]:
    items = []
    for f in sorted(in_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Apenas artefatos com lista de itens
            if isinstance(data.get("itens"), list):
                items.extend(data.get("itens", []))
        except Exception as e:
            logger.warning("Falha leitura JSON", extra={"file": str(f), "err": str(e)})
    return items


def main():
    ap = argparse.ArgumentParser(description="Consolidador de boletim (multi-formato) + schema (Fase 0)")
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--kind", choices=["docx", "md", "html"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-label", help="Rótulo de data no boletim (opcional)")
    ap.add_argument("--secao-label", help="Rótulo de seção (opcional)")
    ap.add_argument("--summary", action="store_true", help="Ativar resumo (modo simples se não usar advanced)")
    ap.add_argument("--summary-advanced", action="store_true", help="Ativar resumo avançado")
    ap.add_argument("--summary-lines", type=int, default=5)
    ap.add_argument("--summary-mode", default="center",
                    choices=["center", "lead", "keywords-first", "hybrid", "density", "head"])
    ap.add_argument("--keywords", help="Lista ; separada para reforço de resumo")
    ap.add_argument("--meta-json", help="Caminho opcional para salvar meta JSON (default: <out>.meta.json)")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.exists():
        raise SystemExit(f"Diretório não encontrado: {in_dir}")

    itens = _collect_items(in_dir)
    result_base = {
        "data": args.data_label or "",
        "secao": args.secao_label or "",
        "itens": itens
    }

    keywords = []
    if args.keywords:
        for part in args.keywords.split(";"):
            s = part.strip()
            if s:
                keywords.append(s)

    summarizer = None
    summarize_flag = False
    if args.summary_advanced:
        summarizer = lambda txt, ml, md, kw: summarize_advanced(txt, max_lines=ml, mode=md, keywords=kw)
        summarize_flag = True
    elif args.summary:
        summarize_flag = True

    meta = generate_bulletin(
        result_base,
        args.out,
        kind=args.kind,
        summarize=summarize_flag,
        summarizer=summarizer,
        keywords=keywords,
        max_lines=args.summary_lines,
        mode=args.summary_mode
    )

    meta_obj = {
        "schema": schema_block("bulletin"),
        "generatedAt": utc_now_iso(),
        "source": SOURCES.get("bulletin", "bulletin-builder"),
        "params": {
            "data": result_base["data"],
            "secao": result_base["secao"],
            "summary": summarize_flag,
            "summaryAdvanced": args.summary_advanced,
            "summaryMode": args.summary_mode,
            "summaryLines": args.summary_lines,
            "keywordsProvided": bool(keywords)
        },
        "stats": meta,
        "output": str(args.out)
    }

    meta_path = Path(args.meta_json) if args.meta_json else Path(str(args.out) + ".meta.json")
    meta_path.write_text(json.dumps(meta_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Boletim gerado: {args.out} (itens={meta['items']} grupos={meta['groups']} resumos={meta['summarized']})")
    print(f"[OK] Meta JSON: {meta_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Abortado]")
