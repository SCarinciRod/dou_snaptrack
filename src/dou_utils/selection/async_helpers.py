"""
Async selection helper functions.

Provides async-compatible selection utilities for Playwright async API.
"""
from __future__ import annotations

from playwright.async_api import Frame, TimeoutError as PlaywrightTimeoutError

from .constants import SENTINELA_PREFIX


def is_sentinel(value: str | None, label: str | None) -> bool:
    """Check if value/label represents a placeholder sentinel.
    
    Args:
        value: Option value
        label: Option label/text
        
    Returns:
        True if this is a sentinel (placeholder) option
    """
    v = (value or "").strip().lower()
    lbl = (label or "").strip().lower()
    if not v and not lbl:
        return True
    return bool(lbl.startswith(SENTINELA_PREFIX) or v.startswith(SENTINELA_PREFIX))


async def collect_dropdowns(frame: Frame, selector: str = "select") -> list:
    """Collect all dropdown elements matching the selector.
    
    Args:
        frame: Playwright async Frame
        selector: CSS selector for dropdowns
        
    Returns:
        List of element handles
    """
    return await frame.query_selector_all(selector)


async def option_data(opt) -> tuple[str, str]:
    """Extract value and text from an option element.
    
    Args:
        opt: Element handle for an <option> element
        
    Returns:
        Tuple of (value, text)
    """
    val = await opt.get_attribute("value")
    txt = (await opt.text_content()) or ""
    return (val or txt, txt.strip())


async def select_option(dropdown_el, value: str | None, label: str | None) -> bool:
    """Select an option in a native <select> element.
    
    Tries to match by value first, then by label.
    
    Args:
        dropdown_el: Element handle for <select>
        value: Value to select by
        label: Label to select by if value not found
        
    Returns:
        True if selection succeeded
    """
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


async def select_level(
    frame: Frame,
    level: int,
    value: str | None,
    label: str | None,
    wait_ms: int = 300,
    logger=None,
    selector: str = "select"
) -> bool:
    """Select an option at a specific dropdown level.
    
    Args:
        frame: Playwright async Frame
        level: 1-based level index
        value: Value to select
        label: Label to select if value not found
        wait_ms: Time to wait after selection
        logger: Optional logger for debug output
        selector: CSS selector for dropdowns
        
    Returns:
        True if selection succeeded or was skipped (sentinel)
    """
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
