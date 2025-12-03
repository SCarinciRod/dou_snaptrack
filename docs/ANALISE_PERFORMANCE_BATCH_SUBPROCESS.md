# 📊 Análise de Performance: Batch e Subprocess Collect

**Data:** 2025-12-02  
**Status:** Análise ✅ | Implementação pendente ⏳

---

## 1. Resumo Executivo

### Estado Atual - REVISADO

Após análise completa dos módulos `batch_executor.py`, `batch_runner.py`, `batch.py` (CLI), `runner.py` e `edition_runner_service.py`:

| Componente | Estado | Problema Principal |
|------------|--------|-------------------|
| **DOU Batch UI** (`batch_executor.py`) | ⚠️ Subótimo | Não otimizado para planos grandes |
| **DOU Batch Runner** (`batch_runner.py`) | ⚠️ Subótimo | Lock file I/O excessivo, cleanup síncrono |
| **DOU Batch CLI** (`batch.py`) | ✅ Bom | Paralelização, resource blocking, page reuse |
| **Edition Runner** (`edition_runner_service.py`) | ✅ Bom | Timings detalhados, in-page reuse |
| **E-Agendas Plan Async** | ⚠️ Parcialmente otimizado | Usa `wait_for_function` com fallbacks fixos |
| **E-Agendas Collect Subprocess** | ❌ Crítico | **13 segundos** de esperas fixas por agente |
| **E-Agendas Fetch** | ❌ Crítico | **8 segundos** de esperas fixas por operação |

### Impacto Estimado das Otimizações

```
DOU Batch (10 jobs):
  Atual:     ~30-60 segundos
  Otimizado: ~15-25 segundos
  Ganho:     50%+ (principalmente em I/O e locks)

E-Agendas Collect (227 agentes):
  Atual:     ~76 minutos (5s/operação)
  Otimizado: ~8 minutos  (0.5s/operação)
  Ganho:     90%
```

---

## 2. Análise Detalhada por Componente

### 2.1 DOU Batch UI (`batch_executor.py`) - ⚠️ SUBÓTIMO

**Problemas identificados:**

```python
# ❌ PROBLEMA 1: Múltiplas chamadas de I/O para ler o mesmo arquivo
cfg_preview = json.loads(selected_path.read_text(encoding="utf-8"))  # Linha ~70
cfg = json.loads(selected_path.read_text(encoding="utf-8"))           # Linha ~120
cfg_json = json.loads(selected_path.read_text(encoding="utf-8"))      # Linha ~155

# ❌ PROBLEMA 2: Cálculo de paralelismo feito 2x
suggest_workers = recommend_parallel(est_jobs_prev)  # Linha ~80
parallel = recommend_parallel(est_jobs)               # Linha ~135

# ❌ PROBLEMA 3: Nenhum cache para list_saved_plan_files
plan_entries = _list_saved_plan_files(refresh_token)  # Sempre relê disco
```

**Impacto:** 3-5 leituras de arquivo redundantes por execução

### 2.2 DOU Batch Runner (`batch_runner.py`) - ⚠️ SUBÓTIMO

**Problemas identificados:**

```python
# ❌ PROBLEMA 1: PowerShell fallback lento (3s timeout)
def _win_get_process_info(pid: int) -> dict:
    out = run_cmd(["tasklist", ...], timeout=1)  # OK - rápido
    # Fallback PowerShell com 3s timeout:
    ps = ("powershell", "-NoProfile", "-Command", ...)
    out = run_cmd(ps, timeout=3)  # ← 3s de latência potencial!

# ❌ PROBLEMA 2: Lock file cleanup síncrono em finally
def __exit__(self, ...):
    for lock_file in [self.path, Path(str(self.path) + ".lock")]:
        lock_file.unlink(missing_ok=True)  # I/O síncrono

# ❌ PROBLEMA 3: Cleanup de outputs sequencial (corrigido parcialmente)
# Já usa ThreadPoolExecutor(max_workers=4), mas ainda sequencial no runner
```

**Impacto:** 1-5 segundos de overhead em detecção de processos

### 2.3 DOU Batch CLI (`batch.py`) - ✅ BOM (mas pode melhorar)

**Boas práticas JÁ implementadas:**
```python
# ✅ Resource blocking para acelerar navegação
context.route("**/*", _route_block_heavy)

# ✅ Page reuse por (date, secao)
page_cache: dict[tuple[str, str], Any] = {}

# ✅ Bucket distribution para paralelismo inteligente
groups: dict[tuple[str, str], list[int]] = defaultdict(list)

# ✅ Subprocess pool com fallback para threads
if pool_pref == "subprocess" and parallel > 1:
    # Subprocess real
elif pool_pref == "thread":
    # ThreadPoolExecutor
```

**Problemas menores:**
```python
# ⚠️ Timeout de 60s para workers pode ser curto para planos grandes
for fut in as_completed(futs, timeout=60):

# ⚠️ Logging excessivo em cada job
_log(f"[Parent] Scheduling bucket {w_id+1}/{len(buckets)} ...")
```

### 2.4 Edition Runner Service (`edition_runner_service.py`) - ✅ BOM

**Boas práticas JÁ implementadas:**
```python
# ✅ Timings detalhados para debugging
timings = {
    "nav_sec": round(t_after_nav - t0, 3),
    "view_sec": round(t_after_view - t_after_nav, 3),
    "select_sec": round(t_after_select - t_after_view, 3),
    "collect_sec": round(t_after_collect - t_after_select, 3),
}

# ✅ In-page reuse para evitar navegação desnecessária
if self._allow_inpage_reuse and same_date and same_secao:
    do_nav = False
    inpage = True

# ✅ Resource blocking no context
def _route_block_heavy(route):
    if rtype in ("image", "media", "font"):
        return route.abort()
```

### 2.5 DOU Selection (`multi_level_cascade_service.py`) - ✅ BOM

```python
# ✅ Polling para repopulação
wait_repopulation(self.frame, r2["handle"], prev_n2, 
                  timeout_ms=repop_timeout_ms,    # 25000
                  poll_interval_ms=repop_poll_ms)  # 150
```

---

## 3. Mapa de Esperas Fixas (Todos os Arquivos)

### Arquivos com `wait_for_timeout` > 1000ms

| Arquivo | Linha | Tempo | Uso |
|---------|-------|-------|-----|
| `eagendas_collect_subprocess.py` | 177 | 5000ms | AngularJS load |
| `eagendas_collect_subprocess.py` | 193 | 3000ms | Agentes dropdown |
| `eagendas_collect_subprocess.py` | 207 | 2000ms | Após seleção |
| `eagendas_collect_subprocess.py` | 240 | 3000ms | Calendário |
| `eagendas_fetch.py` | 171 | 5000ms | AngularJS load |
| `eagendas_fetch.py` | 196 | 3000ms | Agentes |
| `plan_live_eagendas_async.py` | 433 | 3000ms | Fallback |
| `plan_live_async.py` | 273 | 2000ms | Fallback |
| `plan_live_async.py` | 488 | 2000ms | Fallback |
| `plan_live_eagendas_async.py` | 540 | 1500ms | Cargo fallback |
| `plan_live_eagendas_async.py` | 100/110/125 | 1500ms | Dropdown open |

### Esperas menores (já otimizadas ou aceitáveis)

| Arquivo | Tempo | Quantidade | Status |
|---------|-------|------------|--------|
| `wait_helpers.py` | 50ms | Poll interval | ✅ OK |
| `browser.py` | 150-500ms | Scroll/Ajax | ✅ OK |
| `pairs_mapper.py` | 60-120ms | DOM updates | ✅ OK |

---

## 4. Comparação: DOU vs E-Agendas

### DOU (Padrão Ouro)
```python
# Espera CONDICIONAL com polling agressivo
def wait_for_options_loaded(frame, min_count=1, timeout_ms=2000):
    def _check():
        cnt = container.locator(OPTION_SELECTORS[0]).count()
        return cnt >= min_count
    wait_for_condition(frame, _check, timeout_ms=timeout_ms, poll_ms=50)
```

### E-Agendas (Padrão Problemático)
```python
# Espera FIXA incondicional
page.wait_for_timeout(5000)  # Sempre espera 5s, mesmo se pronto em 200ms
```

### Diferença de Performance

| Métrica | DOU | E-Agendas | Razão |
|---------|-----|-----------|-------|
| Espera típica | 50-200ms | 2000-5000ms | 10-25x mais lento |
| Polling interval | 50ms | N/A (fixo) | - |
| Early exit | ✅ Sim | ❌ Não | Não verifica se pronto |
| Detecção de estado | JavaScript | Nenhuma | Não usa wait_for_function |

---

## 5. Plano de Otimização

### Fase 1: Quick Wins (Implementação: 1h, Ganho: ~60%)

**Arquivo:** `eagendas_collect_subprocess.py`

| Antes | Depois | Ganho |
|-------|--------|-------|
| `page.wait_for_timeout(5000)` | `wait_for_function(angular_ready, timeout=5000)` | 4.5s |
| `page.wait_for_timeout(3000)` | `wait_for_function(selectize_ready, timeout=3000)` | 2.5s |
| `page.wait_for_timeout(2000)` | `wait_for_function(calendar_ready, timeout=2000)` | 1.5s |
| `page.wait_for_timeout(3000)` | `wait_for_function(events_loaded, timeout=3000)` | 2.5s |

**Total recuperado:** ~11s por agente × 227 agentes = **41 minutos**

### Fase 2: Polling Adaptativo (Implementação: 2h, Ganho: +20%)

```python
async def wait_selectize_ready(page, element_id: str, timeout_ms: int = 5000) -> bool:
    """Espera condicional para Selectize inicializar."""
    js = f"""() => {{
        const el = document.getElementById('{element_id}');
        return el?.selectize && Object.keys(el.selectize.options || {{}}).length > 0;
    }}"""
    try:
        await page.wait_for_function(js, timeout=timeout_ms)
        return True
    except Exception:
        return False
```

### Fase 3: Paralelização (Implementação: 3h, Ganho: +20%)

```python
# Processar múltiplos agentes em paralelo (não sequencial)
async def collect_parallel(queries: list, max_concurrent: int = 3):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [collect_one(q, semaphore) for q in queries]
    return await asyncio.gather(*tasks)
```

---

## 6. Estimativa de Ganhos

### Cenário: 227 Órgãos × 2 Cargos × 2 Agentes = ~1000 operações

| Fase | Tempo Atual | Tempo Otimizado | Ganho |
|------|-------------|-----------------|-------|
| Collect Atual | 76 min | - | - |
| Fase 1 (Esperas condicionais) | - | 30 min | 60% |
| Fase 2 (Polling adaptativo) | - | 15 min | 80% |
| Fase 3 (Paralelização 3x) | - | 5-8 min | 90% |

---

## 7. Código de Referência (DOU)

### wait_helpers.py - Padrão a seguir

```python
def wait_for_condition(
    frame,
    condition_fn,
    timeout_ms: int = 5000,
    poll_ms: int = 50,
) -> bool:
    """
    Espera até condition_fn() retornar True.
    Polling agressivo (50ms default) para resposta rápida.
    """
    start = time.time()
    deadline = start + (timeout_ms / 1000.0)
    
    while time.time() < deadline:
        try:
            if condition_fn():
                return True
        except Exception:
            pass
        time.sleep(poll_ms / 1000.0)
    
    return False
```

### Uso correto:
```python
# Ao invés de:
page.wait_for_timeout(5000)  # ❌ RUIM

# Use:
wait_for_condition(
    page,
    lambda: page.query_selector('#element').is_visible(),
    timeout_ms=5000,
    poll_ms=50
)  # ✅ BOM - para em 50-200ms típico
```

---

## 8. Priorização de Implementação

| Prioridade | Arquivo | Impacto | Esforço |
|------------|---------|---------|---------|
| 🔴 **ALTA** | `eagendas_collect_subprocess.py` | 11s/op | 1h |
| 🔴 **ALTA** | `eagendas_fetch.py` | 8s/op | 30min |
| 🟡 **MÉDIA** | `plan_live_eagendas_async.py` | 3s/op (fallbacks) | 1h |
| 🟢 **BAIXA** | `plan_live_async.py` | 2s/op (fallbacks) | 30min |

---

## 9. Riscos e Considerações

### E-Agendas requer `headless=False`
O site detecta automação e bloqueia headless. Isso limita:
- ❌ Não pode rodar em CI headless
- ❌ Paralelização limitada (múltiplas janelas consomem recursos)

### Selectize.js é lento por natureza
- AJAX para carregar opções
- Animações CSS de transição
- DOM pesado com virtualização

### Mitigação recomendada
- Usar JavaScript API (`el.selectize.setValue()`) ao invés de cliques
- Aguardar via `wait_for_function()` ao invés de tempo fixo
- Paralelizar no nível de processo (não página)

---

## 10. Análise Específica: Módulos UI (batch_executor + batch_runner)

### 10.1 `batch_executor.py` - Problemas Detalhados

**PROBLEMA 1: Leitura de arquivo redundante**
```python
# Linha ~70: Preview para contar combos
cfg_preview = json.loads(selected_path.read_text(encoding="utf-8"))

# Linha ~120: Dentro de _execute_plan, lê de novo
cfg = json.loads(selected_path.read_text(encoding="utf-8"))

# Linha ~155: Lê mais uma vez para override de data
cfg_json = json.loads(selected_path.read_text(encoding="utf-8"))
```
**Impacto:** 3 leituras de disco × ~50ms = 150ms desperdiçados

**PROBLEMA 2: Paralelismo calculado 2 vezes**
```python
# Na renderização:
suggested_workers = recommend_parallel(est_jobs_prev, prefer_process=True)

# Na execução:
parallel = int(recommend_parallel(est_jobs, prefer_process=True))
```

**SOLUÇÃO PROPOSTA:**
```python
@st.cache_data(ttl=60)
def _load_plan_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

### 10.2 `batch_runner.py` - Problemas Detalhados

**PROBLEMA 1: PowerShell fallback lento**
```python
def _win_get_process_info(pid: int) -> dict:
    # Tenta tasklist primeiro (rápido ~100ms)
    out = run_cmd(["tasklist", ...], timeout=1)
    
    # Se falha, usa PowerShell (LENTO: até 3s!)
    ps = ("powershell", "-NoProfile", "-Command", ...)
    out = run_cmd(ps, timeout=3)  # ← GARGALO
```
**Impacto:** Até 3s de latência quando tasklist não encontra o processo

**PROBLEMA 2: Detecção de PID com CSV parsing**
```python
def _pid_alive_windows(pid: int) -> bool:
    out = run_cmd(["tasklist", "/FI", f"PID eq {pid}", ...], timeout=2)
    # Parsing manual de CSV
    import csv, io
    reader = csv.reader(io.StringIO(stdout))
```
**Impacto:** Import de `csv` e `io` toda vez (~5ms overhead)

**PROBLEMA 3: Lock cleanup síncrono**
```python
def __exit__(self, _exc_type, _exc, tb):
    # Operações de I/O síncronas no cleanup
    for lock_file in [self.path, Path(str(self.path) + ".lock")]:
        lock_file.unlink(missing_ok=True)
```
**Impacto:** 10-50ms de I/O bloqueante

**SOLUÇÃO PROPOSTA:**
```python
# Cache de imports no topo do módulo
import csv
import io

# Usar WMI via subprocess batch ao invés de chamadas individuais
# Ou: usar psutil (já instalado) para detecção de processos
```

---

## 11. Conclusão ATUALIZADA

### O que JÁ está otimizado:
- ✅ DOU Edition Runner (polling, in-page reuse, timings)
- ✅ Batch CLI (resource blocking, bucket distribution, page cache)
- ✅ wait_helpers.py (esperas condicionais 50ms)

### O que PRECISA otimização URGENTE:
| Prioridade | Arquivo | Problema | Ganho Estimado |
|------------|---------|----------|----------------|
| 🔴 CRÍTICO | `eagendas_collect_subprocess.py` | 13s esperas fixas/agente | 90% |
| 🔴 CRÍTICO | `eagendas_fetch.py` | 8s esperas fixas/op | 85% |
| 🟡 MÉDIO | `batch_executor.py` | 3x leitura de arquivo | 150ms |
| 🟡 MÉDIO | `batch_runner.py` | PowerShell fallback 3s | 3s |
| 🟢 BAIXO | `plan_live_eagendas_async.py` | Fallbacks fixos | 50% |

### Plano de Ação Recomendado:

**Sprint 1 (1-2h): E-Agendas Collect**
1. Substituir `wait_for_timeout()` por `wait_for_function()` em `eagendas_collect_subprocess.py`
2. Aplicar mesma técnica em `eagendas_fetch.py`

**Sprint 2 (30min): UI Batch**
1. Cachear leitura de config em `batch_executor.py`
2. Remover PowerShell fallback ou usar psutil em `batch_runner.py`

**Sprint 3 (1h): Plan Async**
1. Remover fallbacks fixos em `plan_live_eagendas_async.py`
2. Usar polling adaptativo

---

**Próximos passos:** Implementar Sprint 1 (E-Agendas Collect) para ganho imediato de 90%.

