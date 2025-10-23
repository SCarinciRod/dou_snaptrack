"""
Domain models (dataclasses) for DOU processing utilities.
Centralizes structured representations to improve typing, validation, and reuse.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ExpandedJob:
    """
    Represents a fully expanded job (after processing topics/combos/repeats).
    Fields beginning with underscore are internal/meta.
    """
    topic: str
    query: str
    data: str | None = None
    secao: str | None = None
    key1: str = ""
    key2: str = ""
    key3: str = ""
    summary_keywords: str | None = None
    summary_lines: int | None = None
    summary_mode: str | None = None
    _repeat: int = 1
    _combo_index: int | None = None
    _job_index: int | None = None  # for direct jobs (non-combos)
    # Keep original arbitrary extras if present (extensibility)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    titulo: str | None = None
    ementa: str | None = None
    texto: str | None = None
    orgao: str | None = None
    tipo_ato: str | None = None
    secao: str | None = None
    data_publicacao_raw: str | None = None
    data_publicacao: datetime | None = None
    pdf_url: str | None = None
    edicao: str | None = None
    pagina: str | None = None
    # raw meta capture (optional)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    detail_url: str | None = None
    pdf_url: str | None = None
    data_publicacao: str | None = None
    edicao: str | None = None
    pagina: str | None = None
    texto: str | None = None
    ementa: str | None = None

    def base_text(self) -> str:
        return self.texto or self.ementa or ""
