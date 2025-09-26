"""
Service layer for dropdown mapping and N1->N2 pair expansion.

Enhancements:
- Label-based discovery of N1/N2 before index fallback
- Structured logging
- Filtering utilities (regex, pick list, limit)
- Schema-based output assembly (separated from CLI)
- Dedup + priority logic maintained, but encapsulated
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Iterable, Tuple

from ..selectors import DROPDOWN_ROOT_SELECTORS
from ..dropdown_utils import (
    open_dropdown,
    read_open_list_options,
    _is_select,
    _read_select_options
)
from ..element_utils import label_for_control, elem_common_info
from ..log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class DropdownRootMeta:
    kind: str
    selector: str
    index: int
    y: float
    x: float
    handle: Any
    id_attr: Optional[str] = None
    label: str = ""
    info: Dict[str, Any] = None


def _filter_options(options: List[Dict[str, Any]],
                    select_regex: Optional[str] = None,
                    pick_list: Optional[str] = None,
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
    out = options or []
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in out if pat.search((o.get("text") or ""))]
        except re.error as e:
            logger.warning("Invalid regex filter", extra={"regex": select_regex, "err": str(e)})
            out = []
    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]
    if limit and limit > 0:
        out = out[:limit]
    return out


def _remove_placeholders(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bad = {
        "selecionar organizacao principal", "selecionar organização principal",
        "selecionar organizacao subordinada", "selecionar organização subordinada",
        "selecionar tipo do ato", "selecionar", "todos"
    }
    out = []
    for o in options or []:
        text = (o.get("text") or "").strip().lower()
        if text in bad:
            continue
        out.append(o)
    return out


def _discover_roots(frame,
                    max_per_type: int = 50) -> List[DropdownRootMeta]:
    roots: List[Dict[str, Any]] = []
    seen = set()

    def _append(kind: str, sel: str, index: int, handle):
        try:
            box = handle.bounding_box()
            if not box:
                return
            key = (sel, index, round(box["y"], 2), round(box["x"], 2))
            if key in seen:
                return
            seen.add(key)
            roots.append({
                "kind": kind,
                "sel": sel,
                "index": index,
                "handle": handle,
                "y": box["y"],
                "x": box["x"]
            })
        except Exception:
            return

    # Role combobox
    cb = frame.get_by_role("combobox")
    try:
        m = cb.count()
    except Exception:
        m = 0
    for i in range(min(m, max_per_type)):
        _append("combobox", "role=combobox", i, cb.nth(i))

    # Native selects
    sel = frame.locator("select")
    try:
        n = sel.count()
    except Exception:
        n = 0
    for i in range(min(n, max_per_type)):
        _append("select", "select", i, sel.nth(i))

    # Generic selectors
    for selroot in DROPDOWN_ROOT_SELECTORS:
        loc = frame.locator(selroot)
        try:
            c = loc.count()
        except Exception:
            c = 0
        for i in range(min(c, max_per_type)):
            _append("unknown", selroot, i, loc.nth(i))

    enriched: List[DropdownRootMeta] = []
    for r in roots:
        h = r["handle"]
        try:
            el_id = h.get_attribute("id")
        except Exception:
            el_id = None
        try:
            lab = label_for_control(frame, h)
        except Exception:
            lab = ""
        info = {}
        try:
            info = elem_common_info(frame, h)
        except Exception:
            pass
        label_final = lab or info.get("attrs", {}).get("aria-label", "") or ""
        enriched.append(DropdownRootMeta(
            kind=r["kind"],
            selector=r["sel"],
            index=r["index"],
            y=r["y"],
            x=r["x"],
            handle=h,
            id_attr=el_id,
            label=label_final,
            info=info
        ))
    return _dedup_roots(enriched)


def _dedup_roots(roots: List[DropdownRootMeta]) -> List[DropdownRootMeta]:
    def _priority(kind: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)
    chosen = {}
    for r in roots:
        if r.id_attr:
            k = ("id", r.id_attr)
        else:
            k = ("pos", round(r.y, 1), round(r.x, 1), r.selector)
        best = chosen.get(k)
        if not best or _priority(r.kind) > _priority(best.kind):
            chosen[k] = r
    out = list(chosen.values())
    out.sort(key=lambda rr: (rr.y, rr.x))
    return out


def _resolve_n_handle(frame, candidates: List[DropdownRootMeta],
                      label_regex: Optional[str], fallback_index: int) -> Optional[DropdownRootMeta]:
    if label_regex:
        try:
            pat = re.compile(label_regex, re.I)
            labeled = [c for c in candidates if c.label and pat.search(c.label)]
            if labeled:
                logger.info("Matched dropdown by label", extra={"regex": label_regex, "count": len(labeled)})
                return labeled[0]
        except re.error as e:
            logger.warning("Invalid label regex", extra={"regex": label_regex, "err": str(e)})
    if candidates:
        if fallback_index < len(candidates):
            return candidates[fallback_index]
        return candidates[0]
    return None


class DropdownMapperService:
    """
    Encapsulates dropdown discovery, mapping, and N1->N2 expansion.
    """

    def __init__(self, frame):
        self.frame = frame

    def map_all(self, open_combos: bool) -> List[Dict[str, Any]]:
        roots = _discover_roots(self.frame)
        results = []
        for r in roots:
            meta = {
                "kind": r.kind,
                "rootSelector": r.selector,
                "index": r.index,
                "label": r.label,
                "info": r.info,
                "options": []
            }
            try:
                if _is_select(r.handle):
                    meta["options"] = _read_select_options(r.handle)
                elif open_combos:
                    if open_dropdown(self.frame, r.handle):
                        meta["options"] = read_open_list_options(self.frame)
            except Exception as e:
                logger.debug("Failed extracting options", extra={"selector": r.selector, "err": str(e)})
            results.append(meta)
        return results

    def map_pairs(self,
                  label1_regex: Optional[str],
                  label2_regex: Optional[str],
                  select1_regex: Optional[str],
                  pick1_list: Optional[str],
                  limit1: Optional[int],
                  select2_regex: Optional[str],
                  pick2_list: Optional[str],
                  limit2: Optional[int],
                  delay_ms: int = 500) -> Dict[str, Any]:
        """
        Map N1->N2 based on first two matched dropdowns by label or fallback order.
        """
        roots = _discover_roots(self.frame)
        if not roots or len(roots) < 2:
            return {"pairs": [], "warning": "Less than two dropdown-like controls found."}

        n1_meta = _resolve_n_handle(self.frame, roots, label1_regex, 0)
        n2_meta = _resolve_n_handle(self.frame, roots, label2_regex, 1 if n1_meta != roots[1] else 0)

        if not n1_meta or not n2_meta:
            return {"pairs": [], "warning": "Could not resolve N1 / N2 controls."}

        # Initial options for N1
        if _is_select(n1_meta.handle):
            n1_options = _read_select_options(n1_meta.handle)
        else:
            open_dropdown(self.frame, n1_meta.handle)
            n1_options = read_open_list_options(self.frame)

        n1_options = _remove_placeholders(n1_options)
        n1_filtered = _filter_options(n1_options, select1_regex, pick1_list, limit1)

        pairs = []
        page = self.frame.page
        for o1 in n1_filtered:
            # Select option in N1
            try:
                if _is_select(n1_meta.handle):
                    n1_meta.handle.select_option(label=o1.get("text"))
                else:
                    # For non-select, open and click the matching entry
                    open_dropdown(self.frame, n1_meta.handle)
                    opts = read_open_list_options(self.frame)
                    for opt in opts:
                        if opt.get("text") == o1.get("text"):
                            # Attempt click
                            try:
                                loc = self.frame.get_by_text(o1.get("text"), exact=True)
                                loc.first.click()
                            except Exception:
                                pass
                            break
            except Exception as e:
                logger.debug("Failed selecting N1 option", extra={"opt": o1.get("text"), "err": str(e)})

            # Wait a bit for N2 to refresh
            page.wait_for_timeout(delay_ms)

            # Read N2
            if _is_select(n2_meta.handle):
                o2_all = _read_select_options(n2_meta.handle)
            else:
                open_dropdown(self.frame, n2_meta.handle)
                o2_all = read_open_list_options(self.frame)
            o2_all = _remove_placeholders(o2_all)
            o2_filtered = _filter_options(o2_all, select2_regex, pick2_list, limit2)
            pairs.append({"n1": o1, "n2_options": o2_filtered})

        return {
            "pairs": pairs,
            "n1": {"label": n1_meta.label, "selector": n1_meta.selector, "index": n1_meta.index},
            "n2": {"label": n2_meta.label, "selector": n2_meta.selector, "index": n2_meta.index},
            "totalPairs": len(pairs)
        }
