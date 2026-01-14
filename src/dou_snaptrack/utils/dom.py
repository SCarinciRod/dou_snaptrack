from __future__ import annotations

import contextlib

# Prefer dou_utils implementations when available, fallback to local
try:
    from dou_utils.page_utils import find_best_frame as _du_find_best_frame  # type: ignore
except Exception:
    _du_find_best_frame = None

try:
    from dou_utils.dropdowns import (  # type: ignore
        is_select as _du_is_select,
        read_select_options as _du_read_select_options,
    )
except Exception:
    _du_is_select = None
    _du_read_select_options = None


# ============================================================================
# VERSÕES ASYNC (para compatibilidade com Streamlit/asyncio)
# ============================================================================

async def find_best_frame_async(context):
    """Versão async de find_best_frame - implementação manual sem dou_utils."""
    # NÃO usar dou_utils para evitar mixing sync/async
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        with contextlib.suppress(Exception):
            score += await fr.get_by_role("combobox").count()
        with contextlib.suppress(Exception):
            score += await fr.locator("select").count()
        with contextlib.suppress(Exception):
            score += await fr.get_by_role("textbox").count()
        if score > best_score:
            best_score = score
            best = fr
    return best


# ============================================================================
# VERSÕES SYNC (mantidas para retrocompatibilidade)
# ============================================================================

def find_best_frame(context):
    if _du_find_best_frame:
        return _du_find_best_frame(context)
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        with contextlib.suppress(Exception):
            score += fr.get_by_role("combobox").count()
        with contextlib.suppress(Exception):
            score += fr.locator("select").count()
        with contextlib.suppress(Exception):
            score += fr.get_by_role("textbox").count()
        if score > best_score:
            best_score = score
            best = fr
    return best

def label_for_control(frame, locator) -> str:
    # 1) aria-label
    try:
        aria = locator.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    # 2) <label for="id">
    try:
        _id = locator.get_attribute("id")
        if _id:
            lab = frame.evaluate("""
            (id) => {
                const l = document.querySelector(`label[for="${id}"]`);
                return l ? l.textContent.trim() : null;
            }""", _id)
            if lab:
                return lab
    except Exception:
        pass
    # 3) label imediatamente anterior
    try:
        prev = locator.locator("xpath=preceding::label[1]").first
        if prev and prev.count() > 0 and prev.is_visible():
            t = (prev.text_content() or "").strip()
            if t:
                return t
    except Exception:
        pass
    return ""

def compute_css_path(frame, locator) -> str | None:
    try:
        return locator.evaluate("""(el) => {
            function cssPath(e){
                if (!(e instanceof Element)) return null;
                const path = [];
                while (e && e.nodeType === Node.ELEMENT_NODE) {
                    let selector = e.nodeName.toLowerCase();
                    if (e.id) { selector += '#' + e.id; path.unshift(selector); break; }
                    else {
                        let sib = e, nth = 1;
                        while (sib = sib.previousElementSibling) { if (sib.nodeName.toLowerCase() === selector) nth++; }
                        selector += `:nth-of-type(${nth})`;
                    }
                    path.unshift(selector);
                    e = e.parentNode;
                    if (!e || e.nodeName.toLowerCase() === 'html') break;
                }
                return path.join(' > ');
            }
            return cssPath(el);
        }""")
    except Exception:
        return None

def compute_xpath(frame, locator) -> str | None:
    try:
        return locator.evaluate("""(el)=>{
            function xpath(el){
                if (el && el.id) return "//*[@id='" + el.id + "']";
                const parts = [];
                while (el && el.nodeType === Node.ELEMENT_NODE){
                    let nb = 0, idx = 0;
                    const siblings = el.parentNode ? el.parentNode.childNodes : [];
                    for (let i=0; i<siblings.length; i++){
                        const sib = siblings[i];
                        if (sib.nodeType === Node.ELEMENT_NODE && sib.nodeName === el.nodeName){
                            nb++;
                            if (sib === el) idx = nb;
                        }
                    }
                    const name = el.nodeName.toLowerCase();
                    const part = (nb>1)? name+"["+idx+"]" : name;
                    parts.unshift(part);
                    el = el.parentNode;
                }
                return "/" + parts.join("/");
            }
            return xpath(el);
        }""")
    except Exception:
        return None

def is_select(locator) -> bool:
    if _du_is_select:
        try:
            return _du_is_select(locator)
        except Exception:
            pass
    try:
        tag = locator.evaluate("el => el && el.tagName && el.tagName.toLowerCase()")
        return tag == "select"
    except Exception:
        return False

def read_select_options(locator):
    if _du_read_select_options:
        try:
            return _du_read_select_options(locator)
        except Exception:
            pass
    try:
        return locator.evaluate(
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
