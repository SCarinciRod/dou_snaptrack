from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dou_utils.content_fetcher import Fetcher


def analyze_file(fp: Path, limit: int = 0) -> List[Dict[str, Any]]:
    data = json.loads(fp.read_text(encoding="utf-8"))
    items = data.get("itens", []) or []
    if limit and limit > 0:
        items = items[:limit]
    out: List[Dict[str, Any]] = []
    f = Fetcher(timeout_sec=20, force_refresh=False, use_browser_if_short=True, short_len_threshold=800, browser_timeout_sec=30)

    for it in items:
        url = it.get("detail_url") or it.get("link") or ""
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://www.in.gov.br{url}"
        method = ""
        l_html = 0
        l_browser_text = 0
        l_browser_html = 0
        try:
            html = f.fetch_html(url)
            txt = f.extract_text_from_html(html)
            l_html = len(txt or "")
        except Exception:
            l_html = 0
        text_b = ""
        if l_html < f.short_len_threshold:
            try:
                text_b = f.fetch_text_browser(url)
                l_browser_text = len(text_b or "")
            except Exception:
                l_browser_text = 0
        if l_html < f.short_len_threshold and l_browser_text < f.short_len_threshold:
            try:
                html_b = f.fetch_html_browser(url)
                txt_b = f.extract_text_from_html(html_b)
                l_browser_html = len(txt_b or "")
            except Exception:
                l_browser_html = 0
        if l_html >= 80:
            method = "html"
        elif l_browser_text >= 80:
            method = "browser_text"
        elif l_browser_html >= 80:
            method = "browser_html"
        else:
            method = "none"
        out.append({
            "titulo": it.get("title_friendly") or it.get("titulo") or "",
            "url": url,
            "orgao": it.get("orgao") or "",
            "len_html": l_html,
            "len_browser_text": l_browser_text,
            "len_browser_html": l_browser_html,
            "method": method,
        })
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diag_summary_sources.py <aggregated.json> [limit]")
        return 1
    fp = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if not fp.exists():
        print(f"File not found: {fp}")
        return 1
    res = analyze_file(fp, limit)
    total = len(res)
    buckets = {}
    for r in res:
        buckets[r["method"]] = buckets.get(r["method"], 0) + 1
    print(f"Analyzed {total} items. Methods: {buckets}")
    for r in res:
        print(f"- [{r['method']}] {r['orgao']} | {r['titulo']} | html={r['len_html']} btxt={r['len_browser_text']} bhtml={r['len_browser_html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
