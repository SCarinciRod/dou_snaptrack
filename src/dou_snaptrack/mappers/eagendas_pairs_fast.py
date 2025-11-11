"""
Mapper OTIMIZADO para e-agendas com esperas condicionais e cache.
Performance esperada: 30x mais rápido que eagendas_pairs.py original.
"""
from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class SelectizeCache:
    """Cache inteligente para seletores Selectize com TTL."""

    def __init__(self, frame):
        self.frame = frame
        self._dropdown_cache: dict[str, Any] = {}
        self._cache_times: dict[str, float] = {}
        self._control_cache: dict[str, dict] = {}

    def get_control(self, label_text: str, max_age_ms: int = 5000) -> dict[str, Any] | None:
        """Obtém controle Selectize com cache."""
        now = time.time() * 1000

        if label_text in self._control_cache:
            age = now - self._cache_times.get(label_text, 0)
            if age < max_age_ms:
                return self._control_cache[label_text]

        # Cache miss - buscar novamente
        control = self._find_selectize_by_label(label_text)
        if control:
            self._control_cache[label_text] = control
            self._cache_times[label_text] = now

        return control

    def _find_selectize_by_label(self, label_text: str) -> dict[str, Any] | None:
        """Busca controle Selectize (implementação rápida)."""
        try:
            label_loc = self.frame.locator(f'label:has-text("{label_text}")').first
            if label_loc.count() == 0:
                return None

            selectize = label_loc.locator(
                'xpath=following::div[contains(@class, "selectize-control")][1]'
            ).first

            if selectize.count() == 0:
                parent = label_loc.locator('xpath=ancestor::div[1]')
                selectize = parent.locator('.selectize-control').first

            if selectize.count() > 0:
                return {
                    "label": label_text,
                    "selector": selectize,
                    "input": selectize.locator('.selectize-input').first,
                }

            return None

        except Exception as e:
            logger.error(f"Erro ao buscar selectize '{label_text}': {e}")
            return None

    def invalidate(self, label_text: str | None = None):
        """Invalida cache de um controle específico ou todos."""
        if label_text:
            self._control_cache.pop(label_text, None)
            self._cache_times.pop(label_text, None)
        else:
            self._control_cache.clear()
            self._cache_times.clear()


def wait_dropdown_ready(frame, timeout_ms: int = 2000, min_options: int = 1, poll_ms: int = 50) -> bool:
    """
    Espera dropdown estar pronto com POLLING RÁPIDO (não sleep fixo).

    Retorna assim que min_options disponíveis (geralmente 50-300ms).
    """
    start_time = time.time()

    while (time.time() - start_time) * 1000 < timeout_ms:
        try:
            # Procurar dropdown visível (display: block ou sem display:none)
            visible_dd = frame.locator('.selectize-dropdown[style*="display: block"]:not([style*="visibility: hidden"]), .selectize-dropdown:not([style*="display: none"]):not([style*="visibility: hidden"])').first

            if visible_dd.count() > 0:
                opts_count = visible_dd.locator('.option').count()
                if opts_count >= min_options:
                    return True

            # Fallback: qualquer dropdown com opções
            any_dd = frame.locator('.selectize-dropdown').first
            if any_dd.count() > 0:
                opts_count = any_dd.locator('.option').count()
                if opts_count >= min_options:
                    return True
        except Exception:
            pass

        time.sleep(poll_ms / 1000.0)

    return False


def wait_ajax_idle(page, timeout_ms: int = 3000, poll_ms: int = 50) -> bool:
    """
    Espera AJAX/animações completarem com polling rápido.

    Verifica ausência de spinners/loaders. Sai assim que idle.
    """
    start_time = time.time()

    while (time.time() - start_time) * 1000 < timeout_ms:
        try:
            # Verificar se não há indicadores de loading
            spinners = page.locator('.loading, .spinner, [class*="load"], [class*="spin"]').count()
            if spinners == 0:
                # Aguardar pequena estabilização (50ms) e verificar novamente
                time.sleep(0.05)
                spinners_recheck = page.locator('.loading, .spinner, [class*="load"]').count()
                if spinners_recheck == 0:
                    return True
        except Exception:
            pass

        time.sleep(poll_ms / 1000.0)

    return False


def open_selectize_fast(page, frame, selectize_control: dict, timeout_ms: int = 2000) -> bool:
    """
    Abre dropdown Selectize com espera CONDICIONAL (não fixo).
    """
    try:
        input_elem = selectize_control["input"]
        if input_elem.count() == 0:
            return False

        # Fechar quaisquer dropdowns abertos
        try:
            page.keyboard.press('Escape')
            time.sleep(0.05)
        except Exception:
            pass

        # Garantir visibilidade antes de clicar
        try:
            input_elem.scroll_into_view_if_needed()
            time.sleep(0.05)
        except Exception:
            pass

        # Clicar para abrir
        input_elem.click()

        # OTIMIZAÇÃO: Aguardar até dropdown estar pronto (não sleep fixo!)
        ready = wait_dropdown_ready(frame, timeout_ms=timeout_ms, min_options=1, poll_ms=50)

        if not ready:
            logger.warning(f"Dropdown não ficou pronto em {timeout_ms}ms - tentando estratégia robusta")
            # Fallback: usar estratégia robusta do DOU utils
            try:
                from dou_utils.dropdown_strategies import open_dropdown_robust
                root = selectize_control.get("selector") or input_elem
                ready = open_dropdown_robust(frame, root, delay_ms=120)
            except Exception:
                pass

        return ready

    except Exception as e:
        logger.error(f"Erro ao abrir dropdown: {e}")
        return False


def get_selectize_options_fast(frame, exclude_patterns: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Coleta opções com busca OTIMIZADA (cache early-exit).
    """
    options_list = []
    exclude_patterns = exclude_patterns or []

    try:
        # OTIMIZAÇÃO: Buscar apenas dropdown visível (early exit)
        dropdown = None

        # Tentar primeiro dropdown visível
        visible_dd = frame.locator('.selectize-dropdown[style*="display: block"]').first
        if visible_dd.count() > 0:
            dropdown = visible_dd
        else:
            # Fallback: qualquer dropdown com opções
            all_dds = frame.locator('.selectize-dropdown').all()
            for dd in all_dds:
                try:
                    if dd.locator('.option').count() > 0:
                        dropdown = dd
                        break
                except Exception:
                    continue

        if not dropdown:
            # Fallback robusto: coletar por estratégias genéricas (como no DOU)
            try:
                from dou_utils.dropdown_strategies import collect_open_list_options
                options_list = collect_open_list_options(frame)
            except Exception:
                options_list = []
            # Filtrar placeholders se vieram do fallback
            try:
                from ..mappers.pairs_mapper import remove_placeholders as _remove_placeholders
                options_list = _remove_placeholders(options_list)
            except Exception:
                pass
            # Excluir padrões (e.g., "todos os ocupantes")
            if exclude_patterns:
                def _skip(txt: str) -> bool:
                    t = (txt or '').lower()
                    return any(pat.lower() in t for pat in exclude_patterns)
                options_list = [o for o in options_list if not _skip(str(o.get('text') or ''))]
            return options_list

        # Coletar opções
        options = dropdown.locator('.option').all()

        for idx, opt in enumerate(options):
            try:
                text = (opt.text_content() or "").strip()

                if not text:
                    continue

                # Verificar exclusões
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern.lower() in text.lower():
                        should_exclude = True
                        break

                if should_exclude:
                    continue

                # Atributos
                data_value = None
                data_index = None
                try:
                    data_value = opt.get_attribute('data-value')
                    data_index = opt.get_attribute('data-index') or opt.get_attribute('data-selectable-index')
                except Exception:
                    pass

                options_list.append({
                    "index": idx,
                    "text": text,
                    "value": data_value,
                    "data_index": data_index,
                    "_handle": opt
                })

            except Exception as e:
                logger.warning(f"Erro ao processar opção {idx}: {e}")

        # Filtrar placeholders usando util do DOU
        try:
            from ..mappers.pairs_mapper import remove_placeholders as _remove_placeholders
            options_list = _remove_placeholders(options_list)
        except Exception:
            pass
        # Excluir padrões (e.g., "todos os ocupantes")
        if exclude_patterns:
            def _skip2(txt: str) -> bool:
                t = (txt or '').lower()
                return any(pat.lower() in t for pat in exclude_patterns)
            options_list = [o for o in options_list if not _skip2(str(o.get('text') or ''))]
        return options_list

    except Exception as e:
        logger.error(f"Erro ao coletar opções: {e}")
        return []


def select_option_fast(page, frame, option: dict[str, Any], wait_ajax: bool = True, timeout_ms: int = 3000) -> bool:
    """
    Seleciona opção com espera AJAX CONDICIONAL.
    """
    try:
        handle = option.get("_handle")
        if not handle:
            return False

        # Clicar
        handle.click()

        # OTIMIZAÇÃO: Aguardar AJAX completar (não sleep fixo!)
        if wait_ajax:
            wait_ajax_idle(page, timeout_ms=timeout_ms, poll_ms=50)
        else:
            time.sleep(0.1)  # Mínimo para garantir clique processado

        return True

    except Exception as e:
        logger.error(f"Erro ao selecionar opção: {e}")
        return False


def check_ativos_checkbox_fast(frame, cache: SelectizeCache, near_label: str) -> bool:
    """Marca checkbox Ativos com cache de controle."""
    try:
        # Usar cache para localizar contexto
        control = cache.get_control(near_label)
        if not control:
            context = frame
        else:
            context = control["selector"].locator('xpath=ancestor::div[2]')

        ativos_labels = context.locator('label:has-text("Ativos")').all()

        for label in ativos_labels:
            try:
                label_text = (label.text_content() or "").strip().lower()

                if label_text != "ativos":
                    continue

                # Procurar checkbox
                cb_inside = label.locator('input[type="checkbox"]')
                if cb_inside.count() > 0:
                    checkbox = cb_inside.first
                else:
                    checkbox = label.locator('xpath=preceding-sibling::input[@type="checkbox"][1]')
                    if checkbox.count() == 0:
                        label_for = label.get_attribute('for')
                        if label_for:
                            checkbox = frame.locator(f'input#{label_for}[type="checkbox"]').first

                if checkbox and checkbox.count() > 0:
                    if not checkbox.is_checked():
                        checkbox.check()
                        time.sleep(0.1)  # Mínimo para garantir mudança processada
                    return True

            except Exception as e:
                logger.warning(f"Erro ao processar checkbox: {e}")

        return False

    except Exception as e:
        logger.error(f"Erro ao buscar checkbox Ativos: {e}")
        return False


def map_eagendas_pairs_fast(
    page,
    orgao_filter: str | None = None,
    cargo_filter: str | None = None,
    limit_orgaos: int | None = None,
    limit_cargos_per_orgao: int | None = None,
    verbose: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None
) -> dict[str, Any]:
    """
    Mapper OTIMIZADO com esperas condicionais e cache.

    Performance esperada: 30x mais rápido (3-4h → 5-8min para 227 órgãos).

    Args:
        page: Página Playwright
        orgao_filter: Regex para filtrar órgãos
        cargo_filter: Regex para filtrar cargos
        limit_orgaos: Limite de órgãos
        limit_cargos_per_orgao: Limite de cargos por órgão
        verbose: Logs detalhados
        progress_callback: Função chamada com (current, total, message)

    Returns:
        Dict com hierarquia mapeada
    """
    import re

    # Selecionar melhor frame do contexto (evita pegar main_frame errado)
    try:
        from ..utils.dom import find_best_frame
        frame = find_best_frame(page.context)
    except Exception:
        frame = page.main_frame

    # Permitir ajuste de timeout via env; default 9000ms
    try:
        DD_TIMEOUT_MS = int(os.environ.get("EAGENDAS_DD_TIMEOUT_MS", "9000"))
    except Exception:
        DD_TIMEOUT_MS = 9000
    cache = SelectizeCache(frame)

    result = {
        "url": page.url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hierarchy": [],
        "stats": {
            "total_orgaos": 0,
            "total_cargos": 0,
            "total_agentes": 0,
        },
        "performance": {
            "start_time": time.time(),
            "end_time": None,
            "total_seconds": None,
        }
    }

    try:
        # 0. Preflight: aguardar o label principal aparecer
        with contextlib.suppress(Exception):
            frame.wait_for_selector('label:has-text("Órgão ou entidade")', timeout=DD_TIMEOUT_MS)

        # 1. Localizar controles com cache
        dd_orgao = cache.get_control("Órgão ou entidade")
        dd_cargo = cache.get_control("Cargo")
        dd_agente = cache.get_control("Agente Público Obrigado")

        if not dd_orgao:
            raise RuntimeError("Dropdown 'Órgão ou entidade' não encontrado")

        # 2. Marcar checkboxes Ativos
        check_ativos_checkbox_fast(frame, cache, "Órgão ou entidade")
        if dd_cargo:
            check_ativos_checkbox_fast(frame, cache, "Cargo")
        if dd_agente:
            check_ativos_checkbox_fast(frame, cache, "Agente Público Obrigado")

        time.sleep(0.5)  # Estabilização após checkboxes (aumentado para 500ms)

        # 3. Coletar órgãos (timeout maior no início)
        if not open_selectize_fast(page, frame, dd_orgao, timeout_ms=DD_TIMEOUT_MS):
            raise RuntimeError("Não foi possível abrir dropdown de Órgãos")

        orgaos = get_selectize_options_fast(frame)

        try:
            page.keyboard.press('Escape')
            time.sleep(0.05)
        except Exception:
            pass

        result["stats"]["total_orgaos"] = len(orgaos)

        # Filtrar órgãos
        if orgao_filter:
            pattern = re.compile(orgao_filter, re.I)
            orgaos = [o for o in orgaos if pattern.search(o.get("text", ""))]

        if limit_orgaos and limit_orgaos > 0:
            orgaos = orgaos[:limit_orgaos]

        total_orgaos = len(orgaos)

        # 4. Iterar órgãos
        for idx_org, orgao in enumerate(orgaos, 1):
            if verbose and idx_org % 10 == 0:  # Log apenas a cada 10 (não todo loop!)
                logger.info(f"[{idx_org}/{total_orgaos}] Progresso...")

            if progress_callback:
                progress_callback(idx_org, total_orgaos, f"Processando {orgao.get('text', '???')}")

            # Invalidar cache de controles (DOM pode ter mudado)
            cache.invalidate("Cargo")
            cache.invalidate("Agente Público Obrigado")

            # Abrir dropdown de órgão
            dd_orgao = cache.get_control("Órgão ou entidade")
            if not dd_orgao:
                logger.error("Dropdown 'Órgão ou entidade' não encontrado ao reabrir")
                continue
            if not open_selectize_fast(page, frame, dd_orgao, timeout_ms=DD_TIMEOUT_MS):
                logger.error("Erro ao abrir dropdown de órgãos")
                continue

            # Selecionar órgão
            if not select_option_fast(page, frame, orgao, wait_ajax=True, timeout_ms=7000):
                logger.error(f"Erro ao selecionar '{orgao.get('text')}'")
                with contextlib.suppress(Exception):
                    page.keyboard.press('Escape')
                continue

            orgao_entry = {
                "orgao": orgao.get("text"),
                "orgao_value": orgao.get("value"),
                "cargos": []
            }

            # 5. Verificar N2 (Cargo)
            dd_cargo = cache.get_control("Cargo")
            if not dd_cargo:
                result["hierarchy"].append(orgao_entry)
                continue

            # Verificar se está desabilitado
            try:
                class_attr = dd_cargo["selector"].get_attribute('class') or ''
                if 'disabled' in class_attr:
                    result["hierarchy"].append(orgao_entry)
                    continue
            except Exception:
                pass

            # Abrir e coletar cargos
            if not open_selectize_fast(page, frame, dd_cargo, timeout_ms=DD_TIMEOUT_MS):
                result["hierarchy"].append(orgao_entry)
                continue

            cargos = get_selectize_options_fast(frame)

            try:
                page.keyboard.press('Escape')
                time.sleep(0.05)
            except Exception:
                pass

            result["stats"]["total_cargos"] += len(cargos)

            # Filtrar cargos
            if cargo_filter:
                pattern = re.compile(cargo_filter, re.I)
                cargos = [c for c in cargos if pattern.search(c.get("text", ""))]

            if limit_cargos_per_orgao and limit_cargos_per_orgao > 0:
                cargos = cargos[:limit_cargos_per_orgao]

            # 6. Iterar cargos
            for _idx_cargo, cargo in enumerate(cargos, 1):
                # Abrir cargo
                dd_cargo = cache.get_control("Cargo")
                if not dd_cargo:
                    continue
                if not open_selectize_fast(page, frame, dd_cargo, timeout_ms=DD_TIMEOUT_MS):
                    continue

                # Selecionar cargo
                if not select_option_fast(page, frame, cargo, wait_ajax=True, timeout_ms=3000):
                    with contextlib.suppress(Exception):
                        page.keyboard.press('Escape')
                    continue

                cargo_entry = {
                    "cargo": cargo.get("text"),
                    "cargo_value": cargo.get("value"),
                    "agentes": []
                }

                # 7. Verificar N3 (Agente)
                cache.invalidate("Agente Público Obrigado")
                dd_agente = cache.get_control("Agente Público Obrigado")

                if not dd_agente:
                    orgao_entry["cargos"].append(cargo_entry)
                    continue

                # Verificar se desabilitado
                try:
                    class_attr = dd_agente["selector"].get_attribute('class') or ''
                    if 'disabled' in class_attr:
                        orgao_entry["cargos"].append(cargo_entry)
                        continue
                except Exception:
                    pass

                # Scroll para garantir visibilidade
                try:
                    dd_agente["input"].scroll_into_view_if_needed()
                    time.sleep(0.1)
                except Exception:
                    pass

                # Abrir e coletar agentes
                if not open_selectize_fast(page, frame, dd_agente, timeout_ms=DD_TIMEOUT_MS):
                    orgao_entry["cargos"].append(cargo_entry)
                    continue

                # FILTRAR "Todos os ocupantes"
                agentes = get_selectize_options_fast(frame, exclude_patterns=["todos os ocupantes"])

                try:
                    page.keyboard.press('Escape')
                    time.sleep(0.05)
                except Exception:
                    pass

                result["stats"]["total_agentes"] += len(agentes)

                cargo_entry["agentes"] = [
                    {
                        "agente": a.get("text"),
                        "agente_value": a.get("value")
                    }
                    for a in agentes
                ]

                orgao_entry["cargos"].append(cargo_entry)

            result["hierarchy"].append(orgao_entry)

        # Finalizar
        result["performance"]["end_time"] = time.time()
        result["performance"]["total_seconds"] = result["performance"]["end_time"] - result["performance"]["start_time"]

        if verbose:
            logger.info(f"\n✅ Mapeamento concluído em {result['performance']['total_seconds']:.1f}s")
            logger.info(f"  Órgãos: {len(result['hierarchy'])}")
            logger.info(f"  Cargos: {result['stats']['total_cargos']}")
            logger.info(f"  Agentes: {result['stats']['total_agentes']}")

        return result

    except Exception as e:
        logger.error(f"Erro ao mapear e-agendas: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)
        result["performance"]["end_time"] = time.time()
        result["performance"]["total_seconds"] = result["performance"]["end_time"] - result["performance"]["start_time"]
        return result
