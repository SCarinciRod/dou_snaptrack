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
    try:
        # Ler input via stdin
        input_data = json.loads(sys.stdin.read())
        queries = input_data.get("queries", [])
        periodo = input_data.get("periodo", {})

        if not queries:
            _write_result({"success": False, "error": "Nenhuma query fornecida"})
            return 1

        # Importar após ler stdin para evitar delay inicial
        from datetime import date

        from playwright.sync_api import sync_playwright

        # Configurar Playwright
        pw_browsers_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "pw-browsers"
        if pw_browsers_path.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers_path)

        agentes_data = []
        total_eventos = 0

        # Converter datas
        try:
            start_date = date.fromisoformat(periodo["inicio"])
            end_date = date.fromisoformat(periodo["fim"])
        except Exception as e:
            _write_result({"success": False, "error": f"Erro ao parsear datas: {e}"})
            return 1

        # Funções helper para Selectize
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
                // setValue com false = não silencioso = dispara eventos do Selectize
                el.selectize.setValue(String(value), false);
                return true;
            }""", {'id': element_id, 'value': value})

        with sync_playwright() as p:
            # NOTA: E-Agendas detecta headless e bloqueia. Usamos headless=False com janela oculta.
            # Combinamos --start-minimized com --window-position fora da tela para garantir invisibilidade.
            LAUNCH_ARGS = [
                '--start-minimized',
                '--window-position=-2000,-2000',  # Posiciona janela fora da tela visível
                '--disable-blink-features=AutomationControlled',
                '--ignore-certificate-errors'
            ]

            # Tentar lançar browser
            browser = None
            for channel in ['chrome', 'msedge']:
                try:
                    print(f"[DEBUG] Tentando channel={channel}...", file=sys.stderr)
                    browser = p.chromium.launch(channel=channel, headless=False, args=LAUNCH_ARGS)
                    print(f"[DEBUG] ✓ {channel} OK", file=sys.stderr)
                    break
                except Exception as e:
                    print(f"[DEBUG] ✗ {channel} falhou: {e}", file=sys.stderr)

            # Fallback: buscar executável
            if not browser:
                exe_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                ]
                for exe_path in exe_paths:
                    if Path(exe_path).exists():
                        try:
                            browser = p.chromium.launch(executable_path=exe_path, headless=False, args=LAUNCH_ARGS)
                            print("[DEBUG] ✓ executable_path OK", file=sys.stderr)
                            break
                        except Exception:
                            continue

            if not browser:
                _write_result({"success": False, "error": "Nenhum browser disponível (Chrome/Edge)"})
                return 1

            # Criar contexto NEGANDO permissões de geolocalização
            context = browser.new_context(
                ignore_https_errors=True,
                viewport={'width': 1280, 'height': 900},
                permissions=[],  # Negar todas as permissões
                geolocation=None,
            )
            context.set_default_timeout(60000)
            page = context.new_page()

            # URL base do E-Agendas
            base_url = "https://eagendas.cgu.gov.br/"

            # Processar cada consulta
            for query_idx, query in enumerate(queries):
                try:
                    # Modelo novo: n3 contém o agente (compatibilidade com listas antigas)
                    # n1 = órgão, n3 = agente (n2 era cargo, agora ignorado)
                    agente_label = query.get('n3_label') or query.get('person_label', 'Agente')
                    agente_value = query.get('n3_value', '')
                    orgao_label = query.get('n1_label', 'Órgão')
                    orgao_value = query.get('n1_value', '')

                    print(f"[PROGRESS] Processando agente {query_idx + 1}/{len(queries)}: {agente_label}",
                          file=sys.stderr)

                    # Navegar para a página
                    print("[DEBUG] Navegando para E-Agendas...", file=sys.stderr)
                    page.goto(base_url, timeout=30000, wait_until="networkidle")
                    
                    # OTIMIZAÇÃO: Espera condicional para AngularJS (era 5000ms fixo)
                    angular_ready_js = "() => document.querySelector('[ng-app]') !== null"
                    try:
                        page.wait_for_function(angular_ready_js, timeout=5000)
                        print("[DEBUG] ✓ AngularJS ready", file=sys.stderr)
                    except Exception:
                        print("[DEBUG] AngularJS timeout, continuando...", file=sys.stderr)

                    # Aguardar selectize de órgãos inicializar
                    wait_orgao_js = f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}"
                    try:
                        page.wait_for_function(wait_orgao_js, timeout=20000)
                        print("[DEBUG] ✓ Selectize inicializado", file=sys.stderr)
                    except Exception as e:
                        print(f"[ERROR] Selectize não inicializou: {e}", file=sys.stderr)
                        continue

                    # PASSO 1: Selecionar órgão
                    print(f"[DEBUG] Selecionando órgão: {orgao_label} (ID: {orgao_value})", file=sys.stderr)
                    if not set_selectize_value(page, DD_ORGAO_ID, orgao_value):
                        print("[ERROR] Não foi possível selecionar órgão", file=sys.stderr)
                        continue
                    
                    # NOTA: Usamos wait_for_timeout em vez de wait_for_function aqui porque
                    # o polling frequente do wait_for_function interfere com o ciclo de digest
                    # do AngularJS e impede que os callbacks (onUpdateOrgao) sejam executados.
                    page.wait_for_timeout(2000)

                    # PASSO 2: Selecionar agente diretamente
                    print(f"[DEBUG] Selecionando agente: {agente_label} (ID: {agente_value})", file=sys.stderr)
                    if not set_selectize_value(page, DD_AGENTE_ID, agente_value):
                        print("[ERROR] Não foi possível selecionar agente", file=sys.stderr)
                        continue
                    
                    # NOTA: Mesma razão - wait_for_timeout permite que o Angular execute
                    # onUpdateServidor() e preencha automaticamente o cargo
                    page.wait_for_timeout(2000)

                    # Mitigar cookie bar
                    try:
                        page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                    except Exception:
                        pass

                    # Clicar em "Mostrar agenda" - o clique causa navegação
                    print("[DEBUG] Clicando em 'Mostrar agenda'...", file=sys.stderr)
                    clicked = False
                    try:
                        btn = page.locator('button:has-text("Mostrar agenda")').first
                        if btn.count() > 0:
                            btn.scroll_into_view_if_needed()
                            page.wait_for_timeout(300)
                            # expect_navigation porque o clique navega para uma nova página com o calendário
                            with page.expect_navigation(wait_until='networkidle', timeout=30000):
                                btn.click()
                            clicked = True
                            print("[DEBUG] ✓ Navegação completa", file=sys.stderr)
                    except Exception as e:
                        print(f"[DEBUG] Clique/navegação falhou: {e}", file=sys.stderr)
                        # Fallback: tentar clique simples
                        try:
                            btn = page.locator('button:has-text("Mostrar agenda")').first
                            btn.click(no_wait_after=True, timeout=5000)
                            page.wait_for_timeout(3000)
                            clicked = True
                        except Exception:
                            pass

                    if not clicked:
                        print(f"[WARNING] Não foi possível clicar em 'Mostrar agenda' para {agente_label}", file=sys.stderr)
                        continue

                    # Aguardar calendário carregar
                    page.wait_for_timeout(2000)

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
