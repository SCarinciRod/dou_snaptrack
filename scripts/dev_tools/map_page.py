from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from ..mappers.page_mapper import map_dropdowns, map_elements_by_category
from ..utils.browser import build_dou_url, fmt_date, goto, launch_browser, new_context, try_visualizar_em_lista
from ..utils.dom import find_best_frame


def dump_debug(page, prefix="debug_map"):
    try: page.screenshot(path=f"{prefix}.png", full_page=True)
    except Exception: pass
    try:
        html = page.content()
        Path(f"{prefix}.html").write_text(html, encoding="utf-8")
    except Exception: pass

def main():
    ap = argparse.ArgumentParser(description="Scanner de página (modular)")
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

    url = build_dou_url(fmt_date(args.data), args.secao) if args.dou else args.url

    p, browser = launch_browser(headful=args.headful, slowmo=args.slowmo)
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        goto(page, url)
        if args.dou:
            try_visualizar_em_lista(page)

        frame = find_best_frame(context)

        dropdowns = map_dropdowns(frame, open_combos=args.open_combos, max_per_type=args.max_per_type)
        categories = map_elements_by_category(frame, max_per_type=args.max_per_type)

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
        print(f"[OK] Mapa salvo em: {args.out}")
        if args.debug_dump:
            dump_debug(page, "debug_map")
    finally:
        try: browser.close()
        except Exception: pass
        try: p.stop()
        except Exception: pass

if __name__ == "__main__":
    main()
