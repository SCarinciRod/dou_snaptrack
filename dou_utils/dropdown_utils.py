# dropdown_utils.py
# Funções utilitárias focadas em <select> nativo

def _is_select(locator):
    try:
        name = locator.evaluate("el => el.tagName")
        return (name or "").lower() == "select"
    except Exception:
        return False

def _read_select_options(locator):
    """
    Lê opções de um <select>, trazendo flags de disabled e selected.
    """
    try:
        return locator.evaluate("""
            el => Array.from(el.options || []).map((o,i) => ({
                text: (o.textContent || '').trim(),
                value: o.value,
                dataValue: o.getAttribute('data-value'),
                disabled: !!o.disabled,
                selected: !!o.selected,
                dataIndex: i
            }))
        """) or []
    except Exception:
        return []
