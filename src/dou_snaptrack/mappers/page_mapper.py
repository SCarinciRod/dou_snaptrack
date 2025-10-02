from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime

from ..constants import DROPDOWN_ROOT_SELECTORS
from ..utils.dom import elem_common_info, label_for_control, is_select, read_select_options
from dou_utils.dropdown_strategies import open_dropdown_robust, collect_open_list_options

def map_dropdowns(frame, open_combos: bool = False, max_per_type: int = 120) -> List[Dict[str, Any]]:
    results = []
    roots = []
    seen = set()

    # 1) get_by_role('combobox')
    cb = frame.get_by_role("combobox")
    try: m = cb.count()
    except Exception: m = 0
    for i in range(min(m, max_per_type)):
        h = cb.nth(i)
        try:
            box = h.bounding_box()
            if not box: continue
            key = ("role=combobox", i, round(box["y"],2), round(box["x"],2))
            if key in seen: continue
            seen.add(key)
            roots.append({"kind":"combobox","sel":"role=combobox","index":i,"handle":h,"y":box["y"],"x":box["x"]})
        except Exception:
            pass

    # 2) <select>
    sel = frame.locator("select")
    try: n = sel.count()
    except Exception: n = 0
    for i in range(min(n, max_per_type)):
        h = sel.nth(i)
        try:
            box = h.bounding_box()
            if not box: continue
            key = ("select", i, round(box["y"],2), round(box["x"],2))
            if key in seen: continue
            seen.add(key)
            roots.append({"kind":"select","sel":"select","index":i,"handle":h,"y":box["y"],"x":box["x"]})
        except Exception:
            pass

    # 3) heurísticas extras
    for selroot in DROPDOWN_ROOT_SELECTORS:
        loc = frame.locator(selroot)
        try: c = loc.count()
        except Exception: c = 0
        if c == 0:
            continue
        for i in range(min(c, max_per_type)):
            h = loc.nth(i)
            try:
                box = h.bounding_box()
                if not box: continue
                key = (selroot, i, round(box["y"],2), round(box["x"],2))
                if key in seen: continue
                seen.add(key)
                roots.append({"kind":"unknown","sel":selroot,"index":i,"handle":h,"y":box["y"],"x":box["x"]})
            except Exception:
                pass

    # dedupe por id/posição, preferindo select > combobox > unknown
    def _priority(kind:str)->int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)

    enriched = []
    for r in roots:
        h = r["handle"]
        try: el_id = h.get_attribute("id")
        except Exception: el_id = None
        lab = ""
        try: lab = label_for_control(frame, h)
        except Exception: pass
        info = elem_common_info(frame, h)
        enriched.append({**r, "id_attr": el_id, "label": lab or (info.get("attrs") or {}).get("aria-label") or "", "info": info})

    by_key = {}
    for r in enriched:
        if r.get("id_attr"):
            k = ("id", r["id_attr"])
        else:
            k = ("pos", round(r["y"],1), round(r["x"],1), r["sel"])
        best = by_key.get(k)
        if not best or _priority(r["kind"]) > _priority(best["kind"]):
            by_key[k] = r

    deduped = list(by_key.values())
    deduped.sort(key=lambda rr: (rr["y"], rr["x"]))

    for r in deduped:
        h = r["handle"]
        meta = {
            "kind": r["kind"],
            "rootSelector": r["sel"],
            "roleIndex": r["index"],
            "label": r.get("label",""),
            "info": r.get("info"),
            "options": []
        }
        try:
            if is_select(h):
                meta["options"] = read_select_options(h)
            elif open_combos:
                if open_dropdown_robust(frame, h):
                    meta["options"] = collect_open_list_options(frame)
        except Exception:
            pass
        results.append(meta)

    return results

def map_elements_by_category(frame, max_per_type=100) -> Dict[str, Any]:
    cats = {}
    categories = {
        "searchbox": frame.get_by_role("searchbox"),
        "textbox": frame.get_by_role("textbox"),
        "button": frame.get_by_role("button"),
        "link": frame.get_by_role("link"),
        "listbox": frame.get_by_role("listbox"),
        "option": frame.get_by_role("option"),
        "haspopup": frame.locator("[aria-haspopup]"),
        "expanded": frame.locator("[aria-expanded]"),
    }
    for name, loc in categories.items():
        items = []
        try: cnt = loc.count()
        except Exception: cnt = 0
        for i in range(min(cnt, max_per_type)):
            el = loc.nth(i)
            items.append(elem_common_info(frame, el))
        cats[name] = {"count": cnt, "sampled": len(items), "items": items}
    return cats
