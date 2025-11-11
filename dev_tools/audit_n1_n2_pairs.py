"""Auditor de pares N1→N2 do DOU (por seção e data).

Gera um JSON com o mapeamento completo de N1 para suas opções N2
(conforme dropdowns do site) usando a versão async do plan_live.

Opcionalmente, compara com um arquivo de referência existente e imprime
um diff resumido (novos N1, N1 removidos, N2 adicionados/removidos por N1).

Exemplos:
  python dev_tools/audit_n1_n2_pairs.py --date 10-11-2025 --secao DO1 \
    --out artefatos/pairs_DO1_full.audit.json --headless

  python dev_tools/audit_n1_n2_pairs.py --date 10-11-2025 --secao DO1 \
    --compare artefatos/pairs_DO1_full.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from playwright.async_api import async_playwright

from dou_snaptrack.cli.plan_live_async import build_plan_live_async


async def _scrape_pairs(secao: str, data: str, limit1: int | None, limit2: int | None, headless: bool) -> dict[str, list[str]]:
    """Usa build_plan_live_async para capturar combos e pivota para dict N1->list[N2]."""


    async with async_playwright() as p:
        args = SimpleNamespace(
            secao=secao,
            data=data,
            plan_out=None,
            select1=None,
            select2=None,
            pick1=None,
            pick2=None,
            limit1=limit1,
            limit2=limit2,
            headless=headless,
            slowmo=0,
        )
        cfg = await build_plan_live_async(p, args)
        combos = cfg.get("combos", []) or []

    pairs: dict[str, list[str]] = {}
    for c in combos:
        n1 = (c.get("key1") or "").strip()
        n2 = (c.get("key2") or "").strip()
        if not n1 or not n2:
            continue
        pairs.setdefault(n1, [])
        if n2 not in pairs[n1]:
            pairs[n1].append(n2)
    for k in list(pairs.keys()):
        pairs[k] = sorted(pairs[k])
    return dict(sorted(pairs.items(), key=lambda kv: kv[0].casefold()))


def _load_pairs_file(path: Path) -> dict[str, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "pairs" in data:
            data = data["pairs"]
        out: dict[str, list[str]] = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    out[str(k)] = [str(x) for x in v]
        return out
    except Exception:
        return {}


def _diff_pairs(old: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, Any]:
    old_n1 = set(old.keys())
    new_n1 = set(new.keys())
    added_n1 = sorted(new_n1 - old_n1)
    removed_n1 = sorted(old_n1 - new_n1)
    changed: dict[str, dict[str, list[str]]] = {}
    for n1 in sorted(old_n1 & new_n1):
        o = set(old.get(n1, []))
        n = set(new.get(n1, []))
        add = sorted(n - o)
        rem = sorted(o - n)
        if add or rem:
            changed[n1] = {"added": add, "removed": rem}
    return {
        "added_n1": added_n1,
        "removed_n1": removed_n1,
        "changed": changed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Data DD-MM-YYYY")
    ap.add_argument("--secao", default="DO1", choices=["DO1", "DO2", "DO3"], help="Seção do DOU")
    ap.add_argument("--out", type=Path, default=None, help="Arquivo JSON para salvar pares (opcional)")
    ap.add_argument("--compare", type=Path, default=None, help="Arquivo de referência para diff (opcional)")
    ap.add_argument("--limit1", type=int, default=None, help="Limitar quantos N1 varrer (debug)")
    ap.add_argument("--limit2", type=int, default=None, help="Limitar quantos N2 por N1 (debug)")
    ap.add_argument("--headful", action="store_true", help="Mostrar navegador (debug)")
    args = ap.parse_args()

    pairs = asyncio.run(_scrape_pairs(args.secao, args.date, args.limit1, args.limit2, headless=not args.headful))
    meta = {
        "secao": args.secao,
        "data": args.date,
        "total_n1": len(pairs),
        "total_pairs": sum(len(v) for v in pairs.values()),
    }

    print("\n# Auditoria de Pares N1→N2")
    print(json.dumps(meta, ensure_ascii=False, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"_metadata": meta, "pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGravado em: {args.out}")

    if args.compare and args.compare.exists():
        ref = _load_pairs_file(args.compare)
        diff = _diff_pairs(ref, pairs)
        print("\n# Diff vs referência")
        print(json.dumps(diff, ensure_ascii=False, indent=2))
    elif args.compare:
        print(f"\n[warn] Arquivo de referência não encontrado: {args.compare}")


if __name__ == "__main__":  # pragma: no cover
    main()
