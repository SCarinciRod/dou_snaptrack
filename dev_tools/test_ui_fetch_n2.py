from __future__ import annotations

import json

# Testa a função _plan_live_fetch_n2 (modo direto, sem UI) para garantir contagem completa
from dou_snaptrack.ui.app import _plan_live_fetch_n2


def main():
    date = "10-11-2025"
    targets = [
        "Presidência da República",
        "Ministério da Ciência, Tecnologia e Inovação",
    ]
    for sec in ("DO1", "DO2", "DO3"):
        for n1 in targets:
            n2_list = _plan_live_fetch_n2(sec, date, n1, limit2=None)
            print(json.dumps({
                "secao": sec,
                "n1": n1,
                "n2_count": len(n2_list),
                "sample": n2_list[:10],
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
