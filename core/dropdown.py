"""
Funções para manipulação de dropdowns e comboboxes (sempre com base no frame).
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from utils.text import normalize_text
from core.locators import LISTBOX_SELECTORS, OPTION_SELECTORS, DROPDOWN_ROOT_SELECTORS


def listbox_present(frame) -> bool:
    """Verifica se há um listbox aberto no frame ou na page."""
    for sel in LISTBOX_SELECTORS:
        try:
            if frame.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    page = frame.page
    for sel in LISTBOX_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def get_listbox_container(frame):
    """Obtém o container do listbox aberto, procurando no frame e na page."""
    for sel in LISTBOX_SELECTORS:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    page = frame.page
    for sel in LISTBOX_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    return None


def is_select_root(root: Dict[str, Any]) -> bool:
    """Retorna True se o root for um <select> nativo."""
    try:
        tag = root["handle"].evaluate("el => el && el.tagName && el.tagName.toLowerCase()")
        if tag == "select":
            return True
    except Exception:
        pass
    return root.get("selector") == "select"


def open_dropdown(frame, root) -> bool:
    """
    Abre um dropdown visual. Aceita root dict {"handle": Locator} ou Locator.
    Busca listbox no frame e na page.
    """
    h = root["handle"] if isinstance(root, dict) else root

    def _present():
        return listbox_present(frame)

    if _present():
        return True

    # Clique normal
    try:
        h.scroll_into_view_if_needed(timeout=2000)
        h.click(timeout=2500)
        frame.wait_for_timeout(120)
        if _present():
            return True
    except Exception:
        pass

    # Clique forçado
    try:
        h.click(timeout=2500, force=True)
        frame.wait_for_timeout(120)
        if _present():
            return True
    except Exception:
        pass

    # Ícone interno
    try:
        arrow = h.locator("xpath=.//*[contains(@class,'arrow') or contains(@class,'icon') or contains(@class,'caret')]").first
        if arrow and arrow.count() > 0 and arrow.is_visible():
            arrow.click(timeout=2500)
            frame.wait_for_timeout(120)
            if _present():
                return True
    except Exception:
        pass

    # Teclado
    try:
        h.focus()
        frame.page.keyboard.press("Enter"); frame.wait_for_timeout(120)
        if _present(): return True
        frame.page.keyboard.press("Space"); frame.wait_for_timeout(120)
        if _present(): return True
        frame.page.keyboard.press("Alt+ArrowDown"); frame.wait_for_timeout(120)
        if _present(): return True
    except Exception:
        pass

    return _present()


def scroll_listbox_all(container, frame) -> None:
    """Rola o container do listbox para materializar itens virtualizados."""
    try:
        for _ in range(60):
            changed = container.evaluate(
                """el => { const b = el.scrollTop; el.scrollTop = el.scrollHeight; return el.scrollTop !== b; }"""
            )
            frame.wait_for_timeout(80)
            if not changed:
                break
    except Exception:
        for _ in range(15):
            try:
                frame.page.keyboard.press("End")
            except Exception:
                pass
            frame.wait_for_timeout(80)


def read_open_list_options(frame) -> List[Dict[str, Any]]:
    """Lê as opções do listbox aberto (com id/data-id/value/dataValue/dataIndex/text)."""
    container = get_listbox_container(frame)
    if not container:
        return []
    scroll_listbox_all(container, frame)

    options = []
    for sel in OPTION_SELECTORS:
        try:
            opts = container.locator(sel)
            k = opts.count()
        except Exception:
            k = 0

        for i in range(k):
            o = opts.nth(i)
            try:
                if not o.is_visible():
                    continue
                text = (o.text_content() or "").strip()
                val  = o.get_attribute("value")
                dv   = o.get_attribute("data-value")
                di   = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                oid  = o.get_attribute("id")
                did  = o.get_attribute("data-id") or o.get_attribute("data-key") or o.get_attribute("data-code")
                if text or val or dv or di or oid or did:
                    options.append({
                        "text": text,
                        "value": val,
                        "dataValue": dv,
                        "dataIndex": di,
                        "id": oid,
                        "dataId": did
                    })
            except Exception:
                pass

    seen = set()
    uniq = []
    for o in options:
        key = (o.get("id"), o.get("dataId"), o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)

    try:
        frame.page.keyboard.press("Escape")
        frame.wait_for_timeout(100)
    except Exception:
        pass
    return uniq


def read_select_options(frame, root: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lê opções de um <select> nativo."""
    sel = root["handle"]
    try:
        return sel.evaluate(
            """
            el => Array.from(el.options || []).map((o,i) => ({
                text: (o.textContent || '').trim(),
                value: o.value,
                dataValue: o.getAttribute('data-value'),
                dataIndex: i
            }))
            """
        ) or []
    except Exception:
        return []


def label_for_control(frame, root: Dict[str, Any]) -> str:
    """Obtém rótulo associado ao controle."""
    h = root["handle"] if isinstance(root, dict) else root
    try:
        aria = h.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    try:
        _id = h.get_attribute("id")
        if _id:
            lab = frame.evaluate(
                """
                (id) => {
                    const l = document.querySelector(`label[for="${id}"]`);
                    return l ? l.textContent.trim() : null;
                }
                """,
                _id,
            )
            if lab:
                return lab
    except Exception:
        pass
    try:
        prev = h.locator("xpath=preceding::label[1]").first
        if prev and prev.count() > 0 and prev.is_visible():
            t = (prev.text_content() or "").strip()
            if t:
                return t
    except Exception:
        pass
    return ""


def css_escape(s: str) -> str:
    """Escape mínimo para seletores CSS."""
    return re.sub(r'(\\.#:[\\>+~*^$|])', r'\\\1', s or "")


def select_by_text_or_attrs(frame, root: Dict[str, Any], option: Dict[str, Any]) -> bool:
    """
    Seleciona 'option' no 'root' (<select> nativo ou combobox custom).
    Para <select>, usa select_option (value/index/label). Para custom, abre listbox e clica.
    """
    page = frame.page
    # <select> nativo
    if is_select_root(root):
        sel = root["handle"]
        val = option.get("value")
        if val not in (None, ""):
            try:
                sel.select_option(value=str(val)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        di = option.get("dataIndex")
        if di not in (None, ""):
            try:
                sel.select_option(index=int(di)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        try:
            sel.select_option(label=option.get("text") or "")
            page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception:
            pass
        # segue como custom

    # Combobox custom
    if not open_dropdown(frame, root):
        return False
    container = get_listbox_container(frame)
    if not container:
        return False

    # por id
    oid = option.get("id")
    if oid:
        try:
            opt = container.locator(f"##{css_escape(oid)}").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass

    # por data-id
    did = option.get("dataId")
    if did:
        try:
            opt = container.locator(f"[data-id='{css_escape(did)}'],[data-key='{css_escape(did)}'],[data-code='{css_escape(did)}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass

    # por value
    val = option.get("value")
    if val not in (None, ""):
        try:
            opt = container.locator(f"[value='{css_escape(str(val))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass

    # por data-value
    dv = option.get("dataValue")
    if dv not in (None, ""):
        try:
            opt = container.locator(f"[data-value='{css_escape(str(dv))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass

    # por data-index
    di = option.get("dataIndex")
    if di not in (None, ""):
        try:
            opt = container.locator(f"[data-index='{css_escape(str(di))}'],[data-option-index='{css_escape(str(di))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass

    # texto visual
    txt = option.get("text") or ""
    try:
        opt = container.get_by_role("option", name=re.compile(rf"^{re.escape(txt)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
    except Exception: pass

    try:
        nk = normalize_text(txt)
        any_opt = container.locator(
            "xpath=//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), $k)]",
            k=nk
        ).first
        if any_opt and any_opt.count() > 0 and any_opt.is_visible():
            any_opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
    except Exception: pass

    try: page.keyboard.press("Escape")
    except Exception: pass
    return False


def collect_dropdown_roots(frame) -> List[Dict[str, Any]]:
    """
    Coleta raízes de dropdown (combobox/select/heurísticas), deduplica por id
    e prioriza select > combobox > unknown. Ordena por (y,x).
    """
    roots = []
    seen = set()

    def _maybe_add(sel: str, kind: str, loc):
        try:
            cnt = loc.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            h = loc.nth(i)
            try:
                box = h.bounding_box()
                if not box:
                    continue
                key = (sel, i, round(box["y"], 2), round(box["x"], 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({"selector": sel, "kind": kind, "index": i, "handle": h, "y": box["y"], "x": box["x"]})
            except Exception:
                continue

    _maybe_add("role=combobox", "combobox", frame.get_by_role("combobox"))
    _maybe_add("select", "select", frame.locator("select"))
    for sel in DROPDOWN_ROOT_SELECTORS:
        _maybe_add(sel, "unknown", frame.locator(sel))

    def _priority(kind: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)

    enriched = []
    for r in roots:
        h = r["handle"]
        try:
            el_id = h.get_attribute("id")
        except Exception:
            el_id = None
        lab = label_for_control(frame, r)
        enriched.append({**r, "id_attr": el_id, "label": lab})

    by_key = {}
    for r in enriched:
        if r.get("id_attr"):
            k = ("id", r["id_attr"])
        else:
            k = ("pos", round(r["y"], 1), round(r["x"], 1), r["selector"])
        best = by_key.get(k)
        if not best or _priority(r["kind"]) > _priority(best["kind"]):
            by_key[k] = r

    deduped = list(by_key.values())
    deduped.sort(key=lambda rr: (rr["y"], rr["x"]))
    return deduped
