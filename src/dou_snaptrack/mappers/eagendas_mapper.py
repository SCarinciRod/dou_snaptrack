from __future__ import annotations
from typing import Any, Dict, List, Tuple

from ..utils.text import normalize_text

def _get_label_for_input(frame, el) -> str:
    try:
        aid = el.get_attribute('aria-label')
        if aid:
            return (aid or "").strip()
    except Exception:
        pass
    try:
        ph = el.get_attribute('placeholder')
        if ph:
            return (ph or "").strip()
    except Exception:
        pass
    try:
        tid = el.get_attribute('id')
        if tid:
            lab = frame.locator(f'label[for="{tid}"]')
            if lab.count() > 0:
                return (lab.first.text_content() or "").strip()
    except Exception:
        pass
    try:
        name = el.get_attribute('name')
        if name:
            return (name or "").strip()
    except Exception:
        pass
    try:
        txt = el.text_content()
        if txt:
            return (txt or "").strip()
    except Exception:
        pass
    return ""

def _collect_elements(frame) -> List[Dict[str, Any]]:
    # Query candidate selectors for elements of interest
    selectors = [
        'input', 'select', 'textarea', 'button', 'a[href]',
        '[role=button]', '[role=link]', '[role=combobox]', '[role=listbox]',
        'label', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
    ]
    out: List[Dict[str, Any]] = []
    for sel in selectors:
        try:
            loc = frame.locator(sel)
            cnt = loc.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            try:
                el = loc.nth(i)
                tag = sel
                name = _get_label_for_input(frame, el)
                visible = False
                try:
                    visible = el.is_visible()
                except Exception:
                    visible = False
                eid = None
                try:
                    eid = el.get_attribute('id')
                except Exception:
                    eid = None
                out.append({
                    'selector': sel,
                    'index': i,
                    'name': name,
                    'normalized': normalize_text(name),
                    'visible': bool(visible),
                    'id': eid,
                })
            except Exception:
                pass
    return out

def map_eagendas_elements(frame, max_per_type: int = 200) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """Return (by_type, by_name) where:
      - by_type: { type: [elements...] }
      - by_name: { name: [elements...] }
    Each element is a small dict with selector/index/name/visible/id/normalized.
    """
    elems = _collect_elements(frame)
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    by_name: Dict[str, List[Dict[str, Any]]] = {}

    for e in elems:
        t = e.get('selector') or 'unknown'
        lst = by_type.setdefault(t, [])
        if len(lst) < max_per_type:
            lst.append(e)
        nm = (e.get('name') or '').strip()
        key = nm or '<unnamed>'
        lst2 = by_name.setdefault(key, [])
        if len(lst2) < max_per_type:
            lst2.append(e)

    return by_type, by_name
