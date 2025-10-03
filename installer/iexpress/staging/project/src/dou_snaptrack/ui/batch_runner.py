from __future__ import annotations

import json
import os
import sys
import asyncio
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict


def run_batch_with_cfg(cfg_path: Path, parallel: int, fast_mode: bool = False, prefer_edge: bool = True) -> Dict[str, Any]:
    """Headless-safe wrapper to execute the batch without importing Streamlit UI.

    Returns the loaded report dict or {} if something failed.
    """
    try:
        # Ensure Windows has the proper event loop policy for Playwright subprocesses
        if sys.platform.startswith("win"):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception:
                pass

        # Lazy imports to keep this module light and Streamlit-free
        from playwright.sync_api import sync_playwright  # type: ignore
        from dou_snaptrack.cli.batch import run_batch
        from dou_snaptrack.cli.summary_config import SummaryConfig

        # Determine output dir based on plan date
        try:
            raw_cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
            plan_date = (raw_cfg.get("data") or "").strip() or _date.today().strftime("%d-%m-%Y")
        except Exception:
            raw_cfg = {}
            plan_date = _date.today().strftime("%d-%m-%Y")

        out_dir_path = Path("resultados") / plan_date
        out_dir_path.mkdir(parents=True, exist_ok=True)
        out_dir_str = str(out_dir_path)

        # UI policy: link capture only (no details, no bulletin) to keep fast and safe
        cfg_obj = json.loads(json.dumps(raw_cfg)) if raw_cfg else {}
        dfl = dict(cfg_obj.get("defaults") or {})
        dfl.pop("bulletin", None)
        dfl.pop("bulletin_out", None)
        dfl["scrape_detail"] = False
        dfl["detail_parallel"] = 1
        cfg_obj["defaults"] = dfl
        for key in ("jobs", "combos"):
            seq = cfg_obj.get(key)
            if isinstance(seq, list):
                for j in seq:
                    if isinstance(j, dict):
                        j.pop("bulletin", None)
                        j.pop("bulletin_out", None)
                        j["scrape_detail"] = False
                        j["detail_parallel"] = 1

        tmp_cfg_path = out_dir_path / "_run_cfg.json"
        tmp_cfg_path.write_text(json.dumps(cfg_obj, ensure_ascii=False, indent=2), encoding="utf-8")

        # Environment for workers
        if prefer_edge:
            os.environ["DOU_PREFER_EDGE"] = "1"
        if fast_mode:
            os.environ["DOU_FAST_MODE"] = "1"

        # Ensure PYTHONPATH includes src so workers can import dou_snaptrack on Windows spawn
        src_root = str(Path(__file__).resolve().parents[2])
        cur_pp = os.environ.get("PYTHONPATH") or ""
        if src_root not in (cur_pp.split(";") if os.name == "nt" else cur_pp.split(":")):
            os.environ["PYTHONPATH"] = f"{src_root}{';' if os.name == 'nt' else ':'}{cur_pp}" if cur_pp else src_root

        with sync_playwright() as p:
            from types import SimpleNamespace
            args = SimpleNamespace(
                config=str(tmp_cfg_path),
                out_dir=out_dir_str,
                headful=False,
                slowmo=0,
                state_file=None,
                reuse_page=True,
                parallel=int(parallel),
            )

            run_batch(p, args, SummaryConfig(lines=4, mode="center", keywords=None))

        rep_path = out_dir_path / "batch_report.json"
        return json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
    except Exception as e:
        # Print instead of Streamlit UI feedback to keep this headless-safe
        print(f"[run_batch_with_cfg] Falha: {type(e).__name__}: {e}")
        return {}
