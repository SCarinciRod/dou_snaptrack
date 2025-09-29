from __future__ import annotations
import re
from typing import Optional, List, Tuple, Dict, Any
from playwright.async_api import Frame, TimeoutError as PlaywrightTimeoutError

# Sync helpers expected by services.multi_level_cascade_service
try:
    from .dropdown_utils import _is_select as _du_is_select, _read_select_options as _du_read_select_options
except Exception:
    _du_is_select = None
    _du_read_select_options = None

try:
    from .dropdown_strategies import (
        open_dropdown_robust as _open_dropdown_robust,
        collect_open_list_options as _collect_open_list_options,
    )
except Exception:
    def _open_dropdown_robust(frame, locator, strategy_order=None, delay_ms: int = 120):  # type: ignore
        try:
            locator.click(timeout=2000)
            frame.wait_for_timeout(delay_ms)
            return True
        except Exception:
            return False
    def _collect_open_list_options(frame):  # type: ignore
        return []

from typing import Any as _Any
open_dropdown_robust: _Any = _open_dropdown_robust
collect_open_list_options: _Any = _collect_open_list_options

SENTINELA_PREFIX = "selecionar "

def is_sentinel(value: Optional[str], label: Optional[str]) -> bool:
    v = (value or "").strip().lower()
    l = (label or "").strip().lower()
    if not v and not l:
        return True
    if l.startswith(SENTINELA_PREFIX):
        return True
    if v.startswith(SENTINELA_PREFIX):
        return True
    return False

async def collect_dropdowns(frame: Frame, selector: str = "select") -> List:
    return await frame.query_selector_all(selector)

async def option_data(opt) -> Tuple[str, str]:
    val = await opt.get_attribute("value")
    txt = (await opt.text_content()) or ""
    return (val or txt, txt.strip())

async def select_option(dropdown_el, value: Optional[str], label: Optional[str]) -> bool:
    options = await dropdown_el.query_selector_all("option")
    target = None
    if value:
        for o in options:
            v, t = await option_data(o)
            if v == value:
                target = v
                break
    if target is None and label:
        for o in options:
            v, t = await option_data(o)
            if t == label:
                target = v
                break
    if target is None:
        return False
    await dropdown_el.select_option(value=target)
    return True

async def select_level(frame: Frame,
                       level: int,
                       value: Optional[str],
                       label: Optional[str],
                       wait_ms: int = 300,
                       logger=None,
                       selector: str = "select") -> bool:
    if is_sentinel(value, label):
        if logger:
            logger.debug(f"[DDL{level}] Ignorando sentinela value={value} label={label}")
        return True
    try:
        dds = await collect_dropdowns(frame, selector)
    except PlaywrightTimeoutError:
        if logger:
            logger.warning(f"[DDL{level}] Timeout coletando dropdowns.")
        return False
    idx = level - 1
    if len(dds) <= idx:
        if logger:
            logger.warning(f"[DDL{level}] Dropdown ausente idx={idx} total={len(dds)}.")
        return False
    ok = await select_option(dds[idx], value, label)
    if not ok and logger:
        logger.warning(f"[DDL{level}] Não encontrou opção value={value} label={label}.")
        return False
    await frame.wait_for_timeout(wait_ms)
    return True


# ---------------------- Sync API helpers ----------------------
def _is_native_select(handle) -> bool:
    if _du_is_select:
        try:
            return _du_is_select(handle)
        except Exception:
            pass
    try:
        tag = handle.evaluate("el => el && el.tagName && el.tagName.toLowerCase()")
        return tag == "select"
    except Exception:
        return False


def _read_select_options_sync(handle) -> List[Dict[str, Any]]:
    if _du_read_select_options:
        try:
            return _du_read_select_options(handle)
        except Exception:
            pass
    try:
        return handle.evaluate(
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


def read_rich_options(frame, root_handle) -> List[Dict[str, Any]]:
    """Return a list of option dicts for either native <select> or custom dropdowns."""
    if not root_handle:
        return []
    if _is_native_select(root_handle):
        return _read_select_options_sync(root_handle)
    opened = open_dropdown_robust(frame, root_handle)
    return collect_open_list_options(frame) if opened else []


def _match_option(options: List[Dict[str, Any]], key: str, key_type: str) -> Optional[Dict[str, Any]]:
    if key is None:
        return None
    k = str(key)
    kt = (key_type or "text")
    for o in options:
        if kt == "text" and (o.get("text") or "") == k:
            return o
        if kt == "value" and str(o.get("value")) == k:
            return o
        if kt == "dataValue" and str(o.get("dataValue")) == k:
            return o
        if kt == "dataIndex" and str(o.get("dataIndex")) == k:
            return o
    return None


def select_option_robust(frame, root_handle, key: Optional[str], key_type: Optional[str]) -> bool:
    """Select an option by key/key_type on either native select or custom dropdown.
    Returns True when selection happened and the page stabilized.
    """
    if not root_handle or key is None or key_type is None:
        return False
    page = frame.page
    if _is_native_select(root_handle):
        # Native select: try proper channel based on type
        if key_type == "value":
            try:
                root_handle.select_option(value=str(key))
                page.wait_for_load_state("networkidle", timeout=60_000)
                return True
            except Exception:
                pass
        if key_type == "dataIndex":
            try:
                root_handle.select_option(index=int(key))
                page.wait_for_load_state("networkidle", timeout=60_000)
                return True
            except Exception:
                pass
        # Fallback via options scan (text or dataValue)
        opts = _read_select_options_sync(root_handle)
        target = _match_option(opts, str(key), key_type)
        if target is not None:
            try:
                if key_type == "text":
                    root_handle.select_option(label=target.get("text") or "")
                elif target.get("value") not in (None, ""):
                    root_handle.select_option(value=str(target.get("value")))
                else:
                    root_handle.select_option(index=int(target.get("dataIndex") or 0))
                page.wait_for_load_state("networkidle", timeout=60_000)
                return True
            except Exception:
                pass
        return False

    # Custom dropdown
    if not open_dropdown_robust(frame, root_handle):
        return False
    options = collect_open_list_options(frame)
    target = _match_option(options, str(key), key_type or "text")
    name = (target or {}).get("text") or str(key)
    # Try exact by role name
    try:
        opt = page.get_by_role("option", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4_000)
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    # Fallback: contains
    try:
        opt = page.get_by_role("option", name=re.compile(re.escape(name), re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4_000)
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def wait_repopulation(frame, root_handle, prev_count: int, timeout_ms: int = 15_000, poll_interval_ms: int = 250) -> None:
    """Wait until the number of options for the target dropdown changes (and is > 0)."""
    import time
    page = frame.page
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            if _is_native_select(root_handle):
                cur = len(_read_select_options_sync(root_handle))
            else:
                open_dropdown_robust(frame, root_handle)
                cur = len(collect_open_list_options(frame))
            if cur != prev_count and cur > 0:
                return
        except Exception:
            pass
        try:
            page.wait_for_timeout(poll_interval_ms)
        except Exception:
            time.sleep(poll_interval_ms / 1000.0)
