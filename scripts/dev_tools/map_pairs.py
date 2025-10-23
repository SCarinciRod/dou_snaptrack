from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..mappers.pairs_mapper import map_pairs
from ..utils.browser import build_dou_url, fmt_date, goto, launch_browser, new_context, try_visualizar_em_lista


def main():
    ap = argparse.ArgumentParser(description="Mapeamento N1->N2 (modular)")
    ap.add_argument("--secao", required=True)
    ap.add_argument("--data", required=True, help="DD-MM-AAAA")
    ap.add_argument("--out", required=True)

    ap.add_argument("--label1", help="Regex do rótulo do N1 (ex.: 'Órgão|Orgao')")
    ap.add_argument("--label2", help="Regex do rótulo do N2 (ex.: 'Secretaria|Unidade|Subordinad')")

    ap.add_argument("--select1", help="Regex para filtrar rótulos de N1")
    ap.add_argument("--pick1", help="Lista fixa (vírgula) de rótulos de N1")
    ap.add_argument("--limit1", type=int)

    ap.add_argument("--select2", help="Regex para filtrar rótulos de N2")
    ap.add_argument("--pick2", help="Lista fixa (vírgula) de rótulos de N2")
    ap.add_argument("--limit2-per-n1", type=int, dest="limit2_per_n1")

    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--slowmo", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = fmt_date(args.data)
    url = build_dou_url(data, args.secao)

    p, browser = launch_browser(headful=args.headful, slowmo=args.slowmo)
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        goto(page, url)
        try_visualizar_em_lista(page)

        data_out = map_pairs(
            page, args.secao, data,
            args.label1, args.label2,
            args.select1, args.pick1, args.limit1,
            args.select2, args.pick2, args.limit2_per_n1,
            args.verbose
        )
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(data_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Pairs salvos em: {args.out} (N1 mapeados={len(data_out.get('n1_options', []))})")
    finally:
        try: browser.close()
        except Exception: pass
        try: p.stop()
        except Exception: pass

if __name__ == "__main__":
    main()
