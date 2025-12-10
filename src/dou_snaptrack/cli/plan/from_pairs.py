from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...mappers.pairs_mapper import filter_opts as _filter_opts
from ...utils.browser import fmt_date
from ...utils.text import normalize_text


def _best_key_for_option(opt: dict[str, Any]) -> tuple[str, str | None]:
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


def _build_keys(opts: list[dict[str, Any]], key_type: str) -> list[str]:
    keys: list[str] = []
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
    seen = set()
    out: list[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def build_plan_from_pairs(pairs_file: str, args) -> dict[str, Any]:
    """Build a plan configuration from a pairs file.

    Reads N1-N2 pairs from a JSON file, filters them according to args,
    and generates a plan configuration with combos.
    """
    from .from_pairs_helpers import build_config_from_pairs, create_combo_from_pair

    # Load pairs data
    pf = Path(pairs_file)
    data_pairs = json.loads(pf.read_text(encoding="utf-8"))

    data = data_pairs.get("date") or fmt_date(None)
    secao = data_pairs.get("secao") or getattr(args, "secao", "DO1")
    n1_groups = data_pairs.get("n1_options") or []

    def _key_norm(o: dict[str, Any]) -> str:
        return normalize_text(o.get("text") or "")

    # Filter N1 options
    n1_all = [(grp.get("n1") or {}) for grp in n1_groups]
    n1_filtered = _filter_opts(n1_all, getattr(args, "select1", None), getattr(args, "pick1", None), getattr(args, "limit1", None))

    # Build N1 -> N2 lookup map
    map_n1_to_n2: dict[str, list[dict[str, Any]]] = {
        _key_norm(grp.get("n1") or {}): (grp.get("n2_options") or []) for grp in n1_groups
    }

    # Generate combos from filtered N1 and N2 options
    combos: list[dict[str, Any]] = []
    limit2_per_n1 = getattr(args, "limit2_per_n1", None)
    k1_def = getattr(args, "key1_type_default", None)
    k2_def = getattr(args, "key2_type_default", None)

    for o1 in n1_filtered:
        n2_base = map_n1_to_n2.get(_key_norm(o1), [])
        n2_filtered = _filter_opts(n2_base, getattr(args, "select2", None), getattr(args, "pick2", None), limit2_per_n1)

        for o2 in n2_filtered:
            combos.append(create_combo_from_pair(o1, o2, k1_def, k2_def, args))

    # Apply max combos limit
    maxc = getattr(args, "max_combos", None)
    if isinstance(maxc, int) and maxc > 0 and len(combos) > maxc:
        combos = combos[:maxc]

    if not combos:
        raise RuntimeError("Nenhum combo válido foi gerado a partir dos pares (verifique filtros/limites).")

    # Build and return configuration
    return build_config_from_pairs(args, data, secao, combos)
