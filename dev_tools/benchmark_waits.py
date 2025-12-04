"""Benchmark: Espera Condicional vs Fixa"""
import time
import asyncio
from playwright.async_api import async_playwright


async def benchmark():
    print("=== BENCHMARK: Espera Condicional vs Fixa ===")
    print("")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # CENARIO 1: Site simples (Bing)
        print("CENARIO 1: Bing (input existe rapido)")
        print("-" * 50)
        
        await page.goto("https://www.bing.com", wait_until="commit")
        
        # Metodo ANTIGO: wait_for_timeout fixo
        t1_start = time.perf_counter()
        await page.wait_for_timeout(3000)
        t1_end = time.perf_counter()
        tempo_fixo = (t1_end - t1_start) * 1000
        
        # Metodo NOVO: wait_for_selector condicional
        await page.goto("https://www.bing.com", wait_until="commit")
        t2_start = time.perf_counter()
        try:
            await page.wait_for_selector("#sb_form_q, textarea[name=q]", state="visible", timeout=10000)
        except Exception:
            pass
        t2_end = time.perf_counter()
        tempo_condicional = (t2_end - t2_start) * 1000
        
        ganho1 = tempo_fixo - tempo_condicional
        print(f"  Espera FIXA (3s):       {tempo_fixo:.0f}ms")
        print(f"  Espera CONDICIONAL:     {tempo_condicional:.0f}ms")
        print(f"  GANHO:                  {ganho1:.0f}ms ({ganho1/tempo_fixo*100:.0f}%)")
        print("")
        
        # CENARIO 2: Site DOU
        print("CENARIO 2: DOU (dropdown)")
        print("-" * 50)
        
        await page.goto("https://www.in.gov.br/leiturajornal?data=25-11-2025&secao=DO1", 
                        wait_until="commit", timeout=60000)
        
        t3_start = time.perf_counter()
        await page.wait_for_timeout(5000)
        t3_end = time.perf_counter()
        tempo_fixo2 = (t3_end - t3_start) * 1000
        
        await page.goto("https://www.in.gov.br/leiturajornal?data=25-11-2025&secao=DO1", 
                        wait_until="commit", timeout=60000)
        t4_start = time.perf_counter()
        try:
            await page.wait_for_function(
                "() => document.querySelector('#slcOrgs')?.options?.length > 2",
                timeout=15000
            )
        except Exception:
            pass
        t4_end = time.perf_counter()
        tempo_condicional2 = (t4_end - t4_start) * 1000
        
        ganho2 = tempo_fixo2 - tempo_condicional2
        print(f"  Espera FIXA (5s):       {tempo_fixo2:.0f}ms")
        print(f"  Espera CONDICIONAL:     {tempo_condicional2:.0f}ms")
        print(f"  GANHO:                  {ganho2:.0f}ms ({ganho2/tempo_fixo2*100:.0f}%)")
        print("")
        
        await browser.close()
        
        print("=" * 50)
        print("RESUMO")
        print("=" * 50)
        ganho_medio = (ganho1 + ganho2) / 2
        print(f"Ganho medio por operacao: {ganho_medio:.0f}ms")
        print(f"Em 10 fetches:  {ganho_medio * 10 / 1000:.1f}s economizados")
        print(f"Em 50 fetches:  {ganho_medio * 50 / 1000:.1f}s economizados")
        print(f"Em 100 fetches: {ganho_medio * 100 / 1000:.1f}s economizados")


if __name__ == "__main__":
    asyncio.run(benchmark())
