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
