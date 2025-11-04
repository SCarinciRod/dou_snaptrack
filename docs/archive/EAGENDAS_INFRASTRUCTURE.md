# E-Agendas: Infraestrutura de Mapeamento e Plan Live

## 📋 Visão Geral

O módulo e-agendas mapeia a hierarquia **Órgão → Cargo → Agente Público** do site e-agendas do governo federal.

### Hierarquia de 3 Níveis

```
N1: Órgão (227 opções)
  └─ N2: Cargo (varia por órgão)
       └─ N3: Agente Público (varia por cargo)
```

**Diferença do DOU**: O DOU tem 2 níveis (Órgão → Unidade), e-agendas tem 3 níveis.

---

## 🗂️ Estrutura de Arquivos

### Módulos Core

```
src/dou_snaptrack/
├── mappers/
│   ├── eagendas_mapper.py          # Mapper básico (N1, N2)
│   ├── eagendas_pairs.py           # Mapper hierárquico (N1 → N2 → N3)
│   └── eagendas_selectize.py       # Camada de interação Selectize.js
│
└── cli/
    └── plan_live_eagendas.py       # Gerador de plans para lote
```

### Scripts de Execução

```
scripts/
├── map_eagendas_full.py            # Mapeamento completo (gera artefato)
├── test_pairs_corrected.py         # Teste com limites
└── test_plan_eagendas.py           # Teste de geração de plans
```

### Artefatos Gerados

```
artefatos/
├── pairs_eagendas_YYYYMMDD_HHMMSS.json    # Mapeamento timestamped
└── pairs_eagendas_latest.json              # Última versão (symlink lógico)
```

### Plans de Processamento

```
planos/
├── eagendas_plan_full.json         # Plan completo (todos os pares)
├── eagendas_plan_small.json        # Plan teste (2 órgãos, 3 cargos, 2 agentes)
├── eagendas_plan_medium.json       # Plan médio (5 órgãos)
└── eagendas_plan_specific.json     # Plan específico (1 órgão)
```

---

## 🔧 Tecnologia Frontend

### Selectize.js

O e-agendas usa **Selectize.js** para dropdowns, que tem comportamento especial:

- **N1 e N2**: Dropdowns visíveis (`display: block`)
- **N3**: Container oculto (`display: none`) mas opções visíveis dentro dele

#### Módulo `eagendas_selectize.py`

7 funções especializadas para interagir com Selectize:

1. **`get_selectize_options()`** - Coleta opções de dropdown
   - Prioriza dropdowns visíveis
   - Fallback para último dropdown oculto com opções (caso N3)
   - Suporta `exclude_patterns` para filtrar opções indesejadas

2. **`find_selectize_by_label()`** - Localiza Selectize por label HTML

3. **`open_selectize_dropdown()`** - Abre dropdown para seleção

4. **`select_selectize_option()`** - Seleciona opção por texto

5. **`close_selectize_dropdown()`** - Fecha dropdown

6. **`find_and_check_ativos_checkbox()`** - Marca checkbox "Ativos"

7. **`wait_for_ajax()`** - Aguarda carregamento AJAX (2-3 segundos)

---

## 📊 Artefato de Pares

### Estrutura JSON

```json
{
  "source": "e-agendas",
  "timestamp": "2025-01-17T10:30:00",
  "stats": {
    "total_orgaos": 227,
    "total_cargos": 1500,
    "total_agentes": 5000
  },
  "hierarchy": [
    {
      "orgao": {
        "value": "AGÊNCIA ESPACIAL BRASILEIRA",
        "label": "AGÊNCIA ESPACIAL BRASILEIRA"
      },
      "cargos": [
        {
          "cargo": {
            "value": "ASSESSOR DO PRESIDENTE DA AEB",
            "label": "ASSESSOR DO PRESIDENTE DA AEB"
          },
          "agentes": [
            {
              "value": "JOÃO DA SILVA",
              "label": "JOÃO DA SILVA"
            },
            {
              "value": "MARIA SANTOS",
              "label": "MARIA SANTOS"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 🚀 Uso

### 1. Gerar Artefato de Pares

```powershell
# Mapeamento COMPLETO (todos os 227 órgãos - pode levar horas!)
python scripts/map_eagendas_full.py

# Teste com limites (1 órgão, 2 cargos)
python scripts/test_pairs_corrected.py
```

**Saída**: `artefatos/pairs_eagendas_latest.json`

### 2. Gerar Plans de Processamento

```powershell
# Testar geração de plans
python scripts/test_plan_eagendas.py

# Ou usar módulo diretamente
python -c "
from src.dou_snaptrack.cli.plan_live_eagendas import build_plan_eagendas, save_plan_eagendas

plan = build_plan_eagendas(
    limit_orgaos=5,
    limit_cargos_per_orgao=10,
    verbose=True
)

save_plan_eagendas(plan, 'planos/meu_plan.json', verbose=True)
"
```

**Saída**: `planos/*.json`

### 3. Usar Plan no Código

```python
import json
from pathlib import Path

# Carregar plan
plan = json.loads(Path("planos/eagendas_plan_small.json").read_text(encoding='utf-8'))

# Iterar combos
for combo in plan["combos"]:
    orgao = combo["orgao_label"]
    cargo = combo["cargo_label"]
    agente = combo["agente_label"]
    
    print(f"Processar: {orgao} → {cargo} → {agente}")
    # TODO: Executar scraping/processamento
```

---

## 🎯 Filtros Especiais

### "Todos os ocupantes"

O e-agendas exibe uma opção genérica **"Todos os ocupantes"** no N3 (agentes).

**Solução**: Filtramos automaticamente usando `exclude_patterns`:

```python
agentes = get_selectize_options(
    frame,
    exclude_patterns=["todos os ocupantes"]
)
```

Isso garante apenas agentes reais (não labels genéricos).

---

## 📈 Estatísticas Esperadas

Baseado em teste inicial (1 órgão = AEB):

| Nível | Quantidade |
|-------|------------|
| N1    | 227 órgãos |
| N2    | ~5-20 cargos por órgão |
| N3    | ~1-5 agentes por cargo |

**Estimativa conservadora**:
- 227 órgãos × 10 cargos/órgão × 2 agentes/cargo = **~4.540 combos**

**Estimativa otimista**:
- 227 órgãos × 15 cargos/órgão × 3 agentes/cargo = **~10.215 combos**

---

## ⚠️ Problemas Resolvidos

### 1. Sync/Async Conflict
**Erro**: `Playwright Sync API inside asyncio loop`  
**Solução**: Removido setup de event loop em `browser.py`

### 2. N2 Retornando Vazio
**Erro**: Detectava dropdown errado (N0 em vez de N2)  
**Solução**: Iterar todos dropdowns e priorizar visíveis

### 3. N3 Retornando Vazio
**Erro**: Container tem `display: none`  
**Solução**: Fallback para último dropdown oculto com opções visíveis

### 4. "Todos os ocupantes" Incluído
**Erro**: Opção genérica contada como agente  
**Solução**: Parâmetro `exclude_patterns` filtra por substring

---

## 🔮 Próximos Passos

1. **Mapeamento Completo**
   - [ ] Rodar `map_eagendas_full.py` (sem limites)
   - [ ] Validar artefato completo
   - [ ] Backup timestamped

2. **Integração UI**
   - [ ] Adicionar e-agendas na UI Streamlit
   - [ ] Seletor de órgãos/cargos/agentes
   - [ ] Preview de combos

3. **Executor de Lote**
   - [ ] Criar `eagendas_batch_executor.py`
   - [ ] Processar combos do plan
   - [ ] Gerar relatórios

4. **Testes**
   - [ ] Test suite completo
   - [ ] Validação de hierarquia
   - [ ] Performance benchmarks

---

## 📚 Referências

- **Plan Live DOU**: `src/dou_snaptrack/cli/plan_live_async.py`
- **Selectize.js**: https://selectize.dev/
- **E-Agendas**: https://www.gov.br/e-agendas/

---

**Criado**: 2025-01-17  
**Última Atualização**: 2025-01-17  
**Status**: ✅ Infraestrutura completa, pronta para mapeamento full
