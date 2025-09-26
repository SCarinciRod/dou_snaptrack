"""
Domain models (dataclasses) for DOU processing utilities.
Centralizes structured representations to improve typing, validation, and reuse.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, List
from datetime import datetime


@dataclass(slots=True)
class ExpandedJob:
    """
    Represents a fully expanded job (after processing topics/combos/repeats).
    Fields beginning with underscore are internal/meta.
    """
    topic: str
    query: str
    data: Optional[str] = None
    secao: Optional[str] = None
    key1: str = ""
    key2: str = ""
    key3: str = ""
    summary_keywords: Optional[str] = None
    summary_lines: Optional[int] = None
    summary_mode: Optional[str] = None
    _repeat: int = 1
    _combo_index: Optional[int] = None
    _job_index: Optional[int] = None  # for direct jobs (non-combos)
    # Keep original arbitrary extras if present (extensibility)
    _extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job to a dict compatible with legacy usage."""
        base = asdict(self)
        # Merge extras at root (legacy compatibility)
        extra = base.pop("_extra", {}) or {}
        base.update(extra)
        return base


@dataclass(slots=True)
class DetailData:
    """
    Structured representation of a scraped DOU detail page.
    """
    detail_url: str
    titulo: Optional[str] = None
    ementa: Optional[str] = None
    texto: Optional[str] = None
    orgao: Optional[str] = None
    tipo_ato: Optional[str] = None
    secao: Optional[str] = None
    data_publicacao_raw: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    pdf_url: Optional[str] = None
    edicao: Optional[str] = None
    pagina: Optional[str] = None
    # raw meta capture (optional)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if self.data_publicacao:
            out["data_publicacao_iso"] = self.data_publicacao.date().isoformat()
        return out


@dataclass(slots=True)
class BulletinItem:
    """
    Item used for bulletin generation (lightweight view model).
    """
    titulo: str
    orgao: str
    tipo_ato: str
    detail_url: Optional[str] = None
    pdf_url: Optional[str] = None
    data_publicacao: Optional[str] = None
    edicao: Optional[str] = None
    pagina: Optional[str] = None
    texto: Optional[str] = None
    ementa: Optional[str] = None

    def base_text(self) -> str:
        return self.texto or self.ementa or ""
