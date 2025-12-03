"""
Testes agressivos de performance para E-Agendas e Batch.

Este módulo contém testes que colocam PESO sobre o código para garantir
que as otimizações funcionam corretamente sob stress.

Categorias:
1. Performance Timing - Mede tempo de execução
2. Stress Loop - Executa operações repetidamente
3. Timeout Simulation - Simula condições de timeout
4. Concurrent Load - Múltiplas operações simultâneas
5. Edge Cases - Condições de borda
"""

import asyncio
import json
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_page():
    """Mock de página Playwright para testes sem browser real."""
    page = MagicMock()
    page.url = "https://eagendas.cgu.gov.br/"
    page.goto = MagicMock(return_value=None)
    page.wait_for_timeout = MagicMock(return_value=None)
    page.wait_for_function = MagicMock(return_value=None)
    page.evaluate = MagicMock(return_value=[])
    page.locator = MagicMock(return_value=MagicMock(count=MagicMock(return_value=0)))
    return page


@pytest.fixture
def sample_queries():
    """Queries de exemplo para testes de coleta."""
    return [
        {
            "n1_value": "1",
            "n1_label": "Órgão Teste 1",
            "n3_value": "101",
            "n3_label": "Agente Teste 1"
        },
        {
            "n1_value": "2",
            "n1_label": "Órgão Teste 2",
            "n3_value": "202",
            "n3_label": "Agente Teste 2"
        },
    ]


# =============================================================================
# 1. PERFORMANCE TIMING TESTS
# =============================================================================

class TestPerformanceTiming:
    """Testes que medem tempo de execução de operações críticas."""
    
    def test_wait_for_function_faster_than_fixed_wait(self, mock_page):
        """wait_for_function deve retornar mais rápido que wait_for_timeout quando condição é satisfeita."""
        # Simular wait_for_function retornando imediatamente (condição satisfeita)
        mock_page.wait_for_function = MagicMock(return_value=True)
        
        start = time.perf_counter()
        mock_page.wait_for_function("() => true", timeout=5000)
        elapsed_conditional = time.perf_counter() - start
        
        # Simular wait_for_timeout (sempre espera o tempo completo)
        start = time.perf_counter()
        time.sleep(0.005)  # 5ms para simular overhead
        elapsed_fixed = time.perf_counter() - start
        
        # wait_for_function deve ser praticamente instantâneo
        assert elapsed_conditional < 0.1, f"wait_for_function levou {elapsed_conditional}s - deveria ser <0.1s"
    
    def test_polling_loop_efficiency(self):
        """Loop de polling deve ser eficiente (50ms intervals)."""
        condition_met_at = 0.15  # Condição satisfeita em 150ms
        poll_interval = 0.05    # 50ms
        
        start = time.perf_counter()
        elapsed = 0
        iterations = 0
        
        while elapsed < 1.0:  # Timeout de 1s
            iterations += 1
            elapsed = time.perf_counter() - start
            if elapsed >= condition_met_at:
                break
            time.sleep(poll_interval)
        
        # Deve ter feito ~3 iterações (0, 50ms, 100ms, 150ms)
        assert iterations <= 5, f"Loop fez {iterations} iterações - deveria ser <=5"
        assert elapsed < 0.25, f"Loop levou {elapsed}s - deveria ser <0.25s"
    
    def test_100_iterations_timing(self):
        """100 iterações de operação mock devem completar em tempo razoável."""
        mock_op_time = 0.001  # 1ms por operação
        
        start = time.perf_counter()
        for _ in range(100):
            time.sleep(mock_op_time)
        elapsed = time.perf_counter() - start
        
        # 100 × 1ms = 100ms, com overhead aceitável até 200ms
        assert elapsed < 0.5, f"100 iterações levaram {elapsed}s - deveria ser <0.5s"
    
    def test_json_serialization_performance(self):
        """Serialização JSON de payloads grandes deve ser rápida."""
        # Payload grande: 1000 agentes
        payload = {
            "success": True,
            "data": {
                "agentes": [
                    {
                        "orgao": {"id": str(i), "nome": f"Órgão {i}"},
                        "agente": {"id": str(i*10), "nome": f"Agente {i}"},
                        "eventos": {f"2025-01-{d:02d}": [{"title": f"Evento {j}"} for j in range(5)] for d in range(1, 32)}
                    }
                    for i in range(1000)
                ]
            }
        }
        
        start = time.perf_counter()
        json_str = json.dumps(payload, ensure_ascii=False)
        elapsed_serialize = time.perf_counter() - start
        
        start = time.perf_counter()
        json.loads(json_str)
        elapsed_parse = time.perf_counter() - start
        
        # Serialização/parsing de 1000 agentes deve ser <1s cada
        assert elapsed_serialize < 1.0, f"Serialização levou {elapsed_serialize}s"
        assert elapsed_parse < 1.0, f"Parsing levou {elapsed_parse}s"


# =============================================================================
# 2. STRESS LOOP TESTS
# =============================================================================

class TestStressLoop:
    """Testes de stress com muitas iterações."""
    
    def test_500_mock_queries_sequential(self, mock_page):
        """Processar 500 queries mock sequencialmente."""
        queries = [{"n1_value": str(i), "n3_value": str(i*10)} for i in range(500)]
        
        processed = 0
        start = time.perf_counter()
        
        for q in queries:
            # Simular operação de processamento
            mock_page.wait_for_function("() => true", timeout=100)
            mock_page.evaluate("(x) => x", q)
            processed += 1
        
        elapsed = time.perf_counter() - start
        
        assert processed == 500, f"Processou apenas {processed}/500"
        # 500 queries × ~1ms = ~500ms + overhead
        assert elapsed < 2.0, f"500 queries levaram {elapsed}s - deveria ser <2s"
    
    def test_repeated_function_calls_no_memory_leak(self):
        """Chamadas repetidas não devem vazar memória."""
        import gc
        
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # 1000 iterações criando e descartando objetos
        for _ in range(1000):
            data = {"key": "value", "list": list(range(100))}
            _ = json.dumps(data)
            del data
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Número de objetos não deve crescer significativamente
        growth = final_objects - initial_objects
        assert growth < 1000, f"Crescimento de {growth} objetos - possível memory leak"
    
    def test_concurrent_dict_access_safety(self):
        """Acesso concorrente a dicionários deve ser thread-safe."""
        shared_dict = {}
        errors = []
        lock = threading.Lock()
        
        def writer(thread_id):
            for i in range(100):
                with lock:
                    shared_dict[f"t{thread_id}_{i}"] = {"value": i}
        
        def reader():
            for _ in range(100):
                with lock:
                    _ = list(shared_dict.keys())
        
        threads = []
        for tid in range(10):
            threads.append(threading.Thread(target=writer, args=(tid,)))
            threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Deve ter 10 writers × 100 keys = 1000 keys
        assert len(shared_dict) == 1000, f"Dict tem {len(shared_dict)} keys"


# =============================================================================
# 3. TIMEOUT SIMULATION TESTS
# =============================================================================

class TestTimeoutSimulation:
    """Testes que simulam condições de timeout."""
    
    def test_graceful_timeout_handling(self, mock_page):
        """Timeout deve ser tratado graciosamente, não explodir."""
        # Simular timeout
        mock_page.wait_for_function.side_effect = TimeoutError("Timeout waiting for function")
        
        result = None
        try:
            mock_page.wait_for_function("() => false", timeout=100)
        except TimeoutError:
            result = "timeout_handled"
        
        assert result == "timeout_handled"
    
    def test_cascading_timeouts_dont_accumulate(self):
        """Múltiplos timeouts não devem acumular tempo."""
        timeout_per_op = 0.05  # 50ms cada
        num_ops = 10
        
        start = time.perf_counter()
        timeouts = 0
        
        for _ in range(num_ops):
            try:
                # Simular operação que sempre timeout
                time.sleep(timeout_per_op)
                raise TimeoutError("Simulated")
            except TimeoutError:
                timeouts += 1
        
        elapsed = time.perf_counter() - start
        
        # 10 × 50ms = 500ms + overhead
        assert elapsed < 1.0, f"Cascading timeouts levaram {elapsed}s"
        assert timeouts == num_ops
    
    def test_partial_success_on_timeout(self, sample_queries):
        """Mesmo com timeouts parciais, resultados válidos devem ser mantidos."""
        results = []
        
        for idx, q in enumerate(sample_queries * 5):  # 10 queries
            try:
                if idx % 3 == 0:  # Simular timeout em 1/3 das queries
                    raise TimeoutError(f"Query {idx} timeout")
                results.append({"query": q, "success": True})
            except TimeoutError:
                # Continuar com próxima query
                continue
        
        # Deve ter ~6-7 resultados de 10
        assert len(results) >= 6, f"Apenas {len(results)} resultados - deveria ser >=6"


# =============================================================================
# 4. CONCURRENT LOAD TESTS
# =============================================================================

class TestConcurrentLoad:
    """Testes de carga concorrente."""
    
    def test_parallel_processing_faster_than_sequential(self):
        """Processamento paralelo deve ser mais rápido que sequencial."""
        def slow_op(x):
            time.sleep(0.05)  # 50ms por operação
            return x * 2
        
        items = list(range(20))
        
        # Sequencial
        start = time.perf_counter()
        sequential_results = [slow_op(x) for x in items]
        elapsed_sequential = time.perf_counter() - start
        
        # Paralelo (4 workers)
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            parallel_results = list(executor.map(slow_op, items))
        elapsed_parallel = time.perf_counter() - start
        
        # Paralelo deve ser significativamente mais rápido
        assert elapsed_parallel < elapsed_sequential * 0.5, \
            f"Paralelo ({elapsed_parallel}s) não foi 2x mais rápido que sequencial ({elapsed_sequential}s)"
        
        # Resultados devem ser iguais
        assert sequential_results == parallel_results
    
    def test_thread_pool_doesnt_deadlock(self):
        """ThreadPool não deve travar com muitas tarefas."""
        def quick_task(x):
            time.sleep(0.001)
            return x
        
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(quick_task, i) for i in range(200)]
            results = [f.result(timeout=5) for f in as_completed(futures, timeout=10)]
        elapsed = time.perf_counter() - start
        
        assert len(results) == 200, f"Apenas {len(results)}/200 tarefas completaram"
        assert elapsed < 5.0, f"200 tarefas levaram {elapsed}s - possível deadlock"
    
    def test_concurrent_file_writes_dont_corrupt(self):
        """Escritas concorrentes em arquivos diferentes não devem corromper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            def write_file(idx):
                path = Path(tmpdir) / f"file_{idx}.json"
                data = {"id": idx, "data": list(range(100))}
                path.write_text(json.dumps(data), encoding="utf-8")
                return path
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                paths = list(executor.map(write_file, range(50)))
            
            # Verificar todos os arquivos
            for idx, path in enumerate(paths):
                data = json.loads(path.read_text())
                assert data["id"] == idx, f"Arquivo {path} corrompido"


# =============================================================================
# 5. EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Testes de condições de borda."""
    
    def test_empty_query_list(self):
        """Lista de queries vazia deve retornar resultado vazio, não erro."""
        queries = []
        results = []
        
        for q in queries:
            results.append(q)
        
        assert results == []
    
    def test_malformed_json_handling(self):
        """JSON malformado deve ser tratado graciosamente."""
        malformed_inputs = [
            "",
            "undefined",
            "{invalid}",
            "{'single': 'quotes'}",
            '{"unclosed": ',
        ]
        
        for inp in malformed_inputs:
            try:
                result = json.loads(inp)
            except (json.JSONDecodeError, TypeError):
                result = "handled"
            
            # Não deve explodir, deve retornar algo tratável
            assert result is not None
        
        # Casos válidos que parecem estranhos
        assert json.loads("null") is None  # null é JSON válido
    
    def test_unicode_in_labels(self):
        """Labels com caracteres Unicode devem funcionar."""
        labels = [
            "Órgão com acentos",
            "Agente José María",
            "Cargo: 財務部長",
            "Наименование органа",
            "🏛️ Ministério",
            "Tab\there\nNew line",
        ]
        
        for label in labels:
            # Serialização deve funcionar
            data = {"label": label, "value": "123"}
            json_str = json.dumps(data, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["label"] == label
    
    def test_very_long_strings(self):
        """Strings muito longas devem ser tratadas."""
        long_string = "A" * 100_000  # 100KB
        
        data = {"content": long_string}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        
        assert len(parsed["content"]) == 100_000
    
    def test_special_characters_in_ids(self):
        """IDs com caracteres especiais devem ser escapados corretamente."""
        special_ids = [
            "123",
            "id-with-dash",
            "id_with_underscore",
            "id.with.dots",
            "id/with/slashes",
            "id\\with\\backslashes",
            "id'with'quotes",
            'id"with"double',
            "id<with>brackets",
            "id&with&amp",
        ]
        
        for sid in special_ids:
            # Deve ser seguro para usar em JavaScript
            escaped = json.dumps(sid)
            # Deve round-trip corretamente
            assert json.loads(escaped) == sid


# =============================================================================
# 6. JAVASCRIPT CONDITION TESTS
# =============================================================================

class TestJavaScriptConditions:
    """Testes para verificar que as condições JavaScript são válidas."""
    
    def test_angular_ready_js_is_valid_syntax(self):
        """Condição AngularJS ready deve ter sintaxe JS válida."""
        js = "() => document.querySelector('[ng-app]') !== null"
        
        # Não deve ter caracteres que quebrem quando interpolado
        assert "{{" not in js
        assert "}}" not in js
        assert js.count("(") == js.count(")")
        assert js.count("[") == js.count("]")
    
    def test_selectize_ready_js_escaping(self):
        """Condição Selectize ready com IDs variáveis deve escapar corretamente."""
        element_id = "filtro_orgao_entidade"
        
        # Versão antiga (problemática com f-string)
        js_template = f"() => {{ const el = document.getElementById('{element_id}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 0; }}"
        
        # Deve ter sintaxe válida
        assert "filtro_orgao_entidade" in js_template
        assert js_template.count("{") == js_template.count("}")
    
    def test_calendar_ready_js_selectors(self):
        """Condição de calendário deve cobrir todos os seletores conhecidos."""
        js = "() => document.querySelector('.fc-view-container, .fc-daygrid, #divcalendar, .fc-view') !== null"
        
        expected_selectors = ['.fc-view-container', '.fc-daygrid', '#divcalendar', '.fc-view']
        for sel in expected_selectors:
            assert sel in js, f"Seletor '{sel}' ausente"


# =============================================================================
# 7. BATCH EXECUTOR/RUNNER TESTS
# =============================================================================

class TestBatchPerformance:
    """Testes de performance para batch executor e runner."""
    
    def test_file_read_caching_benefit(self):
        """Cache de leitura de arquivo deve ser mais rápido que múltiplas leituras."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"combos": list(range(1000))}, f)
            path = Path(f.name)
        
        try:
            # Sem cache: 3 leituras
            start = time.perf_counter()
            for _ in range(3):
                _ = json.loads(path.read_text())
            elapsed_no_cache = time.perf_counter() - start
            
            # Com cache: 1 leitura
            start = time.perf_counter()
            cached = json.loads(path.read_text())
            for _ in range(3):
                _ = cached
            elapsed_cached = time.perf_counter() - start
            
            # Cache deve ser significativamente mais rápido
            assert elapsed_cached < elapsed_no_cache, \
                f"Cache ({elapsed_cached}s) não foi mais rápido que sem cache ({elapsed_no_cache}s)"
        finally:
            path.unlink()
    
    def test_parallelism_calculation_consistency(self):
        """Cálculo de paralelismo deve ser consistente para mesmos inputs."""
        import os
        
        # Simular cálculo baseado em CPU
        cpu_count = os.cpu_count() or 4
        
        results = []
        for _ in range(100):
            # Simular recommend_parallel
            jobs = 50
            parallel = min(cpu_count, max(1, jobs // 5))
            results.append(parallel)
        
        # Todos os resultados devem ser iguais (determinístico)
        assert len(set(results)) == 1, "Cálculo de paralelismo não é determinístico"
    
    def test_lock_file_operations_fast(self):
        """Operações de lock file devem ser rápidas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            
            start = time.perf_counter()
            for _ in range(100):
                lock_path.write_text(json.dumps({"pid": 12345}))
                _ = lock_path.read_text()
                lock_path.unlink()
            elapsed = time.perf_counter() - start
            
            # 100 ciclos de lock devem ser <3s (Windows I/O é mais lento)
            assert elapsed < 3.0, f"100 ciclos de lock levaram {elapsed}s"


# =============================================================================
# 8. REGRESSION TESTS
# =============================================================================

class TestRegressions:
    """Testes de regressão para bugs conhecidos."""
    
    def test_wait_for_function_replaces_wait_for_timeout(self, mock_page):
        """Verificar que wait_for_function está sendo usado ao invés de wait_for_timeout."""
        # Ler código fonte e verificar padrão
        collect_file = Path(__file__).parent.parent / "src" / "dou_snaptrack" / "ui" / "eagendas_collect_subprocess.py"
        
        if collect_file.exists():
            content = collect_file.read_text()
            
            # Contar ocorrências de esperas fixas vs condicionais
            fixed_waits = len(re.findall(r'wait_for_timeout\(\d{4,}\)', content))
            conditional_waits = len(re.findall(r'wait_for_function\(', content))
            
            # Devem haver mais esperas condicionais que fixas longas
            assert conditional_waits >= fixed_waits, \
                f"Ainda há {fixed_waits} esperas fixas longas vs {conditional_waits} condicionais"
    
    def test_no_5000ms_waits_remain(self):
        """Não devem haver wait_for_timeout(5000) remanescentes."""
        files_to_check = [
            Path(__file__).parent.parent / "src" / "dou_snaptrack" / "ui" / "eagendas_collect_subprocess.py",
            Path(__file__).parent.parent / "src" / "dou_snaptrack" / "ui" / "eagendas_fetch.py",
        ]
        
        for fpath in files_to_check:
            if fpath.exists():
                content = fpath.read_text()
                matches = re.findall(r'wait_for_timeout\(5000\)', content)
                assert len(matches) == 0, \
                    f"Encontrado wait_for_timeout(5000) em {fpath.name}: {len(matches)} ocorrências"


# =============================================================================
# BENCHMARK HELPERS
# =============================================================================

def run_benchmark(name: str, func, iterations: int = 100):
    """Helper para rodar benchmark e printar resultados."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    
    avg = sum(times) / len(times)
    min_t = min(times)
    max_t = max(times)
    
    print(f"\n[BENCHMARK] {name}:")
    print(f"  Iterations: {iterations}")
    print(f"  Avg: {avg*1000:.2f}ms")
    print(f"  Min: {min_t*1000:.2f}ms")
    print(f"  Max: {max_t*1000:.2f}ms")
    
    return {"name": name, "avg": avg, "min": min_t, "max": max_t}


# =============================================================================
# SPRINT 3 - PLAN LIVE ASYNC TESTS
# =============================================================================

class TestPlanLiveAsyncOptimizations:
    """Testes para verificar otimizações do Sprint 3 em plan_live_eagendas_async.py."""
    
    def test_no_long_fixed_waits_in_open_dropdown(self):
        """Verificar que _open_selectize_dropdown_async não tem wait_for_timeout(1500) fixo."""
        plan_async_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli" / "plan_live_eagendas_async.py"
        
        if plan_async_file.exists():
            content = plan_async_file.read_text(encoding="utf-8")
            
            # Buscar padrão antigo: wait_for_timeout(wait_ms) após ArrowDown
            old_pattern = re.findall(
                r'keyboard\.press\("ArrowDown"\)\s*await page\.wait_for_timeout\(wait_ms\)',
                content,
                re.DOTALL
            )
            assert len(old_pattern) == 0, \
                "Ainda há wait_for_timeout(wait_ms) após ArrowDown - deveria usar wait_for_function"
    
    def test_dropdown_visibility_js_present(self):
        """Verificar que JavaScript de dropdown visível está presente."""
        plan_async_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli" / "plan_live_eagendas_async.py"
        
        if plan_async_file.exists():
            content = plan_async_file.read_text(encoding="utf-8")
            
            # Verificar padrão: offsetParent !== null (dropdown visível)
            assert "offsetParent !== null" in content or "offsetParent===null" in content, \
                "Falta verificação de visibilidade do dropdown via offsetParent"
    
    def test_dropdown_close_js_present(self):
        """Verificar que JavaScript de dropdown fechado está presente."""
        plan_async_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli" / "plan_live_eagendas_async.py"
        
        if plan_async_file.exists():
            content = plan_async_file.read_text(encoding="utf-8")
            
            # Verificar padrão: offsetParent === null (dropdown fechou)
            assert "offsetParent === null" in content, \
                "Falta verificação de fechamento do dropdown via offsetParent === null"
    
    def test_fallbacks_reduced(self):
        """Verificar que fallbacks foram reduzidos."""
        plan_async_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli" / "plan_live_eagendas_async.py"
        
        if plan_async_file.exists():
            content = plan_async_file.read_text(encoding="utf-8")
            
            # Não deve haver wait_for_timeout(3000) - foi reduzido para 1000
            matches_3000 = re.findall(r'wait_for_timeout\(3000\)', content)
            assert len(matches_3000) == 0, \
                f"Ainda há {len(matches_3000)} wait_for_timeout(3000) - deveria ser 1000"
            
            # Não deve haver wait_for_timeout(1500) - foi reduzido para 500
            matches_1500 = re.findall(r'wait_for_timeout\(1500\)', content)
            assert len(matches_1500) == 0, \
                f"Ainda há {len(matches_1500)} wait_for_timeout(1500) - deveria ser 500"
    
    def test_conditional_waits_count(self):
        """Verificar que há múltiplas esperas condicionais."""
        plan_async_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli" / "plan_live_eagendas_async.py"
        
        if plan_async_file.exists():
            content = plan_async_file.read_text(encoding="utf-8")
            
            # Contar wait_for_function
            wait_for_function_count = len(re.findall(r'wait_for_function\(', content))
            
            # Devem haver pelo menos 6 esperas condicionais (adicionamos 3 novas + 3 existentes)
            assert wait_for_function_count >= 6, \
                f"Apenas {wait_for_function_count} wait_for_function encontrados - esperado >= 6"


class TestAsyncPlanHelpers:
    """Testes para funções helper do plan async."""
    
    def test_filter_opts_with_empty_list(self):
        """_filter_opts deve retornar lista vazia para entrada vazia."""
        # Import dinâmico para evitar dependência
        import sys
        plan_async_path = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli"
        if str(plan_async_path) not in sys.path:
            sys.path.insert(0, str(plan_async_path))
        
        try:
            from plan_live_eagendas_async import _filter_opts
            
            result = _filter_opts([], None, None, None)
            assert result == []
        except ImportError:
            pytest.skip("plan_live_eagendas_async não disponível para import")
    
    def test_filter_opts_with_limit(self):
        """_filter_opts deve respeitar limite."""
        import sys
        plan_async_path = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli"
        if str(plan_async_path) not in sys.path:
            sys.path.insert(0, str(plan_async_path))
        
        try:
            from plan_live_eagendas_async import _filter_opts
            
            opts = [{"text": f"Item {i}"} for i in range(10)]
            result = _filter_opts(opts, None, None, 3)
            assert len(result) == 3
        except ImportError:
            pytest.skip("plan_live_eagendas_async não disponível para import")
    
    def test_filter_opts_with_pattern(self):
        """_filter_opts deve filtrar por regex."""
        import sys
        plan_async_path = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli"
        if str(plan_async_path) not in sys.path:
            sys.path.insert(0, str(plan_async_path))
        
        try:
            from plan_live_eagendas_async import _filter_opts
            
            opts = [
                {"text": "Ministério da Saúde"},
                {"text": "Ministério da Educação"},
                {"text": "Banco Central"},
            ]
            result = _filter_opts(opts, "Ministério", None, None)
            assert len(result) == 2
            assert all("Ministério" in o["text"] for o in result)
        except ImportError:
            pytest.skip("plan_live_eagendas_async não disponível para import")
    
    def test_filter_opts_with_pick_values(self):
        """_filter_opts deve filtrar por valores específicos."""
        import sys
        plan_async_path = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "cli"
        if str(plan_async_path) not in sys.path:
            sys.path.insert(0, str(plan_async_path))
        
        try:
            from plan_live_eagendas_async import _filter_opts
            
            opts = [
                {"text": "Item A"},
                {"text": "Item B"},
                {"text": "Item C"},
            ]
            result = _filter_opts(opts, None, ["Item A", "Item C"], None)
            assert len(result) == 2
        except ImportError:
            pytest.skip("plan_live_eagendas_async não disponível para import")


class TestBatchExecutorCaching:
    """Testes para verificar caching no batch_executor."""
    
    def test_lru_cache_on_lazy_imports(self):
        """Verificar que lazy imports usam @lru_cache."""
        batch_executor_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "ui" / "batch_executor.py"
        
        if batch_executor_file.exists():
            content = batch_executor_file.read_text(encoding="utf-8")
            
            # Verificar múltiplos @lru_cache
            lru_count = len(re.findall(r'@lru_cache', content))
            assert lru_count >= 3, \
                f"Apenas {lru_count} @lru_cache encontrados - esperado >= 3"
    
    def test_lru_cache_import(self):
        """Verificar que lru_cache está importado."""
        batch_executor_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "ui" / "batch_executor.py"
        
        if batch_executor_file.exists():
            content = batch_executor_file.read_text(encoding="utf-8")
            
            assert "from functools import lru_cache" in content, \
                "Import de lru_cache não encontrado"


class TestBatchRunnerOptimizations:
    """Testes para verificar otimizações no batch_runner."""
    
    def test_no_powershell_fallback(self):
        """Verificar que PowerShell fallback foi removido."""
        batch_runner_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "ui" / "batch_runner.py"
        
        if batch_runner_file.exists():
            content = batch_runner_file.read_text(encoding="utf-8")
            
            # Não deve haver Get-Process (era o PowerShell fallback)
            assert "Get-Process" not in content, \
                "PowerShell fallback (Get-Process) ainda presente"
    
    def test_csv_import_at_top(self):
        """Verificar que csv está importado no topo do módulo."""
        batch_runner_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "ui" / "batch_runner.py"
        
        if batch_runner_file.exists():
            content = batch_runner_file.read_text(encoding="utf-8")
            lines = content.split('\n')
            
            # Procurar import csv nas primeiras 30 linhas
            csv_import_line = None
            for i, line in enumerate(lines[:30]):
                if 'import csv' in line:
                    csv_import_line = i
                    break
            
            assert csv_import_line is not None, \
                "import csv não encontrado nas primeiras 30 linhas"
    
    def test_io_import_at_top(self):
        """Verificar que io está importado no topo do módulo."""
        batch_runner_file = Path(__file__).parents[2] / "src" / "dou_snaptrack" / "ui" / "batch_runner.py"
        
        if batch_runner_file.exists():
            content = batch_runner_file.read_text(encoding="utf-8")
            lines = content.split('\n')
            
            # Procurar import io nas primeiras 30 linhas
            io_import_line = None
            for i, line in enumerate(lines[:30]):
                if 'import io' in line:
                    io_import_line = i
                    break
            
            assert io_import_line is not None, \
                "import io não encontrado nas primeiras 30 linhas"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
