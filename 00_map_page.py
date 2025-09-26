# 00_map_page.py
# Scanner universal de página (Playwright, Python) para mapear frames e elementos interativos.
# Uso (CMD):
# - DOU direto:
#   python 00_map_page.py --dou --secao DO1 --data 08-09-2025 --open-combos --out map_DO1.json --headful --slowmo 200
# - URL genérica:
#   python 00_map_page.py --url "https://exemplo.com" --open-combos --out map.json
#
# Saídas:
# - JSON com: frames, elementos por categoria, seletores propostos (role+name, CSS e XPath),
#   atributos relevantes, bounding box/visibilidade e, se --open-combos, as opções dos combos.
# - (Opcional) screenshot PNG e dump HTML (com --debug-dump).

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


BASE_DOU = "https://www.in.gov.br/leiturajornal"

# Heurísticas de localização (genéricas para frameworks comuns)
DROPDOWN_ROOT_SELECTORS = [
    "[role=combobox]", "select",
    "[aria-haspopup=listbox]", "[aria-expanded][role=button]",
    "div[class*=select]", "div[class*=dropdown]", "div[class*=combobox]"
]
LISTBOX_SELECTORS = [
    "[role=listbox]", "ul[role=listbox]", "div[role=listbox]",
    "ul[role=menu]", "div[role=menu]",
    ".ng-dropdown-panel", ".p-dropdown-items", ".select2-results__options", ".rc-virtual-list"
]
OPTION_SELECTORS = [
    "[role=option]", "li[role=option]",
    ".ng-option", ".p-dropdown-item", ".select2-results__option",
    "[data-value]", "[data-index]"
]

# ====== CASCADE MAPPER: Constantes e utils ======
import re, unicodedata, json, time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# IDs canônicos do DOU (quando presentes)
CASCADE_LEVEL_IDS = {
    1: ["slcOrgs"],       # Órgão (N1)
    2: ["slcOrgsSubs"],   # Subordinada/Unidade (N2)
}

# Seletores de listbox/opções (frameworks comuns)
CASCADE_LISTBOX_SELECTORS = [
    "[role=listbox]", "ul[role=listbox]", "div[role=listbox]",
    ".ng-dropdown-panel", ".p-dropdown-items", ".select2-results__options", ".rc-virtual-list"
]
CASCADE_OPTION_SELECTORS = [
    "[role=option]", "li[role=option]",
    ".ng-option", ".p-dropdown-item", ".select2-results__option",
    "[data-value]", "[data-index]"
]

def casc_normalize_text(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii","ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())

def casc_trim_placeholders(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bad = {
        "selecionar organizacao principal",
        "selecionar organização principal",
        "selecionar organizacao subordinada",
        "selecionar organização subordinada",
        "selecionar tipo do ato",
        "selecionar",
        "todos",
    }
    out = []
    for o in options or []:
        t = casc_normalize_text(o.get("text") or "")
        if t in bad: continue
        out.append(o)
    return out

def casc_filter_opts(options: List[Dict[str, Any]], select_regex: Optional[str], pick_list: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    r"""
    Aplica filtros às opções:
      - select_regex: regex normal; se nada bater, fallback por tokens normalizados (linhas).
      - pick_list: lista de labels exatos (separados por vírgula).
      - limit: trunca no tamanho informado.
    """
    opts = options or []
    out = opts

    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in opts if pat.search(o.get("text") or "")]
        except re.error:
            out = []
        if not out:  # fallback por tokens normalizados
            tokens = [t.strip() for t in select_regex.splitlines() if t.strip()]
            tokens_norm = [casc_normalize_text(t) for t in tokens]
            tmp = []
            for o in opts:
                nt = casc_normalize_text(o.get("text") or "")
                if any(tok and tok in nt for tok in tokens_norm):
                    tmp.append(o)
            out = tmp

    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]

    if limit and limit > 0:
        out = out[:limit]

    return out


def fmt_date(date_str=None):
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")

def goto(page, url):
    print(f"\n[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)
    close_cookies(page)

def close_cookies(page):
    for texto in ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(150)
        except Exception:
            pass

def try_visualizar_em_lista(page):
    """
    Tenta alternar para a visão mais “simples” (lista ou sumário).
    """
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
            return True
    except Exception:
        pass
    return False


def find_best_frame(context):
    page = context.pages[0]
    best = page.main_frame
    best_score = -1
    for fr in page.frames:
        score = 0
        try:
            score += fr.get_by_role("combobox").count()
        except Exception:
            pass
        try:
            score += fr.locator("select").count()
        except Exception:
            pass
        try:
            score += fr.get_by_role("textbox").count()
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best = fr
    return best

def compute_css_path(frame, locator):
    # Gerar um seletor CSS “suficientemente bom” via JS
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

def elem_common_info(frame, locator):
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

def label_for_control(frame, locator):
    # 1) aria-label
    try:
        aria = locator.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    # 2) <label for="id">
    try:
        _id = locator.get_attribute("id")
        if _id:
            lab = frame.evaluate("""
            (id) => {
                const l = document.querySelector(`label[for="${id}"]`);
                return l ? l.textContent.trim() : null;
            }""", _id)
            if lab:
                return lab
    except Exception:
        pass
    # 3) label imediatamente anterior no DOM
    try:
        prev = locator.locator("xpath=preceding::label[1]").first
        if prev and prev.count() > 0 and prev.is_visible():
            t = (prev.text_content() or "").strip()
            if t:
                return t
    except Exception:
        pass
    return ""

def listbox_present(page_or_frame):
    for sel in LISTBOX_SELECTORS:
        try:
            if page_or_frame.locator(sel).count() > 0: return True
        except Exception: pass
    return False

def get_listbox_container(page_or_frame):
    for sel in LISTBOX_SELECTORS:
        try:
            loc = page_or_frame.locator(sel)
            if loc.count() > 0: return loc.first
        except Exception: pass
    return None

def open_dropdown(frame, locator):
    """
    Tenta abrir um dropdown (aria-combobox, <select> custom ou heurístico).
    Estratégias em ordem:
      1) scroll into view + click
      2) click(force=True)
      3) clicar em 'seta/ícone' interno (arrow|icon|caret)
      4) teclado: Enter, Space, Alt+ArrowDown
      5) double-click de contingência
    Considera listbox na page ou no frame.
    """
    # 0) já aberto?
    if listbox_present(frame.page) or listbox_present(frame):
        return True

    # 1) clique normal
    try:
        locator.scroll_into_view_if_needed(timeout=2000)
        locator.click(timeout=2500)
        frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
    except Exception:
        pass

    # 2) clique forçado
    try:
        locator.click(timeout=2500, force=True)
        frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
    except Exception:
        pass

    # 3) seta/ícone interno
    try:
        arrow = locator.locator(
            "xpath=.//*[contains(@class,'arrow') or contains(@class,'icon') or contains(@class,'caret')]"
        ).first
        if arrow.count() > 0 and arrow.is_visible():
            arrow.click(timeout=2500)
            frame.wait_for_timeout(120)
            if listbox_present(frame.page) or listbox_present(frame):
                return True
    except Exception:
        pass

    # 4) teclado
    try:
        locator.focus()
        frame.page.keyboard.press("Enter"); frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
        frame.page.keyboard.press("Space"); frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
        frame.page.keyboard.press("Alt+ArrowDown"); frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
    except Exception:
        pass

    # 5) duplo clique (alguns widgets abrem assim)
    try:
        locator.dblclick(timeout=2500)
        frame.wait_for_timeout(120)
        if listbox_present(frame.page) or listbox_present(frame):
            return True
    except Exception:
        pass

    return listbox_present(frame.page) or listbox_present(frame)

def _is_select(locator) -> bool:
    """Retorna True se o elemento alvo for <select> nativo."""
    try:
        tag = locator.evaluate("el => el && el.tagName && el.tagName.toLowerCase()")
        return tag == "select"
    except Exception:
        return False

def _read_select_options(locator):
    """Lê opções diretamente de um <select> nativo (sem abrir dropdown)."""
    try:
        return locator.evaluate("""
            el => Array.from(el.options || []).map((o,i) => ({
                text: (o.textContent || '').trim(),
                value: o.value,
                dataValue: o.getAttribute('data-value'),
                dataIndex: i
            }))
        """) or []
    except Exception:
        return []

def scroll_listbox_all(container, frame):
    # Rolagem interna do container (JS) para “puxar” todas as opções virtualizadas
    try:
        for _ in range(60):
            changed = container.evaluate("""el => { const b = el.scrollTop; el.scrollTop = el.scrollHeight; return el.scrollTop !== b; }""")
            frame.wait_for_timeout(80)
            if not changed: break
    except Exception:
        # Fallback: rolar viewport
        for _ in range(15):
            try: frame.page.keyboard.press("End")
            except Exception: pass
            frame.wait_for_timeout(80)

def read_open_list_options(frame):
    # Procura container no frame ou na page (portais)
    container = get_listbox_container(frame) or get_listbox_container(frame.page)
    if not container: return []
    scroll_listbox_all(container, frame)
    options = []
    for sel in OPTION_SELECTORS:
        try:
            opts = container.locator(sel)
            k = opts.count()
        except Exception:
            k = 0
        for i in range(k):
            o = opts.nth(i)
            try:
                if not o.is_visible(): continue
                text = (o.text_content() or "").strip()
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                if text or val or dv or di:
                    options.append({"text": text, "value": val, "dataValue": dv, "dataIndex": di})
            except Exception:
                pass
    # dedupe mantendo ordem
    seen = set(); uniq = []
    for o in options:
        key = (o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen: continue
        seen.add(key); uniq.append(o)
    # fechar
    try: frame.page.keyboard.press("Escape")
    except Exception: pass
    return uniq

def map_dropdowns(frame, open_combos=False, max_per_type=50):
    """
    Mapeia dropdowns (combobox/select/heurísticas) e, ao final, DEDUPLICA por id,
    priorizando <select> > combobox > unknown. Mantém ordenação por (y,x).
    """
    results = []
    # Coleta roots (ordenados por posição)
    roots = []
    seen = set()

    # 1) ARIA combobox
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

    # 3) Heurísticas extras
    for selroot in DROPDOWN_ROOT_SELECTORS:
        loc = frame.locator(selroot)
        try: c = loc.count()
        except Exception: c = 0
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

    # ---- DEDUPE por ID (preferindo <select>)
    def _priority(kind:str)->int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)

    # Coleta metadados necessários e constrói chave por ID (quando houver)
    enriched = []
    for r in roots:
        h = r["handle"]
        try:
            el_id = h.get_attribute("id")
        except Exception:
            el_id = None
        # label + info para debug/salvamento
        try:
            lab = label_for_control(frame, r) if callable(label_for_control) else ""
        except Exception:
            lab = ""
        info = elem_common_info(frame, h)
        enriched.append({**r, "id_attr": el_id, "label": lab or (info.get("attrs") or {}).get("aria-label") or "", "info": info})

    # Agrupar por ID quando houver; se não houver ID, agrupar por (rounded y,x) para reduzir duplicidades óbvias
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

    # Coletar opções
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
            if _is_select(h):
                # <select> nativo: ler direto sem abrir
                meta["options"] = _read_select_options(h)
            elif open_combos:
                if open_dropdown(frame, h):
                    opts = read_open_list_options(frame)
                    meta["options"] = opts
        except Exception:
            pass
        results.append(meta)

    return results

def map_elements_by_category(frame, max_per_type=100):
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

def dump_debug(page, prefix="debug"):
    try: page.screenshot(path=f"{prefix}.png", full_page=True)
    except Exception: pass
    try:
        html = page.content()
        Path(f"{prefix}.html").write_text(html, encoding="utf-8")
    except Exception: pass

def main():
    ap = argparse.ArgumentParser(description="Mapeador universal de página (Playwright)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL completa")
    group.add_argument("--dou", action="store_true", help="Usar Leitura do Jornal do DOU")
    ap.add_argument("--data", default=None, help="(DOU) DD-MM-AAAA, default: hoje")
    ap.add_argument("--secao", default="DO1", help="(DOU) DO1|DO2|DO3")
    ap.add_argument("--open-combos", action="store_true", help="Abrir dropdowns e coletar opções")
    ap.add_argument("--out", default="page_map.json")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--slowmo", type=int, default=0)
    ap.add_argument("--debug-dump", action="store_true")
    ap.add_argument("--max-per-type", type=int, default=120, help="Limite por categoria")
    args = ap.parse_args()

    if args.dou:
        data = fmt_date(args.data)
        url = f"{BASE_DOU}?data={data}&secao={args.secao}"
    else:
        url = args.url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)
        context = browser.new_context(ignore_https_errors=True, viewport={"width":1366,"height":900})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)
        try:
            goto(page, url)
            # No DOU, a visualização em lista geralmente simplifica DOM
            if args.dou:
                try_visualizar_em_lista(page)

            # Escolher frame “mais promissor”
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
                "scannedUrl": url,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "frames": frames_meta,
                "dropdowns": dropdowns,
                "elements": categories
            }
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n[OK] Mapa salvo em: {args.out}")
            if args.debug_dump:
                dump_debug(page, "debug_map")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
