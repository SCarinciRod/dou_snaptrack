"""Teste detalhado da migração async com debug"""
import asyncio
import sys
from types import SimpleNamespace

print("[1] Testing async scraping with detailed debug...")

async def test_scraping():
    from playwright.async_api import async_playwright
    from dou_snaptrack.cli.plan_live_async import build_plan_live_async
    
    async with async_playwright() as p:
        args = SimpleNamespace(
            secao="DO1",
            data="27-10-2025",  # Hoje
            plan_out=None,
            select1=None,
            select2=None,
            limit1=2,  # Apenas 2 N1
            limit2=2,  # Apenas 2 N2
            headless=True,
            slowmo=0,
            plan_verbose=True,  # Ativar modo verbose
        )
        
        print(f"[DEBUG] Scraping {args.secao} for {args.data}...")
        print(f"[DEBUG] limit1={args.limit1}, limit2={args.limit2}")
        
        try:
            cfg = await build_plan_live_async(p, args)
            
            combos = cfg.get("combos", [])
            print(f"\n[RESULT] Found {len(combos)} combos")
            
            if combos:
                print("\n[SUCCESS] Sample combos:")
                for i, combo in enumerate(combos[:5]):
                    print(f"  {i+1}. {combo.get('key1')} -> {combo.get('key2')}")
            else:
                print("\n[WARN] No combos found!")
                print("[DEBUG] Config keys:", list(cfg.keys()))
                print("[DEBUG] Config:", cfg)
            
            return cfg
            
        except Exception as e:
            print(f"\n[ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

try:
    result = asyncio.run(test_scraping())
    
    if result and result.get("combos"):
        print("\n[OK] Async scraping works!")
        sys.exit(0)
    else:
        print("\n[FAIL] No combos scraped - need to debug further")
        sys.exit(1)
        
except Exception as e:
    error_msg = str(e)
    if "sync api" in error_msg.lower() or "asyncio loop" in error_msg.lower():
        print(f"[FAIL] ASYNCIO CONFLICT: {error_msg}")
        sys.exit(1)
    else:
        print(f"[ERROR] {type(e).__name__}: {error_msg}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
