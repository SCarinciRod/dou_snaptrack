"""Helper functions for async dropdown operations.

This module contains extracted functions from async dropdown functions to reduce complexity.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any


async def select_native_dropdown_async(handle, text: str, frame) -> bool:
    """Select option in native select dropdown.

    Args:
        handle: Element handle
        text: Text to select
        frame: Playwright frame

    Returns:
        True if selection succeeded
    """
    try:
        tag = await handle.evaluate("el => el.tagName")
        if tag and tag.lower() == "select":
            try:
                await handle.select_option(label=text)
                with contextlib.suppress(Exception):
                    await frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                await frame.page.wait_for_timeout(200)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


async def click_and_wait_dropdown(handle, frame) -> bool:
    """Click dropdown and wait for options to load.

    Args:
        handle: Element handle
        frame: Playwright frame

    Returns:
        True if click succeeded
    """
    try:
        await handle.click(timeout=2000)
        await frame.page.wait_for_timeout(2000)
        return True
    except Exception:
        return False


async def find_listbox_container_async(frame, listbox_selectors: tuple[str, ...]):
    """Find listbox container element.

    Args:
        frame: Playwright frame
        listbox_selectors: Tuple of selector strings

    Returns:
        Container locator or None
    """
    # Try frame first
    for sel in listbox_selectors:
        try:
            loc = frame.locator(sel)
            if await loc.count() > 0:
                return loc.first
        except Exception:
            pass

    # Try page as fallback
    page = frame.page
    for sel in listbox_selectors:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                return loc.first
        except Exception:
            pass

    return None


async def try_click_exact_match_async(container, text: str, frame) -> bool:
    """Try to click option by exact match.

    Args:
        container: Container locator
        text: Text to match
        frame: Playwright frame

    Returns:
        True if click succeeded
    """
    try:
        opt = container.get_by_role("option", name=re.compile(rf"^{re.escape(text)}$", re.I)).first
        if opt and await opt.count() > 0 and await opt.is_visible():
            await opt.click(timeout=3000)
            with contextlib.suppress(Exception):
                await frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            await frame.page.wait_for_timeout(200)
            return True
    except Exception:
        pass
    return False


async def try_click_normalized_match_async(container, text: str, frame, option_selectors: tuple[str, ...], normalize_fn) -> bool:
    """Try to click option by normalized text match.

    Args:
        container: Container locator
        text: Text to match
        frame: Playwright frame
        option_selectors: Tuple of option selector strings
        normalize_fn: Function to normalize text

    Returns:
        True if click succeeded
    """
    nt = normalize_fn(text)
    for sel in option_selectors:
        try:
            cands = container.locator(sel)
            cnt = await cands.count()
        except Exception:
            cnt = 0

        for i in range(cnt):
            o = cands.nth(i)
            try:
                if not await o.is_visible():
                    continue
                t = normalize_fn((await o.text_content() or "").strip())
                if nt and (t == nt or nt in t):
                    await o.click(timeout=3000)
                    with contextlib.suppress(Exception):
                        await frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                    await frame.page.wait_for_timeout(200)
                    return True
            except Exception:
                pass
    return False


async def read_native_select_options_async(handle, is_placeholder_fn) -> list[dict[str, Any]]:
    """Read options from native select element.

    Args:
        handle: Element handle
        is_placeholder_fn: Function to check if text is placeholder

    Returns:
        List of option dictionaries
    """
    try:
        tag = await handle.evaluate("el => el.tagName")
        if tag and tag.lower() == "select":
            options = await handle.evaluate("""
                (select) => {
                    const opts = [];
                    for (let opt of select.options) {
                        opts.push({
                            text: opt.text.trim(),
                            value: opt.value,
                            index: opt.index
                        });
                    }
                    return opts;
                }
            """)
            out = []
            for o in options or []:
                t = (o.get("text") or "").strip()
                if not is_placeholder_fn(t):
                    out.append(o)
            return out
    except Exception:
        pass
    return []


async def scroll_container_to_bottom_async(container, frame) -> None:
    """Scroll container to bottom to load virtualized options.

    Args:
        container: Container locator
        frame: Playwright frame
    """
    try:
        for _ in range(60):
            try:
                await container.evaluate('(el)=>{el.scrollTop=el.scrollHeight}')
            except Exception:
                with contextlib.suppress(Exception):
                    await frame.page.keyboard.press('End')
            await frame.page.wait_for_timeout(80)
    except Exception:
        pass


async def collect_options_from_container_async(container, option_selectors: tuple[str, ...], is_placeholder_fn) -> list[dict[str, Any]]:
    """Collect options from container after scrolling.

    Args:
        container: Container locator
        option_selectors: Tuple of option selector strings
        is_placeholder_fn: Function to check if text is placeholder

    Returns:
        List of option dictionaries
    """
    opts: list[dict[str, Any]] = []
    for sel in option_selectors:
        try:
            cands = container.locator(sel)
            cnt = await cands.count()
        except Exception:
            cnt = 0

        for i in range(cnt):
            o = cands.nth(i)
            try:
                visible = await o.is_visible()
                if not visible:
                    continue
                text = (await o.text_content() or "").strip()
                if is_placeholder_fn(text):
                    continue
                opts.append({"text": text, "index": i})
            except Exception:
                pass

    return opts
