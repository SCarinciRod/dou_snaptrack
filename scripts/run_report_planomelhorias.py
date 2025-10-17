from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from dou_snaptrack.cli.reporting import report_from_aggregated  # type: ignore

    # Aggregated input (allow override via argv)
    if len(sys.argv) > 1:
        in_file = Path(sys.argv[1])
        if not in_file.is_absolute():
            in_file = (repo_root / in_file).resolve()
    else:
        in_file = (repo_root / "resultados" / "17-10-2025" / "planomelhorias_17-10-2025_DO1_17-10-2025.json").resolve()

    if not in_file.exists():
        print(f"[ERR] Input not found: {in_file}")
        return 2

    out_md = in_file.parent / "planomelhorias_DO1_17-10-2025_fallback.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    # Ensure deep-mode on (not offline)
    os.environ["DOU_OFFLINE_REPORT"] = "0"

    # Generate bulletin in Markdown with summaries (4 lines, lead mode)
    report_from_aggregated(
        files=[str(in_file)],
        kind="md",
        out_path=str(out_md),
        date_label="17-10-2025",
        secao_label="DO1",
        summary_lines=4,
        summary_mode="lead",
        summary_keywords=None,
        order_desc_by_date=True,
        enrich_missing=True,
        fetch_parallel=8,
        fetch_timeout_sec=30,
    )
    print(f"[DONE] Written: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
