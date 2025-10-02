from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

from ..utils.text import normalize_text
from ..utils.browser import fmt_date
from ..mappers.pairs_mapper import filter_opts as _filter_opts


def _best_key_for_option(opt: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    if opt.get("value") not in (None, ""):
        return ("value", str(opt["value"]))
    if opt.get("dataValue") not in (None, ""):
        return ("dataValue", str(opt["dataValue"]))
    if opt.get("id"):
        return ("id", opt["id"])  # type: ignore[return-value]
    if opt.get("dataId"):
        return ("dataId", opt["dataId"])  # type: ignore[return-value]
    if opt.get("dataIndex") not in (None, ""):
        return ("dataIndex", str(opt["dataIndex"]))
    return ("text", (opt.get("text") or "").strip())


def _build_keys(opts: List[Dict[str, Any]], key_type: str) -> List[str]:
    keys: List[str] = []
    for o in opts:
        if key_type == "text":
            t = (o.get("text") or "").strip()
            if t:
                keys.append(t)
        elif key_type == "value":
            v = o.get("value")
            if v not in (None, ""):
                keys.append(str(v))
        elif key_type == "dataValue":
            dv = o.get("dataValue")
            if dv not in (None, ""):
                keys.append(str(dv))
        elif key_type == "dataIndex":
            di = o.get("dataIndex")
            if di not in (None, ""):
                keys.append(str(di))
    seen = set(); out: List[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k); out.append(k)
    return out


def build_plan_from_pairs(pairs_file: str, args) -> Dict[str, Any]:
    pf = Path(pairs_file)
    data_pairs = json.loads(pf.read_text(encoding="utf-8"))

    data = data_pairs.get("date") or fmt_date(None)
    secao = data_pairs.get("secao") or getattr(args, "secao", "DO1")
    n1_groups = data_pairs.get("n1_options") or []

    def _key_norm(o: Dict[str, Any]) -> str:
        return normalize_text(o.get("text") or "")

    # 1) filtrar N1
    n1_all = [ (grp.get("n1") or {}) for grp in n1_groups ]
    n1_filtered = _filter_opts(n1_all, getattr(args, "select1", None), getattr(args, "pick1", None), getattr(args, "limit1", None))

    # lookup N2 por N1 normalizado
    map_n1_to_n2: Dict[str, List[Dict[str, Any]]] = { _key_norm(grp.get("n1") or {}): (grp.get("n2_options") or []) for grp in n1_groups }

    combos: List[Dict[str, Any]] = []
    limit2_per_n1 = getattr(args, "limit2_per_n1", None)
    k1_def = getattr(args, "key1_type_default", None)
    k2_def = getattr(args, "key2_type_default", None)

    for o1 in n1_filtered:
        n2_base = map_n1_to_n2.get(_key_norm(o1), [])
        n2_filtered = _filter_opts(n2_base, getattr(args, "select2", None), getattr(args, "pick2", None), limit2_per_n1)

        if k1_def:
            if k1_def == "text":
                k1_type, k1_value = "text", (o1.get("text") or "").strip()
            elif k1_def == "value":
                k1_type, k1_value = ("value", str(o1.get("value"))) if o1.get("value") not in (None, "") else ("text", (o1.get("text") or "").strip())
            elif k1_def == "dataValue":
                dv = o1.get("dataValue"); k1_type, k1_value = ("dataValue", str(dv)) if dv not in (None, "") else ("text", (o1.get("text") or "").strip())
            elif k1_def == "dataIndex":
                di = o1.get("dataIndex"); k1_type, k1_value = ("dataIndex", str(di)) if di not in (None, "") else ("text", (o1.get("text") or "").strip())
            else:
                k1_type, k1_value = _best_key_for_option(o1)
        else:
            k1_type, k1_value = _best_key_for_option(o1)

        for o2 in n2_filtered:
            if k2_def:
                if k2_def == "text":
                    k2_type, k2_value = "text", (o2.get("text") or "").strip()
                elif k2_def == "value":
                    k2_type, k2_value = ("value", str(o2.get("value"))) if o2.get("value") not in (None, "") else ("text", (o2.get("text") or "").strip())
                elif k2_def == "dataValue":
                    dv2 = o2.get("dataValue"); k2_type, k2_value = ("dataValue", str(dv2)) if dv2 not in (None, "") else ("text", (o2.get("text") or "").strip())
                elif k2_def == "dataIndex":
                    di2 = o2.get("dataIndex"); k2_type, k2_value = ("dataIndex", str(di2)) if di2 not in (None, "") else ("text", (o2.get("text") or "").strip())
                else:
                    k2_type, k2_value = _best_key_for_option(o2)
            else:
                k2_type, k2_value = _best_key_for_option(o2)

            combos.append({
                "key1_type": k1_type, "key1": k1_value,
                "key2_type": k2_type, "key2": k2_value,
                "key3_type": None, "key3": None,
                "label1": args.label1 or "", "label2": args.label2 or "", "label3": "",
            })

    maxc = getattr(args, "max_combos", None)
    if isinstance(maxc, int) and maxc > 0 and len(combos) > maxc:
        combos = combos[:maxc]

    if not combos:
        raise RuntimeError("Nenhum combo válido foi gerado a partir dos pares (verifique filtros/limites).")

    cfg: Dict[str, Any] = {
        "data": args.data or data,
        "secaoDefault": args.secao or secao or "DO1",
        "defaults": {
            "scrape_detail": bool(getattr(args, "scrape_detail", False)),
            "fallback_date_if_missing": bool(getattr(args, "fallback_date_if_missing", False)),
            "max_links": int(getattr(args, "max_links", 30)),
            "max_scrolls": int(getattr(args, "max_scrolls", 40)),
            "scroll_pause_ms": int(getattr(args, "scroll_pause_ms", 350)),
            "stable_rounds": int(getattr(args, "stable_rounds", 3)),
            "label1": args.label1, "label2": args.label2, "label3": None,
            "debug_dump": bool(getattr(args, "debug_dump", False)),
            "summary_lines": int(getattr(args, "summary_lines", 3)) if getattr(args, "summary_lines", None) else None,
            "summary_mode": getattr(args, "summary_mode", "center"),
        },
        "combos": combos,
        "output": {"pattern": "{secao}_{date}_{idx}.json", "report": "batch_report.json"},
    }

    if getattr(args, "query", None):
        cfg["topics"] = [{"name": "Topic", "query": args.query}]
    if getattr(args, "state_file", None):
        cfg["state_file"] = args.state_file
    if getattr(args, "bulletin", None):
        ext = "docx" if args.bulletin == "docx" else args.bulletin
        out_b = args.bulletin_out or f"boletim_{{secao}}_{{date}}_{{idx}}.{ext}"
        cfg["output"]["bulletin"] = out_b
        cfg["defaults"]["bulletin"] = args.bulletin
        cfg["defaults"]["bulletin_out"] = out_b

    # garantir combos sem N3
    for c in combos:
        c["key3_type"] = None
        c["key3"] = None

    return cfg
