#!/usr/bin/env python
"""
Benchmark de Performance - Batch Runner

Compara tempo de execução ANTES vs DEPOIS das otimizações:
- ANTES: PowerShell fallback para detecção de processo (3s)
- DEPOIS: Apenas tasklist CSV (rápido)

Uso:
    python scripts/benchmark_batch_runner.py
    python scripts/benchmark_batch_runner.py --iterations 10
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import time
from dataclasses import dataclass


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
    def avg_ms(self) -> float:
        return self.avg * 1000
    
    @property
    def min_ms(self) -> float:
        return min(self.times) * 1000 if self.times else 0
    
    @property
    def max_ms(self) -> float:
        return max(self.times) * 1000 if self.times else 0
    
    def report(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"📊 {self.name}\n"
            f"{'='*60}\n"
            f"  Iterações: {self.iterations}\n"
            f"  Média:     {self.avg_ms:.1f}ms\n"
            f"  Mínimo:    {self.min_ms:.1f}ms\n"
            f"  Máximo:    {self.max_ms:.1f}ms\n"
        )


def benchmark_old_powershell(pid: int, iterations: int = 5) -> BenchmarkResult:
    """
    Simula o estilo ANTIGO com PowerShell fallback.
    
    Era usado quando tasklist falhava - adiciona ~3 segundos.
    """
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        
        # Comando PowerShell antigo (lento)
        ps_cmd = f'Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path,CommandLine | ConvertTo-Json'
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Parse do JSON (se sucesso)
            if result.returncode == 0 and result.stdout.strip():
                import json
                try:
                    json.loads(result.stdout)
                except Exception:
                    pass
        except Exception:
            pass
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  [OLD/PS] Iteração {i+1}/{iterations}: {elapsed*1000:.1f}ms")
    
    return BenchmarkResult("ANTES (PowerShell fallback)", iterations, times)


def benchmark_new_tasklist(pid: int, iterations: int = 5) -> BenchmarkResult:
    """
    Estilo NOVO com apenas tasklist CSV.
    
    Muito mais rápido - apenas uma chamada de sistema.
    """
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        
        # Comando tasklist otimizado (rápido)
        try:
            result = subprocess.run(
                ["tasklist", "/V", "/FO", "CSV", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse CSV
                reader = csv.reader(io.StringIO(result.stdout))
                rows = list(reader)
                if len(rows) > 1:
                    header = rows[0]
                    row = rows[1]
                    # Extrair info
                    info = {
                        "pid": int(row[1]) if len(row) > 1 else 0,
                        "name": row[0] if row else "",
                        "exe": row[0] if row else "",
                    }
        except Exception:
            pass
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  [NEW/CSV] Iteração {i+1}/{iterations}: {elapsed*1000:.1f}ms")
    
    return BenchmarkResult("DEPOIS (tasklist CSV)", iterations, times)


def benchmark_combined_old(pid: int, iterations: int = 5) -> BenchmarkResult:
    """
    Simula fluxo ANTIGO completo: tasklist + PowerShell fallback.
    """
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        
        info = {}
        
        # Passo 1: tasklist (rápido)
        try:
            result = subprocess.run(
                ["tasklist", "/V", "/FO", "CSV", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                reader = csv.reader(io.StringIO(result.stdout))
                rows = list(reader)
                if len(rows) > 1:
                    row = rows[1]
                    info = {"pid": pid, "name": row[0] if row else ""}
        except Exception:
            pass
        
        # Passo 2: PowerShell fallback (LENTO - sempre executado no código antigo)
        ps_cmd = f'Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object Path | ConvertTo-Json'
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
        except Exception:
            pass
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  [OLD/COMBINED] Iteração {i+1}/{iterations}: {elapsed*1000:.1f}ms")
    
    return BenchmarkResult("ANTES (tasklist + PowerShell)", iterations, times)


def run_benchmark(iterations: int = 5):
    """Executa benchmark completo."""
    print("\n" + "="*60)
    print("🚀 BENCHMARK - BATCH RUNNER (Detecção de Processo)")
    print("="*60)
    print(f"Iterações: {iterations}")
    print("="*60)
    
    # Usar PID do processo atual para teste
    pid = os.getpid()
    print(f"PID de teste: {pid}")
    
    # BENCHMARK 1: PowerShell puro (simulando fallback antigo)
    print("\n" + "-"*60)
    print("📏 Testando PowerShell puro (fallback antigo)...")
    print("-"*60)
    result_ps = benchmark_old_powershell(pid, iterations)
    
    # BENCHMARK 2: Tasklist CSV (novo)
    print("\n" + "-"*60)
    print("📏 Testando tasklist CSV (otimizado)...")
    print("-"*60)
    result_csv = benchmark_new_tasklist(pid, iterations)
    
    # BENCHMARK 3: Fluxo combinado antigo
    print("\n" + "-"*60)
    print("📏 Testando fluxo combinado antigo (tasklist + PS fallback)...")
    print("-"*60)
    result_combined = benchmark_combined_old(pid, iterations)
    
    # Relatório final
    print("\n" + "="*60)
    print("📊 RESULTADOS DO BENCHMARK")
    print("="*60)
    
    print(result_ps.report())
    print(result_csv.report())
    print(result_combined.report())
    
    # Comparação
    print("\n" + "="*60)
    print("🎯 COMPARAÇÃO")
    print("="*60)
    
    if result_combined.avg > 0 and result_csv.avg > 0:
        improvement = ((result_combined.avg - result_csv.avg) / result_combined.avg) * 100
        time_saved_ms = (result_combined.avg - result_csv.avg) * 1000
        
        print(f"  PowerShell puro:      {result_ps.avg_ms:.1f}ms")
        print(f"  Tasklist CSV:         {result_csv.avg_ms:.1f}ms")
        print(f"  Combinado antigo:     {result_combined.avg_ms:.1f}ms")
        print(f"\n  Tempo economizado:    {time_saved_ms:.1f}ms por chamada")
        print(f"  Melhoria:             {improvement:.1f}%")
        
        # Projeção para batch típico
        calls_per_batch = 50  # Estimativa de chamadas por batch
        old_total = result_combined.avg * calls_per_batch
        new_total = result_csv.avg * calls_per_batch
        
        print(f"\n  📈 Projeção para {calls_per_batch} chamadas/batch:")
        print(f"     ANTES:  {old_total:.2f}s")
        print(f"     DEPOIS: {new_total:.2f}s")
        print(f"     GANHO:  {old_total - new_total:.2f}s")
    
    print("\n" + "="*60)
    print("✅ Benchmark concluído!")
    print("="*60 + "\n")
    
    return {
        "powershell": result_ps,
        "tasklist": result_csv,
        "combined_old": result_combined,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark batch runner")
    parser.add_argument("--iterations", type=int, default=5, help="Número de iterações")
    args = parser.parse_args()
    
    run_benchmark(iterations=args.iterations)


if __name__ == "__main__":
    main()
