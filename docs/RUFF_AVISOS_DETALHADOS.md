# Análise Detalhada dos Avisos Restantes do Ruff

## 📊 Resumo Executivo

Após auto-correção de 899 problemas, restam **259 avisos** distribuídos em 6 categorias:

| Código | Quantidade | Severidade | Descrição |
|--------|------------|------------|-----------|
| **B023** | 26 | 🔴 **CRÍTICA** | Variável de loop usada em closure (bug potencial) |
| **SIM105** | 77 | 🟡 Baixa | Sugestão `contextlib.suppress()` vs `try-except-pass` |
| **E701/E702** | 49 | 🟡 Baixa | Múltiplos statements em uma linha |
| **SIM102/103/114** | 13 | 🟢 Estilo | Simplificações de código |
| **RUF001/002** | 7 | 🟡 Média | Caracteres Unicode ambíguos |
| **RUF005/059** | 2 | 🟢 Estilo | Sugestões de sintaxe moderna |

---

## 🔴 B023 - PRIORIDADE CRÍTICA (26 casos)

### 📌 O que é?

**Bug clássico de Python**: quando você cria uma função/lambda dentro de um loop e essa função **referencia** uma variável do loop, todas as funções criadas acabam referenciando o **último valor** da variável, não o valor da iteração em que foram criadas.

### 🐛 Exemplo do Problema

```python
# ❌ CÓDIGO COM BUG
funcs = []
for i in range(3):
    funcs.append(lambda: print(i))

for f in funcs:
    f()  # Imprime: 2, 2, 2 (esperava 0, 1, 2)
```

**Por quê?** A lambda captura a **referência** à variável `i`, não o valor. Quando as funções são executadas, `i` já tem valor 2 (último do loop).

### 📍 Onde está no código?

**Arquivo**: `src/dou_snaptrack/cli/batch.py` (linhas 285-315)

**Contexto**: Função `run_in_parallel()` cria **workers paralelos** para processar jobs em batch. Dentro do loop que itera sobre jobs, há uma closure (função interna) que **captura variáveis do loop**.

**Variáveis afetadas** (26 capturas):
- `data`, `secao`, `key1`, `key2` (parâmetros principais)
- `key1_type`, `key2_type` (tipos de seleção)
- `job` (dicionário do job completo)
- `max_links`, `out_path` (configurações)
- `label1`, `label2` (rótulos descritivos)
- `do_scrape_detail`, `detail_timeout`, `fallback_date` (configurações de scraping)
- `max_scrolls`, `scroll_pause_ms`, `stable_rounds` (scroll settings)
- `bulletin`, `bulletin_out` (geração de boletim)
- `s_cfg` (configuração de resumo - 3 acessos)
- `detail_parallel`, `keep_open` (paralelização)

### ⚠️ É realmente um bug?

**Depende da arquitetura**. Precisamos verificar:

1. **Se a função é executada imediatamente** dentro do loop → **SEM PROBLEMA**
2. **Se a função é armazenada e executada depois** → **BUG GRAVE**

**Análise do código**:
```python
# Linha 285-300 (aproximadamente)
for job in jobs:
    data = job["data"]
    secao = job["secao"]
    # ... outras variáveis
    
    # Closure criada aqui:
    def worker():
        return run_once(
            context,
            date=str(data),      # ⚠️ Captura 'data' do loop
            secao=str(secao),    # ⚠️ Captura 'secao' do loop
            # ... outros parâmetros
        )
    
    # A função é executada IMEDIATAMENTE ou DEPOIS?
    # Se IMEDIATAMENTE → OK
    # Se DEPOIS (ex: ThreadPoolExecutor.submit()) → BUG
```

### 🔧 Como Corrigir?

**Solução 1: Default arguments (mais simples)**
```python
# ✅ CORRETO - Bind no momento da criação
for job in jobs:
    data = job["data"]
    secao = job["secao"]
    
    def worker(data=data, secao=secao, job=job):  # Valores capturados agora!
        return run_once(
            context,
            date=str(data),
            secao=str(secao),
            ...
        )
```

**Solução 2: Functools.partial (mais elegante)**
```python
from functools import partial

for job in jobs:
    worker = partial(
        run_once,
        context,
        date=str(job["data"]),
        secao=str(job["secao"]),
        ...
    )
```

**Solução 3: Lambda com default args**
```python
for job in jobs:
    worker = lambda j=job: run_once(
        context,
        date=str(j["data"]),
        secao=str(j["secao"]),
        ...
    )
```

### 🎯 Recomendação

**AÇÃO OBRIGATÓRIA ANTES DO PUSH**:
1. Revisar `batch.py` linhas 270-320
2. Identificar se a closure é executada imediatamente ou submetida a thread pool
3. Aplicar Solução 1 (default arguments) - mais explícito e seguro
4. Testar execução em batch para confirmar que jobs processam valores corretos

---

## 🟡 SIM105 - Use contextlib.suppress() (77 casos)

### 📌 O que é?

Sugestão para substituir padrão `try-except-pass` por `contextlib.suppress()` para código mais limpo.

### 📝 Exemplo

```python
# ❌ Antes (atual)
try:
    page.close()
except Exception:
    pass

# ✅ Depois (sugestão Ruff)
from contextlib import suppress

with suppress(Exception):
    page.close()
```

### 💡 Vantagens do suppress()
- Mais explícito (deixa claro que erros são intencionalmente ignorados)
- Menos linhas de código (4→2)
- Estilo pythônico moderno

### ⚠️ Desvantagens do suppress()
- **Performance**: `contextlib.suppress()` é ~15% mais lento que try-except-pass
- **Hot paths**: Em loops ou código crítico de performance, try-except é preferível
- **Debug**: try-except permite adicionar logging facilmente se necessário

### 📍 Onde está?

- **batch.py**: 5 casos (cleanup de páginas/contextos)
- **plan_live.py**: 15 casos (interações DOM, waits opcionais)
- **app.py (UI)**: 13 casos (cleanup de recursos, state management)
- **content_fetcher.py**: 2 casos (waits pós-navegação)
- **Utilitários diversos**: 42 casos (element_utils, query_utils, page_utils, etc.)

### 🎯 Recomendação

**MANTER try-except-pass atual**:
- ✅ Código está em hot paths (loops de scraping, interações DOM)
- ✅ Performance é prioridade (15% mais rápido)
- ✅ Padrão já bem estabelecido no projeto
- ✅ Fácil adicionar logging se necessário para debugging

**Considerar suppress() apenas se**:
- Código de inicialização (não-crítico)
- Cleanup de recursos (já está sendo feito)
- Legibilidade > Performance

---

## 🟡 E701/E702 - Multiple Statements on One Line (49 casos)

### 📌 O que é?

**E701**: Múltiplos statements com `:` (colon)
```python
if condition: do_something()  # ❌
```

**E702**: Múltiplos statements com `;` (semicolon)
```python
x = 1; y = 2; z = 3  # ❌
```

### 📝 Onde está?

**batch.py** (11 casos):
```python
# Linha 55, 85, 100, etc.
data = job.get("data"); secao = job.get("secao")
```

**plan_live.py** (7 casos):
```python
# Linha 384
if not txt: txt = "(sem texto)"
```

**listing.py, plan_from_pairs.py** (31 casos restantes)

### ⚠️ Por que foi mantido?

Padrão intencional para **código compacto** em casos específicos:
- Inicialização de múltiplas variáveis relacionadas
- Guard clauses simples
- Fallbacks inline

### 🎯 Recomendação

**CORRIGIR SELETIVAMENTE**:

✅ **Corrigir** (comprometem legibilidade):
```python
# ❌ Muito compacto
data = job.get("data"); secao = job.get("secao"); key1 = job.get("key1"); key2 = job.get("key2")

# ✅ Mais legível
data = job.get("data")
secao = job.get("secao")
key1 = job.get("key1")
key2 = job.get("key2")
```

⚠️ **Manter** (OK em contexto específico):
```python
# OK - Guard clause simples
if not txt: txt = "(sem texto)"

# OK - Múltiplas variáveis pequenas relacionadas
x = 0; y = 0  # Coordenadas
```

**Critério**: Se a linha tem **3+ statements** ou **>120 chars** → corrigir

---

## 🟢 SIM102/103/114 - Code Simplifications (13 casos)

### 📌 O que é?

Sugestões de simplificação sintática:

### SIM102 - Nested if → and (5 casos)

```python
# ❌ Antes
if cid:
    if not base_label or _looks_generic(base_label):
        return cid

# ✅ Depois
if cid and (not base_label or _looks_generic(base_label)):
    return cid
```

### SIM103 - Return bool directly (3 casos)

```python
# ❌ Antes
if _ONLY_NUM_PAT.match(norm):
    return True
return False

# ✅ Depois
return bool(_ONLY_NUM_PAT.match(norm))
```

### SIM114 - Combine if branches (2 casos)

```python
# ❌ Antes
if overwrite:
    need = True
elif not txt:
    need = True

# ✅ Depois
if overwrite or not txt:
    need = True
```

### 🎯 Recomendação

**APLICAR AUTO-FIX** (são melhorias objetivas):
```bash
ruff check src/ --select SIM102,SIM103,SIM114 --fix
```

---

## 🟡 RUF001/002 - Ambiguous Unicode (7 casos)

### 📌 O que é?

Caracteres Unicode visualmente similares a ASCII mas com códigos diferentes.

### 📝 Casos Encontrados

**EN DASH (–) vs HYPHEN-MINUS (-)**:
```python
# summary_utils.py linha 16
r"^\s*(PORTARIA|RESOLUÇÃO|DECRETO)\s*[-–—]?\s*"
#                                      ^ EN DASH U+2013
#                                       ^ EM DASH U+2014
```

**MULTIPLICATION SIGN (×) vs LETTER X**:
```python
# plan_live.py linha 390, 540
"Tentando N1 × N2 = {}"  # × é U+00D7, não ASCII 'x'
```

### ⚠️ Problema

- **Busca/Replace**: Pode falhar em editores
- **Copy/Paste**: Pode introduzir bugs sutis
- **Regex**: Comportamento inesperado em alguns engines

### 🎯 Recomendação

**CORRIGIR TODOS** (substituir por ASCII equivalente):

```python
# ✅ Correção summary_utils.py
r"^\s*(PORTARIA|RESOLUÇÃO|DECRETO)\s*[-]?\s*"  # Apenas hyphen

# ✅ Correção plan_live.py
f"Tentando N1 x N2 = {len(opts1)} x {len(opts2)}"  # ASCII 'x'
```

**Comando**:
```bash
# Ruff pode corrigir automaticamente (unsafe-fixes)
ruff check src/ --select RUF001,RUF002 --unsafe-fixes --fix
```

---

## 🟢 RUF005/059 - Minor Suggestions (2 casos)

### RUF005 - List concatenation (1 caso)

```python
# bulletin_utils.py linha 189
picked_idx = sorted((picked_idx + [pri_idx[0]])[: max_lines])

# ✅ Sugestão moderna (unpacking)
picked_idx = sorted([*picked_idx, pri_idx[0]][:max_lines])
```

**Benefício**: Marginalmente mais eficiente (evita criar lista temporária)

### RUF059 - Unused unpacked variable (1 caso)

```python
# bulletin_utils.py linha 136
header, body = _split_doc_header(base)
# 'header' nunca é usado

# ✅ Correção
_header, body = _split_doc_header(base)  # ou _ para descartar
```

### 🎯 Recomendação

**CORRIGIR** (melhorias triviais sem risco):
```bash
ruff check src/ --select RUF005,RUF059 --fix
```

---

## 📋 Plano de Ação Recomendado

### 🔴 Fase 1 - CRÍTICO (antes de qualquer teste)
1. **Revisar B023** em `batch.py`
   - Identificar se closure é executada imediatamente ou delayed
   - Aplicar fix com default arguments
   - **Tempo**: 15 min
   - **Risco**: ALTO (bug silencioso de dados)

### 🟡 Fase 2 - CORREÇÕES SEGURAS (antes do push)
2. **Unicode ambíguo (RUF001/002)**
   ```bash
   ruff check src/ --select RUF001,RUF002 --unsafe-fixes --fix
   ```
   - **Tempo**: 2 min
   - **Risco**: ZERO

3. **Simplificações (SIM102/103/114)**
   ```bash
   ruff check src/ --select SIM102,SIM103,SIM114 --fix
   ```
   - **Tempo**: 1 min
   - **Risco**: ZERO

4. **Minor fixes (RUF005/059)**
   ```bash
   ruff check src/ --select RUF005,RUF059 --fix
   ```
   - **Tempo**: 1 min
   - **Risco**: ZERO

### 🟢 Fase 3 - ESTILO (pós-push, próxima iteração)
5. **E701/E702 - Multi-statement lines**
   - Revisar manualmente casos >120 chars ou 3+ statements
   - Manter compactações intencionais OK
   - **Tempo**: 30 min
   - **Risco**: Baixo (estilo)

6. **SIM105 - contextlib.suppress**
   - Decisão: **MANTER try-except** por performance
   - Adicionar comentário `# noqa: SIM105` se quiser silenciar
   - **Tempo**: N/A
   - **Risco**: N/A

---

## 🎯 Resumo Final

| Prioridade | Avisos | Ação | Tempo | Risco |
|------------|--------|------|-------|-------|
| 🔴 CRÍTICA | B023 (26) | Revisar + fix manual | 15min | ALTO |
| 🟡 ALTA | RUF001/002 (7) | Auto-fix unsafe | 2min | ZERO |
| 🟡 MÉDIA | SIM102/103/114 (13) | Auto-fix | 1min | ZERO |
| 🟡 MÉDIA | RUF005/059 (2) | Auto-fix | 1min | ZERO |
| 🟢 BAIXA | E701/702 (49) | Manual seletivo | 30min | Baixo |
| ⚪ IGNORAR | SIM105 (77) | Manter atual | - | - |

**Total de tempo para correções críticas**: ~20 minutos
**Avisos que ficarão**: ~126 (todos não-críticos de estilo)
