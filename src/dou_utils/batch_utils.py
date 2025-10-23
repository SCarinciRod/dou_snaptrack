"""
Batch job expansion utilities.

Principais funções:
- Expandir configurações batch em jobs individuais
- Sanitização de nomes de arquivos
- Criação de nomes únicos para arquivos

Classes:
- RawBatchConfig: estrutura de dados para configuração de batch
- JobExpander: serviço para expansão de configurações em jobs
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .log_utils import get_logger
from .models import ExpandedJob

logger = get_logger(__name__)

# Configurações padrão caso SETTINGS não esteja disponível
DEFAULT_MAX_FILENAME_LEN = 100

# Tenta importar configurações globais (opcional)
try:
    from .settings import SETTINGS  # optional
    MAX_FILENAME_LEN = getattr(getattr(SETTINGS, "files", object()), "sanitize_max_filename_len", DEFAULT_MAX_FILENAME_LEN)
except Exception:
    MAX_FILENAME_LEN = DEFAULT_MAX_FILENAME_LEN


# ------------------- Sanitização & filename utilities ---------------------

_filename_re = re.compile(r'[^A-Za-z0-9._-]+')

def sanitize_filename(name: str, max_len: int | None = None) -> str:
    """
    Normaliza e limpa nome de arquivo, removendo caracteres inválidos.

    Args:
        name: Nome original a ser sanitizado
        max_len: Tamanho máximo do nome (default=settings.files.sanitize_max_filename_len ou 100)

    Returns:
        Nome de arquivo sanitizado
    """
    if not name:
        return "out"

    # Normalizar para remover acentos
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    ascii_name = ascii_name.strip()

    # Aplicar comprimento máximo (prioridade: argumento > config > default)
    max_len = int(max_len) if isinstance(max_len, int) else int(MAX_FILENAME_LEN)

    # Substituir caracteres inválidos por underscore
    cleaned = _filename_re.sub("_", ascii_name)
    cleaned = cleaned.strip("._")

    # Garantir que não está vazio
    if not cleaned:
        cleaned = "out"

    # Truncar se necessário
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]

    return cleaned


def make_unique(name: str, existing: set[str], max_len: int | None = None) -> str:
    """
    Garante que o nome de arquivo é único dentro do conjunto 'existing' adicionando _N.

    Args:
        name: Nome base a ser usado
        existing: Conjunto de nomes existentes para checar colisão
        max_len: Tamanho máximo do nome final

    Returns:
        Nome único garantido
    """
    max_len = int(max_len) if isinstance(max_len, int) else int(MAX_FILENAME_LEN)
    base = name

    # Se já é único, retornar diretamente
    if name not in existing:
        return name

    # Caso contrário, tentar com sufixos incrementais
    i = 2
    while True:
        suffix = f"_{i}"
        # Garante que o comprimento total respeita max_len
        candidate = base[: max_len - len(suffix)] + suffix

        if candidate not in existing:
            return candidate

        i += 1


def render_out_filename(pattern: str, job: ExpandedJob | dict[str, Any]) -> str:
    """
    Renderiza um padrão de nome de arquivo com campos do job.

    Placeholders suportados:
      {topic} {secao} {date} {idx} {rep} {key1} {key2} {key3}

    Args:
        pattern: String de padrão com placeholders
        job: ExpandedJob ou Dict com dados do job

    Returns:
        Nome do arquivo renderizado e sanitizado
    """
    if isinstance(job, ExpandedJob):
        jdict = job.to_dict()
    else:
        jdict = job

    date_str = (jdict.get("data") or "").replace("/", "-")

    tokens = {
        "topic": jdict.get("topic") or "job",
        "secao": jdict.get("secao") or "DO",
        "date": date_str,
        "idx": str(jdict.get("_combo_index") or jdict.get("_job_index") or ""),
        "rep": str(jdict.get("_repeat") or ""),
        "key1": jdict.get("key1") or "",
        "key2": jdict.get("key2") or "",
        "key3": jdict.get("key3") or "",
    }

    name = pattern
    for k, v in tokens.items():
        name = name.replace("{" + k + "}", sanitize_filename(str(v)))

    return sanitize_filename(name)


# --------------------- Core expansion logic ---------------------------------

def _safe_int(v: Any, default: int = 1) -> int:
    """Converte valor para inteiro com segurança, retornando default em caso de erro."""
    try:
        iv = int(v)
        return iv if iv > 0 else default
    except (ValueError, TypeError):
        return default


@dataclass(slots=True)
class RawBatchConfig:
    """Representa a estrutura bruta de uma configuração de batch."""
    defaults: dict[str, Any]
    jobs: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    combos: list[dict[str, Any]]
    data: str | None
    secao_default: str | None
    repeat: int

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> RawBatchConfig:
        """Cria uma instância RawBatchConfig a partir de um dicionário."""
        return cls(
            defaults=cfg.get("defaults", {}) or {},
            jobs=cfg.get("jobs", []) or [],
            topics=cfg.get("topics", []) or [],
            combos=cfg.get("combos", []) or [],
            data=cfg.get("data"),
            secao_default=cfg.get("secaoDefault"),
            repeat=_safe_int(cfg.get("repeat", 1)),
        )


class JobExpander:
    """
    Serviço para expandir uma configuração de batch em jobs completamente expandidos.
    """
    def __init__(self, cfg: dict[str, Any]):
        """
        Inicializa o expansor com uma configuração de batch.

        Args:
            cfg: Configuração de batch como dicionário
        """
        self.raw = RawBatchConfig.from_dict(cfg)

    def expand(self) -> list[ExpandedJob]:
        """
        Expande a configuração em uma lista de jobs completos.

        Returns:
            Lista de ExpandedJob
        """
        jobs: list[ExpandedJob] = []

        # Expansão de jobs diretos
        jobs.extend(self._expand_direct_jobs())

        # Combinação de tópicos e combos
        if self.raw.topics and self.raw.combos:
            jobs.extend(self._expand_topics_and_combos())
        # Somente combos
        elif self.raw.combos:
            jobs.extend(self._expand_combos_only())

        logger.info("Expanded jobs", extra={"count": len(jobs)})
        return jobs

    # ------------- Internal expansion helpers -----------------

    def _merge_defaults(self, item: dict[str, Any]) -> dict[str, Any]:
        """Mescla defaults com item específico."""
        merged = dict(self.raw.defaults)
        merged.update(item or {})

        # Aplica defaults globais se não definidos no item
        if self.raw.data and not merged.get("data"):
            merged["data"] = self.raw.data

        if self.raw.secao_default and not merged.get("secao"):
            merged["secao"] = self.raw.secao_default

        return merged

    def _expand_direct_jobs(self) -> list[ExpandedJob]:
        """Expande jobs definidos diretamente na configuração."""
        out: list[ExpandedJob] = []

        for jidx, j in enumerate(self.raw.jobs, 1):
            merged = self._merge_defaults(j)
            rep = _safe_int(merged.get("repeat", self.raw.repeat))

            for r in range(1, rep + 1):
                ej = self._to_expanded(merged, repeat=r, job_index=jidx)
                out.append(ej)

        return out

    def _expand_topics_and_combos(self) -> list[ExpandedJob]:
        """Expande combinando cada tópico com cada combo."""
        out: list[ExpandedJob] = []

        for t in self.raw.topics:
            topic_name = t.get("name") or "topic"
            topic_query = t.get("query") or ""
            topic_repeat = _safe_int(t.get("repeat", self.raw.repeat))

            # Extrai campos específicos de tópicos
            overrides = {
                k: t.get(k)
                for k in ("summary_keywords", "summary_lines", "summary_mode")
                if k in t
            }

            for cidx, combo in enumerate(self.raw.combos, 1):
                merged = self._merge_defaults(combo)
                merged["topic"] = topic_name
                merged["query"] = merged.get("query", topic_query)
                merged.update(overrides)

                rep = _safe_int(merged.get("repeat", topic_repeat))

                for r in range(1, rep + 1):
                    ej = self._to_expanded(merged, repeat=r, combo_index=cidx)
                    out.append(ej)

        return out

    def _expand_combos_only(self) -> list[ExpandedJob]:
        """Expande apenas os combos sem tópicos."""
        out: list[ExpandedJob] = []

        for cidx, combo in enumerate(self.raw.combos, 1):
            merged = self._merge_defaults(combo)
            merged["topic"] = merged.get("topic") or f"job{cidx}"
            merged["query"] = merged.get("query", self.raw.defaults.get("query", ""))

            rep = _safe_int(merged.get("repeat", self.raw.repeat))

            for r in range(1, rep + 1):
                ej = self._to_expanded(merged, repeat=r, combo_index=cidx)
                out.append(ej)

        return out

    def _to_expanded(
        self,
        merged: dict[str, Any],
        repeat: int,
        combo_index: int | None = None,
        job_index: int | None = None,
    ) -> ExpandedJob:
        """Converte dicionário mesclado para um ExpandedJob."""
        # Campos conhecidos para ExpandedJob
        core_fields = {
            "topic": merged.get("topic", "job"),
            "query": merged.get("query", ""),
            "data": merged.get("data"),
            "secao": merged.get("secao"),
            "key1": merged.get("key1", ""),
            "key2": merged.get("key2", ""),
            "key3": merged.get("key3", ""),
            "summary_keywords": merged.get("summary_keywords"),
            "summary_lines": merged.get("summary_lines"),
            "summary_mode": merged.get("summary_mode"),
            "_repeat": repeat,
            "_combo_index": combo_index,
            "_job_index": job_index,
        }

        # Outros campos vão para _extra
        extra_fields = {
            k: v
            for k, v in merged.items()
            if k not in core_fields and k != "repeat"
        }

        return ExpandedJob(**core_fields, _extra=extra_fields)


# ------------------ Public API functions (legacy names) ---------------------

def expand_batch_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Interface compatível com legado retornando lista de dicionários.

    Args:
        cfg: Configuração de batch

    Returns:
        Lista de jobs expandidos como dicionários
    """
    expander = JobExpander(cfg)
    return [j.to_dict() for j in expander.expand()]
