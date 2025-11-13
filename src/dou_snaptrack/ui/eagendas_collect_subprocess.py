"""
Script de subprocess para coletar eventos do E-Agendas via Playwright.

Recebe via stdin JSON com:
{
  "queries": [
    {
      "n1_value": "123",
      "n1_label": "Órgão X",
      "n2_value": "456",
      "n2_label": "Cargo Y",
      "n3_value": "789",
      "n3_label": "Agente Z"
    }
  ],
  "periodo": {
    "inicio": "2025-11-01",
    "fim": "2025-11-07"
  }
}

Retorna via stdout JSON com estrutura completa de eventos.
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def main():
    """Executa coleta de eventos para múltiplos agentes."""
    try:
        # Ler input via stdin
        input_data = json.loads(sys.stdin.read())
        queries = input_data.get("queries", [])
        periodo = input_data.get("periodo", {})

        if not queries:
            print(json.dumps({"success": False, "error": "Nenhuma query fornecida"}))
            return 1

        # Importar após ler stdin para evitar delay inicial
        from datetime import date

        from playwright.sync_api import sync_playwright

        # Importar funções de selectize
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from mappers.eagendas_selectize import (
            find_selectize_by_label,
            get_selectize_options,
            open_selectize_dropdown,
            select_selectize_option_via_api,
        )

        # Configurar Playwright
        pw_browsers_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "pw-browsers"
        import os
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers_path)

        agentes_data = []
        total_eventos = 0

        # Converter datas
        try:
            start_date = date.fromisoformat(periodo["inicio"])
            end_date = date.fromisoformat(periodo["fim"])
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Erro ao parsear datas: {e}"}))
            return 1

        with sync_playwright() as p:
            # Tentar lançar browser
            browser = None
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
            except Exception:
                try:
                    browser = p.chromium.launch(channel="msedge", headless=True)
                except Exception:
                    # Fallback: buscar executável
                    chrome_paths = [
                        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                    ]
                    edge_paths = [
                        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                    ]
                    for exe_path in chrome_paths + edge_paths:
                        if Path(exe_path).exists():
                            try:
                                browser = p.chromium.launch(executable_path=exe_path, headless=True)
                                break
                            except Exception:
                                continue

            if not browser:
                browser = p.chromium.launch(headless=True)

            context = browser.new_context()
            page = context.new_page()

            # URL base do E-Agendas
            base_url = "https://eagendas.cgu.gov.br/"

            # Processar cada consulta
            for query_idx, query in enumerate(queries):
                try:
                    print(f"[PROGRESS] Processando agente {query_idx + 1}/{len(queries)}: {query['n3_label']}",
                          file=sys.stderr)

                    # Navegar para a página
                    print("[DEBUG] Navegando para E-Agendas...", file=sys.stderr)
                    page.goto(base_url, timeout=30000, wait_until="networkidle")
                    page.wait_for_timeout(3000)

                    # === ABORDAGEM CORRETA: Usar labels para encontrar selectize ===

                    # PASSO 1: Encontrar selectize N1 (Órgão ou entidade)
                    print("[DEBUG] Procurando selectize 'Órgão ou entidade'...", file=sys.stderr)
                    selectize_n1 = find_selectize_by_label(page, "Órgão ou entidade")
                    if not selectize_n1:
                        print(f"[ERROR] Selectize 'Órgão ou entidade' não encontrado", file=sys.stderr)
                        continue

                    # PASSO 2: Abrir dropdown N1 e selecionar órgão
                    print(f"[DEBUG] Selecionando órgão: {query['n1_label']} (ID: {query['n1_value']})", file=sys.stderr)
                    if not open_selectize_dropdown(page, selectize_n1, wait_ms=2000):
                        print(f"[ERROR] Não foi possível abrir dropdown N1", file=sys.stderr)
                        continue

                    # Selecionar via API (mais confiável)
                    option_n1 = {"value": query["n1_value"], "text": query["n1_label"]}
                    if not select_selectize_option_via_api(page, selectize_n1, option_n1, wait_after_ms=3000):
                        print(f"[ERROR] Não foi possível selecionar N1", file=sys.stderr)
                        continue

                    # PASSO 3: Encontrar selectize N2 (Cargo)
                    print("[DEBUG] Procurando selectize 'Cargo'...", file=sys.stderr)
                    page.wait_for_timeout(2000)
                    selectize_n2 = find_selectize_by_label(page, "Cargo")
                    if not selectize_n2:
                        print(f"[ERROR] Selectize 'Cargo' não encontrado", file=sys.stderr)
                        continue

                    # PASSO 4: Abrir dropdown N2 e selecionar cargo
                    print(f"[DEBUG] Selecionando cargo: {query['n2_label']} (ID: {query['n2_value']})", file=sys.stderr)
                    if not open_selectize_dropdown(page, selectize_n2, wait_ms=2000):
                        print(f"[ERROR] Não foi possível abrir dropdown N2", file=sys.stderr)
                        continue

                    option_n2 = {"value": query["n2_value"], "text": query["n2_label"]}
                    if not select_selectize_option_via_api(page, selectize_n2, option_n2, wait_after_ms=3000):
                        print(f"[ERROR] Não foi possível selecionar N2", file=sys.stderr)
                        continue

                    # PASSO 5: Encontrar selectize N3 (Agente público)
                    print("[DEBUG] Procurando selectize 'Agente público'...", file=sys.stderr)
                    page.wait_for_timeout(2000)
                    selectize_n3 = find_selectize_by_label(page, "Agente público")
                    if not selectize_n3:
                        print(f"[ERROR] Selectize 'Agente público' não encontrado", file=sys.stderr)
                        continue

                    # PASSO 6: Abrir dropdown N3 e selecionar agente
                    print(f"[DEBUG] Selecionando agente: {query['n3_label']} (ID: {query['n3_value']})", file=sys.stderr)
                    if not open_selectize_dropdown(page, selectize_n3, wait_ms=2000):
                        print(f"[ERROR] Não foi possível abrir dropdown N3", file=sys.stderr)
                        continue

                    option_n3 = {"value": query["n3_value"], "text": query["n3_label"]}
                    if not select_selectize_option_via_api(page, selectize_n3, option_n3, wait_after_ms=2000):
                        print(f"[ERROR] Não foi possível selecionar N3", file=sys.stderr)
                        continue

                    # Clicar em "Mostrar agenda"
                    print("[DEBUG] Procurando botão 'Mostrar agenda'...", file=sys.stderr)
                    page.wait_for_timeout(800)

                    # Mitigar cookie bar interceptando cliques
                    try:
                        cookie_bar = page.locator('.br-cookiebar')
                        if cookie_bar.count() > 0:
                            print("[DEBUG] Cookie bar detectada — tentando aceitar/remover...", file=sys.stderr)
                            # Tentar clicar em algum botão dentro da cookiebar primeiro
                            btn_cookie = cookie_bar.locator('button')
                            try:
                                if btn_cookie.count() > 0:
                                    btn_cookie.first.click(timeout=1500)
                                    page.wait_for_timeout(300)
                                    print("[DEBUG] Botão da cookie bar clicado", file=sys.stderr)
                                else:
                                    # Remover via JS se não houver botão
                                    page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                                    print("[DEBUG] Cookie bar removida via JS", file=sys.stderr)
                            except Exception:
                                # Forçar remoção se clique falhar
                                try:
                                    page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                                    print("[DEBUG] Cookie bar removida via JS (fallback)", file=sys.stderr)
                                except Exception:
                                    print("[WARNING] Falha ao remover cookie bar", file=sys.stderr)
                    except Exception:
                        pass

                    # Função helper para clicar com múltiplas tentativas
                    def _click_mostrar_agenda(max_attempts: int = 3) -> bool:
                        for attempt in range(1, max_attempts + 1):
                            try:
                                btn_loc = page.locator('button:has-text("Mostrar agenda"), button:has-text("MOSTRAR AGENDA")').first
                                count = btn_loc.count()
                                print(f"[DEBUG] Tentativa {attempt}: localizar botão (count={count})", file=sys.stderr)
                                if count == 0:
                                    page.wait_for_timeout(400)
                                    continue
                                if not btn_loc.is_visible():
                                    print("[DEBUG] Botão encontrado mas não visível — scroll", file=sys.stderr)
                                    btn_loc.scroll_into_view_if_needed()
                                    page.wait_for_timeout(150)
                                print(f"[DEBUG] Tentativa {attempt}: clicando...", file=sys.stderr)
                                if attempt == 1:
                                    btn_loc.click(timeout=4000)
                                elif attempt == 2:
                                    # Forçar clique
                                    btn_loc.click(timeout=4000, force=True)
                                else:
                                    # Fallback JS
                                    page.evaluate("el => el.click()", btn_loc.element_handle())
                                page.wait_for_timeout(600)
                                return True
                            except Exception as e_inner:
                                print(f"[DEBUG] Tentativa {attempt} falhou: {e_inner}", file=sys.stderr)
                                # Em falhas posteriores, remover cookie bar novamente se reapareceu
                                try:
                                    cookie_bar2 = page.locator('.br-cookiebar')
                                    if cookie_bar2.count() > 0:
                                        page.evaluate("document.querySelector('.br-cookiebar')?.remove()")
                                        print("[DEBUG] Cookie bar removida após falha de clique", file=sys.stderr)
                                except Exception:
                                    pass
                                page.wait_for_timeout(300)
                        return False

                    clicked = _click_mostrar_agenda()
                    if not clicked:
                        print(f"[WARNING] Não foi possível clicar em 'Mostrar agenda' para {query['n3_label']}", file=sys.stderr)
                        continue
                    print("[DEBUG] Clique em 'Mostrar agenda' bem-sucedido, aguardando carregamento...", file=sys.stderr)
                    page.wait_for_timeout(2500)

                    # Verificar se calendário apareceu
                    print("[DEBUG] Aguardando calendário aparecer...", file=sys.stderr)
                    
                    # Tentar múltiplos seletores para calendário
                    calendar_selectors = [
                        "#divcalendar",
                        ".fc-view-container",
                        ".fc-view",
                        ".fc-daygrid",
                        "[class*='calendar']",
                        "[id*='calendar']"
                    ]
                    
                    calendar = None
                    for selector in calendar_selectors:
                        try:
                            cal = page.locator(selector).first
                            if cal.count() > 0:
                                print(f"[DEBUG] Encontrado elemento com seletor '{selector}'", file=sys.stderr)
                                is_visible = cal.is_visible()
                                print(f"[DEBUG] Elemento visível: {is_visible}", file=sys.stderr)
                                if is_visible:
                                    calendar = cal
                                    break
                        except Exception:
                            continue
                    
                    if not calendar:
                        print(f"[WARNING] Calendário não encontrado para {query['n3_label']}", file=sys.stderr)
                        # Salvar screenshot para debug
                        screenshot_path = f"debug_no_calendar_{query_idx}.png"
                        page.screenshot(path=screenshot_path)
                        print(f"[DEBUG] Screenshot salvo: {screenshot_path}", file=sys.stderr)
                        continue
                    
                    print("[DEBUG] Calendário encontrado e visível!", file=sys.stderr)

                    # Coletar eventos do período
                    # SIMPLIFICADO: Buscar todos os eventos visíveis no calendário
                    # (implementação completa requer navegação por mês/dia)
                    eventos_por_dia = {}

                    # Buscar eventos no calendário (view mensal)
                    try:
                        # Detectar dias com eventos
                        day_cells = page.locator(".fc-day[data-date], .fc-daygrid-day[data-date]")
                        count = day_cells.count()

                        for i in range(min(count, 31)):  # Limitar para não demorar muito
                            cell = day_cells.nth(i)
                            try:
                                date_str = cell.get_attribute("data-date")
                                if not date_str:
                                    continue

                                # Verificar se data está no período
                                cell_date = date.fromisoformat(date_str)
                                if not (start_date <= cell_date <= end_date):
                                    continue

                                # Verificar se há eventos neste dia
                                events_in_cell = cell.locator(".fc-event, .fc-daygrid-event")
                                if events_in_cell.count() > 0:
                                    # Extrair informações básicas do evento
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
                        print(f"[WARNING] Erro ao extrair eventos para {query['n3_label']}: {e}", file=sys.stderr)

                    # Adicionar dados do agente
                    agente_data = {
                        "orgao": {
                            "id": query["n1_value"],
                            "nome": query["n1_label"]
                        },
                        "cargo": {
                            "id": query["n2_value"],
                            "nome": query["n2_label"]
                        },
                        "agente": {
                            "id": query["n3_value"],
                            "nome": query["n3_label"]
                        },
                        "eventos": eventos_por_dia
                    }
                    agentes_data.append(agente_data)

                except Exception as e:
                    print(f"[ERROR] Erro ao processar {query['n3_label']}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    continue

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

        print(json.dumps(result))
        return 0

    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {e}"
        traceback_str = traceback.format_exc()
        print(json.dumps({
            "success": False,
            "error": error_msg,
            "traceback": traceback_str
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
