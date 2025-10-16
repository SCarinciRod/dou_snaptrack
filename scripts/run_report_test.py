from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from dou_snaptrack.cli.reporting import report_from_aggregated  # type: ignore

    # Garantir deep-mode ligado (não offline)
    os.environ["DOU_OFFLINE_REPORT"] = "0"

    # Arquivo agregado do plano "testeLuiza" (15-10-2025)
    in_file = repo_root / "resultados" / "15-10-2025" / "testeLuiza_DO1_15-10-2025.json"
    if not in_file.exists():
        raise SystemExit(f"Input not found: {in_file}")

    out_md = repo_root / "resultados" / "15-10-2025" / "testeLuiza_DO1_15-10-2025_deep.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)

    # Gerar boletim em Markdown com resumos (7 linhas, modo center), deep-mode estrito (timeout 15s)
    report_from_aggregated(
        files=[str(in_file)],
        kind="md",
        out_path=str(out_md),
        date_label="15-10-2025",
        secao_label="DO1",
        summary_lines=7,
        summary_mode="center",
        summary_keywords=None,
        order_desc_by_date=True,
        enrich_missing=True,
        fetch_parallel=8,
        fetch_timeout_sec=30,
    )
    print(f"[DONE] Written: {out_md}")


if __name__ == "__main__":
    main()
