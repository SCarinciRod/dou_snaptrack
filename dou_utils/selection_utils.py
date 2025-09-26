from __future__ import annotations
import re
from typing import Optional, List, Tuple, Dict, Any
from playwright.async_api import Frame, TimeoutError as PlaywrightTimeoutError

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
