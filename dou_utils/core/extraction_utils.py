from __future__ import annotations
from typing import List, Dict, Any, Optional
import re

def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def extract_simple_links(root_locator, item_selector: str, link_selector: Optional[str] = None, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        items = root_locator.locator(item_selector)
    except Exception:
        return []
    try:
        n = items.count()
    except Exception:
        n = 0
    out: List[Dict[str, Any]] = []
    for i in range(n):
        if max_items and len(out) >= max_items:
            break
        it = items.nth(i)
        link_loc = it.locator(link_selector) if link_selector else it.locator("a")
        text = ""
        href = ""
        try:
            if link_loc and link_loc.count() > 0:
                first = link_loc.first
                href = first.get_attribute("href") or ""
                text = first.inner_text() or ""
            else:
                text = it.inner_text() or ""
        except Exception:
            pass
        text = clean_text(text)
        if href:
            href = href.strip()
        if not text and not href:
            continue
        out.append({"text": text, "href": href})
    return out
