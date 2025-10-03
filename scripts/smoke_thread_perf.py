from __future__ import annotations
import os, json, time
from pathlib import Path
from types import SimpleNamespace
from datetime import date as _date

# Ensure src on path
import sys
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dou_snaptrack.cli.batch import run_batch
from dou_snaptrack.cli.summary_config import SummaryConfig
from playwright.sync_api import sync_playwright  # type: ignore


def build_smoke_plan(date_str: str) -> dict:
    # 5 basic combos, low scroll, no details, summary off for speed
    defaults = {
        "scrape_detail": False,
        "max_scrolls": 8,
        "scroll_pause_ms": 120,
        "stable_rounds": 1,
        "summary_lines": 0,
        "summary_mode": "center",
    }
    combos = []
    base_pairs = [
        ("Presidência da República", "GABINETE"),
        ("Ministério da Saúde", "GABINETE"),
        ("Ministério da Educação", "GABINETE"),
        ("Ministério da Economia", "GABINETE"),
        ("Ministério da Justiça", "GABINETE"),
    ]
    for k1, k2 in base_pairs:
        combos.append({
            "key1_type": "text", "key1": k1,
            "key2_type": "text", "key2": k2,
            "label1": "", "label2": "", "label3": "",
        })
    return {
        "data": date_str,
        "secaoDefault": "DO1",
        "defaults": defaults,
        "combos": combos,
        "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"}
    }


def main(parallel: int = 5) -> None:
    # Force thread pool for Streamlit-like context
    os.environ.setdefault("DOU_POOL", "thread")
    os.environ.setdefault("DOU_PREFER_EDGE", "1")
    os.environ.setdefault("DOU_FAST_MODE", "1")
    os.environ.setdefault("DOU_BUCKET_SIZE_MIN", "2")
    today = _date.today().strftime("%d-%m-%Y")
    out_dir = Path("resultados") / f"{today}_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_smoke_plan(today)
    cfg_path = out_dir / "_smoke_cfg.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    log_path = out_dir / "batch_run.log"

    print(f"[SMOKE] writing plan to {cfg_path}")
    print(f"[SMOKE] out_dir={out_dir} parallel={parallel} pool=thread")

    t0 = time.perf_counter()
    with sync_playwright() as p:
        args = SimpleNamespace(
            config=str(cfg_path),
            out_dir=str(out_dir),
            headful=False,
            slowmo=0,
            state_file=None,
            reuse_page=True,
            parallel=int(parallel),
            log_file=str(log_path),
        )
        run_batch(p, args, SummaryConfig(lines=0, mode="center", keywords=None))
    elapsed = time.perf_counter() - t0
    print(f"[SMOKE] elapsed={elapsed:.1f}s for {parallel} jobs; target=40s")


if __name__ == "__main__":
    try:
        par = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    except Exception:
        par = 5
    main(parallel=par)
