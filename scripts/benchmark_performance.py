"""
Benchmark de performance para medir impacto das otimizações.

Mede:
- CPU usage
- Memory usage  
- Tempo de execução
- Throughput (documentos/segundo)

Para operações críticas:
1. Text cleaning (remove_dou_metadata, split_doc_header)
2. Summarization (summarize_text)
3. Regex pattern matching
4. Module import time
"""

from __future__ import annotations
import sys
import os
import time
import psutil
import gc
from pathlib import Path
from typing import Callable, Dict, Any, List
import tracemalloc
import json

# Garantir PYTHONPATH
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class PerformanceBenchmark:
    """Utilitário para benchmark de funções com métricas de CPU, memória e tempo."""
    
    def __init__(self, name: str = "Benchmark"):
        self.name = name
        self.process = psutil.Process(os.getpid())
        self.results: List[Dict[str, Any]] = []
    
    def measure(
        self, 
        func: Callable, 
        *args, 
        iterations: int = 100, 
        label: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mede performance de uma função.
        
        Args:
            func: Função a ser medida
            iterations: Número de iterações
            label: Descrição da operação
            *args, **kwargs: Argumentos para a função
            
        Returns:
            Dict com métricas: cpu_percent, memory_mb, time_ms, throughput
        """
        # Warm-up (1 iteração para compilação JIT, cache, etc)
        try:
            func(*args, **kwargs)
        except Exception:
            pass
        
        # Força garbage collection antes de medir
        gc.collect()
        
        # Captura estado inicial
        cpu_before = self.process.cpu_percent(interval=0.1)
        mem_before = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Inicia trace de memória
        tracemalloc.start()
        
        # Executa benchmark
        start_time = time.perf_counter()
        for _ in range(iterations):
            try:
                func(*args, **kwargs)
            except Exception:
                pass
        end_time = time.perf_counter()
        
        # Captura pico de memória
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mem_mb = peak_mem / 1024 / 1024
        
        # Captura estado final
        cpu_after = self.process.cpu_percent(interval=0.1)
        mem_after = self.process.memory_info().rss / 1024 / 1024
        
        # Calcula métricas
        elapsed_ms = (end_time - start_time) * 1000
        avg_time_ms = elapsed_ms / iterations
        throughput = iterations / (elapsed_ms / 1000) if elapsed_ms > 0 else 0
        cpu_delta = max(0, cpu_after - cpu_before)
        mem_delta = mem_after - mem_before
        
        result = {
            "label": label or func.__name__,
            "iterations": iterations,
            "total_time_ms": round(elapsed_ms, 2),
            "avg_time_ms": round(avg_time_ms, 4),
            "throughput_ops_sec": round(throughput, 2),
            "cpu_percent_delta": round(cpu_delta, 2),
            "memory_delta_mb": round(mem_delta, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
        }
        
        self.results.append(result)
        return result
    
    def print_results(self):
        """Imprime resultados formatados."""
        print(f"\n{'='*80}")
        print(f"  {self.name}")
        print(f"{'='*80}\n")
        
        for r in self.results:
            print(f"📊 {r['label']}")
            print(f"   Iterations:     {r['iterations']}")
            print(f"   Avg Time:       {r['avg_time_ms']:.4f} ms")
            print(f"   Throughput:     {r['throughput_ops_sec']:.2f} ops/sec")
            print(f"   CPU Δ:          {r['cpu_percent_delta']:.2f}%")
            print(f"   Memory Δ:       {r['memory_delta_mb']:.2f} MB")
            print(f"   Peak Memory:    {r['peak_memory_mb']:.2f} MB")
            print()
    
    def save_json(self, filepath: str):
        """Salva resultados em JSON."""
        output = {
            "benchmark_name": self.name,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": self.results,
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"✅ Resultados salvos em: {filepath}")


def benchmark_text_cleaning():
    """Benchmark de operações de limpeza de texto."""
    from dou_utils.text_cleaning import (
        remove_dou_metadata,
        split_doc_header,
    )
    
    # Texto de exemplo (simulando documento DOU)
    sample_text = """
    DIÁRIO OFICIAL DA UNIÃO
    Imprensa Nacional
    Publicado em 23/10/2025 | Edição 200 | Seção 1 | Página 45
    
    MINISTÉRIO DA ECONOMIA
    PORTARIA Nº 1.234, DE 22 DE OUTUBRO DE 2025
    
    O MINISTRO DE ESTADO DA ECONOMIA, no uso das atribuições que lhe confere o art. 87,
    parágrafo único, inciso II, da Constituição Federal, resolve:
    
    Art. 1º Fica aprovado o regulamento anexo, que dispõe sobre as normas de execução
    orçamentária e financeira para o exercício de 2026.
    
    Art. 2º Esta Portaria entra em vigor na data de sua publicação.
    
    FERNANDO HADDAD
    """ * 10  # Repetir para simular documento maior
    
    bench = PerformanceBenchmark("Text Cleaning Operations")
    
    # Benchmark: remove_dou_metadata
    bench.measure(
        remove_dou_metadata,
        sample_text,
        iterations=1000,
        label="remove_dou_metadata (1000x)",
    )
    
    # Benchmark: split_doc_header
    bench.measure(
        split_doc_header,
        sample_text,
        iterations=1000,
        label="split_doc_header (1000x)",
    )
    
    bench.print_results()
    return bench


def benchmark_summarization():
    """Benchmark de sumarização de texto."""
    from dou_utils.summary_utils import summarize_text
    
    # Texto de exemplo (ato normativo)
    sample_text = """
    O MINISTRO DE ESTADO DA ECONOMIA, no uso das atribuições que lhe confere o art. 87,
    parágrafo único, inciso II, da Constituição Federal, e tendo em vista o disposto na
    Lei nº 14.194, de 20 de agosto de 2021, resolve:
    
    Art. 1º Fica aprovado o Regulamento do Imposto sobre a Renda e Proventos de Qualquer
    Natureza - RIR, na forma do Anexo I a este Decreto.
    
    Art. 2º As pessoas jurídicas tributadas com base no lucro real deverão apurar o
    Imposto sobre a Renda Pessoa Jurídica - IRPJ e a Contribuição Social sobre o Lucro
    Líquido - CSLL de forma trimestral ou anual.
    
    Art. 3º O imposto devido, apurado na forma do art. 2º, será pago em quota única, até
    o último dia útil do mês subsequente ao do encerramento do período de apuração.
    
    Art. 4º Este Decreto entra em vigor na data de sua publicação.
    """ * 5
    
    bench = PerformanceBenchmark("Summarization Operations")
    
    # Benchmark: summarize_text (mode=center, 5 linhas)
    bench.measure(
        summarize_text,
        sample_text,
        max_lines=5,
        mode="center",
        keywords=None,
        iterations=500,
        label="summarize_text mode=center (500x)",
    )
    
    # Benchmark: summarize_text (mode=keywords-first, com keywords)
    bench.measure(
        summarize_text,
        sample_text,
        max_lines=5,
        mode="keywords-first",
        keywords=["imposto", "renda", "pessoa jurídica"],
        iterations=500,
        label="summarize_text mode=keywords-first (500x)",
    )
    
    bench.print_results()
    return bench


def benchmark_regex_patterns():
    """Benchmark de padrões regex pré-compilados vs inline."""
    import re
    
    bench = PerformanceBenchmark("Regex Pattern Performance")
    
    sample_text = """
    Art. 1º Este é um texto com <tags HTML> que devem ser removidas.
    Contém também    múltiplos    espaços    em   branco.
    E linhas\r\n\r\nquebradas\n\ncom diferentes separadores.
    Valores como R$ 1.500,00 e datas como 23/10/2025 são comuns.
    """ * 100
    
    # Padrão pré-compilado (otimizado)
    WHITESPACE_COMPILED = re.compile(r"\s+")
    
    def test_compiled_pattern():
        return WHITESPACE_COMPILED.sub(" ", sample_text)
    
    # Padrão inline (não otimizado)
    def test_inline_pattern():
        return re.sub(r"\s+", " ", sample_text)
    
    bench.measure(
        test_compiled_pattern,
        iterations=1000,
        label="Regex PRÉ-COMPILADO (otimizado)",
    )
    
    bench.measure(
        test_inline_pattern,
        iterations=1000,
        label="Regex INLINE (não otimizado)",
    )
    
    bench.print_results()
    return bench


def benchmark_module_imports():
    """Benchmark de tempo de importação de módulos."""
    import importlib
    import sys
    
    bench = PerformanceBenchmark("Module Import Time")
    
    modules_to_test = [
        "dou_utils.text_cleaning",
        "dou_utils.summary_utils",
        "dou_utils.bulletin_utils",
        "dou_snaptrack.cli.reporting",
    ]
    
    for module_name in modules_to_test:
        # Remove do cache se já importado
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        def import_module():
            importlib.import_module(module_name)
        
        # Mede tempo de importação (1 iteração apenas)
        result = bench.measure(
            import_module,
            iterations=1,
            label=f"import {module_name}",
        )
        
        # Re-importar para próximo teste
        importlib.import_module(module_name)
    
    bench.print_results()
    return bench


def main():
    """Executa todos os benchmarks."""
    print("\n🚀 Iniciando benchmarks de performance...")
    print(f"Python: {sys.version}")
    print(f"CPU Count: {psutil.cpu_count()}")
    print(f"Memory Total: {psutil.virtual_memory().total / 1024**3:.2f} GB\n")
    
    all_results = []
    
    # 1. Text Cleaning
    print("1️⃣  Testando Text Cleaning...")
    bench1 = benchmark_text_cleaning()
    all_results.extend(bench1.results)
    
    # 2. Summarization
    print("\n2️⃣  Testando Summarization...")
    bench2 = benchmark_summarization()
    all_results.extend(bench2.results)
    
    # 3. Regex Patterns
    print("\n3️⃣  Testando Regex Patterns...")
    bench3 = benchmark_regex_patterns()
    all_results.extend(bench3.results)
    
    # 4. Module Imports
    print("\n4️⃣  Testando Module Imports...")
    bench4 = benchmark_module_imports()
    all_results.extend(bench4.results)
    
    # Salvar resultados consolidados
    output_path = "logs/benchmark_results.json"
    combined = PerformanceBenchmark("Consolidated Results")
    combined.results = all_results
    combined.save_json(output_path)
    
    # Resumo final
    print("\n" + "="*80)
    print("  📈 RESUMO GERAL")
    print("="*80)
    print(f"\nTotal de testes:  {len(all_results)}")
    print(f"Relatório salvo:  {output_path}")
    print("\n✅ Benchmark concluído!\n")


if __name__ == "__main__":
    main()
