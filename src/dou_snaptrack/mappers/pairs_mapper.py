from __future__ import annotations

import re
from typing import Any

from dou_utils.dropdown_strategies import collect_open_list_options, open_dropdown_robust

from ..constants import LEVEL_IDS
from ..utils.dom import read_select_options
from ..utils.text import normalize_text


def remove_placeholders(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = {
        "selecionar organizacao principal","selecionar organização principal",
        "selecionar organizacao subordinada","selecionar organização subordinada",
        "selecionar tipo do ato","selecionar","todos"
    }
    out=[]
    for o in options or []:
        if normalize_text(o.get("text")) in bad: continue
        out.append(o)
    return out

def filter_opts(options: list[dict[str, Any]], select_regex: str | None, pick_list: str | None, limit: int | None) -> list[dict[str, Any]]:
    out = options or []
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in out if pat.search(o.get("text") or "")]
        except re.error:
            toks = [t.strip() for t in select_regex.splitlines() if t.strip()]
            toksn = [normalize_text(t) for t in toks]
            tmp=[]
            for o in out:
                nt = normalize_text(o.get("text") or "")
                if any(tok and tok in nt for tok in toksn):
                    tmp.append(o)
            out=tmp
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
        try: n = cb.count()
        except Exception: n = 0
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
                sel.select_option(value=str(val)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        di = option.get("dataIndex")
        if di not in (None, ""):
            try:
                sel.select_option(index=int(di)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        try:
            sel.select_option(label=option.get("text") or "")
            page.wait_for_load_state("networkidle", timeout=60_000); return True
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
                            opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
                    except Exception:
                        pass
    # texto exato
    txt = option.get("text") or ""
    try:
        opt = page.get_by_role("option", name=txt).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
    except Exception:
        pass
    try: page.keyboard.press("Escape")
    except Exception: pass
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

def map_pairs(page, secao: str, data: str,
              label1: str | None, label2: str | None,
              select1: str | None, pick1: str | None, limit1: int | None,
              select2: str | None, pick2: str | None, limit2_per_n1: int | None,
              verbose: bool) -> dict[str, Any]:

    n1 = find_dropdown_by_id_or_label(page, LEVEL_IDS[1], label1)
    n2 = find_dropdown_by_id_or_label(page, LEVEL_IDS[2], label2)
    if not n1:
        raise RuntimeError("Não consegui localizar o dropdown de N1.")

    n1_opts = read_select_options(n1["handle"]) if is_select_root(n1) else (open_dropdown_robust(page, n1["handle"]) and collect_open_list_options(page)) or []
    n1_opts = remove_placeholders(n1_opts)
    n1_filtered = filter_opts(n1_opts, select1, pick1, limit1)

    if verbose:
        print(f"[N1] total={len(n1_opts)} filtrado={len(n1_filtered)}")

    mapped = []
    for idx, o1 in enumerate(n1_filtered, 1):
        prev_n2_count = 0
        if n2:
            if is_select_root(n2):
                prev_n2_count = len(read_select_options(n2["handle"]))
            else:
                opened = open_dropdown_robust(page, n2["handle"])
                prev_n2_count = len(collect_open_list_options(page)) if opened else 0

        ok = select_by_text_or_attrs(page, n1, o1)
        if not ok:
            if verbose:
                print(f"[skip] N1 não selecionado: {o1.get('text')}")
            continue

        # Re-resolve N2 after selecting N1 (DOM may re-render) and repopulate
        n2 = find_dropdown_by_id_or_label(page, LEVEL_IDS[2], label2) or n2
        if n2:
            wait_n2_repopulated(page, n2, prev_n2_count, timeout_ms=15_000)
            if is_select_root(n2):
                o2_all = read_select_options(n2["handle"]) or []
            else:
                opened = open_dropdown_robust(page, n2["handle"])  # open to collect
                if opened:
                    _scroll_listbox_to_end(page)
                    o2_all = collect_open_list_options(page)
                    try: page.keyboard.press('Escape')
                    except Exception: pass
                else:
                    o2_all = []
            o2_all = remove_placeholders(o2_all)
            o2_filtered = filter_opts(o2_all, select2, pick2, limit2_per_n1)

            if verbose:
                print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> N2 total={len(o2_all)} filtrado={len(o2_filtered)}")

            mapped.append({"n1": o1, "n2_options": o2_filtered})
        else:
            # N1-only context
            if verbose:
                print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> sem N2 (contexto N1-only)")
            mapped.append({"n1": o1, "n2_options": []})

    return {
        "date": data,
        "secao": secao,
        "controls": {
            "n1_id": n1.get("id") if n1 else None,
            "n2_id": n2.get("id") if n2 else None,
        },
        "n1_options": mapped
    }
