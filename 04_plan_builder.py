#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from dou_utils.services.planning_service import (
    PlanFromMapService,
    PlanFromPairsService,
)

try:
    from dou_utils.log_utils import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)

logger = get_logger(__name__)


def _write_json(path: str | Path, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Plan salvo em: %s", p)


def parse_args():
    ap = argparse.ArgumentParser(description="Constrói um plan (combos) a partir de mapping.json ou pairs.json")
    sub = ap.add_subparsers(dest="mode", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--secao", default="DO1")
    common.add_argument("--date", default=datetime.now().strftime("%d-%m-%Y"))
    common.add_argument("--query")
    common.add_argument("--max-combos", type=int)
    common.add_argument("--dynamic-n2", action="store_true")
    common.add_argument("--no-filter-sentinels", action="store_true", help="Não remover opções sentinela")
    common.add_argument("--base-url", help="Inclui defaults.baseUrl no plan")
    common.add_argument("--out", required=True, help="Arquivo de saída do plan JSON")
    common.add_argument("--debug-inspect", action="store_true", help="Mostra insumos detectados antes de gerar o plan")

    # map
    ap_map = sub.add_parser("map", parents=[common], help="Gerar plan a partir de um mapping.json")
    ap_map.add_argument("--map", dest="map_json", required=True, help="Caminho do mapping.json")
    ap_map.add_argument("--label1-regex")
    ap_map.add_argument("--label2-regex")
    ap_map.add_argument("--label3-regex")
    ap_map.add_argument("--enable-level3", action="store_true")
    ap_map.add_argument("--select1")
    ap_map.add_argument("--pick1")
    ap_map.add_argument("--limit1", type=int)
    ap_map.add_argument("--select2")
    ap_map.add_argument("--pick2")
    ap_map.add_argument("--limit2", type=int)
    ap_map.add_argument("--select3")
    ap_map.add_argument("--pick3")
    ap_map.add_argument("--limit3", type=int)

    # pairs
    ap_pairs = sub.add_parser("pairs", parents=[common], help="Gerar plan a partir de um pairs.json")
    ap_pairs.add_argument("--pairs", dest="pairs_json", required=True, help="Caminho do pairs.json")
    ap_pairs.add_argument("--select1")
    ap_pairs.add_argument("--pick1")
    ap_pairs.add_argument("--limit1", type=int)
    ap_pairs.add_argument("--select2")
    ap_pairs.add_argument("--pick2")
    ap_pairs.add_argument("--limit2-per-n1", type=int)

    return ap.parse_args()


def build_from_map(args):
    svc = PlanFromMapService(args.map_json)

    if args.debug_inspect:
        dd = svc.list_dropdowns()
        logger.info("Dropdowns detectados (label/name e contagem de opções): %s", dd)

    defaults = {}
    if args.base_url:
        defaults["baseUrl"] = args.base_url

    plan = svc.build(
        label1_regex=args.label1_regex,
        label2_regex=args.label2_regex,
        select1=args.select1,
        pick1=args.pick1,
        limit1=args.limit1,
        select2=args.select2,
        pick2=args.pick2,
        limit2=args.limit2,
        max_combos=args.max_combos,
        secao=args.secao,
        date=args.date,
        defaults=defaults,
        query=args.query,
        enable_level3=args.enable_level3,
        label3_regex=args.label3_regex,
        select3=args.select3,
        pick3=args.pick3,
        limit3=args.limit3,
        filter_sentinels=not args.no_filter_sentinels,
        dynamic_n2=args.dynamic_n2,
    )
    return plan


def build_from_pairs(args):
    svc = PlanFromPairsService(args.pairs_json)

    if args.debug_inspect:
        logger.info("Pairs carregado (exemplo do 1º item): %s", "ok")

    defaults = {}
    if args.base_url:
        defaults["baseUrl"] = args.base_url

    plan = svc.build(
        select1=args.select1,
        pick1=args.pick1,
        limit1=args.limit1,
        select2=args.select2,
        pick2=args.pick2,
        limit2_per_n1=args.limit2_per_n1,
        max_combos=args.max_combos,
        secao=args.secao,
        date=args.date,
        defaults=defaults,
        query=args.query,
        filter_sentinels=not args.no_filter_sentinels,
    )
    return plan


def main():
    args = parse_args()
    try:
        if args.mode == "map":
            plan = build_from_map(args)
        else:
            plan = build_from_pairs(args)
        _write_json(args.out, plan)
    except Exception as e:
        logger.exception("Erro inesperado: %s", e)
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
