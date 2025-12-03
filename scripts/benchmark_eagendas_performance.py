#!/usr/bin/env python
"""
Benchmark de Performance E-Agendas

Compara tempo de execução ANTES vs DEPOIS das otimizações:
- ANTES: wait_for_timeout fixo (simulado)
- DEPOIS: wait_for_function condicional (real)

Uso:
    python scripts/benchmark_eagendas_performance.py
    python scripts/benchmark_eagendas_performance.py --iterations 3
    python scripts/benchmark_eagendas_performance.py --headful
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BenchmarkResult:
    """Resultado de um benchmark."""
    name: str
    iterations: int
    times: list[float]
    
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
        return (
            f"\n{'='*60}\n"
            f"📊 {self.name}\n"
            f"{'='*60}\n"
            f"  Iterações: {self.iterations}\n"
            f"  Média:     {self.avg:.2f}s\n"
            f"  Mínimo:    {self.min:.2f}s\n"
            f"  Máximo:    {self.max:.2f}s\n"
        )


async def benchmark_old_style(page, iterations: int = 1) -> BenchmarkResult:
    """
    Simula o estilo ANTIGO com wait_for_timeout fixo.
    
    Tempos originais:
    - 5000ms após navegação (AngularJS)
    - 3000ms após dropdown órgão
    - 2000ms após seleção
    - 3000ms após calendário
    Total: 13000ms fixos
    """
    times = []
    
    for i in range(iterations):
        print(f"  [OLD] Iteração {i+1}/{iterations}...")
        start = time.perf_counter()
        
        # Simular esperas fixas do código antigo
        await page.wait_for_timeout(5000)  # AngularJS
        await page.wait_for_timeout(3000)  # Dropdown órgão
        await page.wait_for_timeout(2000)  # Após seleção
        await page.wait_for_timeout(3000)  # Calendário
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  [OLD] Iteração {i+1}: {elapsed:.2f}s")
    
    return BenchmarkResult("ANTES (wait_for_timeout fixo)", iterations, times)


async def benchmark_new_style(page, iterations: int = 1) -> BenchmarkResult:
    """
    Estilo NOVO com wait_for_function condicional.
    
    Condições JavaScript que terminam assim que prontas:
    - AngularJS ready
    - Selectize populado
    - Calendário visível
    """
    times = []
    
    # JavaScript conditions (mesmo do código otimizado)
    angular_ready_js = "() => !!document.querySelector('[ng-app]')"
    selectize_orgao_js = """() => { 
        const el = document.getElementById('filtro_orgao_entidade'); 
        return el?.selectize && Object.keys(el.selectize.options||{}).length > 5; 
    }"""
    selectize_agente_js = """() => { 
        const el = document.getElementById('filtro_servidor'); 
        return el?.selectize && Object.keys(el.selectize.options||{}).length > 0; 
    }"""
    calendar_ready_js = "() => !!document.querySelector('#divcalendar, .fc-view-container, .fc-view')"
    
    for i in range(iterations):
        print(f"  [NEW] Iteração {i+1}/{iterations}...")
        start = time.perf_counter()
        
        # Esperas condicionais - terminam assim que condição é true
        try:
            await page.wait_for_function(angular_ready_js, timeout=5000)
        except Exception:
            pass  # Timeout = fallback
        
        try:
            await page.wait_for_function(selectize_orgao_js, timeout=3000)
        except Exception:
            pass
        
        try:
            await page.wait_for_function(selectize_agente_js, timeout=2000)
        except Exception:
            pass
        
        try:
            await page.wait_for_function(calendar_ready_js, timeout=3000)
        except Exception:
            pass
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  [NEW] Iteração {i+1}: {elapsed:.2f}s")
    
    return BenchmarkResult("DEPOIS (wait_for_function condicional)", iterations, times)


async def run_benchmark(headful: bool = False, iterations: int = 2):
    """Executa benchmark completo."""
    from playwright.async_api import async_playwright
    
    print("\n" + "="*60)
    print("🚀 BENCHMARK DE PERFORMANCE E-AGENDAS")
    print("="*60)
    print(f"Modo: {'Headful (visível)' if headful else 'Minimizado'}")
    print(f"Iterações: {iterations}")
    print("="*60)
    
    # Launch args
    args = ['--disable-blink-features=AutomationControlled', '--ignore-certificate-errors']
    if not headful:
        args.append('--start-minimized')
    
    async with async_playwright() as p:
        # Tentar Chrome, depois Edge
        browser = None
        for channel in ["chrome", "msedge"]:
            try:
                browser = await p.chromium.launch(
                    channel=channel,
                    headless=False,  # E-Agendas bloqueia headless
                    args=args
                )
                print(f"✓ Browser: {channel}")
                break
            except Exception:
                continue
        
        if not browser:
            print("❌ Nenhum browser disponível (Chrome/Edge)")
            return None
        
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        
        # Navegar para E-Agendas
        print("\n📡 Navegando para E-Agendas...")
        url = "https://eagendas.cgu.gov.br/"
        
        try:
            await page.goto(url, wait_until="commit", timeout=30000)
            print(f"✓ Página carregada: {url}")
        except Exception as e:
            print(f"❌ Erro ao carregar página: {e}")
            await browser.close()
            return None
        
        # Aguardar página estabilizar
        await page.wait_for_timeout(2000)
        
        # BENCHMARK 1: Estilo ANTIGO (simulado)
        print("\n" + "-"*60)
        print("📏 Testando estilo ANTIGO (wait_for_timeout fixo)...")
        print("-"*60)
        result_old = await benchmark_old_style(page, iterations)
        
        # Recarregar página para teste limpo
        await page.reload(wait_until="commit", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # BENCHMARK 2: Estilo NOVO (otimizado)
        print("\n" + "-"*60)
        print("📏 Testando estilo NOVO (wait_for_function condicional)...")
        print("-"*60)
        result_new = await benchmark_new_style(page, iterations)
        
        await browser.close()
        
        # Relatório final
        print("\n" + "="*60)
        print("📊 RESULTADOS DO BENCHMARK")
        print("="*60)
        
        print(result_old.report())
        print(result_new.report())
        
        # Comparação
        if result_old.avg > 0 and result_new.avg > 0:
            improvement = ((result_old.avg - result_new.avg) / result_old.avg) * 100
            time_saved = result_old.avg - result_new.avg
            
            print("\n" + "="*60)
            print("🎯 COMPARAÇÃO")
            print("="*60)
            print(f"  Tempo economizado: {time_saved:.2f}s por operação")
            print(f"  Melhoria:          {improvement:.1f}%")
            
            # Projeção para 227 agentes
            agents = 227
            old_total = result_old.avg * agents
            new_total = result_new.avg * agents
            
            print(f"\n  📈 Projeção para {agents} agentes:")
            print(f"     ANTES:  {old_total/60:.1f} minutos")
            print(f"     DEPOIS: {new_total/60:.1f} minutos")
            print(f"     GANHO:  {(old_total - new_total)/60:.1f} minutos")
        
        print("\n" + "="*60)
        print("✅ Benchmark concluído!")
        print("="*60 + "\n")
        
        return {
            "old": result_old,
            "new": result_new,
            "improvement_percent": improvement if result_old.avg > 0 else 0,
        }


def main():
    parser = argparse.ArgumentParser(description="Benchmark de performance E-Agendas")
    parser.add_argument("--headful", action="store_true", help="Mostrar navegador")
    parser.add_argument("--iterations", type=int, default=2, help="Número de iterações")
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(headful=args.headful, iterations=args.iterations))


if __name__ == "__main__":
    main()
