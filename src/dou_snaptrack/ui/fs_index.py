"""Filesystem index helpers for Streamlit UI.

Goal: reduce UI jank by avoiding repeated directory scans and full JSON parsing
on every Streamlit rerun.

This module centralizes:
- listing plan files with lightweight metadata extraction
- listing day folders under resultados/
- indexing aggregated JSON files under a day folder

All public functions are cached with short TTLs; callers can pass a refresh token
(or rely on file mtimes) to invalidate.
"""

# ruff: noqa: I001

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

import streamlit as st


_PLAN_DATE_RE = re.compile(r"\"data\"\s*:\s*\"([^\"]*)\"")
_PLAN_SECAO_RE = re.compile(r"\"secaoDefault\"\s*:\s*\"([^\"]*)\"")
_PLAN_COMBO_KEY_BYTES = b'"key1_type"'


def _safe_stat_mtime_ns(p: Path) -> int:
    try:
        return p.stat().st_mtime_ns
    except Exception:
        return 0


def _read_plan_meta_streaming(p: Path) -> dict[str, Any] | None:
    try:
        size = p.stat().st_size
    except Exception:
        return None

    # Large plan: avoid full JSON load; scan bytes for combo markers and grab metadata from prefix.
    if size >= 256 * 1024:
        try:
            combos_count = 0
            prefix_text = ""

            with p.open("rb") as f:
                prefix = f.read(128 * 1024)
                try:
                    prefix_text = prefix.decode("utf-8", errors="ignore")
                except Exception:
                    prefix_text = ""

                buf = prefix
                combos_count += buf.count(_PLAN_COMBO_KEY_BYTES)
                tail = buf[-(len(_PLAN_COMBO_KEY_BYTES) - 1) :] if len(buf) >= len(_PLAN_COMBO_KEY_BYTES) else buf

                while True:
                    chunk = f.read(256 * 1024)
                    if not chunk:
                        break
                    buf = tail + chunk
                    combos_count += buf.count(_PLAN_COMBO_KEY_BYTES)
                    tail = buf[-(len(_PLAN_COMBO_KEY_BYTES) - 1) :]

            m_date = _PLAN_DATE_RE.search(prefix_text)
            m_sec = _PLAN_SECAO_RE.search(prefix_text)

            return {
                "path": str(p),
                "stem": p.stem,
                "combos": int(combos_count),
                "data": (m_date.group(1) if m_date else ""),
                "secao": (m_sec.group(1) if m_sec else ""),
                "size_kb": round(size / 1024, 1),
                "mtime_ns": _safe_stat_mtime_ns(p),
            }
        except Exception:
            return None

    # Small plan: full JSON parse is ok.
    try:
        import json

        data = json.loads(p.read_text(encoding="utf-8"))
        combos = data.get("combos", [])
        return {
            "path": str(p),
            "stem": p.stem,
            "combos": len(combos),
            "data": data.get("data", ""),
            "secao": data.get("secaoDefault", ""),
            "size_kb": round(size / 1024, 1),
            "mtime_ns": _safe_stat_mtime_ns(p),
        }
    except Exception:
        return None


@st.cache_data(ttl=10, show_spinner=False)
def list_plan_entries(plans_dir_str: str, refresh_token: float = 0.0) -> list[dict[str, Any]]:
    """List plan JSON files with lightweight metadata.

    Args:
        plans_dir_str: directory containing plan JSON files
        refresh_token: optional cache invalidation token
    """
    _ = refresh_token
    plans_dir = Path(plans_dir_str)
    if not plans_dir.exists():
        return []

    entries: list[dict[str, Any]] = []
    try:
        # Use scandir for speed on Windows.
        with os.scandir(plans_dir) as it:
            paths: list[Path] = []
            for e in it:
                if not e.is_file():
                    continue
                if not e.name.lower().endswith(".json"):
                    continue
                paths.append(Path(e.path))

        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in paths:
            meta = _read_plan_meta_streaming(p)
            if meta:
                entries.append(meta)
    except Exception:
        return entries

    return entries


@st.cache_data(ttl=5, show_spinner=False)
def list_result_days(results_root_str: str, refresh_token: float = 0.0) -> list[str]:
    """List day directory names under resultados/ (cached briefly)."""
    _ = refresh_token
    root = Path(results_root_str)
    try:
        day_dirs = [d for d in root.iterdir() if d.is_dir()]
    except Exception:
        return []
    return sorted((d.name for d in day_dirs), reverse=True)


@st.cache_data(ttl=5, show_spinner=False)
def index_aggregates_by_day(day_dir_str: str, refresh_token: float = 0.0) -> dict[str, list[str]]:
    """Index aggregated JSON file names by plan for a given resultados/<day> folder."""
    _ = refresh_token
    day_dir = Path(day_dir_str)
    idx: dict[str, list[str]] = {}
    try:
        for f in day_dir.glob("*_DO?_*.json"):
            name = f.name
            try:
                parts = name[:-5].split("_")
                if len(parts) < 3:
                    continue
                sec = parts[-2]
                date = parts[-1]
                plan = "_".join(parts[:-2])
                if not sec.upper().startswith("DO"):
                    continue
                if date != day_dir.name:
                    continue
            except Exception:
                continue
            idx.setdefault(plan, []).append(name)
    except Exception:
        return {}
    return idx
