"""
dropdown_discovery.py
Descoberta centralizada de dropdowns (selects nativos e componentes custom)
com heurísticas de derivação de label reutilizáveis.

Responsável por:
 - Encontrar elementos candidatos (select, [role=combobox], heurísticos de classes)
 - Extrair atributos e posição
 - Gerar um label significativo (prioridades configuradas)
 - Retornar lista ordenada por posição (y, x)

Dependências externas (já existentes):
 - element_utils.elem_common_info
 - element_utils.label_for_control
 - dropdown_utils._read_select_options
 - dropdown_utils._is_select
 - selectors.DROPDOWN_ROOT_SELECTORS

Uso:
    from dou_utils.core.dropdown_discovery import discover_dropdown_roots
    roots = discover_dropdown_roots(frame)

Saída:
    Lista de DropdownRoot (dataclass) com:
      kind, selector, index, label, id_attr, y, x, info, options_preview (se select)
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, List, Dict, Optional, Iterable, Tuple
import re

from ..element_utils import elem_common_info, label_for_control
from ..dropdown_utils import _read_select_options, _is_select
from ..selectors import DROPDOWN_ROOT_SELECTORS
from ..log_utils import get_logger
from ..settings import SETTINGS

logger = get_logger(__name__)


# ---------------- Dataclass ----------------

@dataclass(slots=True)
class DropdownRoot:
    kind: str
    selector: str
    index: int
    y: float
    x: float
    handle: Any
    id_attr: Optional[str] = None
    label: str = ""
    info: Dict[str, Any] = field(default_factory=dict)
    options_preview: List[Dict[str, Any]] = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, Any]:
        """
        Representação simplificada (compatível com o formato anterior de mapeamento).
        """
        return {
            "kind": self.kind,
            "rootSelector": self.selector,
            "index": self.index,
            "label": self.label,
            "info": self.info,
            # options preenchidas posteriormente pelo serviço que coleta (map_all)
        }


# ---------------- Label Heuristics ----------------

_GENERIC_PATTERNS = [
    re.compile(r"^\s*selecionar\s*$", re.I),
    re.compile(r"^\s*selecionar\s+o\s+dia\s+desejado\s*$", re.I),
    re.compile(r"^\s*selecione\s*$", re.I),
    re.compile(r"^\s*selecionar.*$", re.I),
]

_PLACEHOLDER_IGNORE = re.compile(r"^\s*(selecionar|selecione)\b", re.I)
_OPTION_IGNORE = re.compile(r"^\s*(selecionar|selecione|todos?)\b", re.I)


def _looks_generic(label: str) -> bool:
    if not label:
        return True
    return any(p.match(label.strip()) for p in _GENERIC_PATTERNS)


def _first_non_trivial_option(options: List[Dict[str, Any]]) -> str:
    for o in options:
        t = (o.get("text") or "").strip()
        if not t:
            continue
        if _OPTION_IGNORE.search(t):
            continue
        return t
    return ""


# ... (mantém cabeçalho existente) ...
# Apenas mostrar a função derive_label modificada e pequena adição utilitária

# Substitua a função derive_label existente por esta versão:

def derive_label(frame, handle, base_label: str, info: Dict[str, Any], options_preview: List[Dict[str, Any]]) -> str:
    """
    Estratégia unificada (ordem):
      1. Label explícito não genérico
      2. placeholder válido (attrs.placeholder)
      3. primeira opção não-trivial
      4. aria-label não genérica
      5. id atribuído (NOVO: se label genérico, preferimos id)
      6. fallback para label original
    """
    attrs = (info or {}).get("attrs") or {}

    # Se já temos label claro
    if base_label and not _looks_generic(base_label):
        return base_label.strip()

    # placeholder
    placeholder = (attrs.get("placeholder") or "").strip()
    if placeholder and not _looks_generic(placeholder):
        return placeholder

    # primeira opção não-trivial
    first_opt = _first_non_trivial_option(options_preview)
    if first_opt and not _looks_generic(first_opt):
        return first_opt

    # aria-label
    aria = (attrs.get("aria-label") or "").strip()
    if aria and not _looks_generic(aria):
        return aria

    # NOVO: se label é genérico e temos id, usar id
    cid = attrs.get("id")
    if cid:
        # Se base_label vazio ou genérico explicitamente
        if not base_label or _looks_generic(base_label):
            return cid

    # fallback
    return base_label or cid or ""

# ---------------- Discovery Core ----------------

def _push_candidates(frame, kind: str, sel: str, loc, limit: int, acc: List[Dict], seen: set):
    try:
        cnt = loc.count()
    except Exception:
        cnt = 0

    for i in range(min(cnt, limit)):
        h = loc.nth(i)
        try:
            box = h.bounding_box()
            if not box:
                continue
            key = (sel, i, round(box["y"], 2), round(box["x"], 2))
            if key in seen:
                continue
            seen.add(key)
            acc.append({
                "kind": kind,
                "selector": sel,
                "index": i,
                "handle": h,
                "y": box["y"],
                "x": box["x"]
            })
        except Exception:
            continue


def _collect_raw_roots(frame) -> List[Dict]:
    """
    Coleta bruta de elementos candidatos a dropdown.
    """
    out: List[Dict] = []
    seen = set()
    max_per_type = SETTINGS.dropdown.max_per_type

    # Prioridade ARIA / semântica
    _push_candidates(frame, "combobox", "[role=combobox]", frame.get_by_role("combobox"), max_per_type, out, seen)
    _push_candidates(frame, "select", "select", frame.locator("select"), max_per_type, out, seen)

    # Heurísticos adicionais
    for sel in DROPDOWN_ROOT_SELECTORS:
        if sel == "select" or sel == "[role=combobox]":
            continue
        try:
            loc = frame.locator(sel)
        except Exception:
            continue
        _push_candidates(frame, "unknown", sel, loc, max_per_type, out, seen)

    return out


def _deduplicate(raw: List[Dict]) -> List[Dict]:
    """
    Deduplica por ID (quando disponível) ou por posição aproximada.
    """
    by_key = {}
    for r in raw:
        try:
            el = r["handle"]
            el_id = el.get_attribute("id")
        except Exception:
            el_id = None

        if el_id:
            key = ("id", el_id)
        else:
            key = ("pos", round(r["y"], 1), round(r["x"], 1), r["selector"])

        prev = by_key.get(key)
        if not prev:
            by_key[key] = r
            continue

        # Critério de prioridade: select > combobox > unknown
        prio = {"select": 3, "combobox": 2, "unknown": 1}
        if prio.get(r["kind"], 0) > prio.get(prev["kind"], 0):
            by_key[key] = r

    return list(by_key.values())


def discover_dropdown_roots(frame) -> List[DropdownRoot]:
    """
    Função principal: retorna lista de DropdownRoot ordenada por (y,x).

    Observações:
      - options_preview só é populado para selects nativos (para heurística de label/preview).
      - Não coleta todas as opções de custom dropdowns (isso é responsabilidade de outro estágio, se solicitado).
    """
    raw = _collect_raw_roots(frame)
    dedup = _deduplicate(raw)

    roots: List[DropdownRoot] = []
    for r in dedup:
        h = r["handle"]

        # Metadados
        try:
            el_id = h.get_attribute("id")
        except Exception:
            el_id = None

        try:
            base_label = label_for_control(frame, h)
        except Exception:
            base_label = ""

        info = {}
        try:
            info = elem_common_info(frame, h)
        except Exception:
            pass

        options_preview: List[Dict[str, Any]] = []
        if _is_select(h):
            try:
                options_preview = _read_select_options(h) or []
            except Exception:
                options_preview = []

        final_label = derive_label(frame, h, base_label or info.get("attrs", {}).get("aria-label", ""),
                                   info, options_preview)

        roots.append(
            DropdownRoot(
                kind=r["kind"],
                selector=r["selector"],
                index=r["index"],
                y=r["y"],
                x=r["x"],
                handle=h,
                id_attr=el_id,
                label=final_label,
                info=info,
                options_preview=options_preview
            )
        )

    roots.sort(key=lambda rr: (rr.y, rr.x))
    logger.debug("discover_dropdown_roots total=%s labels=%s ids=%s",
                 len(roots), [rt.label for rt in roots], [rt.id_attr for rt in roots])
    return roots
