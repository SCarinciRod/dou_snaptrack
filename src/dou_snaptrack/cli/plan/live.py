from __future__ import annotations

import contextlib
import re
from typing import Any

from ...constants import DROPDOWN_ROOT_SELECTORS, LEVEL_IDS
from ...utils.browser import fmt_date
from ...utils.dom import is_select, read_select_options
from ...utils.text import normalize_text
from ...utils.wait_utils import wait_for_condition, wait_for_options_loaded

try:
    from dou_utils.selection import LISTBOX_SELECTORS, OPTION_SELECTORS  # type: ignore
except Exception:
    LISTBOX_SELECTORS = (
        "[role=listbox]",
        "ul[role=listbox]",
        "div[role=listbox]",
        "ul[role=menu]",
        "div[role=menu]",
        ".ng-dropdown-panel",
        ".p-dropdown-items",
        ".select2-results__options",
        ".rc-virtual-list",
    )
    OPTION_SELECTORS = (
        "[role=option]",
        "li[role=option]",
        ".ng-option",
        ".p-dropdown-item",
        ".select2-results__option",
        "[data-value]",
        "[data-index]",
    )


def _collect_dropdown_roots(frame) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    seen = set()

    def _push(kind: str, sel: str, loc):
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

    _push("combobox", "role=combobox", frame.get_by_role("combobox"))
    _push("select", "select", frame.locator("select"))
    for sel in DROPDOWN_ROOT_SELECTORS:
        _push("unknown", sel, frame.locator(sel))

    def _prio(k: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(k, 0)

    by_key: dict[Any, dict[str, Any]] = {}
    for r in roots:
        h = r["handle"]
        try:
            elid = h.get_attribute("id")
        except Exception:
            elid = None
        k = ("id", elid) if elid else ("pos", round(r["y"], 1), round(r["x"], 1), r["selector"])
        best = by_key.get(k)
        if not best or _prio(r["kind"]) > _prio(best["kind"]):
            by_key[k] = r

    out = list(by_key.values())
    out.sort(key=lambda rr: (rr["y"], rr["x"]))
    return out


def _locate_root_by_id(frame, elem_id: str) -> dict[str, Any] | None:
    """Try to locate a dropdown root by a specific element id within the frame or page.

    Returns a root dict compatible with _collect_dropdown_roots entries or None if not found.
    """
    try:
        loc = frame.locator(f"#{elem_id}")
        if not loc or loc.count() == 0:
            loc = frame.page.locator(f"#{elem_id}")
        if not loc or loc.count() == 0:
            return None
        h = loc.first
        try:
            box = h.bounding_box() or {"y": 0, "x": 0}
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


def _select_roots(frame) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Pick r1/r2 roots prioritizing known IDs from LEVEL_IDS; fallback to first two roots."""
    r1 = None
    r2 = None
    try:
        for eid in LEVEL_IDS.get(1, []) or []:
            r1 = _locate_root_by_id(frame, eid)
            if r1:
                break
    except Exception:
        r1 = None
    try:
        for eid in LEVEL_IDS.get(2, []) or []:
            r2 = _locate_root_by_id(frame, eid)
            if r2:
                break
    except Exception:
        r2 = None
    if not r1 or (not r2):
        roots = _collect_dropdown_roots(frame)
        if not r1:
            r1 = roots[0] if roots else None
        if not r2:
            r2 = roots[1] if roots and len(roots) > 1 else None
    return r1, r2


def _get_listbox_container(frame):
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


def _read_open_list_options(frame) -> list[dict[str, Any]]:
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
    container = _get_listbox_container(frame)
    if not container:
        return []
    opts: list[dict[str, Any]] = []
    for sel in OPTION_SELECTORS:
        try:
            cands = container.locator(sel)
            cnt = cands.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            o = cands.nth(i)
            try:
                if not o.is_visible():
                    continue
                text = (o.text_content() or "").strip()
                # descartar placeholders genéricos (ex.: "Selecionar organização subordinada")
                if _is_placeholder_text(text):
                    continue
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                opts.append({"text": text, "value": val, "dataValue": dv, "dataIndex": di})
            except Exception:
                pass
    with contextlib.suppress(Exception):
        frame.page.keyboard.press("Escape")
    # dedupe
    seen = set()
    uniq: list[dict[str, Any]] = []
    for o in opts:
        key = (o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)
    return uniq


def _read_dropdown_options(frame, root: dict[str, Any]) -> list[dict[str, Any]]:
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
    if is_select(h):
        opts = read_select_options(h)
        # Filtrar placeholders em listas nativas <select>
        out = []
        for o in opts or []:
            try:
                t = (o.get("text") or "").strip()
                if _is_placeholder_text(t):
                    continue
                out.append(o)
            except Exception:
                out.append(o)
        return out
    with contextlib.suppress(Exception):
        h.click(timeout=2000)
        # OTIMIZAÇÃO: espera inteligente até opções aparecerem
        # Timeout aumentado para 2s (DOU pode ser lento) com polling a cada 50ms
        wait_for_options_loaded(frame, min_count=1, timeout_ms=2000)
    return _read_open_list_options(frame)


def _select_by_text(frame, root: dict[str, Any], text: str) -> bool:
    h = root.get("handle")
    if h is None:
        return False
    # select native <select>
    if is_select(h):
        try:
            h.select_option(label=text)
            # Espera mais curta e específica
            with contextlib.suppress(Exception):
                frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            # OTIMIZAÇÃO: Polling condicional ao invés de wait fixo (economiza 50-150ms)
            with contextlib.suppress(Exception):
                wait_for_condition(frame, lambda: frame.page.is_visible("body"), timeout_ms=200, poll_ms=50)
            return True
        except Exception:
            pass
    # custom: open and click matching option
    with contextlib.suppress(Exception):
        h.click(timeout=2000)
        # OTIMIZAÇÃO: espera até opções carregarem (timeout 2s para DOU lento)
        wait_for_options_loaded(frame, min_count=1, timeout_ms=2000)
    container = _get_listbox_container(frame)
    if not container:
        return False
    try:
        # exact by role
        opt = container.get_by_role("option", name=re.compile(rf"^{re.escape(text)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=3000)
            with contextlib.suppress(Exception):
                frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            # OTIMIZAÇÃO: Polling condicional ao invés de wait fixo
            with contextlib.suppress(Exception):
                wait_for_condition(frame, lambda: frame.page.is_visible("body"), timeout_ms=200, poll_ms=50)
            return True
    except Exception:
        pass
    # fallback contains (normalized)
    nt = normalize_text(text)
    for sel in OPTION_SELECTORS:
        try:
            cands = container.locator(sel)
            cnt = cands.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            o = cands.nth(i)
            try:
                if not o.is_visible():
                    continue
                t = normalize_text((o.text_content() or "").strip())
                if nt and (t == nt or nt in t):
                    o.click(timeout=3000)
                    with contextlib.suppress(Exception):
                        frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                    # OTIMIZAÇÃO: Polling condicional
                    with contextlib.suppress(Exception):
                        wait_for_condition(frame, lambda: frame.page.is_visible("body"), timeout_ms=200, poll_ms=50)
                    return True
            except Exception:
                pass
    with contextlib.suppress(Exception):
        frame.page.keyboard.press("Escape")
    return False


def _filter_opts(options: list[dict[str, Any]], select_regex: str | None, pick_list: str | None, limit: int | None) -> list[dict[str, Any]]:
    opts = options or []
    out = opts
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in opts if pat.search(o.get("text") or "")]
        except re.error:
            out = []
        # Robust fallback: se regex compila mas não encontrou nada, tenta match por tokens normalizados
        if not out:
            tokens = [t.strip() for t in select_regex.splitlines() if t.strip()]
            tokens_norm = [normalize_text(t) for t in tokens if normalize_text(t)]
            if tokens_norm:
                # OTIMIZAÇÃO: usar regex compilada em vez de any() com substring O(n*k) -> O(n)
                token_pattern = "|".join(re.escape(t) for t in tokens_norm)
                token_rx = re.compile(token_pattern, re.I)
                out = [o for o in opts if token_rx.search(normalize_text(o.get("text") or ""))]
    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]
    if limit and limit > 0:
        out = out[:limit]
    return out


def _build_keys(opts: list[dict[str, Any]], key_type: str) -> list[str]:
    keys: list[str] = []
    for o in opts:
        if key_type == "text":
            t = (o.get("text") or "").strip()
            if t:
                keys.append(t)
        elif key_type == "value":
            v = o.get("value")
            if v not in (None, ""):
                keys.append(str(v))
        elif key_type == "dataValue":
            dv = o.get("dataValue")
            if dv not in (None, ""):
                keys.append(str(dv))
        elif key_type == "dataIndex":
            di = o.get("dataIndex")
            if di not in (None, ""):
                keys.append(str(di))
    seen = set()
    out: list[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def build_plan_live(p, args, browser=None) -> dict[str, Any]:
    """Gera um plano dinâmico L1xL2 diretamente do site (sem N3).

    This implementation starts a local Playwright context so all browser
    operations happen in the same thread. The provided `p` argument is ignored
    here to avoid cross-thread usage.
    """
    from .helpers import (
        build_plan_config_dict,
        cleanup_browser_context,
        collect_n1_candidates,
        collect_n2_for_n1,
        ensure_n1_root,
        generate_combos_for_n1,
        launch_browser_with_fallbacks,
        setup_browser_and_page,
        try_select_n1,
        wait_after_selection,
    )

    v = bool(getattr(args, "plan_verbose", False))
    headful = bool(getattr(args, "headful", False))
    slowmo = int(getattr(args, "slowmo", 0) or 0)

    combos: list[dict[str, Any]] = []
    pctx_mgr = None
    pctx = None
    must_close_browser = False
    context = None

    try:
        # Launch browser if not provided
        if browser is None:
            from playwright.sync_api import sync_playwright  # type: ignore
            pctx_mgr = sync_playwright()
            pctx = pctx_mgr.__enter__()
            browser = launch_browser_with_fallbacks(pctx, headful, slowmo)
            must_close_browser = True

        # Setup page and navigate
        context, page, frame = setup_browser_and_page(browser, args)
        data = fmt_date(args.data)

        # Get dropdown roots
        r1, r2 = _select_roots(frame)
        if not r1 and not r2:
            raise RuntimeError("Nenhum dropdown detectado.")

        # Ensure we have N1
        if not r1:
            r1 = ensure_n1_root(frame, v)
        if not r1:
            raise RuntimeError("Dropdown N1 não encontrado.")

        # Collect N1 candidates
        k1_list = collect_n1_candidates(frame, r1, args, v)

        # Process each N1 to generate combos
        maxc = getattr(args, "max_combos", None)
        if isinstance(maxc, int) and maxc <= 0:
            maxc = None

        for k1 in k1_list:
            if maxc and len(combos) >= maxc:
                break

            # Re-resolve N1 root (DOM may change)
            r1 = ensure_n1_root(frame, v)
            if not r1:
                continue

            # Select N1
            if not try_select_n1(frame, r1, k1, v):
                continue

            wait_after_selection(page, frame)

            # Collect N2 for this N1
            _, r2 = _select_roots(frame)
            k2_list = collect_n2_for_n1(frame, r2, args, k1, v)

            # Generate combos for this N1
            new_combos = generate_combos_for_n1(k1, k2_list, args, frame, r1, r2, maxc, len(combos))
            combos.extend(new_combos)

            if maxc and len(combos) >= maxc:
                break

        if not combos:
            raise RuntimeError("Nenhum combo válido L1xL2 foi gerado.")

        # Build configuration dictionary
        cfg = build_plan_config_dict(args, data, combos)

        # Cleanup
        cleanup_browser_context(context, browser, must_close_browser, pctx_mgr)
        return cfg
    except Exception:
        cleanup_browser_context(context, browser if must_close_browser else None, must_close_browser, pctx_mgr)
        raise
