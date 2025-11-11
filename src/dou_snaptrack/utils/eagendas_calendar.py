"""
Módulo para interação com o calendário do e-agendas.

Após selecionar Órgão → Cargo → Agente Público, o sistema:
1. Clica em "Mostrar agenda" para carregar o calendário
2. Detecta dias com compromissos
3. Navega entre visualizações (Mês/Dia)
4. Extrai compromissos de cada dia

ESTRUTURA DO CALENDÁRIO:
- Filtros de visualização: Mês | Semana | Dia | Lista
- Grid de dias (clicáveis)
- Dias com eventos têm indicadores visuais
- Ao clicar em um dia: muda para visualização "Dia" com detalhes
"""
from __future__ import annotations

import contextlib
import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# DETECÇÃO DE ELEMENTOS DA PÁGINA DE AGENDA
# ============================================================================

async def find_mostrar_agenda_button_async(page) -> Any | None:
    """Encontra o botão 'Mostrar agenda' após seleção de filtros."""
    button_texts = ["Mostrar agenda", "Mostrar Agenda", "MOSTRAR AGENDA"]

    for text in button_texts:
        try:
            # Buscar botão por texto exato
            btn = page.get_by_role("button", name=text).first
            if await btn.count() > 0 and await btn.is_visible():
                return btn

            # Fallback: buscar por texto contido
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.count() > 0 and await btn.is_visible():
                return btn

        except Exception:
            pass

    # Fallback genérico: buscar por class/id comum
    try:
        btn = page.locator('button[type="submit"]').first
        if await btn.count() > 0 and await btn.is_visible():
            text = await btn.text_content() or ""
            if "mostrar" in text.lower() or "agenda" in text.lower():
                return btn
    except Exception:
        pass

    return None


async def click_mostrar_agenda_async(page, wait_calendar_ms: int = 3000) -> bool:
    """
    Clica no botão 'Mostrar agenda' e aguarda calendário carregar.

    Args:
        page: Página Playwright
        wait_calendar_ms: Tempo de espera para calendário aparecer

    Returns:
        True se sucesso, False caso contrário
    """
    try:
        btn = await find_mostrar_agenda_button_async(page)
        if not btn:
            logger.warning("Botão 'Mostrar agenda' não encontrado")
            return False

        await btn.click(timeout=5000)
        logger.info("Botão 'Mostrar agenda' clicado")

        # Aguardar calendário carregar
        await page.wait_for_timeout(wait_calendar_ms)

        # Aguardar AJAX
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)

        # Verificar se calendário apareceu
        calendar = page.locator("#divcalendar, .fc-view-container, .fc-view").first
        if await calendar.count() > 0:
            logger.info("✅ Calendário carregado com sucesso")
            return True

        logger.warning("⚠️  Calendário não detectado após clicar")
        return False

    except Exception as e:
        logger.error(f"Erro ao clicar em 'Mostrar agenda': {e}")
        return False


# ============================================================================
# NAVEGAÇÃO ENTRE VISUALIZAÇÕES DO CALENDÁRIO
# ============================================================================

async def get_current_calendar_view_async(page) -> str | None:
    """
    Detecta visualização atual do calendário.

    Returns:
        "month" | "week" | "day" | "list" | None
    """
    try:
        # FullCalendar.js usa classes específicas para cada view
        view_classes = {
            "month": [".fc-month-view", ".fc-dayGridMonth-view"],
            "week": [".fc-timeGridWeek-view", ".fc-week-view"],
            "day": [".fc-timeGridDay-view", ".fc-day-view", ".fc-agendaDay-view"],
            "list": [".fc-listMonth-view", ".fc-list-view"],
        }

        for view_type, class_list in view_classes.items():
            for cls in class_list:
                loc = page.locator(cls).first
                if await loc.count() > 0 and await loc.is_visible():
                    return view_type

        return None

    except Exception:
        return None


async def switch_calendar_view_async(page, target_view: str, wait_ms: int = 1000) -> bool:
    """
    Alterna para visualização específica do calendário.

    Args:
        page: Página Playwright
        target_view: "month" | "week" | "day" | "list"
        wait_ms: Tempo de espera após troca

    Returns:
        True se sucesso, False caso contrário
    """
    view_buttons = {
        "month": ["Mês", "Month", "month"],
        "week": ["Semana", "Week", "week"],
        "day": ["Dia", "Day", "day"],
        "list": ["Lista", "List", "list"],
    }

    if target_view not in view_buttons:
        logger.warning(f"Visualização inválida: {target_view}")
        return False

    try:
        # Verificar se já está na view correta
        current = await get_current_calendar_view_async(page)
        if current == target_view:
            logger.info(f"Já na visualização '{target_view}'")
            return True

        # Buscar botão da view
        for btn_text in view_buttons[target_view]:
            try:
                # Por role
                btn = page.get_by_role("button", name=btn_text).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=3000)
                    await page.wait_for_timeout(wait_ms)
                    logger.info(f"✅ Alternado para visualização '{target_view}'")
                    return True

                # Por seletor genérico
                btn = page.locator(f'button:has-text("{btn_text}")').first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=3000)
                    await page.wait_for_timeout(wait_ms)
                    logger.info(f"✅ Alternado para visualização '{target_view}'")
                    return True

            except Exception:
                pass

        logger.warning(f"⚠️  Botão para view '{target_view}' não encontrado")
        return False

    except Exception as e:
        logger.error(f"Erro ao trocar visualização: {e}")
        return False


# ============================================================================
# DETECÇÃO DE DIAS COM EVENTOS
# ============================================================================

async def get_days_with_events_async(page, year: int, month: int) -> list[dict[str, Any]]:
    """
    Detecta dias com eventos no calendário (visualização Mês).

    Args:
        page: Página Playwright
        year: Ano (ex: 2025)
        month: Mês (1-12)

    Returns:
        Lista de dicts: [{"day": 15, "date": "2025-11-15", "has_events": True, "handle": ...}, ...]
    """
    try:
        # Garantir que estamos na view de mês
        await switch_calendar_view_async(page, "month")

        days_with_events = []

        # FullCalendar.js: dias com eventos têm classes específicas
        # Ex: .fc-day.fc-day-number que contém .fc-event
        day_cells = page.locator(".fc-day, [data-date]")
        count = await day_cells.count()

        for i in range(count):
            cell = day_cells.nth(i)
            try:
                # Extrair data do atributo data-date (formato: YYYY-MM-DD)
                date_str = await cell.get_attribute("data-date")
                if not date_str:
                    continue

                # Verificar se data pertence ao mês correto
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if dt.year != year or dt.month != month:
                        continue
                except Exception:
                    continue

                # Verificar se há eventos neste dia
                # Opção 1: buscar .fc-event dentro do cell
                events = cell.locator(".fc-event, .fc-daygrid-event")
                has_events = await events.count() > 0

                # Opção 2: verificar classes indicadoras
                if not has_events:
                    classes = await cell.get_attribute("class") or ""
                    has_events = "has-event" in classes or "fc-event" in classes

                # Buscar número do dia clicável
                day_link = cell.locator("a, .fc-daygrid-day-number, .fc-day-number").first

                days_with_events.append({
                    "day": dt.day,
                    "date": date_str,
                    "date_obj": dt,
                    "has_events": has_events,
                    "handle": cell,
                    "day_link": day_link if await day_link.count() > 0 else None,
                })

            except Exception as e:
                logger.debug(f"Erro ao processar dia {i}: {e}")
                continue

        # Filtrar apenas dias com eventos
        days_with_events = [d for d in days_with_events if d["has_events"]]

        logger.info(f"📅 Encontrados {len(days_with_events)} dias com eventos em {year}-{month:02d}")
        return days_with_events

    except Exception as e:
        logger.error(f"Erro ao detectar dias com eventos: {e}")
        return []


async def click_calendar_day_async(page, day_date: str, wait_ms: int = 2000) -> bool:
    """
    Clica em um dia específico do calendário para abrir visualização detalhada.

    Args:
        page: Página Playwright
        day_date: Data no formato YYYY-MM-DD
        wait_ms: Tempo de espera após clicar

    Returns:
        True se sucesso, False caso contrário
    """
    try:
        # Buscar célula do dia
        day_cell = page.locator(f'[data-date="{day_date}"]').first

        if await day_cell.count() == 0:
            logger.warning(f"Dia {day_date} não encontrado no calendário")
            return False

        # Tentar clicar no link do número do dia
        day_link = day_cell.locator("a, .fc-daygrid-day-number, .fc-day-number").first
        if await day_link.count() > 0:
            await day_link.click(timeout=3000)
        else:
            # Fallback: clicar na célula inteira
            await day_cell.click(timeout=3000)

        await page.wait_for_timeout(wait_ms)

        # Verificar se mudou para view de dia
        current_view = await get_current_calendar_view_async(page)
        if current_view == "day":
            logger.info(f"✅ Aberta visualização do dia {day_date}")
            return True

        logger.warning(f"⚠️  Visualização não mudou para 'day' após clicar em {day_date}")
        return False

    except Exception as e:
        logger.error(f"Erro ao clicar no dia {day_date}: {e}")
        return False


# ============================================================================
# EXTRAÇÃO DE COMPROMISSOS
# ============================================================================

async def extract_day_events_async(page, day_date: str) -> list[dict[str, Any]]:
    """
    Extrai compromissos de um dia específico (deve estar em visualização 'day').

    Args:
        page: Página Playwright
        day_date: Data no formato YYYY-MM-DD

    Returns:
        Lista de eventos: [{"title": "", "time": "", "type": "", "details": ""}, ...]
    """
    events = []

    try:
        # Verificar se estamos na view de dia
        current_view = await get_current_calendar_view_async(page)
        if current_view != "day":
            logger.warning(f"Não está na visualização 'day' (atual: {current_view})")
            return []

        # Buscar eventos na view de dia
        # FullCalendar.js: .fc-timegrid-event, .fc-event-container, .fc-event
        event_containers = page.locator(".fc-timegrid-event, .fc-event, .fc-list-event")
        count = await event_containers.count()

        logger.info(f"Encontrados {count} eventos potenciais no dia {day_date}")

        for i in range(count):
            event = event_containers.nth(i)
            try:
                # Extrair título
                title_loc = event.locator(".fc-event-title, .fc-list-event-title, .fc-title").first
                title = ""
                if await title_loc.count() > 0:
                    title = (await title_loc.text_content() or "").strip()

                # Extrair horário
                time_loc = event.locator(".fc-event-time, .fc-list-event-time, .fc-time").first
                time_str = ""
                if await time_loc.count() > 0:
                    time_str = (await time_loc.text_content() or "").strip()

                # Extrair tipo de evento (se houver badge/tag)
                type_loc = event.locator(".badge, .label, .fc-event-type").first
                event_type = ""
                if await type_loc.count() > 0:
                    event_type = (await type_loc.text_content() or "").strip()

                # Extrair descrição/detalhes (se houver)
                details_loc = event.locator(".fc-event-desc, .fc-description").first
                details = ""
                if await details_loc.count() > 0:
                    details = (await details_loc.text_content() or "").strip()

                # Se não encontrou título, tentar pegar todo o texto do evento
                if not title:
                    title = (await event.text_content() or "").strip()

                if title:  # Só adicionar se tiver pelo menos um título
                    events.append({
                        "date": day_date,
                        "title": title,
                        "time": time_str,
                        "type": event_type,
                        "details": details,
                    })

            except Exception as e:
                logger.debug(f"Erro ao processar evento {i}: {e}")
                continue

        logger.info(f"✅ Extraídos {len(events)} eventos do dia {day_date}")
        return events

    except Exception as e:
        logger.error(f"Erro ao extrair eventos do dia {day_date}: {e}")
        return []


# ============================================================================
# FLUXO COMPLETO: NAVEGAR POR PERÍODO E COLETAR EVENTOS
# ============================================================================

async def collect_events_for_period_async(
    page,
    start_date: date,
    end_date: date,
    return_to_month_view: bool = True
) -> dict[str, list[dict[str, Any]]]:
    """
    Coleta eventos de todos os dias com compromissos em um período.

    Fluxo:
    1. Garante que está na visualização 'month'
    2. Detecta dias com eventos no período
    3. Para cada dia:
       - Clica no dia
       - Extrai eventos
       - Volta para visualização 'month'

    Args:
        page: Página Playwright
        start_date: Data inicial
        end_date: Data final
        return_to_month_view: Se True, volta para 'month' após cada dia

    Returns:
        Dict: {"2025-11-15": [{evento1}, {evento2}], "2025-11-20": [{evento3}], ...}
    """
    all_events = {}

    try:
        # Garantir view de mês
        await switch_calendar_view_async(page, "month")

        # Detectar dias com eventos
        # Nota: assumindo período dentro de um único mês
        # TODO: estender para múltiplos meses
        year = start_date.year
        month = start_date.month

        days_with_events = await get_days_with_events_async(page, year, month)

        # Filtrar dias dentro do período
        days_in_period = [
            d for d in days_with_events
            if start_date <= d["date_obj"] <= end_date
        ]

        logger.info(f"📅 {len(days_in_period)} dias com eventos no período {start_date} → {end_date}")

        # Processar cada dia
        for day_info in days_in_period:
            day_date = day_info["date"]
            logger.info(f"\n🔍 Processando dia: {day_date}")

            # Clicar no dia para abrir detalhes
            ok = await click_calendar_day_async(page, day_date)
            if not ok:
                logger.warning(f"⚠️  Não foi possível abrir dia {day_date}")
                continue

            # Extrair eventos
            events = await extract_day_events_async(page, day_date)
            if events:
                all_events[day_date] = events
                logger.info(f"✅ {len(events)} eventos extraídos de {day_date}")

            # Voltar para visualização de mês (se solicitado)
            if return_to_month_view:
                await switch_calendar_view_async(page, "month", wait_ms=1000)

        logger.info(f"\n📊 TOTAL: {len(all_events)} dias processados, {sum(len(e) for e in all_events.values())} eventos coletados")
        return all_events

    except Exception as e:
        logger.error(f"Erro ao coletar eventos do período: {e}")
        return all_events


# ============================================================================
# HELPER: FORMATAR RESULTADO
# ============================================================================

def format_events_report(events_by_day: dict[str, list[dict[str, Any]]]) -> str:
    """Formata eventos coletados em relatório legível."""
    lines = []
    lines.append("=" * 80)
    lines.append("RELATÓRIO DE COMPROMISSOS")
    lines.append("=" * 80)

    if not events_by_day:
        lines.append("\n⚠️  Nenhum compromisso encontrado no período.")
        return "\n".join(lines)

    total_events = sum(len(events) for events in events_by_day.values())
    lines.append(f"\nTotal: {len(events_by_day)} dias com compromissos")
    lines.append(f"Total de eventos: {total_events}\n")

    for day_date in sorted(events_by_day.keys()):
        events = events_by_day[day_date]
        lines.append(f"\n📅 {day_date} ({len(events)} evento{'s' if len(events) > 1 else ''})")
        lines.append("-" * 80)

        for i, event in enumerate(events, 1):
            lines.append(f"\n  {i}. {event['title']}")
            if event['time']:
                lines.append(f"     ⏰ {event['time']}")
            if event['type']:
                lines.append(f"     🏷️  {event['type']}")
            if event['details']:
                lines.append(f"     📝 {event['details']}")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)
