# Solução: Adapter Pattern para E-Agendas Document

## Problema Original

**Sintoma**: "❌ Módulo python-docx não encontrado ou corrompido" - erro de lxml ao tentar gerar documentos E-Agendas, mesmo após reinstalação do pacote.

**Causa Raiz**: Python cacheia imports que falharam. Quando `from lxml import etree` falha pela primeira vez (lxml corrompido), o Python armazena esse erro em cache. Mesmo após reinstalar lxml, qualquer tentativa de `import` direto no código da UI continua usando o import falhado do cache.

**Por que DOU funcionava mas E-Agendas não**: 
- DOU usa **adapter pattern** com try/except no nível do módulo
- E-Agendas importava diretamente a função de geração de documento
- O adapter do DOU retorna `None` quando o import falha, sem cachear o erro
- Import direto cacheia o erro e não permite retry mesmo após fix

## Solução Implementada

### 1. Criado Adapter para E-Agendas

**Arquivo**: `src/dou_snaptrack/adapters/eagendas_adapter.py`

```python
from collections.abc import Callable
from typing import Any

generate_eagendas_document_from_json: Callable[..., Any] | None

try:
    from dou_utils.eagendas_document import generate_eagendas_document_from_json as _gen
    generate_eagendas_document_from_json = _gen
except Exception:
    generate_eagendas_document_from_json = None  # Silent failure - não cacheia erro
```

**Padrão**: Igual ao adapter do DOU em `src/dou_snaptrack/adapters/utils.py`

**Comportamento**:
- Se lxml estiver OK: importa a função normalmente
- Se lxml estiver corrompido: retorna `None` sem cachear o erro
- Permite retry após reinstalar lxml (basta recarregar a UI)

### 2. Modificado UI para Usar Adapter

**Arquivo**: `src/dou_snaptrack/ui/app.py` (linhas ~1781-1841)

**Antes** (import direto):
```python
from dou_utils.eagendas_document import generate_eagendas_document_from_json

# ... código ...

try:
    result = generate_eagendas_document_from_json(...)
except ImportError:
    st.error("Módulo corrompido")
```

**Depois** (via adapter):
```python
from dou_snaptrack.adapters.eagendas_adapter import generate_eagendas_document_from_json

# Verificar se adapter retornou None (lxml corrompido)
if generate_eagendas_document_from_json is None:
    st.error("❌ **Módulo python-docx não encontrado ou corrompido**")
    st.warning("🔧 Este é um problema comum no Windows com lxml corrompido")
    
    with st.expander("🔍 Detalhes do erro"):
        st.code("O módulo eagendas_document não pôde ser carregado (lxml corrompido)")
    
    # Mostrar comandos de fix
    fix_cmd = f'"{sys.executable}" -m pip uninstall -y lxml python-docx\\n"{sys.executable}" -m pip install --no-cache-dir lxml python-docx'
    st.code(fix_cmd, language="powershell")
    st.caption("Execute os comandos acima no PowerShell, reinicie a UI e tente novamente")
else:
    # Adapter funcionou, função disponível
    try:
        result = generate_eagendas_document_from_json(
            json_path=json_to_use,
            out_path=out_path,
            include_metadata=True,
            title=doc_title
        )
        st.success("✅ Documento gerado com sucesso!")
        # ... mostrar métricas e download ...
    except Exception as e:
        st.error(f"❌ Erro ao gerar documento: {e}")
        with st.expander("🔍 Traceback completo"):
            import traceback
            st.code(traceback.format_exc())
```

### 3. Estrutura de Indentação

**CRÍTICO**: A estrutura correta para adapter pattern com try/except aninhado:

```python
if adapter_function is None:                    # 16 espaços (4 níveis)
    # Mostrar erro e comandos de fix           # 20 espaços
else:                                           # 16 espaços
    try:                                        # 20 espaços (5 níveis)
        # Gerar caminhos                        # 24 espaços
        if is_example:                          # 24 espaços
            out_path = ...                      # 28 espaços
        
        with st.spinner(...):                   # 24 espaços
            result = function(...)              # 28 espaços (parâmetros: 32)
        
        st.success(...)                         # 24 espaços
        st.metric(...)                          # 24 espaços
        
        # Download button                       # 24 espaços
        with open(...) as f:                    # 24 espaços
            st.download_button(...)             # 28 espaços
        
        # Persistence                           # 24 espaços
        try:                                    # 24 espaços
            with open(...) as _df:              # 28 espaços
                st.session_state[...] = ...     # 32 espaços
        except Exception:                       # 24 espaços
            pass                                # 28 espaços
    
    except Exception as e:                      # 20 espaços (mesmo nível do try)
        st.error(...)                           # 24 espaços
        with st.expander(...):                  # 24 espaços
            st.code(...)                        # 28 espaços
```

**Erros comuns corrigidos**:
- Blocos de download/persistence estavam em 20 espaços (ERRADO) → movidos para 24 espaços (dentro do try)
- Duplicação de `except ImportError` e `except Exception` → removidos e substituídos por único `except Exception`
- Emoji corrompido `�` em string → substituído por emoji UTF-8 correto `🔍`

## Testes Realizados

### 1. Teste com lxml Corrompido
```bash
# Adapter detecta lxml corrompido
python -c "from dou_snaptrack.adapters.eagendas_adapter import generate_eagendas_document_from_json; print(generate_eagendas_document_from_json)"
# Output: None (não crash!)
```

**Resultado UI**: Mostra mensagem de erro clara com comandos de fix, não trava a aplicação.

### 2. Teste com lxml OK
```bash
# Reinstalar lxml
"C:\Projetos\.venv\Scripts\python.exe" -m pip uninstall -y lxml python-docx
"C:\Projetos\.venv\Scripts\python.exe" -m pip install --no-cache-dir lxml python-docx

# Adapter importa com sucesso
python -c "from dou_snaptrack.adapters.eagendas_adapter import generate_eagendas_document_from_json; print('OK' if generate_eagendas_document_from_json else 'FAIL')"
# Output: OK
```

**Resultado UI**: Gera documento DOCX com sucesso, mostra métricas (agentes/eventos), oferece download.

### 3. Validação de Sintaxe
```bash
python -m py_compile c:\Projetos\src\dou_snaptrack\ui\app.py
# Output: (sem erros)
```

## Fluxo de Correção para Usuários

1. **Erro aparece**: "❌ Módulo python-docx não encontrado ou corrompido"
2. **Copiar comandos** mostrados na UI (botão "🔍 Detalhes do erro")
3. **Executar no PowerShell**:
   ```powershell
   "C:\Projetos\.venv\Scripts\python.exe" -m pip uninstall -y lxml python-docx
   "C:\Projetos\.venv\Scripts\python.exe" -m pip install --no-cache-dir lxml python-docx
   ```
4. **Recarregar UI** (Ctrl+R no navegador ou fechar/abrir)
5. **Retry**: Adapter vai re-importar com lxml novo, documento será gerado

**Vantagem**: Não precisa reiniciar Python/Streamlit - apenas recarregar página.

## Arquitetura

```
app.py (UI)
    ↓
eagendas_adapter.py (isolamento de import)
    ↓ (try/except no módulo)
dou_utils/eagendas_document.py
    ↓
lxml.etree (pode estar corrompido)
```

**Isolamento**: Se lxml falha, erro fica contido no adapter (retorna `None`). UI continua funcionando e mostra mensagem amigável.

**Referência**: Padrão usado em `src/dou_snaptrack/adapters/utils.py` para DOU (comprovadamente funcional).

## Commits Relacionados

1. **Criação do adapter**: `src/dou_snaptrack/adapters/eagendas_adapter.py`
2. **Refatoração da UI**: `src/dou_snaptrack/ui/app.py` (linhas 1781-1841)
3. **Documentação**: Este arquivo

## Lições Aprendidas

1. **Python cacheia imports falhados**: `importlib.reload()` não resolve porque erro já está no cache
2. **Adapter pattern é a solução**: Try/except no nível do módulo evita cache de erros
3. **Indentação é crítica**: Em estruturas `if/else/try/except` aninhadas, erros de indentação causam cascata
4. **Referência é ouro**: DOU já tinha a solução correta implementada - bastava replicar
5. **Test-driven fix**: Validar com py_compile e import direto antes de testar UI completa

## Próximos Passos (Opcional)

- [ ] Aplicar mesmo padrão para outros módulos que dependem de lxml (se houver)
- [ ] Adicionar testes unitários para adapter pattern
- [ ] Documentar adapter pattern no README principal
- [ ] Criar script de diagnóstico para verificar saúde do lxml no ambiente

---
**Data**: 2025-11-13  
**Versão**: 1.0  
**Status**: ✅ Implementado e testado
# =============================================================================
# MODULE DOCUMENTATION AND CONTRACTS
# =============================================================================
#
# Streamlit UI for SnapTrack DOU.
#
# ═══════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE MODULARIZATION PLAN
# ═══════════════════════════════════════════════════════════════════════════════
#
# PHASE 1: UI Layer Split (ui/)
# ─────────────────────────────
# ui/
# ├── __init__.py              # Re-exports main entry point
# ├── app.py                   # Main Streamlit layout and tabs (slim ~500 lines)
# ├── state.py                 # PlanState, EAgendasState, SessionManager (~150 lines)
# ├── subprocess_utils.py      # _execute_script_and_read_result (~100 lines)
# ├── dou_fetch.py             # _plan_live_fetch_n1_options, _plan_live_fetch_n2 (~400 lines)
# ├── eagendas_fetch.py        # _eagendas_fetch_hierarchy (~300 lines)
# ├── plan_editor.py           # Plan editor with pagination (~600 lines)
# ├── batch_executor.py        # Batch execution UI (from TAB DOU) (~300 lines)
# ├── report_generator.py      # Bulletin generation (~200 lines)
# ├── maintenance.py           # Pairs file maintenance sidebar (~150 lines)
# └── components.py            # Reusable widgets: _render_hierarchy_selector, etc.
#
# PHASE 2: Shared Utilities Consolidation (utils/)
# ─────────────────────────────────────────────────
# Current state: utils/ has good separation, but some overlap with dou_utils/
#
# RECOMMENDED MERGE/CONSOLIDATION:
# ├── utils/browser.py         # ✓ Keep - URL builders, async page helpers
# ├── utils/text.py            # ✓ Keep - sanitize_filename, text normalization
# ├── utils/parallel.py        # ✓ Keep - recommend_parallel, pool management
# ├── utils/pairs_updater.py   # ✓ Keep - pairs file management
# ├── utils/selectize.py       # → MERGE with mappers/eagendas_selectize.py
# ├── utils/dom.py             # → MOVE to dou_utils/page_utils.py (find_best_frame_async)
# ├── utils/wait_utils.py      # → MERGE with dou_utils/page_utils.py
# └── utils/eagendas_calendar.py # ✓ Keep - calendar-specific logic
#
# PHASE 3: CLI Layer Cleanup (cli/)
# ──────────────────────────────────
# Current state: Good structure, but some redundancy
#
# OBSERVATIONS:
# ├── cli/plan_live.py           # Sync version - consider deprecating
# ├── cli/plan_live_async.py     # Async version - PRIMARY, keep
# ├── cli/plan_live_eagendas.py  # → MERGE with plan_live_eagendas_async.py
# ├── cli/batch.py               # ✓ Keep - core batch runner
# ├── cli/reporting.py           # ✓ Keep - aggregation and reports
# └── cli/runner.py              # Worker entry - review for consolidation
#
# PHASE 4: dou_utils Consolidation
# ────────────────────────────────
# dou_utils/ has many small files - consider grouping:
#
# RECOMMENDED STRUCTURE:
# dou_utils/
# ├── __init__.py
# ├── core/                    # ✓ Keep as-is
# │   ├── combos.py
# │   ├── dropdown_actions.py
# │   ├── option_filter.py
# │   ├── polling.py
# │   └── sentinel_utils.py
# ├── services/                # ✓ Keep as-is
# │   ├── cascade_service.py
# │   ├── edition_runner_service.py
# │   ├── multi_level_cascade_service.py
# │   └── planning_service.py
# ├── page.py                  # ← MERGE: page_utils.py + wait helpers
# ├── text.py                  # ← MERGE: text_cleaning.py + summary_utils.py
# ├── selectors.py             # ✓ Keep - centralized selectors
# ├── models.py                # ✓ Keep - data models
# └── log_utils.py             # ✓ Keep - logging configuration
#
# FILES TO DEPRECATE/MERGE:
# ├── dropdown_utils.py        # → core/dropdown_actions.py
# ├── dropdown_strategies.py   # → core/dropdown_actions.py
# ├── selection_utils.py       # → core/dropdown_actions.py
# ├── query_utils.py           # → services/planning_service.py
# ├── detail_utils.py          # → content_fetcher.py
# ├── enrich_utils.py          # → content_fetcher.py
# ├── dedup_state.py           # → core/sentinel_utils.py
#
# PHASE 5: Constants Centralization
# ──────────────────────────────────
# Current: constants.py exists but some constants scattered
#
# CONSOLIDATE TO constants.py:
# - RESULT_JSON_ENV from app.py
# - ALLOW_TLS_BYPASS_ENV from app.py
# - DEFAULT_SUBPROCESS_TIMEOUT from app.py
# - All URL bases (BASE_DOU, EAGENDAS_URL)
# - All selector IDs (LEVEL_IDS, EAGENDAS_LEVEL_IDS)
# - Cookie button texts
#
# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY ORDER FOR REFACTORING
# ═══════════════════════════════════════════════════════════════════════════════
#
# HIGH PRIORITY (Do First):
# 1. Extract ui/state.py - PlanState, EAgendasState (reduces app.py by ~200 lines)
# 2. Extract ui/subprocess_utils.py - subprocess helper (reduces app.py by ~100 lines)
# 3. Consolidate constants to constants.py
#
# MEDIUM PRIORITY:
# 4. Extract ui/dou_fetch.py - N1/N2 fetch functions
# 5. Extract ui/eagendas_fetch.py - hierarchy fetch
# 6. Merge dou_utils dropdown modules
#
# LOW PRIORITY (Future):
# 7. Extract ui/plan_editor.py
# 8. Extract ui/batch_executor.py
# 9. Full dou_utils consolidation
#
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE CONTRACTS AND ENVIRONMENT FLAGS
# ═══════════════════════════════════════════════════════════════════════════════
#
# SUBPROCESS CONTRACT (RESULT_JSON_PATH):
# ───────────────────────────────────────
# Child scripts MUST write their final JSON payload to the path provided in
# the environment variable `RESULT_JSON_PATH` (set by the parent). Format:
#     {"success": bool, "options": [...], "error": "..."}
#
# ENVIRONMENT FLAGS:
# ──────────────────
# UI Configuration:
#   - DOU_UI_ALLOW_TLS_BYPASS  : (1/true/yes) bypass TLS for corporate proxies
#   - DOU_UI_SUBPROCESS_TIMEOUT: timeout in seconds (default: 120)
#   - DOU_UI_LOG_LEVEL         : logging level (default: INFO)
#   - DOU_UI_LOGO_MODE         : "corner" or "sidebar"
#   - DOU_UI_PORT              : Streamlit port (default: 8501)
#
# Batch/Worker Configuration:
#   - DOU_POOL                 : "thread" or "subprocess" for workers
#   - DOU_PREFER_EDGE          : (1) prefer Edge over Chrome
#   - DOU_FAST_MODE            : (1) skip detail scraping
#
# Playwright Configuration:
#   - PLAYWRIGHT_BROWSERS_PATH : browser cache location (.venv/pw-browsers)
#   - PLAYWRIGHT_CHROME_PATH   : explicit Chrome executable path
#   - CHROME_PATH              : fallback Chrome path
#
# =============================================================================


# =============================================================================
# SECTION: DOU LIVE FETCH (N1/N2 dropdowns)
# Functions extracted to: dou_snaptrack.ui.dou_fetch
# Imports: _plan_live_fetch_n1_options, _plan_live_fetch_n2, _prepare_subprocess_env,
#          _make_error, _find_system_browser_exe
# =============================================================================