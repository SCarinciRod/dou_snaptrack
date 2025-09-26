"""
Advanced option filtering with:
 - regex (case-insensitive)
 - fallback multiline tokens → normalized matching
 - pick list
 - limit
Normalization: NFKD + ASCII + lowercase + collapse whitespace.
"""

from __future__ import annotations
import re
import unicodedata
from typing import List, Dict, Optional


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())


PLACEHOLDER_NORMALIZED = {
    "selecionar organizacao principal",
    "selecionar organização principal",
    "selecionar organizacao subordinada",
    "selecionar organização subordinada",
    "selecionar tipo do ato",
    "selecionar",
    "todos"
}


def remove_placeholders(options: List[Dict]) -> List[Dict]:
    out = []
    for o in options or []:
        if normalize_text(o.get("text") or "") in PLACEHOLDER_NORMALIZED:
            continue
        out.append(o)
    return out


def filter_options(
    options: List[Dict],
    select_regex: Optional[str] = None,
    pick_list: Optional[str] = None,
    limit: Optional[int] = None,
    fallback_multiline: bool = True
) -> List[Dict]:
    opts = options or []
    out = opts

    if select_regex:
        # Primary regex attempt
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in opts if pat.search(o.get("text") or "")]
        except re.error:
            out = []
        # Fallback multiline tokens (acentos-insensível)
        if fallback_multiline and not out:
            lines = [t.strip() for t in select_regex.splitlines() if t.strip()]
            norms = [normalize_text(l) for l in lines]
            tmp = []
            for o in opts:
                nt = normalize_text(o.get("text") or "")
                if any(n and n in nt for n in norms):
                    tmp.append(o)
            out = tmp

    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]

    if limit and limit > 0:
        out = out[:limit]
    return out
