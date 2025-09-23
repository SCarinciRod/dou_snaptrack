# mappers/page_mapper.py
# Mapeador de página - baseado no 00_map_page.py

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.sync_api import BrowserContext, Page

from datetime import datetime
from utils.date import fmt_date
from core.navigation import find_best_frame, goto
from core.dropdown import (
    open_dropdown, is_select_root, listbox_present, 
    read_select_options, read_open_list_options
)

def collect_dropdown_roots(frame) -> List[Dict[str, Any]]:
    """
    Coleta raízes de dropdown (combobox/select/heurísticas), DEDUPLICA por id,
    e prioriza select > combobox > unknown. Mantém ordenação por (y,x).
    """
    from core.dropdown import DROPDOWN_ROOT_SELECTORS
    
    roots = []
    seen = set()

    def _maybe_add(sel: str, kind: str, loc):
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
                key = (sel, i, round(box["y"],2), round(box["x"],2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({"selector": sel, "kind": kind, "index": i, "handle": h, "y": box["y"], "x": box["x"]})
            except Exception:
                continue

    # 1) ARIA combobox
    _maybe_add("role=combobox", "combobox", frame.get_by_role("combobox"))
    # 2) <select>
    _maybe_add("select", "select", frame.locator("select"))
    # 3) Heurísticas extras
    for sel in DROPDOWN_ROOT_SELECTORS:
        _maybe_add(sel, "unknown", frame.locator(sel))

    def _priority(kind:str)->int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)

    enriched = []
    for r in roots:
        h = r["handle"]
        try:
            el_id = h.get_attribute("id")
        except Exception:
            el_id = None
        enriched.append({**r, "id_attr": el_id})

    # DEDUPE por id; se sem id, usa (pos,selector)
    by_key = {}
    for r in enriched:
        if r.get("id_attr"):
            k = ("id", r["id_attr"])
        else:
            k = ("pos", round(r["y"],1), round(r["x"],1), r["selector"])
        best = by_key.get(k)
        if not best or _priority(r["kind"]) > _priority(best["kind"]):
            by_key[k] = r

    deduped = list(by_key.values())
    deduped.sort(key=lambda rr: (rr["y"], rr["x"]))
    return deduped

def label_for_control(frame, root: Dict[str, Any]) -> str:
    """Obtém o rótulo associado a um controle."""
    h = root["handle"]
    try:
        aria = h.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    try:
        _id = h.get_attribute("id")
        if _id:
            lab = frame.evaluate(
                """
                (id) => {
                    const l = document.querySelector(`label[for="${id}"]`);
                    return l ? l.textContent.trim() : null;
                }
                """,
                _id,
            )
            if lab:
                return lab
    except Exception:
        pass
    try:
        prev = h.locator("xpath=preceding::label[1]").first
        if prev and prev.count() > 0 and prev.is_visible():
            t = (prev.text_content() or "").strip()
            if t:
                return t
    except Exception:
        pass
    return ""

def elem_common_info(frame, locator):
    """Coleta informações comuns de um elemento (visibilidade, box, atributos, seletores)."""
    info = {"visible": None, "box": None, "attrs": {}, "text": None, "cssPath": None, "xpath": None}
    try: info["visible"] = locator.is_visible()
    except Exception: pass
    try: info["box"] = locator.bounding_box()
    except Exception: pass
    # atributos
    for a in ["id","name","class","role","placeholder","aria-label","aria-haspopup","aria-expanded",
              "value","data-value","data-index","data-option-index"]:
        try:
            v = locator.get_attribute(a)
            if v is not None: info["attrs"][a] = v
        except Exception:
            pass
    # texto leve
    try:
        t = locator.text_content()
        if t: info["text"] = t.strip()
    except Exception:
        pass
    # seletores
    info["cssPath"] = compute_css_path(frame, locator)
    info["xpath"] = compute_xpath(frame, locator)
    return info

def compute_css_path(frame, locator):
    """Gera um seletor CSS para o elemento."""
    # Gerar um seletor CSS "suficientemente bom" via JS
    try:
        return locator.evaluate("""(el) => {
            function cssPath(e){
                if (!(e instanceof Element)) return null;
                const path = [];
                while (e.nodeType === Node.ELEMENT_NODE) {
                    let selector = e.nodeName.toLowerCase();
                    if (e.id) { selector += '#' + e.id; path.unshift(selector); break; }
                    else {
                        let sib = e, nth = 1;
                        while (sib = sib.previousElementSibling) { if (sib.nodeName.toLowerCase() === selector) nth++; }
                        selector += `:nth-of-type(${nth})`;
                    }
                    path.unshift(selector);
                    e = e.parentNode;
                    if (!e || e.nodeName.toLowerCase() === 'html') break;
                }
                return path.join(' > ');
            }
            return cssPath(el);
        }""")
    except Exception:
        return None

def compute_xpath(frame, locator):
    """Gera um seletor XPath para o elemento."""
    try:
        return locator.evaluate("""(el)=>{
            function xpath(el){
                if (el && el.id) return "//*[@id='" + el.id + "']";
                const parts = [];
                while (el && el.nodeType === Node.ELEMENT_NODE){
                    let nb = 0, idx = 0;
                    const siblings = el.parentNode ? el.parentNode.childNodes : [];
                    for (let i=0; i<siblings.length; i++){
                        const sib = siblings[i];
                        if (sib.nodeType === Node.ELEMENT_NODE && sib.nodeName === el.nodeName){
                            nb++;
                            if (sib === el) idx = nb;
                        }
                    }
                    const name = el.nodeName.toLowerCase();
                    const part = (nb>1)? name+"["+idx+"]" : name;
                    parts.unshift(part);
                    el = el.parentNode;
                }
                return "/" + parts.join("/");
            }
            return xpath(el);
        }""")
    except Exception:
        return None

def map_dropdowns(frame, open_combos=False, max_per_type=50):
    """
    Mapeia dropdowns (combobox/select/heurísticas) e, ao final, DEDUPLICA por id,
    priorizando <select> > combobox > unknown. Mantém ordenação por (y,x).
    """
    roots = collect_dropdown_roots(frame)
    results = []
    
    # Coletar opções
    for r in roots:
        h = r["handle"]
        meta = {
            "kind": r["kind"],
            "rootSelector": r["selector"],
            "roleIndex": r["index"],
            "label": label_for_control(frame, r),
            "info": elem_common_info(frame, h),
            "options": []
        }
        try:
            if is_select_root(r):
                # <select> nativo: ler direto sem abrir
                meta["options"] = read_select_options(frame, r)
            elif open_combos:
                if open_dropdown(frame, h):
                    opts = read_open_list_options(frame)
                    meta["options"] = opts
        except Exception:
            pass
        results.append(meta)

    return results

def map_elements_by_category(frame, max_per_type=100):
    """Mapeia elementos por categoria (searchbox, textbox, button, etc.)"""
    cats = {}
    # Principais
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

def map_page(context: BrowserContext, args) -> Dict[str, Any]:
    """
    Mapeia uma página do DOU ou URL genérica.
    Retorna uma estrutura com frames, dropdowns e elementos.
    """
    page = context.pages[0]
    
    # Navegação
    if args.dou:
        data = fmt_date(args.data)
        goto(page, data, args.secao)
    else:
        url = args.url
        print(f"\n[Abrindo] {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_load_state("networkidle", timeout=90_000)
    
    # Escolher frame "mais promissor"
    frame = find_best_frame(context)
    
    # Mapear dropdowns (com ou sem abrir opções)
    dropdowns = map_dropdowns(frame, open_combos=args.open_combos, max_per_type=args.max_per_type)
    
    # Mapear outras categorias
    categories = map_elements_by_category(frame, max_per_type=args.max_per_type)
    
    # Compilar estrutura de frames para referência
    frames_meta = []
    for fr in page.frames:
        try:
            fi = {
                "name": fr.name or "",
                "url": fr.url or "",
                "isMain": fr == page.main_frame,
                "comboboxCount": fr.get_by_role("combobox").count(),
                "selectCount": fr.locator("select").count()
            }
        except Exception:
            fi = {"name":"", "url":"", "isMain": fr == page.main_frame}
        frames_meta.append(fi)
    
    result = {
        "scannedUrl": page.url,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "frames": frames_meta,
        "dropdowns": dropdowns,
        "elements": categories
    }
    
    return result

def save_map(data: Dict[str, Any], out_path: str) -> None:
    """Salva o mapa em um arquivo JSON."""
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Mapa salvo em: {out_path}")

def dump_debug(page, prefix="debug"):
    """Salva screenshot e HTML para debugging."""
    try: page.screenshot(path=f"{prefix}.png", full_page=True)
    except Exception: pass
    try:
        html = page.content()
        Path(f"{prefix}.html").write_text(html, encoding="utf-8")
    except Exception: pass
