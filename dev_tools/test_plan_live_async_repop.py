"""Pequeno teste para validar repopulação do N2 no plan_live_async.

Executa build_plan_live_sync_wrapper selecionando N1='Presidência da República'
para as seções DO1/DO2/DO3 e imprime a quantidade de combos (equivale a N2
coletados quando existe N2; caso não haja N2, gera 1 combo com 'Todos').
"""

from __future__ import annotations

import argparse

from dou_snaptrack.cli.plan_live_async import build_plan_live_sync_wrapper


class Args:
    def __init__(self, data: str, secao: str):
        self.plan_verbose = True
        self.headful = False
        self.slowmo = 0
        self.secao = secao
        self.data = data
        # filtros: pick1 apenas Presidência
        self.select1 = None
        self.pick1 = "Presidência da República"
        self.limit1 = None  # 1 N1
        # sem limitar N2 para pegar tudo
        self.select2 = None
        self.pick2 = None
        self.limit2 = None
        # defaults/keys
        self.key1_type_default = "text"
        self.key2_type_default = "text"
        self.defaults = {}
        self.plan_out = None


def run_one(secao: str, data: str) -> int:
    cfg = build_plan_live_sync_wrapper(None, Args(data, secao))
    combos = cfg.get("combos") or []
    print(f"[TEST] {secao} combos (N2) para N1='Presidência da República': {len(combos)}")
    return len(combos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="10-11-2025")
    args = ap.parse_args()

    total = 0
    for sec in ("DO1", "DO2", "DO3"):
        total += run_one(sec, args.date)
    print(f"[TEST] Total combos nas três seções: {total}")


if __name__ == "__main__":
    main()
