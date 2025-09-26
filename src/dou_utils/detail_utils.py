"""
detail_utils.py
Scraping de detalhe com modo básico e avançado.

Recursos (advanced=True):
 - Títulos adicionais (h2, classes com *titulo* ou *title*)
 - Seção a partir de meta[name="dc.subject"] quando link direto não aparece
 - PDF certificado (link com 'VERS(Ã|A)O CERTIFICADA')
 - Edição / Página (regex no corpo)
 - Hash único (sha1) com título
 - Fallback de data (data_publicacao_fallback sinalizado em meta)
 - Coleta de meta keys centrais
 - Texto completo (até 8000 chars, preservando corte em frase)

Saída via DetailData (models.DetailData) – espera-se que esse dataclass já exista.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from urllib.parse import urljoin
import re

from .models import DetailData
from .log_utils import get_logger
from .hash_utils import stable_sha1

logger = get_logger(__name__)


# ---------------- Helpers básicos ----------------
def abs_url(base_or_page_url: str, href: str) -> str:
    if not href:
        return ""
    try:
        return urljoin(base_or_page_url, href)
    except Exception:
        return href


def text_of(locator) -> str:
    try:
        if locator and locator.count() > 0 and locator.first.is_visible():
            t = locator.first.text_content() or ""
            return re.sub(r"\s+", " ", t).strip()
    except Exception:
        pass
    return ""


def meta_content(page, selector: str) -> Optional[str]:
    try:
        el = page.locator(selector).first
        if el and el.count() > 0:
            v = el.get_attribute("content")
            if v:
                return v.strip()
    except Exception:
        pass
    return None


def _normalize_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return raw


def _extract_publication_date(page) -> Optional[str]:
    for sel in [
        "meta[property='article:published_time']",
        "meta[name='publicationDate']",
        "meta[name='dc.date']",
    ]:
        pub = meta_content(page, sel)
        if pub:
            return pub
    try:
        time_el = page.locator("time[datetime]").first
        if time_el and time_el.count() > 0:
            dv = time_el.get_attribute("datetime")
            if dv:
                return dv
    except Exception:
        pass
    return None


def _extract_title_basic(page) -> Optional[str]:
    for sel in ["meta[property='og:title']", "meta[name='dc.title']"]:
        t = meta_content(page, sel)
        if t:
            return t
    for sel in ["article h1", "main article h1", "h1"]:
        t = text_of(page.locator(sel))
        if t:
            return t
    try:
        return (page.title() or "").strip() or None
    except Exception:
        return None


def _extract_title_advanced(page) -> Optional[str]:
    basic = _extract_title_basic(page)
    if basic:
        return basic
    for sel in [
        "article h2", "main article h2", "h2",
        "[class*=titulo] h1", "[class*=title] h1",
        "[class*=titulo]", "[class*=title]"
    ]:
        t = text_of(page.locator(sel))
        if t:
            return t
    return basic


def find_dt_dd_value(page, labels_regex: str, max_scan: int = 400) -> Optional[str]:
    pat = re.compile(labels_regex, re.I)
    dts = page.locator("dl dt")
    try:
        n = dts.count()
    except Exception:
        n = 0
    for i in range(min(n, max_scan)):
        try:
            dt = dts.nth(i)
            if not dt.is_visible():
                continue
            txt = (dt.text_content() or "").strip()
            if not txt or not pat.search(txt):
                continue
            dd = dt.locator("xpath=following-sibling::dd[1]")
            val = text_of(dd)
            if val:
                return val
        except Exception:
            continue

    # fallback: strong/b/label/span
    cands = page.locator("strong, b, label, span")
    try:
        k = cands.count()
    except Exception:
        k = 0
    for i in range(min(k, 600)):
        try:
            c = cands.nth(i)
            if not c.is_visible():
                continue
            t = (c.text_content() or "").strip()
            if not t or not pat.search(t):
                continue
            parent = c.locator("xpath=..")
            val = text_of(parent)
            if val:
                val2 = re.sub(r"^\s*(Órgão|Orgao|Tipo|Tipo do Ato)\s*:\s*", "", val, flags=re.I).strip()
                if val2:
                    return val2
        except Exception:
            continue
    return None


def _extract_ementa(page) -> Optional[str]:
    for sel in ["article .texto p", "article p", "main article p", "div[class*=materia] p", "main p"]:
        p = text_of(page.locator(sel))
        if p:
            return p
    return None


def _collect_article_text(page, max_chars: int = 8000) -> Optional[str]:
    selectors = ["article", "main article", "div[class*=materia]", "main"]
    buf: List[str] = []
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0 and loc.first.is_visible():
                ps = loc.locator("p")
                n = min(ps.count(), 300)
                for i in range(n):
                    t = (ps.nth(i).text_content() or "").strip()
                    if t:
                        buf.append(re.sub(r"\s+", " ", t))
                if buf:
                    break
        except Exception:
            continue
    if not buf:
        return None
    text = " ".join(buf)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        trunc = text[:max_chars]
        if "." in trunc:
            trunc = trunc.rsplit(".", 1)[0] + "."
        text = trunc
    return text


def _extract_pdf(page, advanced: bool) -> Optional[str]:
    pdf = None
    try:
        pdfs = page.locator("a[href$='.pdf'], a[href*='.pdf?']")
        kk = pdfs.count()
    except Exception:
        kk = 0
    for i in range(min(kk, 30)):
        a = pdfs.nth(i)
        try:
            href = a.get_attribute("href")
            if href and (href.lower().endswith(".pdf") or ".pdf?" in href.lower()):
                pdf = abs_url(page.url, href)
                break
        except Exception:
            continue
    if not pdf and advanced:
        try:
            vc = page.get_by_role("link", name=re.compile("VERS(Ã|A)O CERTIFICADA", re.I)).first
            if vc and vc.count() > 0 and vc.is_visible():
                hv = vc.get_attribute("href")
                if hv:
                    pdf = abs_url(page.url, hv)
        except Exception:
            pass
    return pdf


def _extract_edicao_pagina(page) -> Dict[str, Optional[str]]:
    result = {"edicao": None, "pagina": None}
    try:
        body_text = text_of(page.locator("article")) or text_of(page.locator("main")) or (page.inner_text("body") or "")
        m_ed = re.search(r"Edi[cç][aã]o\s*:\s*(\d+)", body_text, re.I)
        m_pg = re.search(r"P[aá]gina\s*:\s*(\d+)", body_text, re.I)
        if m_ed:
            result["edicao"] = m_ed.group(1)
        if m_pg:
            result["pagina"] = m_pg.group(1)
    except Exception:
        pass
    return result


def scrape_detail_structured(
    context,
    url: str,
    timeout_ms: int = 60_000,
    capture_meta: bool = True,
    advanced: bool = False,
    fallback_date: Optional[str] = None,
    compute_hash: bool = True
) -> DetailData:
    page = context.new_page()
    detail = DetailData(detail_url=url)
    logger.debug("Starting detail scrape", extra={"url": url, "advanced": advanced})
    try:
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception as e:
        logger.warning("Navigation issue", extra={"url": url, "err": str(e)})

    try:
        # Título
        detail.titulo = _extract_title_advanced(page) if advanced else _extract_title_basic(page)

        # Data publicação
        used_fallback = False
        raw_pub = _extract_publication_date(page)
        norm = _normalize_date(raw_pub)
        if not norm and fallback_date:
            norm = fallback_date
            used_fallback = True
        detail.data_publicacao_raw = raw_pub
        if norm:
            try:
                detail.data_publicacao = datetime.strptime(norm, "%Y-%m-%d")
            except Exception:
                pass

        # Órgão / Tipo
        detail.orgao = find_dt_dd_value(page, r"(Órgão|Orgao)")
        detail.tipo_ato = find_dt_dd_value(page, r"(Tipo|Tipo do Ato)")

        # Seção
        try:
            sec_link = page.locator('a[href*="secao=DO"]').first
            stext = text_of(sec_link)
            if stext:
                detail.secao = stext
        except Exception:
            pass
        if advanced and not detail.secao:
            alt = meta_content(page, 'meta[name="dc.subject"]')
            if alt and re.search(r"DO[123]", alt):
                detail.secao = alt

        # Ementa / texto
        detail.ementa = _extract_ementa(page)
        detail.texto = _collect_article_text(page, max_chars=8000) or detail.ementa

        # PDF
        detail.pdf_url = _extract_pdf(page, advanced=advanced)

        # Edição / Página
        ep = _extract_edicao_pagina(page)
        detail.edicao = ep.get("edicao")
        detail.pagina = ep.get("pagina")

        # Meta
        if capture_meta:
            meta_keys = [
                "meta[name='dc.title']",
                "meta[name='dc.date']",
                "meta[property='og:title']",
                "meta[property='article:published_time']",
                "meta[name='dc.subject']"
            ]
            meta_map = {}
            for sel in meta_keys:
                val = meta_content(page, sel)
                if val:
                    meta_map[sel] = val
            meta_map["data_publicacao_fallback"] = used_fallback
            detail.meta = meta_map

        # Hash
        if compute_hash:
            h = stable_sha1(url, detail.titulo or "")
            detail.meta["hash"] = h

        logger.info("Detail scrape ok", extra={"url": url, "title": detail.titulo})
    except Exception as e:
        logger.error("Detail scrape error", extra={"url": url, "err": str(e)})
    finally:
        try:
            page.close()
        except Exception:
            pass
    return detail


def scrape_detail(
    context,
    url: str,
    timeout_ms: int = 60_000,
    capture_meta: bool = True,
    advanced: bool = False,
    fallback_date: Optional[str] = None,
    compute_hash: bool = True
) -> Dict[str, Any]:
    return scrape_detail_structured(
        context,
        url,
        timeout_ms=timeout_ms,
        capture_meta=capture_meta,
        advanced=advanced,
        fallback_date=fallback_date,
        compute_hash=compute_hash
    ).to_dict()
