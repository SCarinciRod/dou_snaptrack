from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DOU bulletin from aggregated JSON files")
    parser.add_argument("--kind", required=True, choices=["docx", "md", "html"], help="Output format")
    parser.add_argument("--out", required=True, help="Output path")
    parser.add_argument("--files", nargs="+", required=True, help="Aggregated JSON files")
    parser.add_argument("--date", default="", help="Date label")
    parser.add_argument("--secao", default="", help="Section label")
    parser.add_argument("--summary-lines", type=int, default=7)
    parser.add_argument("--summary-mode", default="center")
    parser.add_argument("--fetch-parallel", type=int, default=8)
    parser.add_argument("--fetch-timeout-sec", type=int, default=30)
    parser.add_argument("--fetch-force-refresh", action="store_true", default=True)
    parser.add_argument("--fetch-browser-fallback", action="store_true", default=False)
    parser.add_argument("--short-len-threshold", type=int, default=800)
    parser.add_argument("--order-desc-by-date", action="store_true", default=True)
    parser.add_argument("--offline", action="store_true", default=False, help="Disable enrichment (offline)")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Offline mode disables deep enrichment
    if args.offline:
        os.environ["DOU_OFFLINE_REPORT"] = "1"

    try:
        from .reporter import report_from_aggregated

        report_from_aggregated(
            list(args.files),
            args.kind,
            str(out_path),
            date_label=args.date,
            secao_label=args.secao,
            summary_lines=int(args.summary_lines),
            summary_mode=str(args.summary_mode),
            summary_keywords=None,
            order_desc_by_date=bool(args.order_desc_by_date),
            enrich_missing=True,
            fetch_parallel=int(args.fetch_parallel),
            fetch_timeout_sec=int(args.fetch_timeout_sec),
            fetch_force_refresh=bool(args.fetch_force_refresh),
            fetch_browser_fallback=bool(args.fetch_browser_fallback),
            short_len_threshold=int(args.short_len_threshold),
        )
    except Exception as e:
        # Emit structured error for callers
        payload = {"ok": False, "error": str(e)}
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    payload = {"ok": True, "out": str(out_path)}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
