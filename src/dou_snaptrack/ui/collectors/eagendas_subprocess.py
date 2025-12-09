"""
Script de subprocess para coletar eventos do E-Agendas via Playwright.

Modelo simplificado de 2 níveis: Órgão → Agente (direto, sem cargo intermediário).

Recebe via stdin JSON com:
{
  "queries": [
    {
      "n1_value": "123",
      "n1_label": "Órgão X",
      "n3_value": "789",
      "n3_label": "Agente Z"
    }
  ],
  "periodo": {
    "inicio": "2025-11-01",
    "fim": "2025-11-07"
  }
}

Writes result to RESULT_JSON_PATH (contract with _execute_script_and_read_result).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# IDs dos selectize do E-Agendas
DD_ORGAO_ID = "filtro_orgao_entidade"
DD_AGENTE_ID = "filtro_servidor"


def _write_result(data: dict) -> None:
    """Write result to RESULT_JSON_PATH file (subprocess contract)."""
    result_path = os.environ.get("RESULT_JSON_PATH")
    if result_path:
        Path(result_path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    else:
        # Fallback to stdout if no RESULT_JSON_PATH (for direct testing)
        print(json.dumps(data, ensure_ascii=False))


def main():
    """Executa coleta de eventos para múltiplos agentes (modelo 2 níveis: Órgão → Agente)."""
    from .eagendas_helpers import (
        parse_input_and_periodo,
        setup_playwright_env,
        launch_browser_with_channels,
        launch_browser_with_exe_paths,
        create_browser_context,
        wait_for_angular_and_selectize,
        select_orgao_and_agente,
        click_mostrar_agenda,
        extract_query_info,
    )
    
    try:
        # Read and parse input
        input_data = json.loads(sys.stdin.read())
        queries, start_date, end_date = parse_input_and_periodo(input_data)
        
        if not queries:
            _write_result({"success": False, "error": "Nenhuma query fornecida"})
            return 1

        # Import after reading stdin
        from playwright.sync_api import sync_playwright

        # Setup Playwright
        setup_playwright_env()

        agentes_data = []
        total_eventos = 0

        # Selectize helper functions
        def get_selectize_options(page, element_id: str):
            """Extract options from a Selectize dropdown."""
            return page.evaluate("""(id) => {
                const el = document.getElementById(id);
                if (!el || !el.selectize) return [];
                const s = el.selectize;
                const out = [];
                const opts = s.options || {};
                for (const [val, raw] of Object.entries(opts)) {
                    const v = String(val ?? '');
                    const t = (raw && (raw.text || raw.label || raw.nome || raw.name)) || v;
                    if (!t) continue;
                    out.push({ value: v, text: String(t) });
                }
                return out;
            }""", element_id)

        def set_selectize_value(page, element_id: str, value: str):
            """Set a value in a Selectize dropdown."""
            return page.evaluate("""(args) => {
                const { id, value } = args;
                const el = document.getElementById(id);
                if (!el || !el.selectize) return false;
                el.selectize.setValue(String(value), false);
                return true;
            }""", {'id': element_id, 'value': value})

        with sync_playwright() as p:
            # Launch browser
            LAUNCH_ARGS = [
                '--headless=new',
                '--disable-blink-features=AutomationControlled',
                '--ignore-certificate-errors'
            ]

            browser = launch_browser_with_channels(p, LAUNCH_ARGS)
            if not browser:
                browser = launch_browser_with_exe_paths(p, LAUNCH_ARGS)

            if not browser:
                _write_result({"success": False, "error": "Nenhum browser disponível (Chrome/Edge)"})
                return 1

            # Create context and page
            context, page = create_browser_context(browser)

            # URL base
            base_url = "https://eagendas.cgu.gov.br/"

            # Process each query
            for query_idx, query in enumerate(queries):
                try:
                    agente_label, agente_value, orgao_label, orgao_value = extract_query_info(query)

                    print(f"[PROGRESS] Processando agente {query_idx + 1}/{len(queries)}: {agente_label}",
                          file=sys.stderr)

                    # Navigate and wait
                    print("[DEBUG] Navegando para E-Agendas...", file=sys.stderr)
                    page.goto(base_url, timeout=30000, wait_until="networkidle")

                    # Wait for initialization
                    if not wait_for_angular_and_selectize(page, DD_ORGAO_ID):
                        continue

                    # Select orgao and agente
                    if not select_orgao_and_agente(page, orgao_value, orgao_label, agente_value, agente_label, 
                                                   DD_ORGAO_ID, DD_AGENTE_ID, set_selectize_value):
                        continue

                    # Click Mostrar agenda
                    if not click_mostrar_agenda(page):
                        print(f"[WARNING] Não foi possível clicar em 'Mostrar agenda' para {agente_label}", file=sys.stderr)
                        continue

                    # Verificar se calendário apareceu
                    calendar_found = page.evaluate("() => !!document.querySelector('.fc, #calendar, #divcalendar')")
                    if not calendar_found:
                        print(f"[WARNING] Calendário não encontrado para {agente_label}", file=sys.stderr)
                        continue
                    print("[DEBUG] ✓ Calendário encontrado", file=sys.stderr)

                    # Função para extrair eventos do calendário visível
                    def extract_events_from_visible_calendar():
                        """Extrai eventos das células visíveis do calendário."""
                        return page.evaluate("""(args) => {
                            const { startDate, endDate } = args;
                            const start = new Date(startDate);
                            const end = new Date(endDate);
                            
                            const eventos = {};
                            const dayCells = document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date]');
                            
                            for (const cell of dayCells) {
                                const dateStr = cell.getAttribute('data-date');
                                if (!dateStr) continue;
                                
                                const cellDate = new Date(dateStr);
                                if (cellDate < start || cellDate > end) continue;
                                
                                const eventsInCell = cell.querySelectorAll('.fc-event');
                                if (eventsInCell.length === 0) continue;
                                
                                const eventList = [];
                                for (const evt of eventsInCell) {
                                    const titleEl = evt.querySelector('.fc-event-title');
                                    const timeEl = evt.querySelector('.fc-event-time');
                                    eventList.push({
                                        title: (titleEl?.textContent || evt.textContent || 'Evento').trim(),
                                        time: timeEl?.textContent?.trim() || '',
                                        type: 'Compromisso',
                                        details: ''
                                    });
                                }
                                
                                if (eventList.length > 0) {
                                    eventos[dateStr] = eventList;
                                }
                            }
                            
                            return eventos;
                        }""", {'startDate': str(start_date), 'endDate': str(end_date)})

                    # Coletar eventos de todos os meses necessários
                    eventos_por_dia = {}
                    meses_visitados = set()

                    # Obter mês atual do calendário
                    def get_calendar_month():
                        return page.evaluate("() => document.querySelector('.fc-toolbar-title')?.textContent || ''")

                    current_month = get_calendar_month()
                    meses_visitados.add(current_month)

                    # Coletar eventos do mês atual
                    eventos = extract_events_from_visible_calendar()
                    eventos_por_dia.update(eventos)
                    print(f"[DEBUG] {current_month}: {len(eventos)} dias com eventos", file=sys.stderr)

                    # Determinar quantos meses precisamos navegar para trás
                    # Para cobrir o período, precisamos ir até o mês de start_date
                    months_to_go_back = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)

                    for _ in range(months_to_go_back):
                        # Clicar no botão "anterior"
                        try:
                            prev_btn = page.locator('.fc-prev-button').first
                            if prev_btn.count() > 0:
                                prev_btn.click()
                                page.wait_for_timeout(1500)

                                current_month = get_calendar_month()
                                if current_month and current_month not in meses_visitados:
                                    meses_visitados.add(current_month)
                                    eventos = extract_events_from_visible_calendar()
                                    eventos_por_dia.update(eventos)
                                    print(f"[DEBUG] {current_month}: {len(eventos)} dias com eventos", file=sys.stderr)
                        except Exception as nav_err:
                            print(f"[DEBUG] Erro navegando mês: {nav_err}", file=sys.stderr)
                            break

                    # Contar total de eventos
                    eventos_count = sum(len(evts) for evts in eventos_por_dia.values())
                    total_eventos += eventos_count

                    # Adicionar dados do agente (modelo simplificado)
                    agente_data = {
                        "orgao": {
                            "id": orgao_value,
                            "nome": orgao_label
                        },
                        "cargo": {
                            "id": "",
                            "nome": ""  # Cargo removido do modelo
                        },
                        "agente": {
                            "id": agente_value,
                            "nome": agente_label
                        },
                        "eventos": eventos_por_dia
                    }
                    agentes_data.append(agente_data)
                    print(f"[DEBUG] ✓ {agente_label}: {len(eventos_por_dia)} dias com eventos", file=sys.stderr)

                except Exception as e:
                    print(f"[ERROR] Erro ao processar {query.get('n3_label', 'agente')}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    continue

            context.close()
            browser.close()

        # Estrutura final
        result = {
            "success": True,
            "data": {
                "periodo": periodo,
                "agentes": agentes_data,
                "metadata": {
                    "data_coleta": datetime.now().isoformat(),
                    "total_agentes": len(agentes_data),
                    "total_eventos": total_eventos
                }
            }
        }

        _write_result(result)
        return 0

    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {e}"
        traceback_str = traceback.format_exc()
        _write_result({
            "success": False,
            "error": error_msg,
            "traceback": traceback_str
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
