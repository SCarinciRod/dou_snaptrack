from __future__ import annotations
import json
from types import SimpleNamespace
from pathlib import Path

from dou_snaptrack.cli.plan_live import build_plan_live


def run_smoke(data: str = "12-09-2025", secao: str = "DO1"):
    args = SimpleNamespace(
        data=data,
        secao=secao,
        plan_verbose=True,
        headful=False,
        slowmo=0,
        select1=None,
        pick1=None,
        limit1=3,  # small
        select2=None,
        pick2=None,
        limit2=3,  # small per N1
        key1_type_default="text",
        key2_type_default="text",
        max_combos=6,
        query=None,
        state_file=None,
        bulletin=None,
        bulletin_out=None,
    )
    cfg = build_plan_live(None, args)
    outp = Path("resultados/_plan_live_smoke.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[SMOKE] combos={len(cfg.get('combos', []))} saved to {outp}")


if __name__ == "__main__":
    run_smoke()
