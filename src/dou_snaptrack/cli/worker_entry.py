from __future__ import annotations

import argparse
import json
import sys
import asyncio
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dou_snaptrack worker from payload JSON")
    parser.add_argument("--payload", required=True, help="Path to payload JSON file")
    parser.add_argument("--out", required=True, help="Path to write result JSON")
    args = parser.parse_args()

    # Ensure Windows has proper event loop policy for Playwright
    if sys.platform.startswith("win"):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass

    payload_path = Path(args.payload)
    out_path = Path(args.out)
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[worker_entry] Falha ao ler payload: {e}")
        return 2

    try:
        from dou_snaptrack.cli.batch import _worker_process  # type: ignore
        result = _worker_process(payload)
    except Exception as e:
        print(f"[worker_entry] Execução do worker falhou: {e}")
        result = {"ok": 0, "fail": len(payload.get("indices", [])), "items_total": 0, "outputs": [], "error": str(e)}

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[worker_entry] Falha ao escrever resultado: {e}")
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
