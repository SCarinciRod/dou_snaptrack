"""
Script de subprocess PARALELO para coletar eventos do E-Agendas via Playwright.

OTIMIZAÇÕES:
1. PARALELIZAÇÃO: Processa N agentes em paralelo (default 4 workers)
2. BROWSER ÚNICO: 1 browser com múltiplos contexts (economiza RAM)
3. CONTEXTS ISOLADOS: Cada worker tem seu próprio context/page (sessão separada)

Modelo simplificado de 2 níveis: Órgão → Agente (direto, sem cargo intermediário).

Recebe via variável de ambiente INPUT_JSON_PATH ou stdin com JSON:
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
  },
  "max_workers": 4  // opcional, default 4
}

Writes result to RESULT_JSON_PATH (contract with _execute_script_and_read_result).
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# Melhorar legibilidade de logs no Windows (evita '?' em acentos)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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


async def collect_for_agent(
    page,
    query: dict,
    start_date: date,
    end_date: date,
    worker_id: int
) -> dict | None:
    """
    Coleta eventos para um único agente.

    Returns:
        Dict com dados do agente ou None se falhou
    """
    # Support both n2 (direct) and n3 (via mapping) field names
    agente_label = query.get('n3_label') or query.get('n2_label') or query.get('person_label', 'Agente')
    agente_value = query.get('n3_value') or query.get('n2_value', '')
    orgao_label = query.get('n1_label', 'Órgão')
    orgao_value = query.get('n1_value', '')

    prefix = f"[W{worker_id}]"
    base_url = "https://eagendas.cgu.gov.br/"

    try:
        # Sempre navegar para página inicial (cada coleta é independente)
        print(f"{prefix} Navegando para E-Agendas...", file=sys.stderr)
        await page.goto(base_url, timeout=30000, wait_until="domcontentloaded")

        # WAIT CONDICIONAL: Aguardar selectize de órgãos inicializar (substitui wait fixo)
        wait_orgao_js = f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}"
        try:
            await page.wait_for_function(wait_orgao_js, timeout=15000, polling=100)
        except Exception as e:
            print(f"{prefix} Selectize não inicializou: {e}", file=sys.stderr)
            return None

        # Selecionar órgão via Selectize.
        # IMPORTANTE: não disparar eventos adicionais aqui; isso pode atrapalhar
        # o auto-preenchimento (cargo) no fluxo do site.
        print(f"{prefix} Selecionando órgão: {orgao_label[:30]}...", file=sys.stderr)
        orgao_selected = await page.evaluate("""(args) => {
            const { id, value } = args;
            const el = document.getElementById(id);
            if (!el || !el.selectize) return false;
            el.selectize.setValue(String(value), false);
            return true;
        }""", {'id': DD_ORGAO_ID, 'value': orgao_value})

        if not orgao_selected:
            print(f"{prefix} Falha ao selecionar órgão (value={orgao_value})", file=sys.stderr)
            return None

        # IMPORTANTE: Pequeno delay para Angular processar o ng-change e disparar requisição
        # Sem isso, o wait_for_function abaixo pode começar antes do Angular processar
        await page.wait_for_timeout(300)

        # Debug: verificar se órgão foi realmente selecionado
        orgao_check = await page.evaluate(f"() => document.getElementById('{DD_ORGAO_ID}')?.selectize?.getValue()")
        print(f"{prefix} Órgão selecionado: {orgao_check} (esperado: {orgao_value})", file=sys.stderr)

        # WAIT CONDICIONAL: Aguardar lista de agentes popular (substitui wait fixo de 2000ms)
        # NOTA: polling=500 é necessário para dar tempo ao Angular processar. Polling muito rápido
        # (100ms) pode impedir que o Angular execute seus ciclos $digest.
        wait_agentes_js = f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 0; }}"
        try:
            await page.wait_for_function(wait_agentes_js, timeout=10000, polling=500)
        except Exception:
            print(f"{prefix} Lista de agentes não populou", file=sys.stderr)
            return None

        # Selecionar agente via Selectize.
        # IMPORTANTE: não disparar eventos adicionais aqui; o site usa este
        # onchange para auto-preencher cargo e habilitar o botão.
        print(f"{prefix} Selecionando agente: {agente_label[:30]}...", file=sys.stderr)
        agente_selected = await page.evaluate("""(args) => {
            const { id, value } = args;
            const el = document.getElementById(id);
            if (!el || !el.selectize) return false;
            el.selectize.setValue(String(value), false);
            return true;
        }""", {'id': DD_AGENTE_ID, 'value': agente_value})

        if not agente_selected:
            print(f"{prefix} Falha ao selecionar agente (value={agente_value})", file=sys.stderr)
            return None

        # Debug: verificar se agente foi realmente selecionado
        agente_check = await page.evaluate(f"() => document.getElementById('{DD_AGENTE_ID}')?.selectize?.getValue()")
        print(f"{prefix} Agente selecionado: {agente_check} (esperado: {agente_value})", file=sys.stderr)

        # Remover cookie bar se presente (fazer logo para não atrapalhar)
        await page.evaluate("document.querySelector('.br-cookiebar')?.remove()")

        # A partir daqui, NÃO interagir com o campo de cargo.
        # O site auto-preenche cargo (quando aplicável) e habilita o botão.
        # Nossa responsabilidade é apenas esperar passivamente.
        btn_ready = False

        btn_ready_js = """() => {
            const btn = document.querySelector('button[ng-click*="submit"]');
            return !!(btn && !btn.disabled);
        }"""

        async def _dump_form_state() -> dict:
            return await page.evaluate(
                """() => {
                    const out = {};
                    const btns = Array.from(document.querySelectorAll('button[ng-click*="submit"]'));
                    out.submitButtons = btns.map(b => ({
                        text: (b.innerText || '').trim().slice(0, 80),
                        disabled: !!b.disabled,
                        display: (window.getComputedStyle(b).display || ''),
                        visibility: (window.getComputedStyle(b).visibility || ''),
                    }));

                    const org = document.getElementById('filtro_orgao_entidade');
                    const srv = document.getElementById('filtro_servidor');
                    const cargo = document.getElementById('filtro_cargo');

                    function sz(el) {
                        if (!el || !el.selectize) return null;
                        const s = el.selectize;
                        let value = '';
                        try { value = String((s.getValue && s.getValue()) || ''); } catch (e) { value = ''; }
                        const optCount = Object.keys(s.options || {}).length;
                        return { value, optCount };
                    }

                    out.selectize = {
                        orgao: sz(org),
                        agente: sz(srv),
                        cargo: sz(cargo),
                        cargoExists: !!cargo,
                        cargoHasSelectize: !!(cargo && cargo.selectize),
                    };

                    // Capturar possíveis mensagens/alertas visíveis (somente leitura)
                    const alerts = Array.from(document.querySelectorAll('.alert, .text-danger, .invalid-feedback'))
                        .map(el => (el.innerText || '').trim())
                        .filter(t => t.length > 0)
                        .slice(0, 5);
                    out.alerts = alerts;

                    // Indicadores de loading comuns
                    out.loading = {
                        hasSpinner: !!document.querySelector('.spinner, .loading, .br-loading, .ngx-spinner'),
                    };

                    return out;
                }"""
            )

        async def _wait_for_button(timeout_ms: int) -> bool:
            try:
                await page.wait_for_function(btn_ready_js, timeout=timeout_ms, polling=500)
                print(f"{prefix} ✓ Botão pronto", file=sys.stderr)
                return True
            except Exception:
                return False

        # 1) Espera passiva inicial
        btn_ready = await _wait_for_button(60000)

        # 2) Retry seguro (sem tocar em cargo): re-aplicar setValue do agente uma vez.
        # Alguns casos parecem não disparar o fluxo de auto-preenchimento; repetir a seleção
        # é o mais próximo possível da ação do usuário, sem sobrescrever cargo.
        if not btn_ready:
            try:
                await page.evaluate(
                    """(args) => {
                        const { id, value } = args;
                        const el = document.getElementById(id);
                        if (!el || !el.selectize) return false;
                        el.selectize.setValue(String(value), false);
                        return true;
                    }""",
                    {"id": DD_AGENTE_ID, "value": agente_value},
                )
            except Exception:
                pass
            btn_ready = await _wait_for_button(30000)

        # Se ainda não habilitou, registrar diagnóstico (somente leitura) e desistir.
        if not btn_ready:
            try:
                diag = await _dump_form_state()
                diag_str = json.dumps(diag, ensure_ascii=False)
                print(f"{prefix} DIAG botão desabilitado: {diag_str[:2000]}", file=sys.stderr)
            except Exception:
                pass

        # Verificar botão - deve estar pronto após as esperas acima
        btn_enabled_js = "() => { const btn = document.querySelector('button[ng-click*=\\\"submit\\\"]'); return btn && !btn.disabled; }"
        if not btn_ready:
            try:
                await page.wait_for_function(btn_enabled_js, timeout=5000, polling=500)
            except Exception:
                print(f"{prefix} ⚠ Botão ainda desabilitado, pulando agente...", file=sys.stderr)
                return None

        # Clicar em "Mostrar agenda" via JavaScript com expect_navigation
        # IMPORTANTE: O clique via JavaScript + expect_navigation é a abordagem mais robusta
        # Usar locator.click() pode travar em "waiting for scheduled navigations"
        print(f"{prefix} Clicando em 'Mostrar agenda'...", file=sys.stderr)
        try:
            async with page.expect_navigation(wait_until='domcontentloaded', timeout=60000):
                await page.evaluate("""() => document.querySelector('button[ng-click*="submit"]').click()""")
            print(f"{prefix} ✓ Navegação completa", file=sys.stderr)
        except Exception as e:
            print(f"{prefix} Navegação falhou ({e}), aguardando calendário...", file=sys.stderr)
            # Fallback: wait for calendar to appear instead of fixed timeout
            try:
                await page.wait_for_function(
                    "() => !!document.querySelector('.fc, #calendar, #divcalendar')",
                    timeout=10000,
                    polling=100
                )
            except Exception:
                pass  # Continue to check below

        # Verificar se calendário apareceu
        calendar_found = await page.evaluate("() => !!document.querySelector('.fc, #calendar, #divcalendar')")
        if not calendar_found:
            print(f"{prefix} Calendário não encontrado", file=sys.stderr)
            return None

        # Evitar corrida: em alguns agentes o calendário aparece, mas os eventos
        # ainda estão carregando/renderizando.
        try:
            await page.wait_for_timeout(400)
            evt_count = await page.evaluate("() => document.querySelectorAll('.fc-event').length")
            if evt_count == 0:
                await page.wait_for_timeout(2500)
        except Exception:
            pass

        # Debug: verificar estrutura do calendário
        calendar_info = await page.evaluate("""() => {
            const fc = document.querySelector('.fc');
            const dayCells = document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date]');
            const timeCols = document.querySelectorAll('.fc-timegrid-col[data-date], .fc-timegrid-col-frame[data-date]');
            const events = document.querySelectorAll('.fc-event');
            const title = document.querySelector('.fc-toolbar-title')?.textContent || 'sem título';
            return {
                hasFC: !!fc,
                dayCellsCount: dayCells.length,
                timeColsCount: timeCols.length,
                eventsCount: events.length,
                title: title
            };
        }""")
        print(
            f"{prefix} Calendário: {calendar_info['title']}, "
            f"dayGrid={calendar_info['dayCellsCount']}, timeGrid={calendar_info['timeColsCount']}, "
            f"eventos={calendar_info['eventsCount']}",
            file=sys.stderr,
        )

        def _merge_events(dest: dict, date_str: str, new_events: list[dict]) -> None:
            """Merge events lists with simple de-dup by (title,time)."""
            if not new_events:
                return
            existing = dest.setdefault(date_str, [])
            seen = {(e.get("title", ""), e.get("time", "")) for e in existing}
            for e in new_events:
                key = (e.get("title", ""), e.get("time", ""))
                if key in seen:
                    continue
                seen.add(key)
                existing.append(e)

        async def _get_visible_calendar_date_range() -> tuple[date | None, date | None]:
            """Retorna o intervalo (min,max) de datas visíveis na grade do calendário."""
            res = await page.evaluate(
                """() => {
                    const sel = [
                        '.fc-daygrid-day[data-date]',
                        '.fc-day[data-date]',
                        '.fc-timegrid-col[data-date]',
                        '.fc-timegrid-col-frame[data-date]',
                    ].join(',');
                    const cells = Array.from(document.querySelectorAll(sel));
                    const dates = cells.map(c => c.getAttribute('data-date')).filter(Boolean).sort();
                    if (!dates.length) return { min: null, max: null };
                    return { min: dates[0], max: dates[dates.length - 1] };
                }"""
            )
            try:
                min_s = (res or {}).get("min")
                max_s = (res or {}).get("max")
                return (
                    date.fromisoformat(min_s) if min_s else None,
                    date.fromisoformat(max_s) if max_s else None,
                )
            except Exception:
                return None, None

        async def _goto_month_containing(target: date) -> None:
            """Navega (prev/next) até a grade que contenha a data alvo."""
            for _ in range(48):
                dmin, dmax = await _get_visible_calendar_date_range()
                if dmin is None or dmax is None:
                    return
                if target < dmin:
                    prev_btn = page.locator('.fc-prev-button').first
                    if await prev_btn.count() == 0:
                        return
                    old_min, old_max = dmin.isoformat(), dmax.isoformat()
                    await prev_btn.click(timeout=5000)
                    try:
                        await page.wait_for_function(
                            """(args) => {
                                const { oldMin, oldMax } = args;
                                const cells = Array.from(document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date], .fc-timegrid-col[data-date], .fc-timegrid-col-frame[data-date]'));
                                const dates = cells.map(c => c.getAttribute('data-date')).filter(Boolean).sort();
                                if (!dates.length) return false;
                                return dates[0] !== oldMin || dates[dates.length - 1] !== oldMax;
                            }""",
                            {"oldMin": old_min, "oldMax": old_max},
                            timeout=5000,
                            polling=100,
                        )
                    except Exception:
                        return
                    continue
                if target > dmax:
                    next_btn = page.locator('.fc-next-button').first
                    if await next_btn.count() == 0:
                        return
                    old_min, old_max = dmin.isoformat(), dmax.isoformat()
                    await next_btn.click(timeout=5000)
                    try:
                        await page.wait_for_function(
                            """(args) => {
                                const { oldMin, oldMax } = args;
                                const cells = Array.from(document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date], .fc-timegrid-col[data-date], .fc-timegrid-col-frame[data-date]'));
                                const dates = cells.map(c => c.getAttribute('data-date')).filter(Boolean).sort();
                                if (!dates.length) return false;
                                return dates[0] !== oldMin || dates[dates.length - 1] !== oldMax;
                            }""",
                            {"oldMin": old_min, "oldMax": old_max},
                            timeout=5000,
                            polling=100,
                        )
                    except Exception:
                        return
                    continue
                return

        async def _extract_events_visible_and_more() -> tuple[dict, list[str]]:
            """Extrai eventos das células visíveis e retorna também dias com "+mais"."""
            res = await page.evaluate(
                """(args) => {
                    const { startDate, endDate } = args;
                    const startParts = startDate.split('-').map(Number);
                    const endParts = endDate.split('-').map(Number);
                    const startNum = startParts[0] * 10000 + startParts[1] * 100 + startParts[2];
                    const endNum = endParts[0] * 10000 + endParts[1] * 100 + endParts[2];

                    const eventos = {};
                    const moreDates = [];
                    const dayCells = document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date]');

                    function addEvent(dateStr, evt) {
                        if (!dateStr) return;
                        const dateParts = dateStr.split('-').map(Number);
                        const dateNum = dateParts[0] * 10000 + dateParts[1] * 100 + dateParts[2];
                        if (dateNum < startNum || dateNum > endNum) return;

                        const titleEl = evt.querySelector('.fc-event-title');
                        const timeEl = evt.querySelector('.fc-event-time');
                        const rawTitle = (titleEl?.textContent || evt.textContent || 'Evento').trim();
                        const rawTime = timeEl?.textContent?.trim() || '';
                        const obj = { title: rawTitle, time: rawTime, type: 'Compromisso', details: '' };

                        if (!eventos[dateStr]) eventos[dateStr] = [];
                        eventos[dateStr].push(obj);
                    }

                    for (const cell of dayCells) {
                        const dateStr = cell.getAttribute('data-date');
                        if (!dateStr) continue;

                        // Evento(s) visíveis na célula (dayGrid)
                        const eventsInCell = cell.querySelectorAll('.fc-event');
                        for (const evt of eventsInCell) addEvent(dateStr, evt);

                        // Indicação de overflow ("+ mais") - eventos podem estar escondidos no popover
                        const moreLink = cell.querySelector('.fc-daygrid-more-link, .fc-more-link');
                        if (moreLink) moreDates.push(dateStr);
                    }

                    // timeGrid (agenda semanal/diária)
                    const timeCols = document.querySelectorAll('.fc-timegrid-col[data-date]');
                    for (const col of timeCols) {
                        const dateStr = col.getAttribute('data-date');
                        if (!dateStr) continue;
                        const eventsInCol = col.querySelectorAll('.fc-event');
                        for (const evt of eventsInCol) addEvent(dateStr, evt);
                    }

                    return { eventos, moreDates };
                }""",
                {"startDate": str(start_date), "endDate": str(end_date)},
            )
            eventos = (res or {}).get("eventos") or {}
            more_dates = (res or {}).get("moreDates") or []
            # Dedup e estabilidade
            more_dates = sorted({d for d in more_dates if isinstance(d, str)})
            return eventos, more_dates

        async def _extract_events_from_popover() -> list[dict]:
            return await page.evaluate(
                """() => {
                    const pop = document.querySelector('.fc-popover');
                    if (!pop) return [];
                    const items = pop.querySelectorAll('.fc-event');
                    const out = [];
                    for (const evt of items) {
                        const titleEl = evt.querySelector('.fc-event-title');
                        const timeEl = evt.querySelector('.fc-event-time');
                        out.push({
                            title: (titleEl?.textContent || evt.textContent || 'Evento').trim(),
                            time: timeEl?.textContent?.trim() || '',
                            type: 'Compromisso',
                            details: ''
                        });
                    }
                    return out;
                }"""
            )

        async def _collect_events_for_period() -> tuple[dict, int]:
            """Coleta eventos cobrindo start_date..end_date a partir do calendário já aberto."""
            eventos_por_dia: dict = {}

            # 1) Ir para uma grade que contenha o fim do período
            await _goto_month_containing(end_date)

            # 2) Coletar grade corrente e voltar até cobrir o início do período
            for _ in range(48):
                dmin, dmax = await _get_visible_calendar_date_range()

                visible_events, more_dates = await _extract_events_visible_and_more()
                for date_str, evts in (visible_events or {}).items():
                    if isinstance(date_str, str) and isinstance(evts, list):
                        _merge_events(eventos_por_dia, date_str, evts)

                # Buscar eventos escondidos no popover ("+ mais")
                for date_str in more_dates:
                    more_link = page.locator(
                        f'.fc-daygrid-day[data-date="{date_str}"] .fc-daygrid-more-link, '
                        f'.fc-day[data-date="{date_str}"] .fc-daygrid-more-link, '
                        f'.fc-daygrid-day[data-date="{date_str}"] .fc-more-link, '
                        f'.fc-day[data-date="{date_str}"] .fc-more-link'
                    ).first
                    if await more_link.count() == 0:
                        continue
                    try:
                        await more_link.click(timeout=1500, force=True, no_wait_after=True)
                        await page.wait_for_selector('.fc-popover', state='visible', timeout=5000)
                        pop_events = await _extract_events_from_popover()
                        _merge_events(eventos_por_dia, date_str, pop_events)
                    except Exception:
                        continue
                    finally:
                        close_btn = page.locator('.fc-popover .fc-popover-close').first
                        if await close_btn.count() > 0:
                            try:
                                await close_btn.click(timeout=1500, force=True, no_wait_after=True)
                            except Exception:
                                pass
                        else:
                            try:
                                await page.keyboard.press('Escape')
                            except Exception:
                                pass
                        await page.wait_for_timeout(100)

                # Se já cobrimos o mês do start_date, podemos parar
                if dmin is None or start_date >= dmin:
                    break

                prev_btn = page.locator('.fc-prev-button').first
                if await prev_btn.count() == 0:
                    break

                # Click e aguardar a grade mudar (evita re-scrape do mesmo mês)
                old_min = dmin.isoformat() if dmin else ""
                old_max = dmax.isoformat() if dmax else ""
                await prev_btn.click(timeout=5000)
                try:
                    await page.wait_for_function(
                        """(args) => {
                            const { oldMin, oldMax } = args;
                            const cells = Array.from(document.querySelectorAll('.fc-daygrid-day[data-date], .fc-day[data-date], .fc-timegrid-col[data-date], .fc-timegrid-col-frame[data-date]'));
                            const dates = cells.map(c => c.getAttribute('data-date')).filter(Boolean).sort();
                            if (!dates.length) return false;
                            return dates[0] !== oldMin || dates[dates.length - 1] !== oldMax;
                        }""",
                        {"oldMin": old_min, "oldMax": old_max},
                        timeout=5000,
                        polling=100,
                    )
                except Exception:
                    break

            eventos_count = sum(len(evts) for evts in eventos_por_dia.values())
            return eventos_por_dia, eventos_count

        eventos_por_dia, eventos_count = await _collect_events_for_period()
        print(f"{prefix} ✓ {agente_label[:25]}: {len(eventos_por_dia)} dias, {eventos_count} eventos", file=sys.stderr)

        return {
            "orgao": {"id": orgao_value, "nome": orgao_label},
            "cargo": {"id": "", "nome": ""},
            "agente": {"id": agente_value, "nome": agente_label},
            "eventos": eventos_por_dia
        }

    except Exception as e:
        print(f"{prefix} Erro {agente_label[:20]}: {e}", file=sys.stderr)
        return None


async def worker_task(
    worker_id: int,
    page,
    queries: list[dict],
    start_date: date,
    end_date: date,
    results: list,
    lock: asyncio.Lock
):
    """
    Task de worker que processa uma lista de queries usando uma page dedicada.

    Args:
        worker_id: ID do worker (para logs)
        page: Page do Playwright (dentro de um context isolado)
        queries: Lista de queries a processar
        start_date: Data inicial
        end_date: Data final
        results: Lista compartilhada para resultados
        lock: Lock para acesso thread-safe aos resultados
    """
    prefix = f"[W{worker_id}]"
    print(f"{prefix} Iniciando com {len(queries)} agentes...", file=sys.stderr)

    per_agent_timeout = int(os.environ.get("DOU_UI_EAGENDAS_AGENT_TIMEOUT", "180"))

    for query in queries:
        try:
            result = await asyncio.wait_for(
                collect_for_agent(
                    page=page,
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    worker_id=worker_id,
                ),
                timeout=per_agent_timeout,
            )
        except asyncio.TimeoutError:
            agent_label = query.get("n3_label") or query.get("n2_label") or query.get("person_label") or "Agente"
            print(f"{prefix} ⏱ Timeout por agente ({per_agent_timeout}s): {agent_label}", file=sys.stderr)
            continue

        if result:
            async with lock:
                results.append(result)

    print(f"{prefix} Finalizado", file=sys.stderr)


def group_queries_by_orgao(queries: list[dict]) -> dict[str, list[dict]]:
    """Agrupa queries por órgão para otimizar reutilização."""
    groups = defaultdict(list)
    for q in queries:
        orgao_id = q.get('n1_value', '')
        groups[orgao_id].append(q)
    return groups


def distribute_queries_to_workers(queries: list[dict], num_workers: int) -> list[list[dict]]:
    """
    Distribui queries entre workers de forma balanceada.

    OTIMIZAÇÃO: Tenta manter queries do mesmo órgão no mesmo worker.
    """
    if not queries:
        return [[] for _ in range(num_workers)]

    # Agrupar por órgão
    groups = group_queries_by_orgao(queries)

    # Ordenar grupos por tamanho (maiores primeiro para melhor balanceamento)
    sorted_groups = sorted(groups.values(), key=len, reverse=True)

    # Distribuir usando algoritmo de "longest processing time first"
    worker_queues: list[list[dict]] = [[] for _ in range(num_workers)]
    worker_loads = [0] * num_workers

    for group in sorted_groups:
        # Encontrar worker com menor carga
        min_load_idx = worker_loads.index(min(worker_loads))
        worker_queues[min_load_idx].extend(group)
        worker_loads[min_load_idx] += len(group)

    return worker_queues


async def main_async():
    """Função principal assíncrona."""
    import time

    from playwright.async_api import async_playwright

    start_time = time.perf_counter()

    # Ler input via INPUT_JSON_PATH (preferido) ou stdin (fallback)
    input_file = os.environ.get("INPUT_JSON_PATH")
    if input_file and Path(input_file).exists():
        input_data = json.loads(Path(input_file).read_text(encoding="utf-8-sig"))
    else:
        input_data = json.loads(sys.stdin.read())

    queries = input_data.get("queries", [])
    periodo = input_data.get("periodo", {})
    max_workers = input_data.get("max_workers", 4)

    if not queries:
        _write_result({"success": False, "error": "Nenhuma query fornecida"})
        return 1

    # Converter datas
    try:
        start_date = date.fromisoformat(periodo["inicio"])
        end_date = date.fromisoformat(periodo["fim"])
    except Exception as e:
        _write_result({"success": False, "error": f"Erro ao parsear datas: {e}"})
        return 1

    # Ajustar número de workers (não mais que queries disponíveis)
    actual_workers = min(max_workers, len(queries))

    print(f"\n{'='*60}", file=sys.stderr)
    print("E-AGENDAS PARALLEL COLLECTOR (Single Browser Mode)", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Agentes: {len(queries)}", file=sys.stderr)
    print(f"Workers: {actual_workers}", file=sys.stderr)
    print(f"Período: {start_date} → {end_date}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Configurar Playwright
    pw_browsers_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "pw-browsers"
    if pw_browsers_path.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers_path)

    LAUNCH_ARGS = [
        '--headless=new',
        '--disable-blink-features=AutomationControlled',
        '--ignore-certificate-errors',
        '--disable-dev-shm-usage',
        '--no-sandbox',
    ]

    results: list[dict] = []
    lock = asyncio.Lock()

    async with async_playwright() as p:
        # Lançar UM ÚNICO browser
        browser = None
        for channel in ['chrome', 'msedge']:
            try:
                browser = await p.chromium.launch(channel=channel, headless=True, args=LAUNCH_ARGS)
                print(f"[MAIN] ✓ Browser {channel} iniciado (único para todos workers)", file=sys.stderr)
                break
            except Exception:
                continue

        if not browser:
            # Fallback para executável
            exe_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ]
            for exe_path in exe_paths:
                if Path(exe_path).exists():
                    try:
                        browser = await p.chromium.launch(executable_path=exe_path, headless=True, args=LAUNCH_ARGS)
                        print("[MAIN] ✓ Browser executable iniciado", file=sys.stderr)
                        break
                    except Exception:
                        continue

        if not browser:
            _write_result({"success": False, "error": "Nenhum browser disponível (Chrome/Edge)"})
            return 1

        # Criar contexts e pages para cada worker
        # Cada context é isolado (como sessão incógnita separada)
        contexts = []
        pages = []

        for _ in range(actual_workers):
            ctx = await browser.new_context(
                ignore_https_errors=True,
                viewport={'width': 1280, 'height': 900},
                permissions=[],
                geolocation=None,
            )
            ctx.set_default_timeout(60000)
            page = await ctx.new_page()
            contexts.append(ctx)
            pages.append(page)

        print(f"[MAIN] ✓ {actual_workers} contexts/pages criados", file=sys.stderr)

        # Distribuir queries entre workers
        worker_queues = distribute_queries_to_workers(queries, actual_workers)

        # Criar e executar tasks em paralelo
        tasks = []
        for i, worker_queries in enumerate(worker_queues):
            if worker_queries:  # Só criar task se tiver queries
                task = asyncio.create_task(
                    worker_task(
                        worker_id=i + 1,
                        page=pages[i],
                        queries=worker_queries,
                        start_date=start_date,
                        end_date=end_date,
                        results=results,
                        lock=lock
                    )
                )
                tasks.append(task)

        # Aguardar todos os workers
        await asyncio.gather(*tasks)

        # Cleanup: fechar contexts
        for ctx in contexts:
            await ctx.close()
        await browser.close()

    elapsed = time.perf_counter() - start_time
    total_eventos = sum(
        sum(len(evts) for evts in ag.get("eventos", {}).values())
        for ag in results
    )

    print(f"\n{'='*60}", file=sys.stderr)
    print("RESULTADO FINAL", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Agentes processados: {len(results)}/{len(queries)}", file=sys.stderr)
    print(f"Total de eventos: {total_eventos}", file=sys.stderr)
    print(f"Tempo total: {elapsed:.1f}s", file=sys.stderr)
    if len(queries) > 0:
        print(f"Tempo médio por agente: {elapsed/len(queries):.1f}s", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Estrutura final
    result = {
        "success": True,
        "data": {
            "periodo": periodo,
            "agentes": results,
            "metadata": {
                "data_coleta": datetime.now().isoformat(),
                "total_agentes": len(results),
                "total_eventos": total_eventos,
                "tempo_execucao_segundos": round(elapsed, 1),
                "workers_utilizados": actual_workers,
                "parallel_mode": True,
                "single_browser_mode": True
            }
        }
    }

    _write_result(result)
    return 0


def main():
    """Entry point síncrono que executa main_async."""
    try:
        return asyncio.run(main_async())
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
