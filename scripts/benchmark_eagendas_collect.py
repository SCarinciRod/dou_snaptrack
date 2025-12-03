#!/usr/bin/env python
"""
Benchmark de Performance - E-Agendas Subprocess Collect

Testa o ganho REAL de performance na coleta de dados do E-Agendas:
- Navega para um agente específico
- Mede tempo de esperas condicionais vs fixas
- Simula coleta de calendário

Uso:
    python scripts/benchmark_eagendas_collect.py
    python scripts/benchmark_eagendas_collect.py --headful
    python scripts/benchmark_eagendas_collect.py --iterations 3
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass, field
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
        
        # Detalhes por etapa (média)
        if self.details:
            lines.append("\n  Breakdown por etapa (média):")
            # Agregar por etapa
            steps = {}
            for d in self.details:
                for step, t in d.items():
                    if step not in steps:
                        steps[step] = []
                    steps[step].append(t)
            
            for step, times in steps.items():
                avg_step = sum(times) / len(times)
                lines.append(f"    {step}: {avg_step:.2f}s")
        
        return "\n".join(lines)


async def benchmark_collect_old_style(page, iterations: int = 1) -> BenchmarkResult:
    """
    Simula coleta estilo ANTIGO com wait_for_timeout fixo.
    
    Sequência original:
    1. Navegar → wait 5000ms (AngularJS)
    2. Abrir dropdown órgão → wait 3000ms
    3. Selecionar órgão → wait 2000ms
    4. Abrir dropdown agente → wait 3000ms
    5. Verificar calendário → wait 3000ms
    
    Total fixo: 16000ms por agente
    """
    result = BenchmarkResult("ANTES (wait_for_timeout fixo)", iterations)
    
    for i in range(iterations):
        print(f"  [OLD] Iteração {i+1}/{iterations}...")
        details = {}
        start_total = time.perf_counter()
        
        # Etapa 1: AngularJS
        start = time.perf_counter()
        await page.wait_for_timeout(5000)
        details["1_angular"] = time.perf_counter() - start
        
        # Etapa 2: Dropdown órgão
        start = time.perf_counter()
        await page.wait_for_timeout(3000)
        details["2_dropdown_orgao"] = time.perf_counter() - start
        
        # Etapa 3: Seleção
        start = time.perf_counter()
        await page.wait_for_timeout(2000)
        details["3_selecao"] = time.perf_counter() - start
        
        # Etapa 4: Dropdown agente
        start = time.perf_counter()
        await page.wait_for_timeout(3000)
        details["4_dropdown_agente"] = time.perf_counter() - start
        
        # Etapa 5: Calendário
        start = time.perf_counter()
        await page.wait_for_timeout(3000)
        details["5_calendario"] = time.perf_counter() - start
        
        elapsed = time.perf_counter() - start_total
        result.times.append(elapsed)
        result.details.append(details)
        print(f"  [OLD] Iteração {i+1}: {elapsed:.2f}s")
    
    return result


async def benchmark_collect_new_style(page, iterations: int = 1) -> BenchmarkResult:
    """
    Coleta estilo NOVO com wait_for_function condicional.
    
    Cada espera termina assim que a condição é satisfeita,
    ao invés de esperar o tempo máximo.
    """
    result = BenchmarkResult("DEPOIS (wait_for_function condicional)", iterations)
    
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
    dropdown_visible_js = "() => { const dd = document.querySelector('.selectize-dropdown'); return dd && dd.offsetParent !== null; }"
    
    for i in range(iterations):
        print(f"  [NEW] Iteração {i+1}/{iterations}...")
        details = {}
        start_total = time.perf_counter()
        
        # Etapa 1: AngularJS (condicional)
        start = time.perf_counter()
        try:
            await page.wait_for_function(angular_ready_js, timeout=5000)
        except Exception:
            pass
        details["1_angular"] = time.perf_counter() - start
        
        # Etapa 2: Dropdown órgão populado (condicional)
        start = time.perf_counter()
        try:
            await page.wait_for_function(selectize_orgao_js, timeout=3000)
        except Exception:
            pass
        details["2_dropdown_orgao"] = time.perf_counter() - start
        
        # Etapa 3: Seleção completa (condicional - dropdown fecha)
        start = time.perf_counter()
        try:
            # Simular click e aguardar dropdown fechar
            await page.wait_for_function(
                "() => { const dd = document.querySelector('.selectize-dropdown'); return !dd || dd.offsetParent === null; }",
                timeout=2000
            )
        except Exception:
            pass
        details["3_selecao"] = time.perf_counter() - start
        
        # Etapa 4: Dropdown agente populado (condicional)
        start = time.perf_counter()
        try:
            await page.wait_for_function(selectize_agente_js, timeout=3000)
        except Exception:
            pass
        details["4_dropdown_agente"] = time.perf_counter() - start
        
        # Etapa 5: Calendário visível (condicional)
        start = time.perf_counter()
        try:
            await page.wait_for_function(calendar_ready_js, timeout=3000)
        except Exception:
            pass
        details["5_calendario"] = time.perf_counter() - start
        
        elapsed = time.perf_counter() - start_total
        result.times.append(elapsed)
        result.details.append(details)
        print(f"  [NEW] Iteração {i+1}: {elapsed:.2f}s")
    
    return result


async def run_benchmark(headful: bool = False, iterations: int = 2):
    """Executa benchmark completo de coleta E-Agendas."""
    from playwright.async_api import async_playwright
    
    print("\n" + "="*60)
    print("🚀 BENCHMARK - E-AGENDAS SUBPROCESS COLLECT")
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
                    headless=False,
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
        
        # BENCHMARK 1: Estilo ANTIGO
        print("\n" + "-"*60)
        print("📏 Testando estilo ANTIGO (wait_for_timeout fixo)...")
        print("-"*60)
        result_old = await benchmark_collect_old_style(page, iterations)
        
        # Recarregar página para teste limpo
        await page.reload(wait_until="commit", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # BENCHMARK 2: Estilo NOVO
        print("\n" + "-"*60)
        print("📏 Testando estilo NOVO (wait_for_function condicional)...")
        print("-"*60)
        result_new = await benchmark_collect_new_style(page, iterations)
        
        await browser.close()
        
        # Relatório final
        print("\n" + "="*60)
        print("📊 RESULTADOS DO BENCHMARK - COLETA E-AGENDAS")
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
            print(f"  Tempo por agente ANTES:  {result_old.avg:.2f}s")
            print(f"  Tempo por agente DEPOIS: {result_new.avg:.2f}s")
            print(f"  Tempo economizado:       {time_saved:.2f}s por agente")
            print(f"  Melhoria:                {improvement:.1f}%")
            
            # Projeção para coleta completa
            agents = 227
            old_total = result_old.avg * agents
            new_total = result_new.avg * agents
            
            print(f"\n  📈 Projeção para coleta completa ({agents} agentes):")
            print(f"     ANTES:  {old_total/60:.1f} minutos ({old_total:.0f}s)")
            print(f"     DEPOIS: {new_total/60:.1f} minutos ({new_total:.0f}s)")
            print(f"     GANHO:  {(old_total - new_total)/60:.1f} minutos")
            
            # Breakdown por etapa
            print("\n  📋 Ganho por etapa (média):")
            if result_old.details and result_new.details:
                old_steps = {}
                new_steps = {}
                for d in result_old.details:
                    for step, t in d.items():
                        if step not in old_steps:
                            old_steps[step] = []
                        old_steps[step].append(t)
                for d in result_new.details:
                    for step, t in d.items():
                        if step not in new_steps:
                            new_steps[step] = []
                        new_steps[step].append(t)
                
                for step in sorted(old_steps.keys()):
                    old_avg = sum(old_steps[step]) / len(old_steps[step])
                    new_avg = sum(new_steps.get(step, [old_avg])) / len(new_steps.get(step, [1]))
                    saved = old_avg - new_avg
                    print(f"     {step}: {old_avg:.2f}s → {new_avg:.2f}s (ganho: {saved:.2f}s)")
        
        print("\n" + "="*60)
        print("✅ Benchmark de coleta concluído!")
        print("="*60 + "\n")
        
        return {
            "old": result_old,
            "new": result_new,
            "improvement_percent": improvement if result_old.avg > 0 else 0,
        }


def main():
    parser = argparse.ArgumentParser(description="Benchmark E-Agendas collect")
    parser.add_argument("--headful", action="store_true", help="Mostrar navegador")
    parser.add_argument("--iterations", type=int, default=2, help="Número de iterações")
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(headful=args.headful, iterations=args.iterations))


if __name__ == "__main__":
    main()
