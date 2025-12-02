# Análise Comparativa: Versão Nov 19 vs Versão Atual (Modular)

## ✅ CORREÇÃO APLICADA (01/12/2025)

O módulo `dou_fetch.py` foi atualizado para usar a mesma abordagem da versão Nov 19:

| Função | Antes | Depois |
|--------|-------|--------|
| `fetch_n1_options` | `async_playwright` + `build_plan_live_async` | `sync_playwright` + operações DOM diretas |
| `fetch_n2_options` | Arquivo temp JSON via `RESULT_JSON_PATH` | stdout (última linha JSON) |
| Comunicação IPC | `subprocess_utils.execute_script_and_read_result` | `subprocess.run` com parse de stdout |

---

## Resumo Executivo

Comparação entre a versão monolítica funcional de 19/Nov/2025 (commit `f4a012e`) e a versão modularizada atual.

| Aspecto | Nov 19 (Monolítica) | Atual (Modular) |
|---------|---------------------|-----------------|
| `app.py` | 2252 linhas | 699 linhas |
| Arquitetura | Inline em app.py | Separado em módulos |
| TAB2 (Batch) | Inline | `batch_executor.py` (212 linhas) |
| TAB3 (Report) | Inline | `report_generator.py` (218 linhas) |
| Fetch N1/N2 | Inline em app.py | `dou_fetch.py` (322 linhas) |

---

## 1. ANÁLISE DE FETCH N1/N2 (Dropdowns)

### 1.1 Fetch N1 - Diferenças Críticas

#### Versão Nov 19 (`_plan_live_fetch_n1_options`, linhas 498-628):
```python
# Usa sync_playwright (síncrono) com subprocess isolado
script_content = f'''
from playwright.sync_api import sync_playwright, TimeoutError

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(ignore_https_errors=True, viewport={{"width": 1366, "height": 900}})
    context.set_default_timeout(90_000)
    page = context.new_page()
    
    url = build_dou_url("{date}", "{secao}")
    goto(page, url)
    # ... operações síncronas diretas
'''

# Execução via subprocess.run com "-c"
result = subprocess.run(
    [sys.executable, "-c", script_content],
    capture_output=True, text=True, timeout=120, cwd=...
)

# Parse JSON da última linha do stdout
stdout_lines = result.stdout.strip().splitlines()
json_line = stdout_lines[-1] if stdout_lines else ""
```

#### Versão Atual (`fetch_n1_options` em `dou_fetch.py`, linhas 99-185):
```python
# Usa async_playwright (assíncrono) via build_plan_live_async
script_content = f"""
from playwright.async_api import async_playwright
from dou_snaptrack.cli.plan_live_async import build_plan_live_async

async def fetch_n1_options():
    async with async_playwright() as p:
        args = SimpleNamespace(
            secao={secao_literal}, data={date_literal},
            plan_out=None, select1=None, select2=None, # ... etc
        )
        cfg = await build_plan_live_async(p, args)
        combos = cfg.get("combos", [])
        # ... extrai N1 de combos
"""

# Execução via subprocess_utils.execute_script_and_read_result
data, stderr = execute_script_and_read_result(
    script_content, timeout=DEFAULT_SUBPROCESS_TIMEOUT, cwd=CWD_ROOT
)
```

### ⚠️ DIFERENÇAS CRÍTICAS:

| Aspecto | Nov 19 | Atual |
|---------|--------|-------|
| **API Playwright** | `sync_playwright` (síncrono) | `async_playwright` (assíncrono) |
| **Abordagem** | Operações DOM diretas | Delega para `build_plan_live_async` |
| **Imports no script** | `_collect_dropdown_roots`, `_read_dropdown_options`, `goto`, `find_best_frame` | `build_plan_live_async` |
| **Comunicação** | stdout (última linha JSON) | Arquivo temporário via `RESULT_JSON_PATH` |
| **Execução** | `python -c "script"` | Arquivo temp `.py` |
| **Timeout** | 120s hardcoded | `DEFAULT_SUBPROCESS_TIMEOUT` (importado) |

### 🔴 POSSÍVEIS PROBLEMAS NA VERSÃO ATUAL:

1. **`build_plan_live_async` pode ter bugs não presentes na abordagem direta**
   - A versão Nov 19 usa funções de baixo nível específicas
   - A versão atual depende de um orquestrador complexo

2. **Async vs Sync**
   - `asyncio.run()` pode ter problemas em certos ambientes Windows
   - A versão Nov 19 evita completamente asyncio no subprocess

3. **Path do script**
   - Nov 19: Injeta `src_path` diretamente no script inline
   - Atual: Depende do `CWD_ROOT` e imports relativos

---

## 2. ANÁLISE DE FETCH N2

### Versão Nov 19 (`_plan_live_fetch_n2`, linhas 312-410):
```python
# Também usa abordagem async, mas com subprocess e inline script
script_content = f"""
from playwright.async_api import async_playwright
from dou_snaptrack.cli.plan_live_async import build_plan_live_async

args = SimpleNamespace(
    secao={secao_literal}, data={date_literal},
    select1={_select1_literal},  # Regex ancorada ^...$
    limit2={_limit2_literal},
    ...
)
cfg = await build_plan_live_async(p, args)
"""

# Parse da última linha do stdout como JSON
stdout_lines = result.stdout.strip().splitlines()
json_line = stdout_lines[-1] if stdout_lines else ""
```

### Versão Atual (`fetch_n2_options` em `dou_fetch.py`, linhas 210-300):
```python
# Praticamente idêntico ao Nov 19 neste caso
script_content = f"""
from playwright.async_api import async_playwright
from dou_snaptrack.cli.plan_live_async import build_plan_live_async
# ...
"""

# Usa execute_script_and_read_result (arquivo temp JSON)
data, stderr = execute_script_and_read_result(...)
```

### ✅ N2 está funcionalmente equivalente
A principal diferença é o mecanismo de comunicação (arquivo temp vs stdout).

---

## 3. ANÁLISE DE TAB2 - EXECUTAR PLANO

### Versão Nov 19 (inline em `app.py`, linhas 1315-1443):
- Código inline dentro de `with tab2:`
- Usa `get_batch_runner()` para lazy import
- Lógica de paralelismo e execução idêntica

### Versão Atual (`batch_executor.py`):
- Função `render_batch_executor()` chamada de app.py
- Usa `_get_batch_runner()` interno ao módulo
- Lógica praticamente idêntica

### ✅ TAB2 está funcionalmente equivalente
A modularização manteve a lógica intacta.

---

## 4. ANÁLISE DE TAB3 - GERAR BOLETIM

### Versão Nov 19 (inline em `app.py`, linhas 1445-1600):
- Código inline dentro de `with tab3:`
- Função `_index_aggregates_in_day` definida inline

### Versão Atual (`report_generator.py`):
- Função `render_report_generator()` chamada de app.py
- `_index_aggregates_in_day` extraída como função de módulo
- Refatorada em sub-funções: `_render_manual_aggregation`, `_render_report_selection`, etc.

### ✅ TAB3 está funcionalmente equivalente
A modularização manteve a lógica intacta.

---

## 5. ANÁLISE DE FUNÇÕES AUXILIARES

### `_run_batch_with_cfg`

| Nov 19 | Atual |
|--------|-------|
| Definida em `app.py` linha 885 | Movida para `batch_executor.py` |
| Código idêntico | Código idêntico |

### `_run_report`

| Nov 19 | Atual |
|--------|-------|
| Definida em `app.py` linha 898 | **NÃO ENCONTRADA** na versão modular |

⚠️ **POSSÍVEL PROBLEMA**: A função `_run_report` foi removida na modularização. Verificar se ainda é usada.

---

## 6. DIAGNÓSTICO DE PROBLEMAS POTENCIAIS

### 6.1 Problema Principal: Fetch N1 usa abordagem diferente

A versão **Nov 19** usa:
- `sync_playwright` (API síncrona)
- Funções de baixo nível: `_collect_dropdown_roots`, `_read_dropdown_options`, `goto`, `find_best_frame`
- Manipulação direta do DOM

A versão **Atual** usa:
- `async_playwright` (API assíncrona)
- `build_plan_live_async` (orquestrador de alto nível)
- Extração indireta de `combos`

**Impacto**: Se `build_plan_live_async` tiver bugs ou comportamento diferente, o fetch N1 falha.

### 6.2 Comunicação IPC

| Nov 19 | Atual |
|--------|-------|
| stdout (última linha) | Arquivo temp JSON |
| Simples, robusto | Mais complexo |

**Impacto**: Se o arquivo temp não for criado ou lido corretamente, retorna `None`.

### 6.3 Módulo `subprocess_utils.py`

A versão atual introduziu um novo módulo `subprocess_utils.py` que:
- Cria arquivo temporário para script
- Cria arquivo temporário para resultado JSON
- Define variável de ambiente `RESULT_JSON_PATH`

**Pontos de falha**:
1. Permissões de escrita em temp
2. Cleanup de arquivos temporários
3. Encoding issues

---

## 7. RECOMENDAÇÕES

### 7.1 Prioridade ALTA: Reverter Fetch N1 para abordagem síncrona

**Justificativa**: A versão Nov 19 usa uma abordagem mais direta e confiável para N1.

**Ação**: Criar versão híbrida que usa `sync_playwright` para N1 (como Nov 19) mas mantém a estrutura modular atual.

### 7.2 Prioridade MÉDIA: Simplificar IPC

**Justificativa**: A comunicação via arquivo temp adiciona complexidade desnecessária.

**Ação**: Considerar voltar para parse de stdout (última linha JSON) como Nov 19.

### 7.3 Prioridade BAIXA: Verificar `_run_report`

**Justificativa**: A função pode estar faltando ou renomeada.

**Ação**: Verificar se há código órfão ou chamadas quebradas.

---

## 8. TESTES RECOMENDADOS

```python
# Teste 1: Fetch N1 isolado
from dou_snaptrack.ui.dou_fetch import fetch_n1_options
result = fetch_n1_options("DO1", "25-11-2025")
print(f"N1 options: {result}")

# Teste 2: Fetch N2 isolado  
from dou_snaptrack.ui.dou_fetch import fetch_n2_options
result = fetch_n2_options("DO1", "25-11-2025", "Ministério da Fazenda")
print(f"N2 options: {result}")

# Teste 3: Verificar subprocess_utils
from dou_snaptrack.ui.subprocess_utils import execute_script_and_read_result
script = 'import json; print(json.dumps({"test": True}))'
data, stderr = execute_script_and_read_result(script)
print(f"IPC test: {data}")
```

---

## 9. CONCLUSÃO

A modularização foi bem-sucedida em termos de organização de código, mas introduziu uma regressão potencial no **fetch N1** ao mudar de uma abordagem síncrona direta para uma assíncrona via orquestrador.

**Próximos passos**:
1. Testar fetch N1/N2 isoladamente
2. Se N1 falhar, reverter para abordagem sync_playwright
3. Manter estrutura modular mas ajustar implementação interna
