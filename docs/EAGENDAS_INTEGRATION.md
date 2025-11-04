# Integração do E-Agendas ao Projeto DOU SnapTrack

## Resumo das Modificações

Este documento descreve as modificações realizadas para expandir o escopo do projeto para incluir o site e-agendas da CGU.

---

## 1. Ajustes em `src/dou_snaptrack/utils/browser.py`

### ✅ Adicionada função `build_url()`

Função genérica para construir URLs de diferentes sites do projeto:

```python
def build_url(site: str, path: str | None = None, **params) -> str:
    """Constrói URL para diferentes sites do projeto.
    
    Args:
        site: Nome do site ('dou' ou 'eagendas')
        path: Caminho adicional na URL (opcional)
        **params: Parâmetros de query string
    
    Returns:
        URL completa
    
    Examples:
        build_url('dou', date='01-01-2025', secao='DO1')
        build_url('eagendas', path='/agendas/list')
    """
```

**Uso:**
- `build_url('dou', date='01-01-2025', secao='DO1')` → URL do DOU
- `build_url('eagendas')` → URL base do e-agendas
- `build_url('eagendas', path='/agendas/list')` → URL específica do e-agendas

---

## 2. Ajustes em `src/dou_snaptrack/constants.py`

### ✅ Constantes específicas do e-agendas

```python
# URL do E-Agendas
EAGENDAS_URL = "https://eagendas.cgu.gov.br/"

# IDs específicos do E-Agendas (a serem mapeados conforme necessário)
EAGENDAS_LEVEL_IDS = {
    1: [],  # A definir após mapeamento
    2: [],  # A definir após mapeamento
}

# Seletores específicos do E-Agendas
EAGENDAS_SELECTORS = {
    "search_button": ["Pesquisar", "Buscar", "Procurar", "Search"],
}
```

**Próximos passos:**
- Executar `test_eagendas_map.py` para mapear os IDs reais dos dropdowns
- Atualizar `EAGENDAS_LEVEL_IDS` com os IDs encontrados

---

## 3. Melhorias em `src/dou_snaptrack/mappers/eagendas_pairs.py`

### ✅ Implementação robusta com fallbacks

- **Adapters de compatibilidade**: Unificam assinaturas entre `dou_utils` e código interno
- **Fallbacks completos**: Implementações alternativas quando `dou_utils` não está disponível
- **Logging detalhado**: Rastreamento de erros e uso de fallbacks
- **Função `map_eagendas_dropdowns()`**: Mapeia dropdowns específicos do e-agendas

**Características:**
- Compatível com diferentes versões de `dou_utils`
- Não quebra quando dependências externas faltam
- Logs informativos para debugging

---

## 4. Estrutura dos Módulos E-Agendas

```
src/dou_snaptrack/mappers/
├── eagendas_mapper.py    # Extração de labels para inputs do e-agendas
├── eagendas_pairs.py     # Lógica de interação com dropdowns do e-agendas
├── page_mapper.py        # Mapeamento genérico de elementos (reutilizável)
└── pairs_mapper.py       # Mapeamento de pares N1-N2 do DOU (base para e-agendas)
```

---

## 5. Script de Teste: `scripts/test_eagendas_map.py`

### ✅ Corrigido import de `build_url`

O script agora importa corretamente a função `build_url`:

```python
from dou_snaptrack.utils.browser import launch_browser, new_context, goto, build_url
```

**Execução:**
```powershell
python scripts/test_eagendas_map.py
```

**Saída esperada:**
- Arquivo `test_eagendas_map.json` com mapeamento completo dos elementos do e-agendas

---

## 6. Próximos Passos para Completar a Integração

### 6.1. Mapeamento Inicial
1. ✅ Executar `test_eagendas_map.py` para mapear elementos do e-agendas
2. ⏳ Analisar `test_eagendas_map.json` para identificar:
   - IDs dos dropdowns principais
   - Estrutura dos filtros disponíveis
   - Seletores específicos

### 6.2. Atualização de Constantes
1. ⏳ Atualizar `EAGENDAS_LEVEL_IDS` em `constants.py` com IDs reais
2. ⏳ Adicionar seletores específicos em `EAGENDAS_SELECTORS`

### 6.3. Implementação da Lógica de Negócio
1. ⏳ Criar função `map_eagendas_pairs()` similar a `map_pairs()` do DOU
2. ⏳ Adaptar lógica de navegação para o fluxo do e-agendas
3. ⏳ Implementar extração de dados específicos do e-agendas

### 6.4. Integração com UI
1. ⏳ Adicionar opção de seleção entre DOU e e-agendas na UI
2. ⏳ Adaptar formulários para parâmetros específicos do e-agendas
3. ⏳ Criar templates de relatório para e-agendas

### 6.5. Testes
1. ⏳ Criar casos de teste específicos para e-agendas
2. ⏳ Validar interação com dropdowns
3. ⏳ Testar geração de relatórios

---

## 7. Arquitetura Unificada

```
DOU SnapTrack (expandido)
│
├── Sites Suportados
│   ├── DOU (Diário Oficial da União)
│   └── E-Agendas (CGU)
│
├── Módulos Compartilhados
│   ├── browser.py      → Navegação (build_url, goto, launch_browser)
│   ├── dom.py          → Manipulação DOM (find_best_frame, is_select)
│   └── page_mapper.py  → Mapeamento genérico de elementos
│
├── Módulos Específicos DOU
│   └── pairs_mapper.py → Lógica de pares N1-N2 do DOU
│
└── Módulos Específicos E-Agendas
    ├── eagendas_mapper.py → Extração de labels
    └── eagendas_pairs.py  → Lógica de interação com dropdowns
```

---

## 8. Comandos Úteis

```powershell
# Testar mapeamento do e-agendas
python scripts/test_eagendas_map.py

# Ver resultado do mapeamento
cat test_eagendas_map.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Verificar erros de lint
python -m pylint src/dou_snaptrack/mappers/eagendas_*.py

# Executar UI para testar integração
python -m streamlit run src/dou_snaptrack/ui/app.py
```

---

## 9. Checklist de Validação

- [x] Função `build_url()` implementada e testável
- [x] Constantes do e-agendas criadas
- [x] Módulo `eagendas_pairs.py` com fallbacks robustos
- [x] Script de teste `test_eagendas_map.py` corrigido
- [ ] Mapeamento inicial executado e analisado
- [ ] IDs dos dropdowns identificados
- [ ] Lógica de navegação implementada
- [ ] Integração com UI concluída
- [ ] Testes end-to-end executados

---

## 10. Observações Importantes

### Compatibilidade
- O código mantém **retrocompatibilidade total** com a funcionalidade DOU existente
- Fallbacks garantem funcionamento mesmo sem `dou_utils` completo
- Logs informativos facilitam debugging

### Warnings do Linter
Os warnings sobre "Function declaration obscured" em `eagendas_pairs.py` são **intencionais**:
- Padrão try/except com definições alternativas
- Permite graceful degradation quando dependências faltam
- Não afeta funcionalidade

### Performance
- Navegação assíncrona disponível (`goto_async`, `find_best_frame_async`)
- Timeouts configuráveis via ambiente
- Cache de frames para otimização

---

**Status:** ✅ Fundação completa - Pronto para mapeamento e implementação de lógica de negócio

**Última atualização:** 2025-11-03
