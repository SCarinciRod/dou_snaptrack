#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from dou_utils.services.cascade_executor import (
    CascadeExecutor,
    CascadeConfig
)

try:
    from dou_utils.log_utils import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)

logger = get_logger(__name__)


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_plan(path: str | Path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Plan não encontrado: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def parse_args():
    ap = argparse.ArgumentParser(description="Executa cascade (plan -> resultados).")
    ap.add_argument("--plan", required=True, help="Arquivo JSON do plan.")
    ap.add_argument("--out", required=True, help="Arquivo de saída (cascade JSON).")

    ap.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--slow-mo", type=int, default=0)

    ap.add_argument("--n1-index", type=int, default=0)
    ap.add_argument("--n2-index", type=int, default=1)
    ap.add_argument("--n3-index", type=int)

    ap.add_argument("--results-root")
    ap.add_argument("--item-selector", default="article, li, .resultado, .item")
    ap.add_argument("--link-selector")

    ap.add_argument("--delay-ms", type=int, default=600)
    ap.add_argument("--wait-after-n1", type=int, default=500)
    ap.add_argument("--wait-after-n2", type=int, default=500)
    ap.add_argument("--per-combo-timeout", type=int, default=15000)
    ap.add_argument("--select-ready-timeout", type=int, default=30000)

    ap.add_argument("--submit-selector", help="CSS do botão de pesquisar/submit (opcional)")
    ap.add_argument("--submit-wait", type=int, default=800, help="Delay após submit (ms)")

    ap.add_argument("--max-items-per-combo", type=int)
    ap.add_argument("--limit-combos", type=int)

    ap.add_argument("--stop-on-error", action="store_true")

    ap.add_argument("--dynamic-n2-chunk", type=int)
    ap.add_argument("--no-dynamic-cache", action="store_true")

    ap.add_argument("--sample-size", type=int, default=3)

    ap.add_argument("--inspect-selects", action="store_true", help="Apenas inspeciona os selects e sai")

    ap.add_argument("--debug", action="store_true")

    return ap.parse_args()


def main():
    args = parse_args()
    plan = read_plan(args.plan)

    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug ligado.")

    cfg = CascadeConfig(
        select_strategy="by_index",
        n1_index=args.n1_index,
        n2_index=args.n2_index,
        n3_index=args.n3_index,
        delay_after_select_ms=args.delay_ms,
        wait_after_n1_ms=args.wait_after_n1,
        wait_after_n2_ms=args.wait_after_n2,
        per_combo_timeout_ms=args.per_combo_timeout,
        select_ready_timeout_ms=args.select_ready_timeout,
        results_root_selector=args.results_root,
        result_item_selector=args.item_selector,
        result_link_selector=args.link_selector,
        max_items_per_combo=args.max_items_per_combo,
        dynamic_n2_chunk_limit=args.dynamic_n2_chunk,
        dynamic_reuse_cache=not args.no_dynamic_cache,
        stop_on_error=args.stop_on_error,
        sample_size=args.sample_size,
        submit_selector=args.submit_selector,
        submit_wait_ms=args.submit_wait
    )

    from playwright.sync_api import sync_playwright

    url = plan.get("defaults", {}).get("baseUrl") or plan.get("defaults", {}).get("url")
    if not url:
        logger.warning("Plan não contém defaults.baseUrl/url - você precisará navegar manualmente depois.")
    with sync_playwright() as pw:
        browser_type = getattr(pw, args.browser)
        browser = browser_type.launch(
            headless=not args.headful,
            slow_mo=args.slow_mo if args.headful else 0
        )
        page = browser.new_page()
        if url:
            logger.info("Abrindo URL base: %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=90000)

        executor = CascadeExecutor(page.main_frame, cfg)

        if args.inspect_selects:
            data = executor.list_select_options([args.n1_index, args.n2_index] + ([args.n3_index] if args.n3_index is not None else []))
            print(json.dumps({"selects": data}, ensure_ascii=False, indent=2))
            browser.close()
            return

        result = executor.run(plan, limit=args.limit_combos)

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Cascade finalizado. Saída: %s", out_path)

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Falha na execução do cascade.")
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)
