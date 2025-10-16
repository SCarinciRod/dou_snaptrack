from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SummaryConfig:
    lines: int = 0
    mode: str = "center"
    keywords: List[str] | None = None


def setup_summary_from_args(args) -> SummaryConfig:
    """Extract summary settings from argparse args into a typed config (no globals)."""
    # Fixa summary-lines=0 por padrão (sem fallback para summary-sentences)
    lines = int(getattr(args, "summary_lines", 0) or 0)

    mode = getattr(args, "summary_mode", "center") or "center"
    if mode not in ("center", "lead", "keywords-first"):
        mode = "center"

    # Collect keywords from CLI and optional file
    kws: list[str] = []
    raw = getattr(args, "summary_keywords", None)
    if raw:
        for part in raw.split(";"):
            s = (part or "").strip()
            if s:
                kws.append(s.lower())

    fn = getattr(args, "summary_keywords_file", None)
    if fn:
        try:
            txt = Path(fn).read_text(encoding="utf-8")
            for line in txt.splitlines():
                s = (line or "").strip()
                if s:
                    kws.append(s.lower())
        except Exception:
            # Silently ignore bad file
            pass

    return SummaryConfig(lines=lines, mode=mode, keywords=kws or None)


def apply_summary_overrides_from_job(base: SummaryConfig, job: dict) -> SummaryConfig:
    """Return a new SummaryConfig with per-job overrides (if present)."""
    if not isinstance(job, dict):
        return base

    lines = base.lines
    mode = base.mode
    keywords = list(base.keywords or [])

    sl = job.get("summary_lines")
    if isinstance(sl, int) and sl > 0:
        lines = sl

    sm = job.get("summary_mode")
    if sm in ("center", "lead", "keywords-first"):
        mode = sm

    kws = job.get("summary_keywords")
    if isinstance(kws, list) and kws:
        keywords = [str(k).strip().lower() for k in kws if str(k).strip()]

    return SummaryConfig(lines=lines, mode=mode, keywords=keywords or None)
