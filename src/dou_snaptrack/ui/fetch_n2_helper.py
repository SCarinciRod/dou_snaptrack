import sys
import json
import asyncio
from types import SimpleNamespace
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

async def main():
    from playwright.async_api import async_playwright
    from dou_snaptrack.cli.plan_live_async import build_plan_live_async
    
    if len(sys.argv) != 5:
        print(json.dumps([]))
        sys.exit(0)
    
    secao, date, n1, limit2 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    limit2 = int(limit2) if limit2 != "None" else None
    
    args = SimpleNamespace(
        secao=secao, data=date, plan_out=None,
        select1=None, select2=None,
        pick1=n1, pick2=None,
        limit1=None, limit2=limit2,
        headless=True, slowmo=0, plan_verbose=False,
        key1_type_default="text", key2_type_default="text"
    )
    
    async with async_playwright() as p:
        try:
            cfg = await build_plan_live_async(p, args)
            combos = cfg.get("combos", [])
            n2_set = {c.get("key2") for c in combos if c.get("key2") and c.get("key2") != "Todos"}
            print(json.dumps(sorted(n2_set), ensure_ascii=False))
        except Exception as e:
            print(json.dumps([]))
            print(f"ERRO: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
