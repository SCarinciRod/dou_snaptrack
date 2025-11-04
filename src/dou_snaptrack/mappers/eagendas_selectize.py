"""
Funções específicas para interação com Selectize.js no e-agendas.
"""
from __future__ import annotations
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


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
            return {
                "label": label_text,
                "selector": selectize,
                "input": selectize.locator('.selectize-input').first,
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
        return 'disabled' in class_attr
    except Exception:
        return False


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


def get_selectize_options(frame, include_empty: bool = False, exclude_patterns: list[str] | None = None) -> list[dict[str, Any]]:
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
    exclude_patterns = exclude_patterns or []
    
    try:
        # Procurar TODOS os dropdowns (tanto separados quanto dentro dos controles)
        all_dropdowns = frame.locator('.selectize-dropdown').all()
        
        logger.info(f"Total de dropdowns encontrados: {len(all_dropdowns)}")
        
        dropdown = None
        fallback_dropdown = None
        
        for idx, dd in enumerate(all_dropdowns):
            # Verificar se está visível OU se tem opções (mesmo com display:none no container)
            try:
                is_visible = dd.is_visible()
                
                # Contar opções (não verificar is_visible pois podem estar em container oculto)
                opts = dd.locator('.option').all()
                total_opts = len(opts)
                
                logger.info(f"  Dropdown #{idx}: container_visible={is_visible}, total_options={total_opts}")
                
                # PRIORIZAR dropdowns visíveis!
                if is_visible and total_opts > 0:
                    dropdown = dd
                    logger.info(f"  ✓ Usando dropdown #{idx} (VISÍVEL)")
                    break
                elif total_opts > 0:
                    # Guardar último dropdown oculto com opções (será o mais específico: N3)
                    fallback_dropdown = dd
                    logger.info(f"  ~ Dropdown #{idx} como candidato (oculto mas com opções)")
                    
            except Exception as e:
                logger.warning(f"  Erro ao verificar dropdown #{idx}: {e}")
                continue
        
        # Se não achou visível, usar o fallback (último oculto com opções)
        if not dropdown:
            dropdown = fallback_dropdown
            if dropdown:
                logger.info(f"  Usando dropdown fallback (oculto)")
        
        if dropdown:
            logger.info(f"  Dropdown final selecionado")
        else:
            logger.warning("Nenhum dropdown selectize visível encontrado")
            return []
        
        # Coletar opções
        options = dropdown.locator('.option, [class*="option"]').all()
        logger.info(f"Encontradas {len(options)} opções no dropdown")
        
        for idx, opt in enumerate(options):
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
                    "_handle": opt  # Manter referência para clicar depois
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
        if not handle:
            logger.error("Opção não tem handle para clicar")
            return False
        
        # Clicar na opção
        handle.click()
        time.sleep(wait_after_ms / 1000.0)
        
        logger.info(f"Selecionado: {option.get('text', '???')}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao selecionar opção: {e}")
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
                        logger.info(f"Checkbox 'Ativos' marcado")
                    return True
                    
            except Exception as e:
                logger.warning(f"Erro ao processar checkbox Ativos: {e}")
        
        return False
        
    except Exception as e:
        logger.error(f"Erro ao buscar checkbox Ativos: {e}")
        return False
