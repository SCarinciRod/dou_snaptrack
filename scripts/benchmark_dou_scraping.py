#!/usr/bin/env python
"""
Benchmark de Performance - DOU Scraping

Mede o tempo de coleta do DOU (Diário Oficial da União).

Uso:
    python scripts/benchmark_dou_scraping.py
    python scripts/benchmark_dou_scraping.py --date 03-12-2025
    python scripts/benchmark_dou_scraping.py --iterations 2
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    """Resultado de um benchmark."""
    name: str
    iterations: int
    times: list[float] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)
    
    @property
    def avg(self) -> float:
        return sum(self.times) / len(self.times) if self.times else 0
    
    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0
    
    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0
    
    def report(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"📊 {self.name}",
            f"{'='*60}",
            f"  Iterações: {self.iterations}",
            f"  Média:     {self.avg:.2f}s",
            f"  Mínimo:    {self.min:.2f}s",
            f"  Máximo:    {self.max:.2f}s",
        ]
        return "\n".join(lines)


async def benchmark_dou_single_section(target_date: str, secao: str = "do1", iterations: int = 1) -> BenchmarkResult:
    """
    Benchmark de coleta de uma seção do DOU.
    """
    from playwright.async_api import async_playwright
    
    result = BenchmarkResult(f"DOU {secao.upper()} - {target_date}", iterations)
    
    # Launch args
    args = ['--disable-blink-features=AutomationControlled', '--ignore-certificate-errors', '--start-minimized']
    
    for i in range(iterations):
        print(f"  [{secao.upper()}] Iteração {i+1}/{iterations}...")
        details = {}
        start_total = time.perf_counter()
        
        async with async_playwright() as p:
            # Launch browser
            start = time.perf_counter()
            browser = None
            for channel in ["chrome", "msedge"]:
                try:
                    browser = await p.chromium.launch(channel=channel, headless=False, args=args)
                    break
                except Exception:
                    continue
            
            if not browser:
                print(f"  ❌ Nenhum browser disponível")
                continue
            
            details["1_browser_launch"] = time.perf_counter() - start
            
            # Context and page
            start = time.perf_counter()
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            details["2_context"] = time.perf_counter() - start
            
            # Build URL
            # Formato: https://www.in.gov.br/leiturajornal?data=03-12-2025&secao=do1
            url = f"https://www.in.gov.br/leiturajornal?data={target_date}&secao={secao}"
            
            # Navigate
            start = time.perf_counter()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"  ⚠️ Navegação: {e}")
            details["3_navigation"] = time.perf_counter() - start
            
            # Wait for content
            start = time.perf_counter()
            try:
                # Aguardar lista de publicações
                await page.wait_for_selector(".resultados-wrapper, .resultado, .publicacao", timeout=15000)
            except Exception:
                pass
            details["4_content_load"] = time.perf_counter() - start
            
            # Count items
            start = time.perf_counter()
            items = await page.query_selector_all(".resultado, .publicacao, .item-resultado")
            item_count = len(items)
            details["5_query_items"] = time.perf_counter() - start
            details["item_count"] = item_count
            
            await browser.close()
        
        elapsed = time.perf_counter() - start_total
        result.times.append(elapsed)
        result.details.append(details)
        
        print(f"  [{secao.upper()}] Iteração {i+1}: {elapsed:.2f}s ({item_count} itens)")
        print(f"    Browser: {details.get('1_browser_launch', 0):.2f}s")
        print(f"    Context: {details.get('2_context', 0):.2f}s")
        print(f"    Navigate: {details.get('3_navigation', 0):.2f}s")
        print(f"    Content: {details.get('4_content_load', 0):.2f}s")
    
    return result


async def run_benchmark(target_date: str | None = None, iterations: int = 1):
    """Executa benchmark completo do DOU."""
    if not target_date:
        target_date = date.today().strftime("%d-%m-%Y")
    
    print("\n" + "="*60)
    print("🚀 BENCHMARK - DOU SCRAPING")
    print("="*60)
    print(f"Data: {target_date}")
    print(f"Iterações: {iterations}")
    print("="*60)
    
    results = {}
    
    # Testar DO1
    print("\n" + "-"*60)
    print("📏 Testando DO1 (Seção 1)...")
    print("-"*60)
    results["do1"] = await benchmark_dou_single_section(target_date, "do1", iterations)
    
    # Testar DO2
    print("\n" + "-"*60)
    print("📏 Testando DO2 (Seção 2)...")
    print("-"*60)
    results["do2"] = await benchmark_dou_single_section(target_date, "do2", iterations)
    
    # Relatório final
    print("\n" + "="*60)
    print("📊 RESULTADOS DO BENCHMARK - DOU")
    print("="*60)
    
    for secao, result in results.items():
        print(result.report())
    
    # Total
    total_avg = sum(r.avg for r in results.values())
    print(f"\n  📈 Tempo total médio (DO1 + DO2): {total_avg:.2f}s")
    
    # Breakdown médio
    print("\n  📋 Breakdown médio por etapa:")
    all_details = []
    for r in results.values():
        all_details.extend(r.details)
    
    if all_details:
        steps = {}
        for d in all_details:
            for step, t in d.items():
                if step != "item_count" and isinstance(t, (int, float)):
                    if step not in steps:
                        steps[step] = []
                    steps[step].append(t)
        
        for step in sorted(steps.keys()):
            avg_step = sum(steps[step]) / len(steps[step])
            print(f"     {step}: {avg_step:.2f}s")
    
    print("\n" + "="*60)
    print("✅ Benchmark DOU concluído!")
    print("="*60 + "\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Benchmark DOU scraping")
    parser.add_argument("--date", help="Data no formato DD-MM-YYYY")
    parser.add_argument("--iterations", type=int, default=1, help="Número de iterações")
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(target_date=args.date, iterations=args.iterations))


if __name__ == "__main__":
    main()
