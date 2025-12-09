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
import contextlib
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
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

    try:
        # Sempre navegar para página inicial (cada coleta é independente)
        print(f"{prefix} Navegando para E-Agendas...", file=sys.stderr)
        await page.goto("https://eagendas.cgu.gov.br/", timeout=30000, wait_until="domcontentloaded")

        # WAIT CONDICIONAL: Aguardar selectize de órgãos inicializar (substitui wait fixo)
        wait_orgao_js = f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}"
        try:
            await page.wait_for_function(wait_orgao_js, timeout=15000, polling=100)
        except Exception as e:
            print(f"{prefix} Selectize não inicializou: {e}", file=sys.stderr)
            return None

        # Selecionar órgão via JavaScript API (mesmo método que versão sync)
        print(f"{prefix} Selecionando órgão: {orgao_label[:30]}...", file=sys.stderr)
        orgao_selected = await page.evaluate("""(args) => {
            const { id, value } = args;
            const el = document.getElementById(id);
            if (!el || !el.selectize) return false;
            el.selectize.setValue(String(value), false);
            return true;
        }""", {'id': DD_ORGAO_ID, 'value': orgao_value})

        if not orgao_selected:
            print(f"{prefix} Falha ao selecionar órgão", file=sys.stderr)
            return None

        # IMPORTANTE: Pequeno delay para Angular processar o ng-change e disparar requisição
        # Sem isso, o wait_for_function abaixo pode começar antes do Angular processar
        await page.wait_for_timeout(300)

        # WAIT CONDICIONAL: Aguardar lista de agentes popular (substitui wait fixo de 2000ms)
        # NOTA: polling=500 é necessário para dar tempo ao Angular processar. Polling muito rápido
        # (100ms) pode impedir que o Angular execute seus ciclos $digest.
        wait_agentes_js = f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 0; }}"
        try:
            await page.wait_for_function(wait_agentes_js, timeout=10000, polling=500)
        except Exception:
            print(f"{prefix} Lista de agentes não populou", file=sys.stderr)
            return None

        # Selecionar agente via JavaScript API
        print(f"{prefix} Selecionando agente: {agente_label[:30]}...", file=sys.stderr)
        agente_selected = await page.evaluate("""(args) => {
            const { id, value } = args;
            const el = document.getElementById(id);
            if (!el || !el.selectize) return false;
            el.selectize.setValue(String(value), false);
            return true;
        }""", {'id': DD_AGENTE_ID, 'value': agente_value})

        if not agente_selected:
            print(f"{prefix} Falha ao selecionar agente", file=sys.stderr)
            return None

        # IMPORTANTE: Delay para Angular processar ng-change e auto-popular cargo
        # O site E-Agendas usa AngularJS que precisa de tempo para:
        # 1. Processar o evento change do selectize
        # 2. Executar ng-change="onUpdateServidor()"
        # 3. Fazer requisição HTTP para buscar cargo do agente
        # 4. Popular o selectize de cargo com o resultado
        # 2000ms é necessário para cobrir a latência de rede
        await page.wait_for_timeout(2000)

        # Remover cookie bar se presente (fazer logo para não atrapalhar)
        await page.evaluate("document.querySelector('.br-cookiebar')?.remove()")

        # OTIMIZAÇÃO: Aguardar cargo E botão ficarem prontos em um único wait
        # Isso combina a espera do cargo + espera do botão em uma operação
        ready_js = """() => {
            const cargo = document.getElementById('filtro_cargo');
            const btn = document.querySelector('button[ng-click*="submit"]');
            // Retorna true quando cargo tem valor E botão está habilitado
            const cargoReady = cargo?.selectize?.getValue()?.length > 0;
            const btnReady = btn && !btn.disabled;
            return cargoReady && btnReady;
        }"""

        try:
            # Esperar até 12s para cargo+botão ficarem prontos
            # NOTA: polling=500 é necessário para dar tempo ao Angular processar o ng-change
            # e auto-popular o campo cargo. Polling muito rápido bloqueia o Angular.
            await page.wait_for_function(ready_js, timeout=12000, polling=500)
            print(f"{prefix} ✓ Cargo + Botão prontos", file=sys.stderr)
        except Exception:
            # Fallback: tentar selecionar cargo manualmente se não auto-populou
            cargo_options = await page.evaluate("""() => {
                const cargo = document.getElementById('filtro_cargo');
                if (!cargo || !cargo.selectize) return [];
                return Object.keys(cargo.selectize.options || {});
            }""")

            if cargo_options:
                print(f"{prefix} ⚠ Selecionando cargo manualmente...", file=sys.stderr)
                await page.evaluate("""() => {
                    const cargo = document.getElementById('filtro_cargo');
                    if (cargo && cargo.selectize) {
                        const opts = Object.keys(cargo.selectize.options || {});
                        if (opts.length > 0) {
                            cargo.selectize.setValue(opts[0], false);
                        }
                    }
                }""")
                # Wait handled by button check below
            else:
                print(f"{prefix} ⚠ Sem cargos disponíveis", file=sys.stderr)

        # Verificar botão - já deve estar pronto após o wait acima, mas verificar novamente
        btn_enabled_js = "() => { const btn = document.querySelector('button[ng-click*=\"submit\"]'); return btn && !btn.disabled; }"
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

        # Função para extrair eventos do calendário visível
        async def extract_events():
            return await page.evaluate("""(args) => {
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

        # Obter mês atual do calendário
        async def get_calendar_month():
            return await page.evaluate("() => document.querySelector('.fc-toolbar-title')?.textContent || ''")

        meses_visitados = set()
        current_month = await get_calendar_month()
        meses_visitados.add(current_month)

        # Coletar eventos do mês atual
        eventos = await extract_events()
        eventos_por_dia.update(eventos)

        # Calcular quantos meses navegar para trás
        months_to_go_back = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)

        for _ in range(months_to_go_back):
            prev_btn = page.locator('.fc-prev-button').first
            if await prev_btn.count() > 0:
                old_month = current_month
                await prev_btn.click()
                # Wait for calendar month title to change (conditional wait)
                try:
                    await page.wait_for_function(
                        f"""(oldMonth) => {{
                            const title = document.querySelector('.fc-toolbar-title')?.textContent || '';
                            return title && title !== oldMonth;
                        }}""",
                        old_month,
                        timeout=5000,
                        polling=50
                    )
                except Exception:
                    pass  # Continue even if timeout - month may already have changed

                current_month = await get_calendar_month()
                if current_month and current_month not in meses_visitados:
                    meses_visitados.add(current_month)
                    eventos = await extract_events()
                    eventos_por_dia.update(eventos)

        eventos_count = sum(len(evts) for evts in eventos_por_dia.values())
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

    for query in queries:
        result = await collect_for_agent(
            page=page,
            query=query,
            start_date=start_date,
            end_date=end_date,
            worker_id=worker_id
        )

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
