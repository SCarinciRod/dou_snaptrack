# Plan Live E-Agendas (Async) - Documentação

## 📋 Resumo

Implementação **async** do gerador de plans para o site **e-agendas**, baseada no padrão do `plan_live_async.py` (DOU).

### Arquivos Criados

1. **`src/dou_snaptrack/cli/plan_live_eagendas_async.py`** (~560 linhas)
   - Versão async que navega no site e-agendas usando Playwright
   - Detecta e interage com dropdowns Selectize.js
   - Gera combos N1→N2→N3 (Órgão → Cargo → Agente Público)

2. **`dev_tools/test_plan_eagendas_async.py`** (~75 linhas)
   - Script de teste smoke para validação
   - Configurado para limites pequenos (2×2×2) com headful + slowmo

---

## 🏗️ Arquitetura

### Diferenças entre DOU e E-Agendas

| Aspecto | DOU (plan_live_async.py) | E-Agendas (plan_live_eagendas_async.py) |
|---------|--------------------------|------------------------------------------|
| **URL** | `in.gov.br/leiturajornal` | `eagendas.cgu.gov.br` |
| **Níveis** | 2 (N1: Órgão, N2: Subordinada) | 3 (N1: Órgão, N2: Cargo, N3: Agente) |
| **Dropdown** | `<select>` nativo + custom | Selectize.js (biblioteca JS avançada) |
| **Detecção** | ID-based (`#slcOrgs`, `#slcOrgsSubs`) | Label-based ("Órgão ou entidade", "Cargo", "Agente público") |
| **Repopulação** | AJAX rápido (~800ms) | AJAX mais lento (~1500ms por nível) |

---

## 🔧 Funções Principais

### Helpers Async para Selectize.js

```python
_find_selectize_by_label_async(frame, label_text)
# Encontra controle Selectize pelo label associado
# Retorna: dict com selector, input, bbox

_is_selectize_disabled_async(selectize_control)
# Verifica se controle está desabilitado via class/aria-disabled

_open_selectize_dropdown_async(page, selectize_control, wait_ms)
# Abre dropdown clicando no input e aguarda aparecer

_get_selectize_options_async(frame, include_empty)
# Lê opções do dropdown aberto, filtrando placeholders genéricos
# Retorna: list[dict] com text, value, index, handle

_select_selectize_option_async(page, option, wait_after_ms)
# Clica na opção e aguarda AJAX completar

_read_selectize_options_for_label_async(frame, label)
# Wrapper completo: encontra → abre → lê → fecha

_select_by_label_and_text_async(frame, label, text)
# Seleciona opção específica por texto (com fallback por prefixo)
```

### Função Principal

```python
async def build_plan_eagendas_async(p, args) -> dict[str, Any]:
    """
    Gera plan de combos navegando no site e-agendas.
    
    Fluxo:
    1. Lança navegador (Chrome/Edge/fallback)
    2. Navega para eagendas.cgu.gov.br
    3. Detecta dropdowns via labels
    4. Itera N1 (Órgãos):
       - Seleciona órgão
       - Aguarda N2 (Cargos) repopular
       - Itera N2:
         - Seleciona cargo
         - Aguarda N3 (Agentes) repopular
         - Cria combos para cada agente
         - Reset para próximo cargo
    5. Retorna plan com stats
    """
```

---

## 📊 Estrutura do Plan Gerado

```json
{
  "source": "e-agendas",
  "url": "https://eagendas.cgu.gov.br/",
  "filters": {
    "select1": null,
    "pick1": null,
    "limit1": 2,
    "select2": null,
    "pick2": null,
    "limit2": 2,
    "select3": null,
    "pick3": null,
    "limit3": 2
  },
  "combos": [
    {
      "orgao_label": "Ministério da Fazenda",
      "orgao_value": "12345",
      "cargo_label": "Secretário Executivo",
      "cargo_value": "67890",
      "agente_label": "João da Silva",
      "agente_value": "11223"
    }
  ],
  "stats": {
    "total_orgaos": 2,
    "total_cargos": 4,
    "total_agentes": 8,
    "total_combos": 8
  }
}
```

---

## 🎯 Filtros Suportados

### Nível 1 (Órgãos)
- `--select1 <regex>`: Filtro regex por texto
- `--pick1 <lista>`: Lista de valores específicos
- `--limit1 <N>`: Limita a N órgãos

### Nível 2 (Cargos)
- `--select2 <regex>`
- `--pick2 <lista>`
- `--limit2 <N>`

### Nível 3 (Agentes)
- `--select3 <regex>`
- `--pick3 <lista>`
- `--limit3 <N>`

---

## 🚀 Uso

### Teste Smoke (Headful)
```bash
python dev_tools/test_plan_eagendas_async.py
```

### Via CLI (exemplo)
```bash
python -c "
from argparse import Namespace
from dou_snaptrack.cli.plan_live_eagendas_async import build_plan_eagendas_sync_wrapper

args = Namespace(
    headful=False,
    slowmo=0,
    limit1=5,
    limit2=3,
    limit3=2,
    select1=None,
    pick1=None,
    select2=None,
    pick2=None,
    select3=None,
    pick3=None,
    plan_out='planos/eagendas_custom.json',
    plan_verbose=True
)

plan = build_plan_eagendas_sync_wrapper(args)
print(f'Gerados {len(plan[\"combos\"])} combos')
"
```

### Integração com Streamlit (futuro)
```python
from dou_snaptrack.cli.plan_live_eagendas_async import build_plan_eagendas_async
from playwright.async_api import async_playwright

async with async_playwright() as p:
    plan = await build_plan_eagendas_async(p, args)
    # processar plan...
```

---

## ⚠️ Considerações

### Desafios do Selectize.js
- **Virtualização**: Dropdowns podem usar scroll virtual (endereçado com scroll completo antes da leitura)
- **AJAX lento**: Repopulação entre níveis requer waits maiores que DOU (~1500ms vs 800ms)
- **Labels variáveis**: Labels podem mudar conforme versão do site (atualmente: "Órgão ou entidade", "Cargo", "Agente público")
- **Fallback por prefixo**: Matching por texto usa fallback de 5 caracteres para robustez

### Melhorias Futuras
1. **Detecção automática de labels**: Buscar labels dinamicamente em vez de hardcoded
2. **Detecção de mudança**: Monitorar mutations DOM em vez de timeouts fixos
3. **Cache de opções**: Cachear opções já lidas para acelerar iterações
4. **Retry automático**: Implementar retry em falhas de seleção
5. **Validação de seleção**: Confirmar que seleção foi aplicada antes de prosseguir

---

## 📝 Notas de Desenvolvimento

### Diferenças vs. Versão Sync Original
- **Original** (`plan_live_eagendas.py`): Carrega de JSON estático pré-gerado
- **Async** (`plan_live_eagendas_async.py`): Navega no site e gera sob demanda

### Compatibilidade com DOU Pattern
- Reutiliza `_filter_opts` do plan_live.py
- Segue mesmo padrão de argumentos (select/pick/limit por nível)
- Browser launch com fallbacks idênticos (chrome → msedge → explicit path → default)

### Validação Necessária
- [ ] Testar com limites grandes (>100 órgãos)
- [ ] Validar performance com ~1000+ combos
- [ ] Confirmar labels no ambiente de produção
- [ ] Testar resilência a timeouts AJAX
- [ ] Validar encoding de caracteres especiais em nomes

---

## 📚 Referências

- **DOU async**: `src/dou_snaptrack/cli/plan_live_async.py`
- **DOU sync**: `src/dou_snaptrack/cli/plan_live.py`
- **E-Agendas sync**: `src/dou_snaptrack/cli/plan_live_eagendas.py`
- **Selectize helpers**: `src/dou_snaptrack/mappers/eagendas_selectize.py`
- **Browser utils**: `src/dou_snaptrack/utils/browser.py`

---

**Status**: ✅ Implementado e pronto para testes
**Autor**: GitHub Copilot
**Data**: 11/11/2025
