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

    # Para <select> nativo
    try:
        tag = await h.evaluate("el => el.tagName")
        if tag and tag.lower() == "select":
            # Ler <option> elements
            options = await h.evaluate("""
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
                if not _is_placeholder_text(t):
                    out.append(o)
            return out
    except Exception:
        pass

    # Para custom dropdown: clicar e ler opções
    try:
        await h.click(timeout=2000)
        await frame.page.wait_for_timeout(400)  # Aguardar opções carregarem
    except Exception:
        pass

    # Buscar container de listbox
    container = None
    for sel in LISTBOX_SELECTORS:
        try:
            loc = frame.locator(sel)
            count = await loc.count()
            if count > 0:
                container = loc.first
                break
        except Exception:
            pass

    if not container:
        # Tentar na page inteira
        page = frame.page
        for sel in LISTBOX_SELECTORS:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                if count > 0:
                    container = loc.first
                    break
            except Exception:
                pass

    if not container:
        return []

    # Scroll até o fim (para listas virtualizadas)
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

    # Ler opções do container (pós-scroll)
    opts: list[dict[str, Any]] = []
    for sel in OPTION_SELECTORS:
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
                if _is_placeholder_text(text):
                    continue
                opts.append({"text": text, "index": i})
            except Exception:
                pass

    return opts


async def _select_by_text_async(frame, root: dict[str, Any], text: str) -> bool:
    """Versão async de _select_by_text."""
    from dou_snaptrack.cli.plan_live import LISTBOX_SELECTORS, OPTION_SELECTORS, normalize_text

    h = root.get("handle")
    if h is None:
        return False

    # Para <select> nativo
    try:
        tag = await h.evaluate("el => el.tagName")
        if tag and tag.lower() == "select":
            try:
                await h.select_option(label=text)
                with contextlib.suppress(Exception):
                    await frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                await frame.page.wait_for_timeout(200)
                return True
            except Exception:
                pass
    except Exception:
        pass

    # Custom dropdown: clicar e selecionar opção
    try:
        await h.click(timeout=2000)
        await frame.page.wait_for_timeout(2000)  # Aguardar opções carregarem
    except Exception:
        pass

    # Buscar container de listbox
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

    if not container:
        return False

    # Tentar match exato por role
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

    # Fallback: buscar por texto normalizado
    nt = normalize_text(text)
    for sel in OPTION_SELECTORS:
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
                t = normalize_text((await o.text_content() or "").strip())
                if nt and (t == nt or nt in t):
                    await o.click(timeout=3000)
                    with contextlib.suppress(Exception):
                        await frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                    await frame.page.wait_for_timeout(200)
                    return True
            except Exception:
                pass

    # Fechar dropdown se não encontrou
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
    v = bool(getattr(args, "plan_verbose", False))

    headful = bool(getattr(args, "headful", False))
    slowmo = int(getattr(args, "slowmo", 0) or 0)

    combos: list[dict[str, Any]] = []
    cfg: dict[str, Any] = {}

    # Launch browser
    browser = None
    try:
        browser = await p.chromium.launch(channel="chrome", headless=not headful, slow_mo=slowmo)
    except Exception:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=not headful, slow_mo=slowmo)
        except Exception:
            exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
            if not exe:
                for c in (
                    r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                ):
                    if Path(c).exists():
                        exe = c
                        break
            if exe and Path(exe).exists():
                browser = await p.chromium.launch(executable_path=exe, headless=not headful, slow_mo=slowmo)

    if not browser:
        browser = await p.chromium.launch(headless=not headful, slow_mo=slowmo)

    context = await browser.new_context(ignore_https_errors=True)
    context.set_default_timeout(90_000)
    page = await context.new_page()

    # Import funções de utilities
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

    # Aguardar especificamente o dropdown #slcOrgs estar populado
    # Espera condicional é mais eficiente que wait_for_timeout fixo
    dropdown_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => document.querySelector('#slcOrgs')?.options?.length > 2",
            timeout=15000
        )
        dropdown_ready = True

    # Fallback: pequena pausa se espera condicional falhou
    if not dropdown_ready:
        await page.wait_for_timeout(2000)

    # Detectar raízes N1/N2
    try:
        r1, r2 = await _select_roots_async(frame)
    except Exception:
        roots = await _collect_dropdown_roots_async(frame)
        r1 = roots[0] if roots else None
        r2 = roots[1] if len(roots) > 1 else None

    if not r1:
        await browser.close()
        raise RuntimeError("Nenhum dropdown N1 detectado")

    # Ler opções N1
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

    # Iterar sobre N1
    for k1 in k1_list:
        # Selecionar N1 (USAR ASYNC)
        # Registrar contagem anterior de N2 (se existir)
        prev_n2_count = 0
        if r2:
            prev_n2_count = await _count_options_async(frame, r2)

        await _select_by_text_async(frame, r1, k1)

        # Aguardar AJAX base - preferir networkidle quando possível
        await page.wait_for_load_state("domcontentloaded", timeout=30_000)
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=5_000)

        # Re-detectar N2 (USAR ASYNC)
        try:
            _, r2_new = await _select_roots_async(frame)
            if r2_new:
                r2 = r2_new
        except Exception:
            pass

        # Aguardar repopulação de N2 e ler opções completas
        if r2:
            with contextlib.suppress(Exception):
                await wait_n2_repopulated_async(frame, r2, prev_n2_count, timeout_ms=25_000, poll_ms=150)
            opts2 = await _read_dropdown_options_async(frame, r2)
            opts2 = _filter_opts(
                opts2,
                getattr(args, "select2", None),
                getattr(args, "pick2", None),
                getattr(args, "limit2", None)
            )
            k2_list = _build_keys(opts2, getattr(args, "key2_type_default", "text"))

            if v:
                print(f"[plan-live-async] N1='{k1}' => N2 válidos: {len(k2_list)}")
        else:
            k2_list = []

        # Criar combos
        if k2_list:
            combos.extend([
                {
                    "key1": k1,
                    "label1": k1,
                    "key2": k2,
                    "label2": k2,
                }
                for k2 in k2_list
            ])
        else:
            combos.append({
                "key1": k1,
                "label1": k1,
                "key2": "Todos",
                "label2": "Todos",
            })

    await browser.close()

    # Montar config
    cfg = {
        "data": data or "",
        "secaoDefault": secao,
        "defaults": getattr(args, "defaults", {}),
        "combos": combos,
        "output": {
            "pattern": "{topic}_{secao}_{date}_{idx}.json",
            "report": "batch_report.json"
        }
    }

    # Salvar plan se especificado
    plan_out = getattr(args, "plan_out", None)
    if plan_out:
        import json
        Path(plan_out).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if v:
            print(f"[plan-live-async] Plano salvo: {plan_out}")

    return cfg


# Wrapper síncrono para compatibilidade
def build_plan_live_sync_wrapper(p, args) -> dict[str, Any]:
    """Wrapper que roda async via asyncio.run()."""
    async def run():
        async with async_playwright() as p_async:
            return await build_plan_live_async(p_async, args)

    return asyncio.run(run())
