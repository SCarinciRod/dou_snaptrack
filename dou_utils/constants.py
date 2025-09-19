"""
constants.py
Bloco central de definição de schemas e helpers para padronização
entre artefatos (Fase 0).
"""

from __future__ import annotations
from datetime import datetime, timezone

SCHEMAS = {
    "mapping": "1.0",
    "pairs": "1.0",
    "batchConfig": "1.0",
    "cascadeResult": "1.0",
    "bulletin": "1.0",
}

SOURCES = {
    "mapping": "mapping-tool",
    "pairs": "mapping-tool",
    "batchConfig": "plan-builder",
    "cascadeResult": "cascade-run",
    "bulletin": "bulletin-builder",
}


def schema_block(name: str) -> dict:
    return {
        "name": name,
        "version": SCHEMAS.get(name, "1.0")
    }


def utc_now_iso() -> str:
    # Sempre UTC em formato segundos + Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
