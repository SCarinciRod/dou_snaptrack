# query_utils.py
# Utilitários para aplicar busca e coletar links no DOU

import contextlib
import re


def apply_query(frame, query: str):
    if not query:
        return
    locs = [
        lambda f: f.locator("#search-bar").first,
        lambda f: f.get_by_role("searchbox").first,
        lambda f: f.get_by_role("textbox", name=re.compile("pesquis", re.I)).first,
        lambda f: f.locator('input[placeholder*="esquis" i]').first,
        lambda f: f.locator('input[type="search"]').first,
        lambda f: f.locator('input[aria-label*="pesquis" i]').first,
        lambda f: f.locator('input[id*="pesquis" i], input[name*="pesquis" i]').first,
    ]
    sb = None
    for get in locs:
        try:
            cand = get(frame)
            if cand and cand.count() > 0:
                cand.wait_for(state="visible", timeout=5000)
                sb = cand
                break
        except Exception:
            continue
    if not sb:
        print("[Aviso] Campo de busca não encontrado; seguindo sem query.")
        return
    with contextlib.suppress(Exception):
        sb.scroll_into_view_if_needed(timeout=1500)
    try:
        sb.fill(query)
    except Exception:
        sb.evaluate(
            "(el, val) => { el.value = val; el.dispatchEvent(new Event('input',{bubbles:true})); }",
            query
        )
    try:
        sb.press("Enter")
    except Exception:
        try:
            bt = frame.get_by_role("button", name=re.compile("pesquis", re.I))
            if bt.count() > 0 and bt.first.is_visible():
                bt.first.click()
        except Exception:
            pass
    # Aguarde o conteúdo aparecer sem travar em "networkidle" longo
    with contextlib.suppress(Exception):
        frame.page.wait_for_load_state("domcontentloaded", timeout=20000)
    with contextlib.suppress(Exception):
        frame.locator("a[href*='/web/dou/']").first.wait_for(state="visible", timeout=20000)

def collect_links(frame, max_links: int = 100, max_scrolls: int = 30, scroll_pause_ms: int = 250, stable_rounds: int = 2):
    page = frame.page
    # Aguarda breve estabilização
    with contextlib.suppress(Exception):
        page.wait_for_timeout(250)

    selectors = [
        "#hierarchy_content a[href*='/web/dou/']",
        "article a[href*='/web/dou/']",
        "main a[href*='/web/dou/']",
        "section a[href*='/web/dou/']",
        "a.card__link[href*='/web/dou/']",
        "a[href*='/web/dou/']",
    ]

    # Escolher o melhor frame + locator (primeiro tenta o frame fornecido)
    frames = [frame] + [f for f in page.frames if f is not frame]
    best = None
    best_cnt = -1
    best_frame = frame
    for fr in frames:
        for sel in selectors:
            try:
                loc = fr.locator(sel)
                cnt = loc.count()
                if cnt > best_cnt:
                    best = loc
                    best_cnt = cnt
                    best_frame = fr
            except Exception:
                continue
    anchors = best or frame.locator("a[href*='/web/dou/']")
    active_frame = best_frame

    # Tente "carregar mais"/"ver mais" dentro do frame ativo
    for _ in range(5):
        try:
            btn = active_frame.get_by_role("button", name=re.compile(r"(carregar|ver).*(mais|resultados)", re.I)).first
            if btn and btn.count() > 0 and btn.is_visible():
                btn.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                active_frame.wait_for_timeout(200)
            else:
                break
        except Exception:
            break

    # Scroll incremental no frame e na página
    last = -1
    stable = 0
    last_scroll_h = None
    for _ in range(max_scrolls):
        # Obter contagem de âncoras e scrollHeight em uma única ida ao frame
        try:
            count, sh = active_frame.evaluate(
                "() => { const c=document.querySelectorAll(\"a[href*='/web/dou/']\").length; const h=document.body.scrollHeight; return [c,h]; }"
            )
        except Exception:
            # fallback para chamadas separadas
            try:
                count = anchors.count()
            except Exception:
                count = 0
            try:
                sh = active_frame.evaluate("document.body.scrollHeight")
            except Exception:
                sh = None
        if count >= max_links:
            break
        if count == last:
            stable += 1
        else:
            stable = 0
        if stable >= stable_rounds or (sh is not None and last_scroll_h == sh):
            break
        last = count
        last_scroll_h = sh
        with contextlib.suppress(Exception):
            active_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        with contextlib.suppress(Exception):
            # Só scroll na página se necessário; maioria dos sites carrega dentro do frame
            if count < max_links:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        with contextlib.suppress(Exception):
            active_frame.wait_for_timeout(scroll_pause_ms)

    # Extrair itens de forma vetorizada (menos RPCs)
    try:
        items = active_frame.evaluate(
            "(limit) => {\n"
            "  const out = [];\n"
            "  const as = Array.from(document.querySelectorAll(\"a[href*='/web/dou/']\"));\n"
            "  for (let i=0; i<as.length && out.length < limit; i++) {\n"
            "    const a = as[i];\n"
            "    const href = a.getAttribute('href') || '';\n"
            "    let text = a.textContent ? a.textContent.trim() : '';\n"
            "    if (href && text) { out.push({titulo: text, link: href}); }\n"
            "  }\n"
            "  return out;\n"
            "}",
            max_links,
        )
        if isinstance(items, list) and items:
            return items
    except Exception:
        pass

    # Fallback seguro (menos eficiente)
    items = []
    try:
        total = anchors.count()
    except Exception:
        total = 0
    for i in range(min(total, max_links)):
        a = anchors.nth(i)
        try:
            titulo = (a.text_content() or "").strip()
            link = a.get_attribute("href") or ""
            if titulo and link:
                items.append({"titulo": titulo, "link": link})
        except Exception:
            continue
    return items
