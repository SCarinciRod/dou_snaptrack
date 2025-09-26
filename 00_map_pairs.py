# 00_map_pairs.py
# Mapeamento dinâmico N1 -> N2 (DOU): para cada opção de N1,
# seleciona N1 na página, aguarda repovoar N2 e captura as opções de N2,
# salvando IDs/atributos + labels em um JSON estruturado.
#
# Uso (exemplo):
#   python 00_map_pairs.py --secao DO1 --data 12-09-2025 ^
#     --select1 "^Ministério" --limit1 8 --limit2-per-n1 10 ^
#     --out "artefatos\\map_pairs_DO1_12-09-2025.json" --verbose
#
# Requisitos: playwright (sync), Chromium instalado via `playwright install`.

import argparse, json, re, unicodedata, sys, time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from playwright.sync_api import sync_playwright

# -------------------- Utilidades --------------------
def fmt_date(date_str: Optional[str]) -> str:
    if date_str:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%d-%m-%Y")
    return datetime.now().strftime("%d-%m-%Y")

def normalize_text(s: Optional[str]) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())

def close_cookies(page) -> None:
    for texto in ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]:
        try:
            btn = page.get_by_role("button", name=re.compile(texto, re.I))
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(150)
        except Exception:
            pass

def goto(page, data: str, secao: str) -> None:
    url = f"https://www.in.gov.br/leiturajornal?data={data}&secao={secao}"
    print(f"[Abrindo] {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=90_000)
    close_cookies(page)
    # alternar visão se necessário
    try:
        btn = page.get_by_role("button", name=re.compile(r"(lista|sum[aá]rio)", re.I))
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

def _id_attr(locator) -> Optional[str]:
    try:
        return locator.get_attribute("id")
    except Exception:
        return None

# -------------------- Localização dos dropdowns --------------------
# IDs canônicos do DOU (quando for <select>)
N1_IDS = ["slcOrgs"]
N2_IDS = ["slcOrgsSubs"]

def find_dropdown_by_id_or_label(page, wanted_ids: List[str], label_regex: Optional[str]) -> Optional[Dict[str, Any]]:
    # 1) tentar por ID diretamente (no DOM principal)
    for wid in wanted_ids:
        try:
            loc = page.locator(f"#{wid}")
            if loc.count() > 0 and loc.first.is_visible():
                return {"kind": "select", "handle": loc.first, "id": wid}
        except Exception:
            pass
    # 2) tentar por label (combobox custom)
    if label_regex:
        pat = re.compile(label_regex, re.I)
        cb = page.get_by_role("combobox")
        try:
            n = cb.count()
        except Exception:
            n = 0
        for i in range(min(n, 30)):
            loc = cb.nth(i)
            # tentar achar <label for=...> ou aria-label
            try:
                aria = loc.get_attribute("aria-label") or ""
            except Exception:
                aria = ""
            if aria and pat.search(aria):
                return {"kind": "combobox", "handle": loc, "id": _id_attr(loc)}
            # tentar label associado
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
    # 3) fallback: primeiro combobox visível
    try:
        cb = page.get_by_role("combobox").first
        if cb and cb.count() > 0 and cb.is_visible():
            return {"kind": "combobox", "handle": cb, "id": _id_attr(cb)}
    except Exception:
        pass
    return None

# -------------------- Listbox helpers --------------------
LISTBOX_SELECTORS = [
    "[role=listbox]", "ul[role=listbox]", "div[role=listbox]",
    "ul[role=menu]",  "div[role=menu]",
    ".ng-dropdown-panel", ".p-dropdown-items", ".select2-results__options", ".rc-virtual-list"
]
OPTION_SELECTORS = [
    "[role=option]", "li[role=option]",
    ".ng-option", ".p-dropdown-item", ".select2-results__option",
    "[data-value]", "[data-index]"
]

def listbox_present(page) -> bool:
    for sel in LISTBOX_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False

def get_listbox_container(page):
    for sel in LISTBOX_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    return None

def open_dropdown(page, root) -> bool:
    h = root["handle"] if isinstance(root, dict) else root
    # já aberto?
    if listbox_present(page):
        return True
    # clicar
    try:
        h.scroll_into_view_if_needed(timeout=2000)
        h.click(timeout=2500)
        page.wait_for_timeout(120)
        if listbox_present(page):
            return True
    except Exception:
        pass
    # clique forçado
    try:
        h.click(force=True, timeout=2500)
        page.wait_for_timeout(120)
        if listbox_present(page):
            return True
    except Exception:
        pass
    # teclado
    try:
        h.focus()
        page.keyboard.press("Enter"); page.wait_for_timeout(120)
        if listbox_present(page): return True
        page.keyboard.press("Space"); page.wait_for_timeout(120)
        if listbox_present(page): return True
        page.keyboard.press("Alt+ArrowDown"); page.wait_for_timeout(120)
        if listbox_present(page): return True
    except Exception:
        pass
    return listbox_present(page)

def scroll_listbox_all(container, page) -> None:
    try:
        for _ in range(80):  # um pouco mais agressivo
            changed = container.evaluate("el => { const b=el.scrollTop; el.scrollTop=el.scrollHeight; return el.scrollTop !== b; }")
            page.wait_for_timeout(60)
            if not changed:
                break
    except Exception:
        # fallback no teclado
        for _ in range(20):
            try: page.keyboard.press("End")
            except Exception: pass
            page.wait_for_timeout(60)

def read_open_list_options(page) -> List[Dict[str, Any]]:
    container = get_listbox_container(page)
    if not container:
        return []
    scroll_listbox_all(container, page)
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
                val  = o.get_attribute("value")
                dv   = o.get_attribute("data-value")
                di   = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                oid  = o.get_attribute("id")
                did  = o.get_attribute("data-id") or o.get_attribute("data-key") or o.get_attribute("data-code")
                if text or val or dv or di or oid or did:
                    options.append({"text": text, "value": val, "dataValue": dv, "dataIndex": di, "id": oid, "dataId": did})
            except Exception:
                pass
    # dedupe
    seen, uniq = set(), []
    for o in options:
        key = (o.get("id"), o.get("dataId"), o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen: continue
        seen.add(key); uniq.append(o)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(80)
    except Exception:
        pass
    return uniq

def read_select_options(root) -> List[Dict[str, Any]]:
    sel = root["handle"]
    try:
        return sel.evaluate("""
            el => Array.from(el.options).map((o,i)=>({
                text: (o.label || o.textContent || '').trim(),
                value: o.value,
                dataValue: o.getAttribute('data-value'),
                dataIndex: i,
                id: o.id || null,
                dataId: o.getAttribute('data-id') || o.getAttribute('data-key') || o.getAttribute('data-code')
            }))
        """) or []
    except Exception:
        return []

def remove_placeholders(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

def filter_opts(options: List[Dict[str, Any]], select_regex: Optional[str], pick_list: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    out = options or []
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in out if pat.search(o.get("text") or "")]
        except re.error:
            # fallback tokens acentos-insensível
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

# -------------------- Seleção de opções --------------------
def is_select_root(root: Dict[str, Any]) -> bool:
    try:
        tag = root["handle"].evaluate("el => el.tagName && el.tagName.toLowerCase()")
        return tag == "select"
    except Exception:
        return False

def select_by_text_or_attrs(page, root: Dict[str,Any], option: Dict[str,Any]) -> bool:
    """
    Tenta selecionar 'option' no controle 'root' (select ou combobox custom).
    Preferência:
      - <select>.select_option por value/index/label
      - combobox: abrir listbox, clicar por id/data-id/value/data-value/data-index; fallback por texto.
    """
    if is_select_root(root):
        sel = root["handle"]
        # tenta value
        val = option.get("value")
        if val not in (None, ""):
            try:
                sel.select_option(value=str(val)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        # tenta dataIndex
        di = option.get("dataIndex")
        if di not in (None, ""):
            try:
                sel.select_option(index=int(di)); page.wait_for_load_state("networkidle", timeout=60_000); return True
            except Exception: pass
        # label
        try:
            sel.select_option(label=option.get("text") or "")
            page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception:
            pass
        # fallback: tratar como custom
    # combobox custom
    if not open_dropdown(page, root):
        return False
    container = get_listbox_container(page)
    if not container:
        return False

    def css_escape(s: str) -> str:
        return re.sub(r'(\\.#:[\\>+~*^$|])', r'\\\1', s or "")

    # por id
    oid = option.get("id")
    if oid:
        try:
            opt = container.locator(f"##{css_escape(oid)}").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass
    # por data-id
    did = option.get("dataId")
    if did:
        try:
            opt = container.locator(f"[data-id='{css_escape(did)}'],[data-key='{css_escape(did)}'],[data-code='{css_escape(did)}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass
    # por value
    val = option.get("value")
    if val not in (None, ""):
        try:
            opt = container.locator(f"[value='{css_escape(str(val))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass
    # por data-value/data-index
    dv = option.get("dataValue")
    if dv not in (None, ""):
        try:
            opt = container.locator(f"[data-value='{css_escape(str(dv))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass
    di = option.get("dataIndex")
    if di not in (None, ""):
        try:
            opt = container.locator(f"[data-index='{css_escape(str(di))}'],[data-option-index='{css_escape(str(di))}']").first
            if opt and opt.count() > 0 and opt.is_visible():
                opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
        except Exception: pass
    # por texto (exato → contains)
    txt = option.get("text") or ""
    try:
        opt = container.get_by_role("option", name=re.compile(rf"^{re.escape(txt)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
    except Exception: pass
    try:
        nk = normalize_text(txt)
        any_opt = container.locator(
           "xpath=//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), $k)]",
            k=nk
        ).first
        if any_opt and any_opt.count() > 0 and any_opt.is_visible():
            any_opt.click(timeout=4000); page.wait_for_load_state("networkidle", timeout=60_000); return True
    except Exception: pass
    try: page.keyboard.press("Escape")
    except Exception: pass
    return False

# -------------------- Mapeamento N1 -> N2 --------------------
def wait_n2_repopulated(page, n2_root, prev_count: int, timeout_ms: int = 15_000) -> None:
    """Espera N2 repopular (contagem mudar ou ficar estável != prev_count)."""
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        # ler opções rapidamente (sem abrir, tenta <select>, senão abre e fecha)
        if is_select_root(n2_root):
            opts = read_select_options(n2_root)
        else:
            opened = open_dropdown(page, n2_root)
            opts = read_open_list_options(page) if opened else []
        cur = len(opts)
        if cur != prev_count and cur > 0:
            return
        page.wait_for_timeout(120)
    # prossegue mesmo assim

def map_pairs(secao: str, data: str, out_path: str,
              label1: Optional[str], label2: Optional[str],
              select1: Optional[str], pick1: Optional[str], limit1: Optional[int],
              select2: Optional[str], pick2: Optional[str], limit2_per_n1: Optional[int],
              headful: bool, slowmo: int, verbose: bool) -> Dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful, slow_mo=slowmo)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        try:
            goto(page, data, secao)
            # localizar N1/N2
            n1 = find_dropdown_by_id_or_label(page, N1_IDS, label1)
            n2 = find_dropdown_by_id_or_label(page, N2_IDS, label2)
            if not n1 or not n2:
                raise RuntimeError("Não consegui localizar os dropdowns N1/N2.")

            # ler N1 bruto
            n1_opts = read_select_options(n1) if is_select_root(n1) else (open_dropdown(page, n1) and read_open_list_options(page)) or []
            n1_opts = remove_placeholders(n1_opts)
            n1_filtered = filter_opts(n1_opts, select1, pick1, limit1)

            if verbose:
                print(f"[N1] total={len(n1_opts)} filtrado={len(n1_filtered)}")

            # para cada N1, selecionar e ler N2
            mapped = []
            for idx, o1 in enumerate(n1_filtered, 1):
                # guarda contagem anterior de N2 para detectar repopulação
                prev_n2_count = 0
                if is_select_root(n2):
                    prev_n2_count = len(read_select_options(n2))
                else:
                    # tenta abrir ler e fechar
                    opened = open_dropdown(page, n2)
                    prev_n2_count = len(read_open_list_options(page)) if opened else 0

                ok = select_by_text_or_attrs(page, n1, o1)
                if not ok:
                    if verbose:
                        print(f"[skip] N1 não selecionado: {o1.get('text')}")
                    continue

                # reencontrar N2 root (DOM pode ter sido recriado)
                n2 = find_dropdown_by_id_or_label(page, N2_IDS, label2) or n2
                # esperar repopular
                wait_n2_repopulated(page, n2, prev_n2_count, timeout_ms=15_000)

                # ler N2
                o2_all = read_select_options(n2) if is_select_root(n2) else (open_dropdown(page, n2) and read_open_list_options(page)) or []
                o2_all = remove_placeholders(o2_all)
                o2_filtered = filter_opts(o2_all, select2, pick2, limit2_per_n1)

                if verbose:
                    print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> N2 total={len(o2_all)} filtrado={len(o2_filtered)}")

                mapped.append({
                    "n1": o1,
                    "n2_options": o2_filtered
                })

            data_out = {
                "date": data,
                "secao": secao,
                "controls": {
                    "n1_id": n1.get("id"),
                    "n2_id": n2.get("id")
                },
                "n1_options": mapped
            }
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(json.dumps(data_out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] Pairs salvos em: {out_path} (N1 mapeados={len(mapped)})")
            return data_out

        finally:
            try: browser.close()
            except Exception: pass

# -------------------- CLI --------------------
def main():
    ap = argparse.ArgumentParser(description="Mapeamento dinâmico N1->N2 (DOU)")
    ap.add_argument("--secao", required=True)
    ap.add_argument("--data", required=True, help="DD-MM-AAAA")
    ap.add_argument("--out", required=True)

    # rótulos (ajudam a localizar dropdowns custom)
    ap.add_argument("--label1", help="Regex do rótulo do N1 (ex.: 'Órgão|Orgao')")
    ap.add_argument("--label2", help="Regex do rótulo do N2 (ex.: 'Secretaria|Unidade|Subordinad')")

    # filtros N1
    ap.add_argument("--select1", help="Regex para filtrar rótulos de N1")
    ap.add_argument("--pick1", help="Lista fixa (vírgula) de rótulos de N1")
    ap.add_argument("--limit1", type=int)

    # filtros N2 (por N1)
    ap.add_argument("--select2", help="Regex para filtrar rótulos de N2")
    ap.add_argument("--pick2", help="Lista fixa (vírgula) de rótulos de N2")
    ap.add_argument("--limit2-per-n1", type=int, dest="limit2_per_n1")

    # ambiente
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--slowmo", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")

    args = ap.parse_args()
    data = fmt_date(args.data)
    map_pairs(
        args.secao, data, args.out,
        args.label1, args.label2,
        args.select1, args.pick1, args.limit1,
        args.select2, args.pick2, args.limit2_per_n1,
        args.headful, args.slowmo, args.verbose
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Abortado]")
        sys.exit(130)
