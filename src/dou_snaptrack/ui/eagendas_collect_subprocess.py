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
                el.selectize.setValue(String(value), false);
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""", {'id': element_id, 'value': value})

        with sync_playwright() as p:
            # NOTA: E-Agendas detecta headless e bloqueia. Usamos headless=False + --start-minimized
            LAUNCH_ARGS = [
                '--start-minimized',
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
                    page.goto(base_url, timeout=30000, wait_until="commit")
                    
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
                    
                    # OTIMIZAÇÃO: Espera condicional para agentes (era 3000ms fixo)
                    agentes_ready_js = f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 0; }}"
                    try:
                        page.wait_for_function(agentes_ready_js, timeout=3000)
                        print("[DEBUG] ✓ Agentes ready", file=sys.stderr)
                    except Exception:
                        print("[DEBUG] Agentes timeout (pode não ter agentes)", file=sys.stderr)

                    # PASSO 2: Selecionar agente diretamente (sem cargo)
                    # Aguardar selectize de agentes
                    wait_agente_js = f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 0; }}"
                    try:
                        page.wait_for_function(wait_agente_js, timeout=15000)
                    except Exception:
                        print(f"[WARNING] Timeout aguardando agentes para {orgao_label}", file=sys.stderr)

                    print(f"[DEBUG] Selecionando agente: {agente_label} (ID: {agente_value})", file=sys.stderr)
                    if not set_selectize_value(page, DD_AGENTE_ID, agente_value):
                        print("[ERROR] Não foi possível selecionar agente", file=sys.stderr)
                        continue
                    
                    # OTIMIZAÇÃO: Espera condicional para seleção (era 2000ms fixo)
                    selection_js = f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize?.getValue() === '{agente_value}'; }}"
                    try:
                        page.wait_for_function(selection_js, timeout=2000)
                    except Exception:
                        page.wait_for_timeout(200)  # Fallback mínimo

                    # Mitigar cookie bar
                    try:
                        page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                    except Exception:
                        pass

                    # Clicar em "Mostrar agenda"
                    print("[DEBUG] Procurando botão 'Mostrar agenda'...", file=sys.stderr)
                    clicked = False
                    for attempt in range(3):
                        try:
                            btn = page.locator('button:has-text("Mostrar agenda"), button:has-text("MOSTRAR AGENDA")').first
                            if btn.count() > 0:
                                btn.scroll_into_view_if_needed()
                                page.wait_for_timeout(200)
                                btn.click(timeout=5000, force=attempt > 0)
                                clicked = True
                                break
                        except Exception as e:
                            print(f"[DEBUG] Tentativa {attempt+1} clique falhou: {e}", file=sys.stderr)
                            try:
                                page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                            except Exception:
                                pass
                            page.wait_for_timeout(500)

                    if not clicked:
                        print(f"[WARNING] Não foi possível clicar em 'Mostrar agenda' para {agente_label}", file=sys.stderr)
                        continue

                    # OTIMIZAÇÃO: Espera condicional para calendário (era 3000ms fixo)
                    print("[DEBUG] Aguardando calendário...", file=sys.stderr)
                    calendar_js = "() => document.querySelector('.fc-view-container, .fc-daygrid, #divcalendar, .fc-view') !== null"
                    try:
                        page.wait_for_function(calendar_js, timeout=3000)
                        print("[DEBUG] ✓ Calendário ready", file=sys.stderr)
                    except Exception:
                        print("[DEBUG] Calendário timeout, verificando manualmente...", file=sys.stderr)

                    # Verificar se calendário apareceu
                    calendar_selectors = [
                        "#divcalendar",
                        ".fc-view-container",
                        ".fc-view",
                        ".fc-daygrid",
                        "[class*='calendar']",
                    ]

                    calendar_found = False
                    for selector in calendar_selectors:
                        try:
                            cal = page.locator(selector).first
                            if cal.count() > 0 and cal.is_visible():
                                calendar_found = True
                                print(f"[DEBUG] ✓ Calendário encontrado ({selector})", file=sys.stderr)
                                break
                        except Exception:
                            continue

                    if not calendar_found:
                        print(f"[WARNING] Calendário não encontrado para {agente_label}", file=sys.stderr)
                        continue

                    # Coletar eventos do período
                    eventos_por_dia = {}

                    try:
                        day_cells = page.locator(".fc-day[data-date], .fc-daygrid-day[data-date]")
                        count = day_cells.count()

                        for i in range(min(count, 42)):  # ~6 semanas
                            cell = day_cells.nth(i)
                            try:
                                date_str = cell.get_attribute("data-date")
                                if not date_str:
                                    continue

                                cell_date = date.fromisoformat(date_str)
                                if not (start_date <= cell_date <= end_date):
                                    continue

                                events_in_cell = cell.locator(".fc-event, .fc-daygrid-event")
                                if events_in_cell.count() > 0:
                                    eventos_dia = []
                                    for j in range(events_in_cell.count()):
                                        evt = events_in_cell.nth(j)
                                        try:
                                            title = evt.text_content() or "Evento"
                                            eventos_dia.append({
                                                "title": title.strip(),
                                                "time": "",
                                                "type": "Compromisso",
                                                "details": ""
                                            })
                                        except Exception:
                                            pass

                                    if eventos_dia:
                                        eventos_por_dia[date_str] = eventos_dia
                                        total_eventos += len(eventos_dia)

                            except Exception:
                                continue

                    except Exception as e:
                        print(f"[WARNING] Erro ao extrair eventos para {agente_label}: {e}", file=sys.stderr)

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
