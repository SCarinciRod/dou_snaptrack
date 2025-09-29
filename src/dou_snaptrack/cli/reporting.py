from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
from ..adapters.utils import generate_bulletin as _generate_bulletin


def consolidate_and_report(in_dir: str, kind: str, out_path: str, date_label: str = "", secao_label: str = "") -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    agg = []
    for f in sorted(Path(in_dir).glob("*.json")):
        try:
            data = __import__('json').loads(f.read_text(encoding="utf-8"))
            agg.extend(data.get("itens", []))
        except Exception:
            pass

    result: Dict[str, Any] = {
        "data": date_label or "",
        "secao": secao_label or "",
        "total": len(agg),
        "itens": agg,
    }
    _generate_bulletin(result, out_path, kind=kind)
    print(f"[OK] Boletim consolidado gerado: {out_path}")
