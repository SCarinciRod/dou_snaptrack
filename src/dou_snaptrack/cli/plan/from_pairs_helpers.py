"""Helper functions for build_plan_from_pairs to reduce complexity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...utils.text import normalize_text


def determine_key_type_and_value(opt: dict[str, Any], key_type_default: str | None):
    """Determine the key type and value for an option based on default preference.
    
    Args:
        opt: Option dictionary with text, value, dataValue, dataIndex fields
        key_type_default: Preferred key type ("text", "value", "dataValue", "dataIndex", or None)
    
    Returns:
        Tuple of (key_type, key_value)
    """
    from .plan_live import _best_key_for_option
    
    if not key_type_default:
        return _best_key_for_option(opt)
    
    if key_type_default == "text":
        return "text", (opt.get("text") or "").strip()
    
    if key_type_default == "value":
        val = opt.get("value")
        if val not in (None, ""):
            return "value", str(val)
        return "text", (opt.get("text") or "").strip()
    
    if key_type_default == "dataValue":
        dv = opt.get("dataValue")
        if dv not in (None, ""):
            return "dataValue", str(dv)
        return "text", (opt.get("text") or "").strip()
    
    if key_type_default == "dataIndex":
        di = opt.get("dataIndex")
        if di not in (None, ""):
            return "dataIndex", str(di)
        return "text", (opt.get("text") or "").strip()
    
    # Default to best key
    return _best_key_for_option(opt)


def create_combo_from_pair(o1: dict[str, Any], o2: dict[str, Any], k1_def: str | None, k2_def: str | None, args) -> dict[str, Any]:
    """Create a combo dictionary from N1 and N2 options.
    
    Args:
        o1: N1 option dictionary
        o2: N2 option dictionary
        k1_def: Key type default for N1
        k2_def: Key type default for N2
        args: Command line arguments with labels
    
    Returns:
        Combo dictionary
    """
    k1_type, k1_value = determine_key_type_and_value(o1, k1_def)
    k2_type, k2_value = determine_key_type_and_value(o2, k2_def)
    
    return {
        "key1_type": k1_type,
        "key1": k1_value,
        "key2_type": k2_type,
        "key2": k2_value,
        "key3_type": None,
        "key3": None,
        "label1": args.label1 or "",
        "label2": args.label2 or "",
        "label3": "",
    }


def build_config_from_pairs(args, data: str, secao: str, combos: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the configuration dictionary from pairs data.
    
    Args:
        args: Command line arguments
        data: Date string
        secao: Section (DO1, DO2, DO3, etc.)
        combos: List of combo dictionaries
    
    Returns:
        Configuration dictionary
    """
    cfg: dict[str, Any] = {
        "data": args.data or data,
        "secaoDefault": args.secao or secao or "DO1",
        "defaults": {
            "scrape_detail": bool(getattr(args, "scrape_detail", False)),
            "fallback_date_if_missing": bool(getattr(args, "fallback_date_if_missing", False)),
            "max_links": int(getattr(args, "max_links", 30)),
            "max_scrolls": int(getattr(args, "max_scrolls", 30)),
            "scroll_pause_ms": int(getattr(args, "scroll_pause_ms", 250)),
            "stable_rounds": int(getattr(args, "stable_rounds", 2)),
            "label1": args.label1,
            "label2": args.label2,
            "label3": None,
            "debug_dump": bool(getattr(args, "debug_dump", False)),
            "summary_lines": int(getattr(args, "summary_lines", 3)) if getattr(args, "summary_lines", None) else None,
            "summary_mode": getattr(args, "summary_mode", "center"),
        },
        "combos": combos,
        "output": {"pattern": "{secao}_{date}_{idx}.json", "report": "batch_report.json"},
    }
    
    # Add optional topic query
    if getattr(args, "query", None):
        cfg["topics"] = [{"name": "Topic", "query": args.query}]
    
    # Add optional state file
    if getattr(args, "state_file", None):
        cfg["state_file"] = args.state_file
    
    # Add optional bulletin output
    if getattr(args, "bulletin", None):
        ext = "docx" if args.bulletin == "docx" else args.bulletin
        out_b = args.bulletin_out or f"boletim_{{secao}}_{{date}}_{{idx}}.{ext}"
        cfg["output"]["bulletin"] = out_b
        cfg["defaults"]["bulletin"] = args.bulletin
        cfg["defaults"]["bulletin_out"] = out_b
    
    # Ensure no N3 in combos
    for c in combos:
        c["key3_type"] = None
        c["key3"] = None
    
    return cfg
