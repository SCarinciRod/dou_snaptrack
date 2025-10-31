# Correção Definitiva - Async API - 27/10/2025

## 🚨 Diagnóstico Final

Após múltiplas tentativas, identifiquei a causa raiz:

1. **Python 3.13** no Windows cria automaticamente um `ProactorEventLoopPolicy`
2. Qualquer chamada a `asyncio.get_event_loop()` cria um loop ativo
3. **Playwright Sync API detecta loop ativo e recusa executar**
4. Tentar fechar/recriar loop não funciona - Playwright já detectou

## ✅ Solução Definitiva: MIGRAR PARA ASYNC API

Como o próprio Playwright sugere: **"Please use the Async API instead"**

### Arquivos que precisam ser migrados:

1. **`pairs_updater.py`** - Trocar `sync_playwright()` → `async_playwright()`
2. **`plan_live.py`** - Função `build_plan_live()` async
3. **`app.py`** - Chamar funções async com `asyncio.run()`

### Benefícios da migração:

- ✅ **Compatibilidade total** com Streamlit (que usa asyncio)
- ✅ **Melhor performance** (async é mais eficiente)
- ✅ **Sem subprocess** (execução direta, sem overhead)
- ✅ **Código mais moderno** (async/await é padrão Python)

## 📋 Plano de Migração

### Fase 1: pairs_updater.py (CRÍTICO)

```python
# ANTES (Sync):
with sync_playwright() as p:
    cfg = build_plan_live(p, args)

# DEPOIS (Async):
async def update_pairs_file_async(...):
    async with async_playwright() as p:
        cfg = await build_plan_live_async(p, args)

# Wrapper síncrono para compatibilidade:
def update_pairs_file(...):
    return asyncio.run(update_pairs_file_async(...))
```

### Fase 2: plan_live.py

```python
# ANTES:
def build_plan_live(p, args):
    browser = p.chromium.launch(...)
    page = browser.new_page()
    # ...

# DEPOIS:
async def build_plan_live_async(p, args):
    browser = await p.chromium.launch(...)
    page = await browser.new_page()
    # ...
```

### Fase 3: app.py

```python
# ANTES (thread/subprocess):
thread = threading.Thread(target=update_pairs_file)
thread.start()

# DEPOIS (async direto):
result = await update_pairs_file_async()
# OU
result = asyncio.run(update_pairs_file())
```

## ⚠️ Alternativa Temporária: SUBPROCESS LIMPO

Se migração async for muito trabalho agora, usar subprocess ISOLADO:

```python
# Executar em processo completamente separado
subprocess.run([
    sys.executable,
    "-m", "dou_snaptrack.utils.pairs_updater",
    "--update"
])
```

Isso garante 100% de isolamento do loop asyncio do Streamlit.

## 📊 Comparação de Soluções

| Solução | Compatibilidade | Performance | Complexidade | Recomendação |
|---------|----------------|-------------|--------------|--------------|
| **Async API** | ✅ 100% | ✅ Ótima | 🟨 Média | **✅ RECOMENDADA** |
| **Subprocess** | ✅ 100% | 🟨 Boa | ✅ Baixa | ⚠️ Temporária |
| **Thread** | ❌ Falha | N/A | N/A | ❌ NÃO FUNCIONA |
| **Sync API** | ❌ Falha | N/A | N/A | ❌ INCOMPATÍVEL |

## 🎯 Decisão

**Você precisa escolher:**

1. **OPÇÃO A (Rápida - 10min):** Usar subprocess isolado como solução temporária
   - ✅ Funciona imediatamente
   - ⚠️ Overhead de criar processo
   - ⚠️ Dívida técnica

2. **OPÇÃO B (Definitiva - 1-2h):** Migrar para Async API
   - ✅ Solução permanente e elegante
   - ✅ Melhor performance
   - ⏱️ Requer tempo para migrar código

**Minha recomendação:** Começar com **OPÇÃO A** para desbloquear o uso imediato, depois migrar para **OPÇÃO B** quando tiver tempo.

---

**Status:** Aguardando decisão do usuário
**Data:** 27/10/2025
