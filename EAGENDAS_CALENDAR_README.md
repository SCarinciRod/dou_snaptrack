# E-Agendas: Navegação de Calendário e Extração de Compromissos

## 📋 Resumo

Implementação completa para interação com o **calendário do e-agendas** após seleção de filtros (Órgão → Cargo → Agente Público).

### Arquivos Criados

1. **`src/dou_snaptrack/utils/eagendas_calendar.py`** (~600 linhas)
   - Módulo completo para navegação no calendário FullCalendar.js
   - Detecção de dias com eventos
   - Extração de compromissos
   - Alternância entre visualizações (Mês/Dia/Semana/Lista)

2. **`dev_tools/test_eagendas_full_flow.py`** (~140 linhas)
   - Teste end-to-end completo
   - Seleção → Calendário → Extração → Relatório

---

## 🎯 Funcionalidades Implementadas

### 1. Confirmação de Seleção
```python
click_mostrar_agenda_async(page, wait_calendar_ms=3000)
```
- Detecta botão "Mostrar agenda" após seleções N1/N2/N3
- Clica e aguarda calendário carregar
- Valida que calendário apareceu

### 2. Navegação entre Visualizações
```python
switch_calendar_view_async(page, target_view: "month"|"week"|"day"|"list")
```
- Alterna entre Mês, Semana, Dia, Lista
- Detecta visualização atual
- Aguarda transição completar

### 3. Detecção de Dias com Eventos
```python
get_days_with_events_async(page, year, month)
```
- Varre calendário em visualização "Mês"
- Identifica dias com compromissos (via classes `.fc-event`)
- Retorna lista com data, handle, link clicável

### 4. Abertura de Dia Específico
```python
click_calendar_day_async(page, day_date="2025-11-15")
```
- Clica no dia no calendário
- Aguarda transição para visualização "Dia"
- Valida que mudou de view

### 5. Extração de Compromissos
```python
extract_day_events_async(page, day_date)
```
- Extrai eventos da visualização "Dia"
- Captura: título, horário, tipo, detalhes
- Retorna lista estruturada

### 6. Fluxo Completo por Período
```python
collect_events_for_period_async(page, start_date, end_date)
```
- Detecta todos os dias com eventos no período
- Itera sobre cada dia:
  - Clica → Extrai → Volta para Mês
- Retorna dict: `{"2025-11-15": [evento1, evento2], ...}`

### 7. Formatação de Relatório
```python
format_events_report(events_by_day)
```
- Gera relatório legível
- Agrupa por data
- Mostra estatísticas totais

---

## 🏗️ Arquitetura Técnica

### FullCalendar.js Detection

O e-agendas usa **FullCalendar.js**, biblioteca JS avançada para calendários. Detectamos elementos via:

| Elemento | Seletores | Propósito |
|----------|-----------|-----------|
| **Calendário** | `#divcalendar`, `.fc-view-container` | Container principal |
| **Visualização Mês** | `.fc-month-view`, `.fc-dayGridMonth-view` | Grade mensal |
| **Visualização Dia** | `.fc-timeGridDay-view`, `.fc-agendaDay-view` | Agenda diária |
| **Célula de Dia** | `[data-date="YYYY-MM-DD"]` | Cada dia do mês |
| **Dia com Eventos** | `.fc-day.fc-event`, `.fc-daygrid-event` | Dias que têm compromissos |
| **Evento** | `.fc-timegrid-event`, `.fc-event` | Compromisso individual |
| **Botões de View** | `button:has-text("Mês")` | Troca de visualização |

### Estrutura de Dados

#### Dia com Eventos
```python
{
    "day": 15,
    "date": "2025-11-15",
    "date_obj": date(2025, 11, 15),
    "has_events": True,
    "handle": <Locator>,
    "day_link": <Locator>
}
```

#### Evento Extraído
```python
{
    "date": "2025-11-15",
    "title": "Reunião com Equipe",
    "time": "14:00 - 16:00",
    "type": "Reunião",
    "details": "Discussão de projetos Q4"
}
```

#### Resultado Consolidado
```python
{
    "2025-11-15": [
        {"title": "Reunião...", "time": "14:00", ...},
        {"title": "Audiência...", "time": "16:30", ...}
    ],
    "2025-11-20": [
        {"title": "Viagem...", "time": "09:00", ...}
    ]
}
```

---

## 🔄 Fluxo de Execução

### Fluxo Completo (test_eagendas_full_flow.py)

```
1. Navegar → eagendas.cgu.gov.br
2. [Manual/Automático] Selecionar Órgão → Cargo → Agente
3. Clicar "Mostrar agenda"
4. Aguardar calendário carregar
5. Detectar dias com eventos (visualização Mês)
6. Para cada dia:
   a. Clicar no dia
   b. Aguardar view "Dia" carregar
   c. Extrair eventos (título, hora, tipo, detalhes)
   d. Voltar para view "Mês"
7. Consolidar eventos por data
8. Gerar relatório formatado
9. Salvar JSON em resultados/
```

### Exemplo de Uso Programático

```python
from datetime import date
from dou_snaptrack.utils.eagendas_calendar import (
    click_mostrar_agenda_async,
    collect_events_for_period_async,
    format_events_report
)

# Após seleção de filtros...
await click_mostrar_agenda_async(page)

# Coletar eventos de novembro/2025
events = await collect_events_for_period_async(
    page,
    start_date=date(2025, 11, 1),
    end_date=date(2025, 11, 30)
)

# Gerar relatório
print(format_events_report(events))
```

---

## ⚠️ Desafios e Soluções

### 1. Calendário Virtual (FullCalendar.js)
**Desafio**: Elementos não estão no DOM estático, são gerados dinamicamente por JS

**Solução**:
- Aguardar load states após cada ação
- Usar `data-date` attribute para identificação confiável
- Detectar view atual via classes CSS específicas

### 2. Transições entre Visualizações
**Desafio**: Mudança de Mês → Dia → Mês requer waits precisos

**Solução**:
- Verificar view atual antes/depois de cada ação
- Waits configuráveis (default: 1000-2000ms)
- Retry implícito via múltiplos seletores

### 3. Extração de Eventos
**Desafio**: Estrutura HTML varia por tipo de evento

**Solução**:
- Buscar múltiplos seletores (`.fc-event-title`, `.fc-title`, etc.)
- Fallback: pegar todo texto do elemento se não encontrar título
- Campos opcionais (time, type, details) com try/except

### 4. Período Multi-Mês
**Desafio**: Coletar eventos que cruzam múltiplos meses

**Solução** (TODO):
- Atual: suporta apenas mês único
- Futuro: navegação de mês (botões prev/next) + loop

---

## 📊 Exemplo de Saída

### Relatório Console
```
================================================================================
RELATÓRIO DE COMPROMISSOS
================================================================================

Total: 3 dias com compromissos
Total de eventos: 5

📅 2025-11-15 (2 eventos)
--------------------------------------------------------------------------------

  1. Reunião com Diretoria
     ⏰ 14:00 - 16:00
     🏷️  Reunião
     📝 Discussão de projetos estratégicos

  2. Audiência Pública
     ⏰ 18:00 - 19:30
     🏷️  Audiência

📅 2025-11-20 (1 evento)
--------------------------------------------------------------------------------

  1. Viagem a Brasília
     ⏰ 09:00
     🏷️  Viagem - Sistema de Concessão de Diárias

📅 2025-11-27 (2 eventos)
--------------------------------------------------------------------------------

  1. Evento Técnico
     ⏰ 10:00 - 12:00
     🏷️  Evento

  2. Afastamento
     ⏰ Dia todo
     🏷️  Afastamento

================================================================================
```

### JSON Output
```json
{
  "period": {
    "start": "2025-11-01",
    "end": "2025-11-30"
  },
  "stats": {
    "total_days": 3,
    "total_events": 5
  },
  "events": {
    "2025-11-15": [
      {
        "date": "2025-11-15",
        "title": "Reunião com Diretoria",
        "time": "14:00 - 16:00",
        "type": "Reunião",
        "details": "Discussão de projetos estratégicos"
      }
    ]
  }
}
```

---

## 🚀 Próximos Passos

### Fase 1: Integração com Seleção ✅ (Parcial)
- [x] Criar módulo de calendário
- [x] Implementar extração de eventos
- [ ] Integrar com `plan_live_eagendas_async.py`
- [ ] Adicionar seleção automática Selectize no teste

### Fase 2: Melhorias de Robustez
- [ ] Suporte a período multi-mês (navegação prev/next)
- [ ] Retry automático em falhas de clique
- [ ] Validação de que evento foi realmente extraído
- [ ] Cache de dias já processados (evitar reprocessamento)

### Fase 3: Integração com UI Streamlit
- [ ] Adicionar aba "E-Agendas" na UI
- [ ] Seletores de período (date picker)
- [ ] Visualização de eventos em tabela
- [ ] Export para Excel/CSV

### Fase 4: Features Avançadas
- [ ] Filtro por tipo de evento (Reunião, Audiência, Viagem, etc.)
- [ ] Busca textual em títulos/detalhes
- [ ] Estatísticas agregadas (eventos por tipo, por mês)
- [ ] Download de anexos (se disponíveis)

---

## 🧪 Como Testar

### Teste Rápido (URL Pré-filtrada)
```bash
python dev_tools/test_eagendas_full_flow.py
```
- Usa URL com filtros já aplicados
- Pula seleção manual
- Extrai eventos de novembro/2025
- Gera relatório e salva JSON

### Teste Completo (Com Seleção)
```python
# Modificar test_eagendas_full_flow.py:
# - Comentar linha 78-82 (URL pré-filtrada)
# - Descomentar seção de seleção Selectize
# - Implementar calls a _select_by_label_and_text_async()
```

### Integração Manual
1. Execute o teste
2. Aguarde navegador abrir
3. Se necessário, complete seleções manualmente
4. Clique "Mostrar agenda" manualmente
5. Script detectará calendário e continuará automaticamente

---

## 📚 Dependências

- **Playwright** (async_api)
- **datetime** (manipulação de datas)
- **json** (serialização)
- **logging** (diagnóstico)

**Compatível com**:
- Python 3.10+
- Windows, Linux, macOS
- Chrome, Edge, Chromium

---

## 🔗 Referências

- **FullCalendar.js Docs**: https://fullcalendar.io/docs
- **E-Agendas Site**: https://eagendas.cgu.gov.br/
- **Playwright Async API**: https://playwright.dev/python/docs/api/class-page

---

**Status**: ✅ Implementado e testado
**Próximo milestone**: Integração completa com plan_live_eagendas_async.py
**Autor**: GitHub Copilot
**Data**: 11/11/2025
