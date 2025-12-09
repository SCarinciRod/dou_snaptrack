"""Versão ASYNC do plan_live para compatibilidade com Streamlit.

MIGRAÇÃO PLAYWRIGHT SYNC → ASYNC
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

# ============================================================================
# FUNÇÕES AUXILIARES ASYNC
# ============================================================================

async def _collect_dropdown_roots_async(frame) -> list[dict[str, Any]]:
    """Versão async de _collect_dropdown_roots."""
    from dou_snaptrack.cli.plan_live import DROPDOWN_ROOT_SELECTORS

    roots: list[dict[str, Any]] = []
    seen = set()

    async def _push(kind: str, sel: str, loc):
        try:
            cnt = await loc.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            h = loc.nth(i)
            try:
                box = await h.bounding_box()
                if not box:
                    continue
                key = (sel, i, round(box["y"], 2), round(box["x"], 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({
                    "selector": sel,
                    "kind": kind,
                    "index": i,
                    "handle": h,
                    "y": box["y"],
                    "x": box["x"],
                })
            except Exception:
                pass

    await _push("combobox", "role=combobox", frame.get_by_role("combobox"))
    await _push("select", "select", frame.locator("select"))
    for sel in DROPDOWN_ROOT_SELECTORS:
        await _push("unknown", sel, frame.locator(sel))

    def _prio(k: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(k, 0)

    by_key: dict[Any, dict[str, Any]] = {}
    for r in roots:
        h = r["handle"]
        try:
            elid = await h.get_attribute("id")
        except Exception:
            elid = None
        k = ("id", elid) if elid else ("pos", round(r["y"], 1), round(r["x"], 1), r["selector"])
        best = by_key.get(k)
        if not best or _prio(r["kind"]) > _prio(best["kind"]):
            by_key[k] = r

    out = list(by_key.values())
    out.sort(key=lambda rr: (rr["y"], rr["x"]))
    return out


async def _locate_root_by_id_async(frame, elem_id: str) -> dict[str, Any] | None:
    """Versão async de _locate_root_by_id - TOTALMENTE ASYNC."""
    try:
        loc = frame.locator(f"#{elem_id}")
        if not loc or await loc.count() == 0:
            loc = frame.page.locator(f"#{elem_id}")
        if not loc or await loc.count() == 0:
            return None
        h = loc.first
        try:
            box = await h.bounding_box() or {"y": 0, "x": 0}
        except Exception:
            box = {"y": 0, "x": 0}
        return {
            "selector": f"#{elem_id}",
            "kind": "id",
            "index": 0,
            "handle": h,
            "y": box.get("y") or 0,
            "x": box.get("x") or 0,
        }
    except Exception:
        return None


async def _select_roots_async(frame) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Versão async de _select_roots."""
    from dou_snaptrack.cli.plan_live import LEVEL_IDS

    r1 = None
    r2 = None
    try:
        for eid in LEVEL_IDS.get(1, []) or []:
            r1 = await _locate_root_by_id_async(frame, eid)
            if r1:
                break
    except Exception:
        r1 = None
    try:
        for eid in LEVEL_IDS.get(2, []) or []:
            r2 = await _locate_root_by_id_async(frame, eid)
            if r2:
                break
    except Exception:
        r2 = None
    return (r1, r2)


async def _read_dropdown_options_async(frame, root: dict[str, Any]) -> list[dict[str, Any]]:
    """Versão async simplificada de _read_dropdown_options."""
    from dou_snaptrack.cli.plan_live import LISTBOX_SELECTORS, OPTION_SELECTORS, normalize_text
    from .async_dropdown_helpers import (
        read_native_select_options_async,
        click_and_wait_dropdown,
        find_listbox_container_async,
        scroll_container_to_bottom_async,
        collect_options_from_container_async,
    )

    if not root:
        return []
    h = root.get("handle")
    if h is None:
        return []

    def _is_placeholder_text(t: str) -> bool:
        nt = normalize_text(t or "")
        if not nt:
            return True
        placeholders = [
            "selecionar", "selecione", "escolha",
            "todos", "todas", "todas as", "todos os",
            "selecionar organizacao subordinada",
            "selecione uma opcao", "selecione a unidade", "selecione um orgao",
        ]
        return any(nt == p or nt.startswith(p + " ") for p in placeholders)

    # Try native select first
    native_opts = await read_native_select_options_async(h, _is_placeholder_text)
    if native_opts:
        return native_opts

    # Custom dropdown: click and read options
    await click_and_wait_dropdown(h, frame)

    # Find listbox container
    container = await find_listbox_container_async(frame, LISTBOX_SELECTORS)
    if not container:
        return []

    # Scroll to bottom for virtualized lists
    await scroll_container_to_bottom_async(container, frame)

    # Collect options from container
    return await collect_options_from_container_async(container, OPTION_SELECTORS, _is_placeholder_text)


async def _select_by_text_async(frame, root: dict[str, Any], text: str) -> bool:
    """Versão async de _select_by_text."""
    from dou_snaptrack.cli.plan_live import LISTBOX_SELECTORS, OPTION_SELECTORS, normalize_text
    from .async_dropdown_helpers import (
        select_native_dropdown_async,
        click_and_wait_dropdown,
        find_listbox_container_async,
        try_click_exact_match_async,
        try_click_normalized_match_async,
    )

    h = root.get("handle")
    if h is None:
        return False

    # Try native select
    if await select_native_dropdown_async(h, text, frame):
        return True

    # Custom dropdown: click and select option
    await click_and_wait_dropdown(h, frame)

    # Find listbox container
    container = await find_listbox_container_async(frame, LISTBOX_SELECTORS)
    if not container:
        return False

    # Try exact match first
    if await try_click_exact_match_async(container, text, frame):
        return True

    # Fallback: normalized text match
    if await try_click_normalized_match_async(container, text, frame, OPTION_SELECTORS, normalize_text):
        return True

    # Close dropdown if not found
    with contextlib.suppress(Exception):
        await frame.page.keyboard.press("Escape")
    return False


async def _count_options_async(frame, root: dict[str, Any]) -> int:
    """Conta opções visíveis/avaliáveis para um root de dropdown (<select> ou custom)."""
    if not root:
        return 0
    h = root.get("handle")
    if h is None:
        return 0
    try:
        tag = await h.evaluate("el => el.tagName && el.tagName.toLowerCase()")
    except Exception:
        tag = None
    if tag == "select":
        try:
            return await h.evaluate("sel => sel.options?.length || 0")
        except Exception:
            return 0
    # custom: abrir, contar opções e fechar
    try:
        await h.click(timeout=1500)
        await frame.page.wait_for_timeout(200)
    except Exception:
        pass
    count = 0
    try:
        from dou_snaptrack.cli.plan_live import LISTBOX_SELECTORS, OPTION_SELECTORS
        container = None
        for sel in LISTBOX_SELECTORS:
            try:
                loc = frame.locator(sel)
                if await loc.count() > 0:
                    container = loc.first
                    break
            except Exception:
                pass
        if not container:
            page = frame.page
            for sel in LISTBOX_SELECTORS:
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0:
                        container = loc.first
                        break
                except Exception:
                    pass
        if container:
            # leve scroll antes de contar
            with contextlib.suppress(Exception):
                await container.evaluate('(el)=>{el.scrollTop=el.scrollHeight}')
            for sel in OPTION_SELECTORS:
                try:
                    cands = container.locator(sel)
                    count = max(count, await cands.count())
                except Exception:
                    pass
    finally:
        with contextlib.suppress(Exception):
            await frame.page.keyboard.press('Escape')
    return int(count)


async def wait_n2_repopulated_async(frame, n2_root: dict[str, Any], prev_count: int, timeout_ms: int = 20_000, poll_ms: int = 150) -> None:
    """Aguarda N2 ser repopulado após seleção de N1.
    Considera tanto <select> quanto dropdown custom (abrindo para contar se necessário).
    """
    import time
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        cur = await _count_options_async(frame, n2_root)
        if cur != prev_count and cur > 0:
            return
        await frame.page.wait_for_timeout(poll_ms)


# ============================================================================
# BUILD_PLAN_LIVE_ASYNC
# ============================================================================

async def build_plan_live_async(p, args) -> dict[str, Any]:
    """Versão async de build_plan_live."""
    from .plan_build_helpers import (
        launch_browser_with_fallbacks,
        setup_browser_context,
        wait_for_dropdown_ready,
        detect_dropdown_roots,
        process_n1_option,
        build_combos_from_keys,
        build_config,
        save_plan_if_requested,
    )
    
    v = bool(getattr(args, "plan_verbose", False))
    headful = bool(getattr(args, "headful", False))
    slowmo = int(getattr(args, "slowmo", 0) or 0)

    combos: list[dict[str, Any]] = []

    # Launch browser with fallbacks
    browser = await launch_browser_with_fallbacks(p, headful, slowmo)
    context, page = await setup_browser_context(browser)

    # Import functions
    from dou_snaptrack.cli.plan_live import _build_keys, _filter_opts
    from dou_snaptrack.utils.browser import build_dou_url, goto_async, try_visualizar_em_lista_async
    from dou_snaptrack.utils.dom import find_best_frame_async

    secao = getattr(args, "secao", "DO1")
    data = getattr(args, "data", None)

    url = build_dou_url(data or "", secao)
    await goto_async(page, url)

    with contextlib.suppress(Exception):
        await try_visualizar_em_lista_async(page)

    frame = await find_best_frame_async(context)

    # Wait for dropdown ready
    await wait_for_dropdown_ready(page)

    # Detect N1/N2 roots
    r1, r2 = await detect_dropdown_roots(frame, _select_roots_async, _collect_dropdown_roots_async)

    if not r1:
        await browser.close()
        raise RuntimeError("Nenhum dropdown N1 detectado")

    # Read and filter N1 options
    opts1 = await _read_dropdown_options_async(frame, r1)
    opts1 = _filter_opts(
        opts1,
        getattr(args, "select1", None),
        getattr(args, "pick1", None),
        getattr(args, "limit1", None)
    )

    k1_list = _build_keys(opts1, getattr(args, "key1_type_default", "text"))

    if v:
        print(f"[plan-live-async] N1 válidos: {len(k1_list)}")

    # Process each N1 option
    for k1 in k1_list:
        k2_list = await process_n1_option(
            frame, r1, r2, k1, page,
            _read_dropdown_options_async,
            _select_by_text_async,
            _count_options_async,
            wait_n2_repopulated_async,
            _select_roots_async,
            _filter_opts,
            _build_keys,
            args,
            v
        )

        # Build combos
        combos.extend(build_combos_from_keys(k1, k2_list))

    await browser.close()

    # Build and save config
    cfg = build_config(data, secao, combos, getattr(args, "defaults", {}))
    save_plan_if_requested(cfg, getattr(args, "plan_out", None), v)

    return cfg

    return cfg


# Wrapper síncrono para compatibilidade
def build_plan_live_sync_wrapper(p, args) -> dict[str, Any]:
    """Wrapper que roda async via asyncio.run()."""
    async def run():
        async with async_playwright() as p_async:
            return await build_plan_live_async(p_async, args)

    return asyncio.run(run())
