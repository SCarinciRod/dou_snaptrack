"""
Mapeamento dinâmico N1 -> N2 (DOU) usando sempre o frame.
"""

import re
import time
from typing import List, Dict, Any, Optional

from core.browser import goto, find_best_frame
from core.locators import N1_IDS, N2_IDS
from core.dropdown import (
    collect_dropdown_roots, is_select_root, read_select_options, read_open_list_options,
    open_dropdown, select_by_text_or_attrs, label_for_control
)
from utils.text import normalize_text, trim_placeholders, filter_options
from utils.files import save_json


def _find_root_by_id(frame, page, element_id: str) -> Optional[Dict[str, Any]]:
    """Procura um root por id no frame e, se não encontrar, na page."""
    if not element_id:
        return None
    try:
        loc = frame.locator(f"#{element_id}")
        if loc.count() > 0 and loc.first.is_visible():
            return {"kind": "select", "selector": f"#{element_id}", "index": 0, "handle": loc.first}
    except Exception:
        pass
    try:
        loc = page.locator(f"#{element_id}")
        if loc.count() > 0 and loc.first.is_visible():
            return {"kind": "select", "selector": f"#{element_id}", "index": 0, "handle": loc.first}
    except Exception:
        pass
    return None


def _find_root_by_label(frame, roots: List[Dict[str, Any]], label_regex: Optional[str]) -> Optional[Dict[str, Any]]:
    """Casa pelo label (ou atributos) usando a lista de roots coletada do frame."""
    if not label_regex:
        return None
    pat = re.compile(label_regex, re.I)

    # 1) label
    for r in roots:
        lab = (r.get("label") or "").strip()
        if lab and pat.search(lab):
            return r

    # 2) atributos do root
    def _attrs_text(h):
        vals = []
        for a in ("placeholder", "id", "name", "aria-label"):
            try:
                v = h.get_attribute(a) or ""
            except Exception:
                v = ""
            if v:
                vals.append(v)
        return " | ".join(vals)

    for r in roots:
        h = r["handle"]
        txt = _attrs_text(h)
        if txt and pat.search(txt):
            return r

    # 3) normalizado (sem acento/minúsculo)
    want_norm = normalize_text(label_regex)
    if want_norm:
        for r in roots:
            h = r["handle"]
            txt = normalize_text(_attrs_text(h))
            if want_norm in txt:
                return r

    return None


def resolve_dropdown_for_pairs(frame, page, wanted_ids: List[str], label_regex: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Resolve o root do dropdown tentando:
    1) IDs canônicos (no frame e na page);
    2) Label/atributos em cima dos roots coletados;
    3) Fallback: primeiro combobox/select visível do frame.
    """
    # 1) Por ID
    for wid in wanted_ids or []:
        r = _find_root_by_id(frame, page, wid)
        if r:
            return r

    # 2) Por label/atributos
    roots = collect_dropdown_roots(frame)
    r = _find_root_by_label(frame, roots, label_regex)
    if r:
        return r

    # 3) Fallback simples
    if roots:
        return roots[0]
    return None


def _wait_n2_repopulated(frame, n2_root, prev_count: int, timeout_ms: int = 15_000) -> None:
    """Espera N2 repopular (contagem diferente de prev_count e > 0)."""
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        if is_select_root(n2_root):
            opts = read_select_options(frame, n2_root)
        else:
            opened = open_dropdown(frame, n2_root)
            opts = read_open_list_options(frame) if opened else []
        cur = len(opts)
        if cur != prev_count and cur > 0:
            return
        frame.wait_for_timeout(120)
    # segue mesmo assim


def map_pairs(context, args) -> Dict[str, Any]:
    """
    Para cada opção em N1, seleciona N1 na página, espera N2 repopular e captura N2.
    Tudo baseado no frame mais promissor.
    """
    page = context.pages[0]

    # Navega e prepara
    data = args.data
    goto(page, data, args.secao)
    frame = find_best_frame(context)

    # Resolve N1/N2 (por ID -> label -> fallback)
    n1_root = resolve_dropdown_for_pairs(frame, page, N1_IDS, args.label1)
    n2_root = resolve_dropdown_for_pairs(frame, page, N2_IDS, args.label2)

    if not n1_root or not n2_root:
        # Diagnóstico: lista até 12 roots detectados com label/id
        roots_dbg = collect_dropdown_roots(frame)
        print("[Debug] Roots detectados (kind/label/id):")
        for r in roots_dbg[:12]:
            try:
                rid = r["handle"].get_attribute("id")
            except Exception:
                rid = None
            print(f" - kind={r['kind']:<9} label='{(r.get('label') or '').strip()}' id={rid}")
        raise RuntimeError("Não consegui localizar os dropdowns N1/N2.")

    # Lê N1
    n1_opts = read_select_options(frame, n1_root) if is_select_root(n1_root) else (open_dropdown(frame, n1_root) and read_open_list_options(frame)) or []
    n1_opts = trim_placeholders(n1_opts)
    n1_filtered = filter_options(n1_opts, args.select1, args.pick1, args.limit1)

    if args.verbose:
        print(f"[N1] total={len(n1_opts)} filtrado={len(n1_filtered)}")

    mapped = []
    for idx, o1 in enumerate(n1_filtered, 1):
        # Guarda contagem anterior de N2
        prev_count = len(read_select_options(frame, n2_root)) if is_select_root(n2_root) else (
            len(read_open_list_options(frame)) if open_dropdown(frame, n2_root) else 0
        )

        # Seleciona N1
        if not select_by_text_or_attrs(frame, n1_root, o1):
            if args.verbose:
                print(f"[skip] N1 não selecionado: {o1.get('text')}")
            continue

        page.wait_for_load_state("networkidle", timeout=60_000)

        # Re-resolve N2 (DOM pode ter sido recriado)
        n2_root = resolve_dropdown_for_pairs(frame, page, N2_IDS, args.label2) or n2_root

        # Espera repopular
        _wait_n2_repopulated(frame, n2_root, prev_count, timeout_ms=15_000)

        # Lê N2
        o2_all = read_select_options(frame, n2_root) if is_select_root(n2_root) else (open_dropdown(frame, n2_root) and read_open_list_options(frame)) or []
        o2_all = trim_placeholders(o2_all)
        o2_filtered = filter_options(o2_all, args.select2, args.pick2, args.limit2_per_n1)

        if args.verbose:
            print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> N2 total={len(o2_all)} filtrado={len(o2_filtered)}")

        mapped.append({"n1": o1, "n2_options": o2_filtered})

    out = {
        "date": data,
        "secao": args.secao,
        "controls": {
            "n1_id": n1_root["handle"].get_attribute("id") if n1_root else None,
            "n2_id": n2_root["handle"].get_attribute("id") if n2_root else None,
        },
        "n1_options": mapped,
    }
    save_json(out, args.out)
    print(f"[OK] Pairs salvos em: {args.out} (N1 mapeados={len(mapped)})")
    return out
