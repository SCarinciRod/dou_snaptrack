from __future__ import annotations
import re
from typing import Optional, List, Tuple
from playwright.async_api import Frame, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

SENTINELA_PREFIX = "selecionar "
PLACEHOLDER_VALUES = {"", None, "0"}

def is_sentinel(value: Optional[str], label: Optional[str], extra_pattern: Optional[re.Pattern] = None) -> bool:
    v = (value or "").strip().lower()
    l = (label or "").strip().lower()
    if not v and not l:
        return True
    if l.startswith(SENTINELA_PREFIX) or v.startswith(SENTINELA_PREFIX):
        return True
    if v in PLACEHOLDER_VALUES and (l in PLACEHOLDER_VALUES or l == v):
        return True
    if v.isdigit() and len(v) == 1 and (l == v or not l):
        return True
    if extra_pattern and ((v and extra_pattern.search(v)) or (l and extra_pattern.search(l))):
        return True
    return False

async def collect_dropdowns(frame: Frame, selector: str = "select") -> List:
    return await frame.query_selector_all(selector)

async def option_data(opt) -> Tuple[str, str]:
    val = await opt.get_attribute("value")
    txt = (await opt.text_content()) or ""
    return ( (val or txt).strip(), txt.strip() )

async def list_options(dropdown_el) -> List[Tuple[str, str]]:
    opts = await dropdown_el.query_selector_all("option")
    out = []
    for o in opts:
        out.append(await option_data(o))
    return out

async def wait_enabled_and_populated(frame: Frame,
                                     dropdown_el,
                                     min_real_options: int = 1,
                                     timeout_ms: int = 8000,
                                     poll_ms: int = 250) -> bool:
    elapsed = 0
    while elapsed <= timeout_ms:
        try:
            if await dropdown_el.is_enabled():
                opts = await list_options(dropdown_el)
                real = [o for o in opts if not is_sentinel(o[0], o[1])]
                if len(real) >= min_real_options:
                    return True
        except PlaywrightError:
            return False  # elemento pode ter sumido
        await frame.wait_for_timeout(poll_ms)
        elapsed += poll_ms
    return False

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
                       selector: str = "select",
                       sentinel_regex: Optional[str] = None) -> bool:
    extra_pattern = re.compile(sentinel_regex, re.IGNORECASE) if sentinel_regex else None

    if is_sentinel(value, label, extra_pattern):
        if logger:
            logger.debug(f"[DDL{level}] Ignorando sentinela value={value!r} label={label!r}")
        return True

    try:
        dropdowns = await collect_dropdowns(frame, selector)
    except PlaywrightTimeoutError:
        if logger:
            logger.warning(f"[DDL{level}] Timeout coletando dropdowns.")
        return False

    idx = level - 1
    if len(dropdowns) <= idx:
        if logger:
            logger.warning(f"[DDL{level}] Dropdown ausente idx={idx} total={len(dropdowns)}.")
        return False

    ddl = dropdowns[idx]

    ready = await wait_enabled_and_populated(frame, ddl, min_real_options=1, timeout_ms=8000)
    if not ready and logger:
        logger.debug(f"[DDL{level}] Dropdown pode não estar totalmente populado (segue tentativa).")

    ok = await select_option(ddl, value, label)
    if not ok and logger:
        opts = await list_options(ddl)
        logger.warning(f"[DDL{level}] Opção não encontrada value={value!r} label={label!r}. Opções:")
        for v, t in opts[:20]:
            logger.warning(f"[DDL{level}]  - v={v!r} t={t!r}")
        return False

    await frame.wait_for_timeout(wait_ms)
    return True

def classify_option_kind(value: Optional[str], label: Optional[str]) -> str:
    return "sentinel" if is_sentinel(value, label) else "real"
