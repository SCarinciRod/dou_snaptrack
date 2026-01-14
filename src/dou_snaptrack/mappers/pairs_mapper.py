from __future__ import annotations

import contextlib
import re
from typing import Any

from dou_utils.dropdowns import collect_open_list_options, open_dropdown_robust

from ..utils.dom import read_select_options
from ..utils.text import normalize_text


def remove_placeholders(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = {
        "selecionar organizacao principal","selecionar organização principal",
        "selecionar organizacao subordinada","selecionar organização subordinada",
        "selecionar tipo do ato","selecionar","todos"
    }
    out = []
    for o in options or []:
        if normalize_text(o.get("text")) in bad:
            continue
        out.append(o)
    return out

def filter_opts(options: list[dict[str, Any]], select_regex: str | None, pick_list: str | None, limit: int | None) -> list[dict[str, Any]]:
    out = options or []
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in out if pat.search(o.get("text") or "")]
        except re.error:
            # Fallback: match por tokens normalizados com regex compilada O(n) em vez de O(n*k)
            toks = [t.strip() for t in select_regex.splitlines() if t.strip()]
            toksn = [normalize_text(t) for t in toks if normalize_text(t)]
            if toksn:
                token_pattern = "|".join(re.escape(t) for t in toksn)
                token_rx = re.compile(token_pattern, re.I)
                out = [o for o in out if token_rx.search(normalize_text(o.get("text") or ""))]
    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]
    if limit and limit > 0:
        out = out[:limit]
    return out

def find_dropdown_by_id_or_label(page, wanted_ids: list[str], label_regex: str | None) -> dict[str, Any] | None:
    # 1) por ID (DOM principal)
    for wid in wanted_ids:
        try:
            loc = page.locator(f"#{wid}")
            if loc.count() > 0 and loc.first.is_visible():
                return {"kind": "select", "handle": loc.first, "id": wid}
        except Exception:
            pass
    # 2) por label em combobox
    if label_regex:
        pat = re.compile(label_regex, re.I)
        cb = page.get_by_role("combobox")
        try:
            n = cb.count()
        except Exception:
            n = 0
        for i in range(min(n, 30)):
            loc = cb.nth(i)
            try:
                aria = loc.get_attribute("aria-label") or ""
            except Exception:
                aria = ""
            if aria and pat.search(aria):
                return {"kind": "combobox", "handle": loc, "id": loc.get_attribute("id")}
            try:
                elid = loc.get_attribute("id")
                if elid:
                    lab = page.locator(f'label[for="{elid}"]').first
                    if lab and lab.count() > 0:
                        ltxt = (lab.text_content() or "").strip()
                        if ltxt and pat.search(ltxt):
                            return {"kind": "combobox", "handle": loc, "id": elid}
            except Exception:
                pass
    # 3) fallback primeiro combobox
    try:
        cb = page.get_by_role("combobox").first
        if cb and cb.count() > 0 and cb.is_visible():
            return {"kind": "combobox", "handle": cb, "id": cb.get_attribute("id")}
    except Exception:
        pass
    return None

def is_select_root(root: dict[str, Any]) -> bool:
    try:
        tag = root["handle"].evaluate("el => el.tagName && el.tagName.toLowerCase()")
        return tag == "select"
    except Exception:
        return False

def select_by_text_or_attrs(page, root: dict[str,Any], option: dict[str,Any]) -> bool:
    # Preferir <select> nativo
    if is_select_root(root):
        sel = root["handle"]
        val = option.get("value")
        if val not in (None, ""):
            try:
                sel.select_option(value=str(val))
                page.wait_for_load_state("networkidle", timeout=60_000)
                return True
            except Exception:
                pass
        di = option.get("dataIndex")
        if di not in (None, ""):
            try:
                sel.select_option(index=int(di))
                page.wait_for_load_state("networkidle", timeout=60_000)
                return True
            except Exception:
                pass
        try:
            sel.select_option(label=option.get("text") or "")
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
        except Exception:
            pass
    # Combobox custom
    if not open_dropdown_robust(page, root["handle"]):
        return False
    container_options = collect_open_list_options(page)
    # match por id/dataId/value/dataValue/dataIndex/text
    wanted = [
        ("id", option.get("id")),
        ("dataId", option.get("dataId")),
        ("value", option.get("value")),
        ("dataValue", option.get("dataValue")),
        ("dataIndex", option.get("dataIndex")),
    ]
    for key, val in wanted:
        if val not in (None, ""):
            for o in container_options:
                if str(o.get(key)) == str(val):
                    try:
                        # localizar pelo texto (fallback) se necessário
                        # aqui simplificamos: reabertura e clique por nome exato
                        name = o.get("text") or ""
                        opt = page.get_by_role("option", name=name).first
                        if opt and opt.count() > 0 and opt.is_visible():
                            opt.click(timeout=4000)
                            page.wait_for_load_state("networkidle", timeout=60_000)
                            return True
                    except Exception:
                        pass
    # texto exato
    txt = option.get("text") or ""
    try:
        opt = page.get_by_role("option", name=txt).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4000)
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    with contextlib.suppress(Exception):
        page.keyboard.press("Escape")
    return False

def wait_n2_repopulated(page, n2_root, prev_count: int, timeout_ms: int = 15_000) -> None:
    import time
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        if is_select_root(n2_root):
            opts = read_select_options(n2_root["handle"])
        else:
            opened = open_dropdown_robust(page, n2_root["handle"])
            opts = collect_open_list_options(page) if opened else []
        cur = len(opts)
        if cur != prev_count and cur > 0:
            return
        page.wait_for_timeout(120)

def _scroll_listbox_to_end(page) -> None:
    try:
        lb = page.locator('[role=listbox], .ng-dropdown-panel, .p-dropdown-items, .select2-results__options').first
        if lb and lb.count() > 0:
            for _ in range(40):
                try:
                    lb.evaluate('(el)=>{el.scrollTop=el.scrollHeight}')
                except Exception:
                    page.keyboard.press('End')
                page.wait_for_timeout(60)
    except Exception:
        pass

