# dou_utils/url_utils.py
from __future__ import annotations
from urllib.parse import urljoin, urlparse

def origin_of(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return "https://www.in.gov.br"

def abs_url(base_or_page_url: str, href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    base = origin_of(base_or_page_url)
    return urljoin(base + "/", href.lstrip("/"))
