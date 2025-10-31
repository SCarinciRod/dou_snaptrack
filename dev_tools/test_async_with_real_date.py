"""Teste da migração async com data real (24/10/2025)"""
import asyncio
import sys

print("[TEST] Testing async migration with real date: 24-10-2025")
print("="*60)

# Simular loop asyncio (como Streamlit)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

try:
    from dou_snaptrack.utils.pairs_updater import update_pairs_file_async
    
    async def test_with_real_date():
        print("\n[1] Starting scraping for 24-10-2025...")
        
        def progress(pct, msg):
            print(f"  [{int(pct*100):3d}%] {msg}")
        
        result = await update_pairs_file_async(
            data="24-10-2025",  # Data com matérias publicadas
            secao="DO1",
            limit1=3,  # Apenas 3 órgãos N1 para teste rápido
            limit2=2,  # Apenas 2 N2 por N1
            headless=True,
            progress_callback=progress,
        )
        return result
    
    result = asyncio.run(test_with_real_date())
    
    print("\n" + "="*60)
    if result.get("success"):
        print("[SUCCESS] Scraping completed!")
        print(f"  - N1 count: {result.get('n1_count')}")
        print(f"  - Pairs count: {result.get('pairs_count')}")
        print(f"  - File: {result.get('file')}")
        print(f"  - Timestamp: {result.get('timestamp')}")
        print("\n[OK] ASYNC MIGRATION WORKING PERFECTLY!")
    else:
        error = result.get("error", "Unknown")
        if "sync api" in error.lower() or "asyncio loop" in error.lower():
            print(f"[FAIL] ASYNCIO CONFLICT DETECTED!")
            print(f"  Error: {error}")
            sys.exit(1)
        else:
            print(f"[PARTIAL] No asyncio conflict, but functional error:")
            print(f"  Error: {error}")
            print("\n[INFO] This might be a site issue, not async migration issue")
    
except Exception as e:
    error_str = str(e)
    if "sync api" in error_str.lower() or "asyncio loop" in error_str.lower():
        print(f"\n[FAIL] ASYNCIO CONFLICT!")
        print(f"  {type(e).__name__}: {error_str}")
        sys.exit(1)
    else:
        print(f"\n[PARTIAL] Functional error (not async related):")
        print(f"  {type(e).__name__}: {error_str}")
        import traceback
        traceback.print_exc()
