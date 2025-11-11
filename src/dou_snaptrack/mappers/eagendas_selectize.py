"""
Funções específicas para interação com Selectize.js no e-agendas.

Objetivos desta revisão:
- Associar corretamente o dropdown (.selectize-dropdown) ao controle aberto,
  evitando coletar opções de outro nível (N1/N2/N3).
- Filtrar rótulos genéricos como "Selecione..." e "Todos os ocupantes" por padrão.
- Tornar a verificação de "desabilitado" mais robusta (aria-disabled/disabled/classes).
"""
from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Padrões genéricos a excluir de todos os níveis, a menos que explicitamente solicitado
DEFAULT_EXCLUDE_PATTERNS = [
    "selecione",  # cobre "Selecione", "Selecione...", etc.
    "selecione uma opção",
    "selecione um item",
    "selecione o órgão",
    "selecione o cargo",
    "selecione o agente",
    "todos os ocupantes",
]


def find_selectize_by_label(frame, label_text: str) -> dict[str, Any] | None:
    """
    Encontra um controle Selectize pelo texto do label associado.

    Args:
        frame: Frame Playwright
        label_text: Texto do label (ex: "Órgão ou entidade")

    Returns:
        Dict com selector e informações, ou None se não encontrado
    """
    try:
        # Procurar label
        label_loc = frame.locator(f'label:has-text("{label_text}")').first
        if label_loc.count() == 0:
            logger.warning(f"Label '{label_text}' não encontrado")
            return None

        # Encontrar controle selectize associado - geralmente em um irmão seguinte
        selectize = frame.locator(f'label:has-text("{label_text}")').first.locator(
            'xpath=following::div[contains(@class, "selectize-control")][1]'
        )

        if selectize.count() == 0:
            # Tentar buscar por proximidade no container pai
            parent = label_loc.locator('xpath=ancestor::div[1]')
            selectize = parent.locator('.selectize-control').first

        if selectize.count() > 0:
            # Tentar também localizar o <select> original (se existir) e medir posição
            select_tag = None
            try:
                # Alguns temas mantêm o <select> como irmão anterior
                select_tag = selectize.locator('xpath=preceding-sibling::select[1]').first
                if select_tag.count() == 0:
                    # Ou dentro do mesmo container
                    select_tag = selectize.locator('xpath=ancestor::div[1]//select').first
                if select_tag and select_tag.count() == 0:
                    select_tag = None
            except Exception:
                select_tag = None

            bbox = None
            try:
                bbox = selectize.bounding_box()
            except Exception:
                bbox = None

            return {
                "label": label_text,
                "selector": selectize,
                "input": selectize.locator('.selectize-input').first,
                "select_tag": select_tag,
                "bbox": bbox,
            }

        logger.warning(f"Controle selectize não encontrado para '{label_text}'")
        return None

    except Exception as e:
        logger.error(f"Erro ao buscar selectize '{label_text}': {e}")
        return None


def is_selectize_disabled(selectize_control: dict) -> bool:
    """
    Verifica se um controle Selectize está desabilitado.

    Args:
        selectize_control: Dict retornado por find_selectize_by_label

    Returns:
        True se desabilitado, False caso contrário
    """
    try:
        selector = selectize_control["selector"]
        class_attr = selector.get_attribute('class') or ''
        if 'disabled' in class_attr or 'locked' in class_attr:
            return True

        # Verificar aria-disabled no container ou no input
        with contextlib.suppress(Exception):
            aria_dis = selector.get_attribute('aria-disabled')
            if aria_dis and aria_dis.lower() in {"true", "1"}:
                return True

        inp = selectize_control.get("input")
        if inp and inp.count() > 0:
            with contextlib.suppress(Exception):
                icls = inp.get_attribute('class') or ''
                if 'disabled' in icls:
                    return True
                aria_dis = inp.get_attribute('aria-disabled')
                if aria_dis and aria_dis.lower() in {"true", "1"}:
                    return True

        # Se existir o <select> original, checar "disabled"
        sel = selectize_control.get("select_tag")
        if sel and sel.count() > 0:
            with contextlib.suppress(Exception):
                if sel.is_disabled():
                    return True

        return False
    except Exception:
        return False


def _distance(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    """Distância euclidiana simples entre centros de bounding boxes."""
    if not a or not b:
        return float("inf")
    ax = a["x"] + a["width"]/2.0
    ay = a["y"] + a["height"]/2.0
    bx = b["x"] + b["width"]/2.0
    by = b["y"] + b["height"]/2.0
    dx = ax - bx
    dy = ay - by
    return (dx*dx + dy*dy) ** 0.5


def _find_dropdown_for_control(frame, selectize_control: dict) -> Any | None:
    """
    Tenta identificar o dropdown (.selectize-dropdown) correspondente ao controle aberto.

    Estratégia:
    - Prioriza dropdowns VISÍVEIS.
    - Se múltiplos, escolhe o mais próximo do bounding box do controle.
    - Se nenhum visível, usa o oculto com opções mais próximo como fallback.
    """
    try:
        all_dropdowns = frame.locator('.selectize-dropdown')
        try:
            total = all_dropdowns.count()
        except Exception:
            total = 0
        if total == 0:
            return None

        ctrl_bbox = selectize_control.get("bbox")
        if not ctrl_bbox:
            with contextlib.suppress(Exception):
                ctrl_bbox = selectize_control["selector"].bounding_box()

        candidates = []
        fallback = []
        for i in range(total):
            dd = all_dropdowns.nth(i)
            try:
                visible = dd.is_visible()
            except Exception:
                visible = False
            try:
                opts_cnt = dd.locator('.option, [class*="option"]').count()
            except Exception:
                opts_cnt = 0
            with contextlib.suppress(Exception):
                dd_bbox = dd.bounding_box()
            dist = _distance(ctrl_bbox, dd_bbox)
            item = (dist, opts_cnt, dd, dd_bbox)
            if visible and opts_cnt > 0:
                candidates.append(item)
            elif opts_cnt > 0:
                fallback.append(item)

        if candidates:
            candidates.sort(key=lambda t: (t[0], -t[1]))
            return candidates[0][2]
        if fallback:
            fallback.sort(key=lambda t: (t[0], -t[1]))
            return fallback[0][2]
        return None
    except Exception:
        return None


def open_selectize_dropdown(page, selectize_control: dict, wait_ms: int = 1500) -> bool:
    """
    Abre um dropdown Selectize.

    Args:
        page: Página Playwright
        selectize_control: Dict retornado por find_selectize_by_label
        wait_ms: Tempo de espera após abrir (ms)

    Returns:
        True se abriu com sucesso, False caso contrário
    """
    try:
        input_elem = selectize_control["input"]
        if input_elem.count() == 0:
            logger.error("Input selectize não encontrado")
            return False

        # Fechar quaisquer dropdowns abertos primeiro
        try:
            page.keyboard.press('Escape')
            time.sleep(0.2)
        except Exception:
            pass

        # Clicar para abrir
        input_elem.click()
        time.sleep(wait_ms / 1000.0)

        return True

    except Exception as e:
        logger.error(f"Erro ao abrir dropdown: {e}")
        return False


def _pick_best_label(obj: dict[str, Any] | None, fallback: str | None = None) -> str:
    """Escolhe o melhor rótulo textual a partir de um objeto de opção Selectize.

    Considera diversos campos comuns em integrações (text, label, nome, descricao, etc.).
    """
    if not obj:
        return (fallback or "")
    # Ordem de preferência de campos que comumente representam o texto visível
    candidates = [
        "text",
        "label",
        "nome",
        "nomeCompleto",
        "nome_completo",
        "descricao",
        "descrição",
        "descricaoFormatada",
        "descricao_formatada",
        "descricaoLista",
        "descricao_lista",
        "display",
        "title",
        "sigla",
    ]
    for key in candidates:
        try:
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            continue
    return (fallback or "")


def _is_numeric_like_label(text: str | None, value: Any | None) -> bool:
    """Determina se o 'text' parece um label numérico/placeholder (ex.: igual ao value ou dígitos puros)."""
    t = (text or "").strip()
    v = "" if value is None else str(value).strip()
    if not t:
        return True
    if v and t == v:
        return True
    # apenas dígitos (aceita '-1' como numérico)
    return t.isdigit() or (t.startswith("-") and t[1:].isdigit())


def _selectize_enumerate_options_via_api(frame, selectize_control: dict) -> list[dict[str, Any]]:
    """
    Usa a API do Selectize para enumerar opções do controle específico.
    Retorna lista de dicts: {text, value}
    """
    try:
        sel = selectize_control.get("select_tag")
        if not sel or sel.count() == 0:
            return []
        sel_id = sel.get_attribute("id")
        if not sel_id:
            return []
        options = frame.evaluate(
            """
            (sid) => {
                const el = document.getElementById(sid);
                if (!el || !el.selectize) return [];
                const opts = el.selectize.options || {};
                const out = [];
                for (const [val, obj] of Object.entries(opts)) {
                    // Retornar também o objeto bruto para heurísticas de rótulo posteriormente
                    const raw = obj || {};
                    const text = (raw && (raw.text || raw.label || raw.name || raw.nome || raw.descricao || raw.descrição || raw.display || raw.title || raw.sigla)) || String(val);
                    out.push({ value: val, text, raw });
                }
                return out;
            }
            """,
            sel_id,
        ) or []
        # Normalizar estrutura
        norm = []
        for idx, o in enumerate(options):
            try:
                t = (o.get("text") or "").strip()
                v = o.get("value")
                norm.append({
                    "index": idx,
                    "text": t,
                    "value": v,
                    "data_index": None,
                    "_handle": None,
                    "_raw": o.get("raw"),
                })
            except Exception:
                continue
        return norm
    except Exception as e:
        logger.warning(f"Falha ao enumerar opções via API Selectize: {e}")
        return []


def get_selectize_options(
    frame,
    include_empty: bool = False,
    exclude_patterns: list[str] | None = None,
    scope_to: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Coleta opções de um dropdown Selectize aberto.

    Args:
        frame: Frame Playwright
        include_empty: Incluir opções vazias
        exclude_patterns: Lista de padrões (case-insensitive) para excluir opções

    Returns:
        Lista de dicts com informações das opções
    """
    options_list = []
    # Aplicar padrões padrão caso não tenham sido informados
    exclude_patterns = (exclude_patterns or [])
    if not include_empty:
        # Anexar padrões genéricos (sem duplicatas)
        lower = {p.lower() for p in exclude_patterns}
        for pat in DEFAULT_EXCLUDE_PATTERNS:
            if pat.lower() not in lower:
                exclude_patterns.append(pat)

    try:
        # Tentar enumerar via API do Selectize quando escopo é informado
        if scope_to:
            api_opts = _selectize_enumerate_options_via_api(frame, scope_to)
            if api_opts:
                # Se possível, obter rótulos visíveis do DOM do dropdown aberto e mapear por data-value
                dom_labels_by_value = {}
                try:
                    dd = _find_dropdown_for_control(frame, scope_to)
                    if dd:
                        dom_options = dd.locator('.option, [class*="option"]')
                        try:
                            dom_cnt = dom_options.count()
                        except Exception:
                            dom_cnt = 0
                        for i in range(dom_cnt):
                            opt = dom_options.nth(i)
                            with contextlib.suppress(Exception):
                                dv = opt.get_attribute('data-value')
                                tx = (opt.text_content() or '').strip()
                                if dv is not None and tx:
                                    dom_labels_by_value[str(dv)] = tx
                except Exception:
                    pass

                # Normalizar rótulos: usar melhor label do raw; se ainda numérico, tentar rótulo do DOM
                normalized = []
                for o in api_opts:
                    v = o.get('value')
                    t = (o.get('text') or '').strip()
                    raw = o.get('_raw') or {}
                    # Escolher melhor label a partir do raw
                    best = _pick_best_label(raw, t)
                    if _is_numeric_like_label(best, v):
                        # Tentar DOM
                        dom_label = dom_labels_by_value.get(str(v))
                        if dom_label:
                            best = dom_label
                    normalized.append({
                        "index": o.get('index'),
                        "text": best,
                        "value": v,
                        "data_index": o.get('data_index'),
                        "_handle": o.get('_handle'),
                    })

                # Aplicar filtros em memória
                filtered = []
                for o in normalized:
                    txt = (o.get("text") or "").strip()
                    if not txt and not include_empty:
                        continue
                    # Além de texto, também excluir por valor conhecido genérico (-1)
                    val = (o.get("value") or "").strip() if isinstance(o.get("value"), str) else str(o.get("value"))
                    if val == "-1":
                        continue
                    if any(p.lower() in txt.lower() for p in exclude_patterns):
                        continue
                    filtered.append(o)
                return filtered

        # Escolher dropdown correto: se scope_to foi passado, restringir por proximidade
        if scope_to:
            dropdown = _find_dropdown_for_control(frame, scope_to)
            if not dropdown:
                logger.warning("Nenhum dropdown associado ao controle atual foi encontrado")
                return []
        else:
            # Fallback legado: varrer todos e escolher um visível com opções
            all_dropdowns = frame.locator('.selectize-dropdown')
            try:
                total = all_dropdowns.count()
            except Exception:
                total = 0
            dropdown = None
            for idx in range(total):
                dd = all_dropdowns.nth(idx)
                try:
                    if dd.is_visible() and dd.locator('.option, [class*="option"]').count() > 0:
                        dropdown = dd
                        break
                except Exception:
                    continue
            if not dropdown:
                logger.warning("Nenhum dropdown selectize visível encontrado")
                return []

        # Coletar opções
        options = dropdown.locator('.option, [class*="option"]')
        try:
            cnt = options.count()
        except Exception:
            cnt = 0
        logger.info(f"Encontradas {cnt} opções no dropdown")

        for idx in range(cnt):
            opt = options.nth(idx)
            try:
                text = (opt.text_content() or "").strip()

                if not text and not include_empty:
                    continue

                # Verificar se deve excluir por padrão
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern.lower() in text.lower():
                        should_exclude = True
                        logger.debug(f"Excluindo opção '{text}' (padrão: '{pattern}')")
                        break

                if should_exclude:
                    continue

                # Tentar obter atributos data-*
                data_value = None
                data_index = None
                with contextlib.suppress(Exception):
                    data_value = opt.get_attribute('data-value')
                    data_index = opt.get_attribute('data-index') or opt.get_attribute('data-selectable-index')

                options_list.append({
                    "index": idx,
                    "text": text,
                    "value": data_value,
                    "data_index": data_index,
                    "_handle": opt,  # Manter referência para clicar depois
                })

            except Exception as e:
                logger.warning(f"Erro ao processar opção {idx}: {e}")

        return options_list

    except Exception as e:
        logger.error(f"Erro ao coletar opções: {e}")
        return []


def select_selectize_option(page, option: dict[str, Any], wait_after_ms: int = 1000) -> bool:
    """
    Seleciona uma opção em um dropdown Selectize.

    Args:
        page: Página Playwright
        option: Dict de opção retornado por get_selectize_options
        wait_after_ms: Tempo de espera após seleção (ms)

    Returns:
        True se selecionou com sucesso, False caso contrário
    """
    try:
        handle = option.get("_handle")
        if handle:
            with contextlib.suppress(Exception):
                handle.scroll_into_view_if_needed()
            handle.click()
            time.sleep(wait_after_ms / 1000.0)
            logger.info(f"Selecionado: {option.get('text', '???')}")
            return True
        else:
            # Sem handle: provavelmente veio via API; impossível clicar diretamente
            logger.debug("Opção sem handle; selecione via API do Selectize no controle correspondente")
            return False

    except Exception as e:
        logger.error(f"Erro ao selecionar opção: {e}")
        return False


def select_selectize_option_via_api(frame, selectize_control: dict, option: dict[str, Any], wait_after_ms: int = 1000) -> bool:
    """
    Seleciona opção via API do Selectize do controle especificado (recomendado para casos com dropdown fora da viewport/visibilidade intermitente).
    """
    try:
        sel = selectize_control.get("select_tag")
        if not sel or sel.count() == 0:
            return False
        sel_id = sel.get_attribute("id")
        if not sel_id:
            return False
        val = option.get("value")
        txt = option.get("text")
        ok = frame.evaluate(
            """
            ({sid, v, t}) => {
                const el = document.getElementById(sid);
                if (!el || !el.selectize) return false;
                const s = el.selectize;
                // Se valor não existir, tentar localizar por texto
                let targetVal = v;
                if (!targetVal) {
                    const entries = Object.entries(s.options || {});
                    const found = entries.find(([k, obj]) => (obj && (obj.text||obj.label||'')).trim() === (t||'').trim());
                    targetVal = found ? found[0] : null;
                }
                if (!targetVal) return false;
                try {
                    s.clear(true);
                    s.setValue(targetVal, true);
                    s.refreshOptions(false);
                    s.updateOriginalInput(true);
                    s.onChange();
                } catch (e) {
                    try { s.addItem(targetVal, true); } catch(_) {}
                }
                return true;
            }
            """,
            {"sid": sel_id, "v": val, "t": txt},
        )
        if ok:
            time.sleep(wait_after_ms / 1000.0)
            logger.info(f"Selecionado (API): {txt or val}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao selecionar via API: {e}")
        return False


def close_selectize_dropdown(page, wait_after_ms: int = 300):
    """
    Fecha qualquer dropdown Selectize aberto.

    Args:
        page: Página Playwright
        wait_after_ms: Tempo de espera após fechar (ms)
    """
    try:
        page.keyboard.press('Escape')
        time.sleep(wait_after_ms / 1000.0)
    except Exception as e:
        logger.warning(f"Erro ao fechar dropdown: {e}")


def find_and_check_ativos_checkbox(frame, near_label: str | None = None) -> bool:
    """
    Encontra e marca o checkbox "Ativos" próximo a um label específico.

    Args:
        frame: Frame Playwright
        near_label: Label próximo ao checkbox (opcional)

    Returns:
        True se encontrou e marcou, False caso contrário
    """
    try:
        # Procurar labels "Ativos"
        if near_label:
            # Procurar na vizinhança do label especificado
            context = frame.locator(f'label:has-text("{near_label}")').first.locator('xpath=ancestor::div[2]')
            ativos_labels = context.locator('label:has-text("Ativos")').all()
        else:
            ativos_labels = frame.locator('label:has-text("Ativos")').all()

        for label in ativos_labels:
            try:
                label_text = (label.text_content() or "").strip().lower()

                # Verificar se é exatamente "Ativos" (não "Inativos")
                if label_text != "ativos":
                    continue

                # Procurar checkbox associado
                checkbox = None

                # Método 1: input dentro do label
                cb_inside = label.locator('input[type="checkbox"]')
                if cb_inside.count() > 0:
                    checkbox = cb_inside.first
                else:
                    # Método 2: input irmão anterior
                    checkbox = label.locator('xpath=preceding-sibling::input[@type="checkbox"][1]')
                    if checkbox.count() == 0:
                        # Método 3: por atributo for
                        label_for = label.get_attribute('for')
                        if label_for:
                            checkbox = frame.locator(f'input#{label_for}[type="checkbox"]').first

                if checkbox and checkbox.count() > 0:
                    if not checkbox.is_checked():
                        checkbox.check()
                        time.sleep(0.3)
                        logger.info("Checkbox 'Ativos' marcado")
                    return True

            except Exception as e:
                logger.warning(f"Erro ao processar checkbox Ativos: {e}")

        return False

    except Exception as e:
        logger.error(f"Erro ao buscar checkbox Ativos: {e}")
        return False
