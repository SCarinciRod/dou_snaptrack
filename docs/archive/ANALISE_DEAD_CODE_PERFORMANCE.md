# MOVED: Este arquivo foi arquivado

O conteúdo completo foi movido para esta pasta de archive para reduzir a quantidade de arquivos soltos na raiz do repositório. Abaixo permanece o conteúdo original para referência.


# 🔍 Análise de Dead Code e Otimizações de Performance

**Data:** 27/10/2025  
**Escopo:** Codebase completo (UI, CLI, Utils)  
**Foco:** Dead code, duplicações, otimizações de locks e performance

---

## 📊 Resumo Executivo

### Estatísticas
- **Arquivos Python:** 178 total
- **Módulos Core:** 20 (cli, ui, utils, adapters, mappers)
- **Dead Code Identificado:** 5 funções/módulos
- **Duplicações:** 3 blocos
- **Otimizações Críticas:** 8 oportunidades

### Impacto Estimado
- **Performance:** 15-25% melhoria em locks e subprocess
- **Manutenibilidade:** 200+ linhas de código removível
- **Segurança:** 2 melhorias em lock management

---

## 🗑️ DEAD CODE IDENTIFICADO

### 1. **`batch_runner._detect_lock()` - NUNCA USADA**

**Arquivo:** `src/dou_snaptrack/ui/batch_runner.py` (linha 93)

```python
def _detect_lock(lock_path: Path) -> dict[str, Any] | None:
    # 40 linhas de código
    # NUNCA CHAMADA em todo o projeto
```

**Análise:**
- ✅ Função definida na linha 93
- ❌ **Zero usages** encontrados (apenas definição)
- ⚠️ Duplica funcionalidade de `detect_other_execution()` e `detect_other_ui()`

**Impacto:** 40 linhas removíveis

**Recomendação:** 🔴 **DELETAR**

---

### 2. **Duplicação: CSV Parsing em `_pid_alive_windows()`**

**Arquivo:** `src/dou_snaptrack/ui/batch_runner.py` (linhas 35-50)

```python
# Parsing CSV manual com loop de caracteres
line = stdout.splitlines()[0]
parts = []
cur = ""
in_q = False
for ch in line:
    if ch == '"':
        in_q = not in_q
    elif ch == "," and not in_q:
        parts.append(cur)
        cur = ""
        continue
    cur += ch
parts.append(cur)
```

**Problema:**
- Parsing CSV manual quando Python tem `csv.reader()`
- Código frágil e verboso
- Sem tratamento de edge cases (escaped quotes, etc)

**Solução:**
```python
import csv
import io

line = stdout.splitlines()[0]
reader = csv.reader(io.StringIO(line))
parts = next(reader, [])
```

**Impacto:** 15 linhas → 3 linhas, mais robusto

**Recomendação:** ⚠️ **REFATORAR**

---

### 3. **PowerShell Process Info - Timeout Inconsistente**

**Arquivo:** `src/dou_snaptrack/ui/batch_runner.py`

**Observação:**
```python
# Linha 186 - timeout=5
subprocess.run(ps, capture_output=True, text=True, check=False, timeout=5)

# Linha 198 - timeout=5
subprocess.run([...], capture_output=True, text=True, check=False, timeout=5)
```

**Problema:**
- Timeout de 5 segundos pode ser muito longo para operação local (tasklist/wmic)
- PowerShell CIM query pode travar em sistemas lentos
- Nenhum fallback se timeout excedido

**Solução:**
```python
# Reduzir timeout para 2s (suficiente para local queries)
timeout=2

# Adicionar fallback para timeout
try:
    out = subprocess.run(ps, ..., timeout=2)
except subprocess.TimeoutExpired:
    return {}  # Graceful degradation
```

**Impacto:** 60-70% redução em espera (5s → 2s), melhor UX

**Recomendação:** ⚠️ **OTIMIZAR**

---

### 4. **mappers/page_mapper.py - RARAMENTE USADO**

**Arquivo:** `src/dou_snaptrack/mappers/page_mapper.py`

**Análise:**
- Módulo de 150 linhas
- **Único uso:** Importado apenas por scripts de desenvolvimento (não em produção)
- Funções `map_dropdowns()` e `map_elements_by_category()` não são críticas

**Usages:**
- ❌ Não usado em `cli/`
- ❌ Não usado em `ui/`
- ✅ Usado apenas em `dev_tools/` (mapeamento experimental)

**Recomendação:** 🟡 **MOVER para dev_tools/** ou marcar como @deprecated

---

### 5. **mappers/pairs_mapper.py - Parcialmente Obsoleto**

**Arquivo:** `src/dou_snaptrack/mappers/pairs_mapper.py`

**Análise:**
- 260 linhas de código complexo
- **Uso limitado:** Apenas `filter_opts()` usado em `cli/plan_from_pairs.py`
- Funções `map_pairs()`, `select_by_text_or_attrs()`, etc não são usadas

**Situação:**
```python
# ✅ USADA
from ..mappers.pairs_mapper import filter_opts as _filter_opts

# ❌ NUNCA USADAS (200+ linhas)
- map_pairs()
- find_dropdown_by_id_or_label()
- select_by_text_or_attrs()
- wait_n2_repopulated()
- _scroll_listbox_to_end()
```

**Motivo:** Sistema de scraping migrou para `cli/plan_live.py` (mais robusto)

**Recomendação:** 
- 🟡 **Extrair** `filter_opts()` para `utils/text.py`
- 🔴 **DELETAR** resto do arquivo (200 linhas)

---

## ⚡ OTIMIZAÇÕES DE PERFORMANCE

### 1. **UI Lock - Overhead de PowerShell Desnecessário**

... (conteúdo original mantido)
