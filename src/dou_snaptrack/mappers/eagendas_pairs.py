from __future__ import annotations

import contextlib
import logging
import re
import time
from typing import Any

from ..utils.dom import is_select

logger = logging.getLogger(__name__)

# Flag para indicar se imports foram bem-sucedidos
_imports_ok = False

# Tentar importar módulos do dou_utils e pairs_mapper
try:
    from dou_utils.dropdown_strategies import (
        collect_open_list_options as _du_collect_options,
        open_dropdown_robust as _du_open_dropdown,
    )

    from ..mappers.pairs_mapper import (
        _scroll_listbox_to_end as _pm_scroll_listbox_to_end,
        filter_opts as _pm_filter_opts,
        remove_placeholders as _pm_remove_placeholders,
        select_by_text_or_attrs as _pm_select_by_text_or_attrs,
        wait_n2_repopulated as _pm_wait_n2_repopulated,
    )

    # Adapters para unificar assinaturas e exportar com nomes padrão
    def _adapter_open_dropdown(page_or_frame, handle):
        """Adapter: converte (page, handle) -> (frame, locator) conforme necessário"""
        try:
            return _du_open_dropdown(page_or_frame, handle)
        except TypeError:
            # Se falhar, tenta com nomenclatura alternativa
            return _du_open_dropdown(frame=page_or_frame, locator=handle)

    def _adapter_collect_options(page_or_frame):
        """Adapter: converte (page) -> (frame) conforme necessário"""
        try:
            return _du_collect_options(page_or_frame)
        except TypeError:
            return _du_collect_options(frame=page_or_frame)

    # Re-exportar funções do pairs_mapper
    remove_placeholders = _pm_remove_placeholders
    filter_opts = _pm_filter_opts
    select_by_text_or_attrs = _pm_select_by_text_or_attrs
    wait_n2_repopulated = _pm_wait_n2_repopulated
    _scroll_listbox_to_end = _pm_scroll_listbox_to_end

    # Atribuir adapters aos nomes públicos
    open_dropdown_robust = _adapter_open_dropdown
    collect_open_list_options = _adapter_collect_options

    _imports_ok = True

except ImportError as e:
    logger.error("Failed to import required modules: %s", e)

    # Fallbacks para quando as importações falharem
    def remove_placeholders(options):
        logger.warning("Using fallback for remove_placeholders.")
        return options or []

    def filter_opts(options, *args, **kwargs):
        logger.warning("Using fallback for filter_opts.")
        return options or []

    def select_by_text_or_attrs(page, root, option):
        logger.warning("Using fallback for select_by_text_or_attrs.")
        try:
            if is_select(root.get('handle')):
                try:
                    root['handle'].select_option(value=option.get('value'))
                    page.wait_for_load_state('networkidle', timeout=30000)
                    return True
                except Exception as e:
                    logger.error("Error selecting option by value: %s", e)
            try:
                root['handle'].click()
            except Exception as e:
                logger.error("Error clicking root handle: %s", e)
            txt = option.get('text') or ''
            try:
                opt = page.get_by_role('option', name=txt).first
                if opt and opt.count() > 0 and opt.is_visible():
                    opt.click()
                    page.wait_for_load_state('networkidle', timeout=30000)
                    return True
            except Exception as e:
                logger.error("Error selecting option by text: %s", e)
        except Exception as e:
            logger.error("General error in select_by_text_or_attrs: %s", e)
        return False

    def wait_n2_repopulated(page, n2_root, prev_count, timeout_ms=15000):
        logger.warning("Using fallback for wait_n2_repopulated.")
        page.wait_for_timeout(1000)

    def _scroll_listbox_to_end(page):
        logger.warning("Using fallback for _scroll_listbox_to_end.")
        pass

    def _fallback_open_dropdown_robust(page, handle):
        logger.warning("Using fallback for open_dropdown_robust.")
        try:
            handle.click()
            page.wait_for_timeout(500)
            return True
        except Exception:
            return False

    def _fallback_collect_open_list_options(page):
        logger.warning("Using fallback for collect_open_list_options.")
        return []

    # Atribuir fallbacks aos nomes públicos
    open_dropdown_robust = _fallback_open_dropdown_robust
    collect_open_list_options = _fallback_collect_open_list_options


def map_eagendas_dropdowns(page, frame=None, verbose: bool = False) -> dict[str, Any]:
    """Mapeia dropdowns específicos do e-agendas.

    Args:
        page: Página Playwright
        frame: Frame específico (opcional, usa find_best_frame se None)
        verbose: Exibir logs detalhados

    Returns:
        Dicionário com mapeamento dos dropdowns
    """
    if frame is None:
        from ..utils.dom import find_best_frame
        # Assumindo que page tem context
        try:
            frame = find_best_frame(page.context)
        except Exception:
            frame = page.main_frame

    result = {
        "url": page.url,
        "dropdowns": [],
        "comboboxes_count": 0
    }

    try:
        comboboxes = frame.get_by_role('combobox')
        cnt = comboboxes.count()
        result["comboboxes_count"] = cnt

        if verbose:
            logger.info(f"Found {cnt} comboboxes in e-agendas")

        # Mapear cada combobox
        for i in range(cnt):
            try:
                cb = comboboxes.nth(i)
                info = {
                    "index": i,
                    "visible": cb.is_visible(),
                    "text": cb.text_content(),
                    "aria_label": cb.get_attribute("aria-label"),
                    "id": cb.get_attribute("id"),
                }
                result["dropdowns"].append(info)
            except Exception as e:
                logger.error(f"Error mapping combobox {i}: %s", e)

    except Exception as e:
        logger.error("Error mapping e-agendas dropdowns: %s", e)

    return result


def map_eagendas_pairs(
    page,
    orgao_filter: str | None = None,
    cargo_filter: str | None = None,
    limit_orgaos: int | None = None,
    limit_cargos_per_orgao: int | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Mapeia pares hierárquicos Órgão → Cargo → Agente Público no e-agendas.

    Args:
        page: Página Playwright (já deve estar em eagendas.cgu.gov.br)
        orgao_filter: Regex para filtrar órgãos (None = todos)
        cargo_filter: Regex para filtrar cargos (None = todos)
        limit_orgaos: Limite de órgãos a processar
        limit_cargos_per_orgao: Limite de cargos por órgão
        verbose: Logs detalhados

    Returns:
        Dict com estrutura hierárquica de pares
    """
    from .eagendas_selectize import (
        DEFAULT_EXCLUDE_PATTERNS,
        close_selectize_dropdown,
        find_and_check_ativos_checkbox,
        find_selectize_by_label,
        get_selectize_options,
        is_selectize_disabled,
        open_selectize_dropdown,
        select_selectize_option,
        select_selectize_option_via_api,
    )

    frame = page.main_frame
    result = {
        "url": page.url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hierarchy": [],
        "stats": {
            "total_orgaos": 0,
            "total_cargos": 0,
            "total_agentes": 0,
        }
    }

    try:
        # 1. Encontrar os 3 dropdowns
        if verbose:
            logger.info("Localizando dropdowns...")

        dd_orgao = find_selectize_by_label(frame, "Órgão ou entidade")
        dd_cargo = find_selectize_by_label(frame, "Cargo")
        dd_agente = find_selectize_by_label(frame, "Agente Público Obrigado")

        if not dd_orgao:
            raise RuntimeError("Dropdown 'Órgão ou entidade' não encontrado")

        # 2. Marcar checkboxes "Ativos" para cada dropdown
        if verbose:
            logger.info("Marcando checkboxes 'Ativos'...")

        find_and_check_ativos_checkbox(frame, "Órgão ou entidade")
        if dd_cargo:
            find_and_check_ativos_checkbox(frame, "Cargo")
        if dd_agente:
            find_and_check_ativos_checkbox(frame, "Agente Público Obrigado")

        time.sleep(1)  # Aguardar atualização após marcar checkboxes

        # 3. Abrir e coletar opções de Órgão (N1)
        if verbose:
            logger.info("Coletando órgãos...")

        if not open_selectize_dropdown(page, dd_orgao):
            raise RuntimeError("Não foi possível abrir dropdown de Órgãos")

        orgaos = get_selectize_options(
            frame,
            include_empty=False,
            exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
            scope_to=dd_orgao,
        )
        close_selectize_dropdown(page)

        result["stats"]["total_orgaos"] = len(orgaos)

        if verbose:
            logger.info(f"Encontrados {len(orgaos)} órgãos")

        # Filtrar órgãos
        if orgao_filter:
            pattern = re.compile(orgao_filter, re.I)
            orgaos = [o for o in orgaos if pattern.search(o.get("text", ""))]
            if verbose:
                logger.info(f"Após filtro: {len(orgaos)} órgãos")

        if limit_orgaos and limit_orgaos > 0:
            orgaos = orgaos[:limit_orgaos]

        # 4. Iterar sobre cada órgão
        for idx_org, orgao in enumerate(orgaos, 1):
            if verbose:
                logger.info(f"[{idx_org}/{len(orgaos)}] Processando: {orgao.get('text', '???')}")

            # Abrir dropdown de órgão novamente
            if not open_selectize_dropdown(page, dd_orgao, wait_ms=800):
                logger.error(f"Erro ao abrir dropdown de órgãos para '{orgao.get('text')}'")
                continue

            # Selecionar órgão
            if not select_selectize_option(page, orgao, wait_after_ms=2000):
                # Fallback via API no controle de Órgão
                sel_ok = False
                with contextlib.suppress(Exception):
                    sel_ok = select_selectize_option_via_api(frame, dd_orgao, orgao, wait_after_ms=2000)
                if not sel_ok:
                    logger.error(f"Erro ao selecionar órgão '{orgao.get('text')}' (via API e clique)")
                    close_selectize_dropdown(page)
                    continue

            # Aguardar população de N2
            time.sleep(2)

            orgao_entry = {
                "orgao": orgao.get("text"),
                "orgao_value": orgao.get("value"),
                "cargos": []
            }

            # 5. Verificar se N2 (Cargo) está disponível
            if not dd_cargo or is_selectize_disabled(dd_cargo):
                if verbose:
                    logger.info(f"  Órgão '{orgao.get('text')}' não possui cargos cadastrados")
                result["hierarchy"].append(orgao_entry)
                continue

            # Abrir e coletar cargos
            if not open_selectize_dropdown(page, dd_cargo, wait_ms=1000):
                logger.warning("  Não foi possível abrir dropdown de Cargos")
                result["hierarchy"].append(orgao_entry)
                continue

            cargos = get_selectize_options(frame, include_empty=False, exclude_patterns=DEFAULT_EXCLUDE_PATTERNS, scope_to=dd_cargo)
            close_selectize_dropdown(page, wait_after_ms=500)

            if verbose:
                logger.info(f"  Encontrados {len(cargos)} cargos")

            result["stats"]["total_cargos"] += len(cargos)

            # Caso especial: órgão sem cargos reais → ir direto para agentes
            if (
                len(cargos) == 0
                and dd_agente
                and not is_selectize_disabled(dd_agente)
                and open_selectize_dropdown(page, dd_agente, wait_ms=1000)
            ):
                        agentes = get_selectize_options(
                            frame,
                            include_empty=False,
                            exclude_patterns=list({*DEFAULT_EXCLUDE_PATTERNS, "todos os ocupantes"}),
                            scope_to=dd_agente,
                        )
                        close_selectize_dropdown(page, wait_after_ms=500)
                        result["stats"]["total_agentes"] += len(agentes)
                        orgao_entry["cargos"].append({
                            "cargo": None,
                            "cargo_value": None,
                            "agentes": [
                                {"agente": a.get("text"), "agente_value": a.get("value")} for a in agentes
                            ],
                        })
                        result["hierarchy"].append(orgao_entry)
                        continue

            # Filtrar cargos
            if cargo_filter:
                pattern = re.compile(cargo_filter, re.I)
                cargos = [c for c in cargos if pattern.search(c.get("text", ""))]

            if limit_cargos_per_orgao and limit_cargos_per_orgao > 0:
                cargos = cargos[:limit_cargos_per_orgao]

            # 6. Iterar sobre cada cargo
            for idx_cargo, cargo in enumerate(cargos, 1):
                if verbose:
                    logger.info(f"    [{idx_cargo}/{len(cargos)}] Cargo: {cargo.get('text', '???')}")

                # Abrir dropdown de cargo
                if not open_selectize_dropdown(page, dd_cargo, wait_ms=800):
                    logger.error("    Erro ao abrir dropdown de cargos")
                    continue

                # Selecionar cargo
                if not select_selectize_option(page, cargo, wait_after_ms=2000):
                    # Fallback via API no controle de Cargo
                    sel_ok = False
                    with contextlib.suppress(Exception):
                        sel_ok = select_selectize_option_via_api(frame, dd_cargo, cargo, wait_after_ms=2000)
                    if not sel_ok:
                        logger.error(f"    Erro ao selecionar cargo '{cargo.get('text')}'")
                        close_selectize_dropdown(page)
                        continue

                # Aguardar população de N3
                time.sleep(2)

                cargo_entry = {
                    "cargo": cargo.get("text"),
                    "cargo_value": cargo.get("value"),
                    "agentes": []
                }

                # 7. Verificar se N3 (Agente Público) está disponível
                if not dd_agente or is_selectize_disabled(dd_agente):
                    if verbose:
                        logger.info(f"      Cargo '{cargo.get('text')}' não possui agentes cadastrados")
                    orgao_entry["cargos"].append(cargo_entry)
                    continue

                # Fechar quaisquer dropdowns abertos e garantir visibilidade de N3
                close_selectize_dropdown(page, wait_after_ms=500)
                try:
                    dd_agente["input"].scroll_into_view_if_needed()
                    time.sleep(0.3)
                except Exception:
                    pass

                # Abrir e coletar agentes
                if not open_selectize_dropdown(page, dd_agente, wait_ms=1000):
                    logger.warning("      Não foi possível abrir dropdown de Agentes")
                    orgao_entry["cargos"].append(cargo_entry)
                    continue

                # Excluir a opção genérica "Todos os ocupantes"
                # Excluir placeholders genéricos e a opção "Todos os ocupantes"
                agentes = get_selectize_options(
                    frame,
                    include_empty=False,
                    exclude_patterns=list({*DEFAULT_EXCLUDE_PATTERNS, "todos os ocupantes"}),
                    scope_to=dd_agente,
                )
                close_selectize_dropdown(page, wait_after_ms=500)

                if verbose:
                    logger.info(f"      Encontrados {len(agentes)} agentes")

                result["stats"]["total_agentes"] += len(agentes)

                # Armazenar agentes
                cargo_entry["agentes"] = [
                    {
                        "agente": a.get("text"),
                        "agente_value": a.get("value")
                    }
                    for a in agentes
                ]

                orgao_entry["cargos"].append(cargo_entry)

            result["hierarchy"].append(orgao_entry)

        # Atualiza estatísticas de órgãos processados com base no que foi realmente mapeado
        result["stats"]["total_orgaos"] = len(result["hierarchy"])  # número efetivamente processado

        if verbose:
            logger.info("\nMapeamento concluído:")
            logger.info(f"  Total de órgãos processados: {result['stats']['total_orgaos']}")
            logger.info(f"  Total de cargos: {result['stats']['total_cargos']}")
            logger.info(f"  Total de agentes: {result['stats']['total_agentes']}")

        return result

    except Exception as e:
        logger.error(f"Erro ao mapear pares e-agendas: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)
        return result
