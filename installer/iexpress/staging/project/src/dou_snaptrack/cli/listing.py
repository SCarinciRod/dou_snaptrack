from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    # Prefer centralized discovery utils if available later
    from dou_utils.page_utils import goto as _goto, find_best_frame as _find_best_frame
except Exception:
    _goto = None
    _find_best_frame = None

from ..utils.dom import label_for_control, is_select, read_select_options
from ..constants import DROPDOWN_ROOT_SELECTORS

try:
    from dou_utils.selectors import LISTBOX_SELECTORS, OPTION_SELECTORS  # type: ignore
except Exception:
    # Local minimal fallbacks
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


def _fallback_goto(page, data: str, secao: str):
    url = f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)


def _fallback_find_best_frame(context):
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        try:
            for sel in DROPDOWN_ROOT_SELECTORS:
                score += fr.locator(sel).count()
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best = fr
    return best


def _collect_dropdown_roots(frame) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
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

    # Dedupe por id/pos
    by_key: Dict[Any, Dict[str, Any]] = {}
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


def _read_dropdown_options(frame, root: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not root:
        return []
    if is_select(root.get("handle")):
        return read_select_options(root.get("handle"))
    # open visual dropdown and read
    h = root.get("handle")
    if h is None:
        return []
    try:
        h.click(timeout=2000)
        frame.wait_for_timeout(150)
    except Exception:
        pass

    container = None
    for sel in LISTBOX_SELECTORS:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                container = loc.first
                break
        except Exception:
            pass
    if not container:
        return []
    opts: List[Dict[str, Any]] = []
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
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                opts.append({"text": text, "value": val, "dataValue": dv, "dataIndex": di})
            except Exception:
                pass
    try:
        frame.page.keyboard.press("Escape")
    except Exception:
        pass
    # dedupe
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for o in opts:
        key = (o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)
    return uniq


def _print_list(label: str, level: int, options: List[Dict[str, Any]]) -> None:
    print(f"\n[Dropdown {level}] {label or '(sem rótulo)'} — {len(options)} opções")
    print("-" * 110)
    for i, o in enumerate(options, 1):
        print(
            f"{i:>2} "
            f"text='{o.get('text','')}' "
            f"value={o.get('value')} "
            f"data-value={o.get('dataValue')} "
            f"data-index={o.get('dataIndex')}"
        )
    print("-" * 110)


def run_list(context, data: str, secao: str, level: int,
             key1: Optional[str], key1_type: Optional[str],
             key2: Optional[str], key2_type: Optional[str],
             out_path: str, debug_dump: bool,
             label1: Optional[str] = None, label2: Optional[str] = None, label3: Optional[str] = None) -> None:

    page = context.pages[0]
    if _goto:
        _goto(page, f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}")
    else:
        _fallback_goto(page, data, secao)

    frame = _find_best_frame(context) if _find_best_frame else _fallback_find_best_frame(context)
    roots = _collect_dropdown_roots(frame)
    if not roots:
        print("[Erro] Nenhum dropdown detectado.")
        Path(out_path).write_text("{}", encoding="utf-8")
        return

    r1 = roots[0] if roots else None
    lab1 = label_for_control(frame, r1["handle"]) if r1 else ""
    opts1 = _read_dropdown_options(frame, r1) if r1 else []
    _print_list(lab1, 1, opts1)

    lab2 = lab3 = ""; opts2: List[Dict[str, Any]] = []; opts3: List[Dict[str, Any]] = []
    if level >= 2 and len(roots) > 1:
        r2 = roots[1]
        lab2 = label_for_control(frame, r2["handle"]) or ""
        opts2 = _read_dropdown_options(frame, r2)
        _print_list(lab2, 2, opts2)
    if level >= 3 and len(roots) > 2:
        r3 = roots[2]
        lab3 = label_for_control(frame, r3["handle"]) or ""
        opts3 = _read_dropdown_options(frame, r3)
        _print_list(lab3, 3, opts3)

    payload: Dict[str, Any] = {"data": data, "secao": secao, "level": level}
    if level == 1:
        payload.update({"label": lab1, "options": opts1})
    elif level == 2:
        payload.update({"label1": lab1, "label2": lab2, "options": opts2, "key1": key1, "key1_type": key1_type})
    else:
        payload.update({
            "label1": lab1, "label2": lab2, "label3": lab3,
            "options": opts3, "key1": key1, "key1_type": key1_type, "key2": key2, "key2_type": key2_type,
        })

    Path(out_path).write_text(__import__('json').dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Opções do nível {level} salvas em: {out_path}")
