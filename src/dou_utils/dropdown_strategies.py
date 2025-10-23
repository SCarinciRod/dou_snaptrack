"""
Robust dropdown opening & option selection strategies.

Provides:
 - open_dropdown_robust(frame, locator, config)
 - select_option_generic(frame, root_locator, option_dict, strategies)

This consolidates heurísticas dos scripts originais (00_map_page, 05_cascade_cli, 00_map_pairs),
mantendo ordem configurável e logging.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, Iterable, List
from .log_utils import get_logger

logger = get_logger(__name__)

DEFAULT_OPEN_STRATEGY_ORDER = (
    "already_open",
    "click",
    "force_click",
    "icon_click",
    "keyboard",
    "double_click",
)

ARROW_XPATH = "xpath=.//*[contains(@class,'arrow') or contains(@class,'icon') or contains(@class,'caret')]"

def _listbox_present(frame) -> bool:
    selectors = [
        "[role=listbox]", "ul[role=listbox]", "div[role=listbox]",
        "ul[role=menu]", "div[role=menu]",
        ".ng-dropdown-panel", ".p-dropdown-items", ".select2-results__options", ".rc-virtual-list"
    ]
    for sel in selectors:
        try:
            if frame.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    # also page-level (portais que montam fora do frame)
    page = frame.page
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def open_dropdown_robust(frame, locator, strategy_order: Optional[Iterable[str]] = None, delay_ms: int = 120) -> bool:
    """
    Try multiple strategies to open a dropdown-like widget.

    strategy_order: sequence of strategy names. Supported:
       already_open, click, force_click, icon_click, keyboard, double_click
    """
    order = tuple(strategy_order) if strategy_order else DEFAULT_OPEN_STRATEGY_ORDER

    def _already_open():
        return _listbox_present(frame)

    def _click():
        locator.scroll_into_view_if_needed(timeout=2000)
        locator.click(timeout=2500)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _force_click():
        locator.click(timeout=2500, force=True)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _icon_click():
        arrow = locator.locator(ARROW_XPATH).first
        if arrow and arrow.count() > 0 and arrow.is_visible():
            arrow.click(timeout=2500)
            frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    def _keyboard():
        locator.focus()
        for key in ["Enter", "Space", "Alt+ArrowDown"]:
            try:
                frame.page.keyboard.press(key)
                frame.wait_for_timeout(delay_ms)
                if _listbox_present(frame):
                    return True
            except Exception:
                continue
        return _listbox_present(frame)

    def _double_click():
        locator.dblclick(timeout=2500)
        frame.wait_for_timeout(delay_ms)
        return _listbox_present(frame)

    strategies = {
        "already_open": _already_open,
        "click": _click,
        "force_click": _force_click,
        "icon_click": _icon_click,
        "keyboard": _keyboard,
        "double_click": _double_click,
    }

    for name in order:
        fn = strategies.get(name)
        if not fn:
            continue
        try:
            if fn():
                return True
        except Exception as e:
            logger.debug("Dropdown open strategy failed", extra={"strategy": name, "err": str(e)})
    return _listbox_present(frame)


def collect_open_list_options(frame) -> List[Dict[str, Any]]:
    """
    After dropdown is open, collect available visible option nodes with rich attributes.
    """
    container = None
    selectors = [
        "[role=listbox]", "ul[role=listbox]", "div[role=listbox]",
        "ul[role=menu]", "div[role=menu]",
        ".ng-dropdown-panel", ".p-dropdown-items", ".select2-results__options", ".rc-virtual-list"
    ]
    for sel in selectors:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                container = loc.first
                break
        except Exception:
            continue
    if not container:
        page = frame.page
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    container = loc.first
                    break
            except Exception:
                continue
    if not container:
        return []

    # scroll virtualization
    try:
        for _ in range(40):
            changed = container.evaluate(
                "el => { const b=el.scrollTop; el.scrollTop=el.scrollHeight; return el.scrollTop !== b; }"
            )
            frame.wait_for_timeout(60)
            if not changed:
                break
    except Exception:
        for _ in range(10):
            try:
                frame.page.keyboard.press("End")
            except Exception:
                pass
            frame.wait_for_timeout(60)

    option_selectors = [
        "[role=option]", "li[role=option]",
        ".ng-option", ".p-dropdown-item", ".select2-results__option",
        "[data-value]", "[data-index]"
    ]

    options = []
    for sel in option_selectors:
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
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                oid = o.get_attribute("id")
                did = o.get_attribute("data-id") or o.get_attribute("data-key") or o.get_attribute("data-code")
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
                continue
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
        frame.wait_for_timeout(80)
    except Exception:
        pass
    return uniq
