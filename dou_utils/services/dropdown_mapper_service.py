"""
dropdown_mapper_service.py (Refatorado)

Serviço unificado para:
  (1) Mapear todos os dropdowns da página (nativos e customizados)
  (2) Mapear pares dependentes N1 -> N2 (ex.: Órgão => Tipo do Ato)

Principais dependências (core):
  - dropdown_discovery.discover_dropdown_roots
  - dropdown_actions (abrir/select/coletar)
  - polling.wait_for_options_change
  - sentinel_utils.is_sentinel_option (filtro opcional)
  - option_filter.filter_options (pode ser usado futuramente para consolidar filtros)

Saídas (map_all):
{
  "dropdowns": [
     {
        "kind": "select|combobox|unknown",
        "rootSelector": "...",
        "index": 0,
        "label": "Órgão",
        "info": {...},
        "options": [ { "text": "...", "value": "...", ... }, ... ]
     },
     ...
  ]
}

Saídas (map_pairs):
{
  "n1Label": "...",
  "n2Label": "...",
  "pairs": [
      {
         "n1Option": { "text": "...", "value": "...", ... },
         "n2Options": [ ... (filtradas) ... ],
         "n2BeforeRaw": [...],
         "n2AfterRaw": [...],
         "n2ChangeInfo": {
             "changed_vs_before_pre": bool,
             "changed_vs_global": bool,
             "changed_vs_previous": bool,
             "beforePreCount": int,
             "afterCount": int,
             "beforePreHash": "sha1",
             "afterHash": "sha1",
             "globalBaselineCount": int
         },
         "globalAggregate": bool   # heurística (ex.: se texto "todos")
      },
      ...
  ],
  "root1Meta": {...},
  "root2Meta": {...},
  "baselineGlobalCount": int,
  "timingSummary": [ { "n1Text": "...", "elapsedMs": float, "afterCount": int, "filteredCount": int, ...}, ... ]
}

Notas:
 - Filtros de opções em map_pairs são aplicados por texto exato (pick) e/ou regex.
 - Placeholders/sentinelas são removidos por padrão (configurável).
 - Polling unificado (core.polling) substitui loops internos duplicados.
 - Mantido hashing de opções para debug/comparação (sha1 simples value::text).
 - Abertura de dropdown custom (segunda lista) opcional (open_n2=True).

Limitações / Futuras extensões:
 - Suporte N3 poderia ser adicionado replicando padrão após N2.
 - Filtros combinados (regex + pick + limit) para N2 podem ser extraídos para core/option_filter.
 - Execução assíncrona poderá ser introduzida (adaptador) posteriormente.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
import re
import time
import hashlib
import json

from ..log_utils import get_logger
from ..core.dropdown_discovery import discover_dropdown_roots, DropdownRoot
from ..core import polling
from ..core.dropdown_actions import (
    collect_native_options,
    ensure_open_then_collect_custom,
    select_in_native,
    open_dropdown
)
from ..core.sentinel_utils import is_sentinel_option

logger = get_logger(__name__)


# ----------------------- Config Dataclasses -----------------------

@dataclass(slots=True)
class MapAllConfig:
    open_custom: bool = False          # Abrir dropdowns customizados para coletar opções
    include_empty: bool = False        # Incluir dropdowns sem opções?
    filter_sentinels: bool = True      # Remover opções sentinelas?
    max_custom_collect: int = 250      # Futura expansão (não usado diretamente aqui)


@dataclass(slots=True)
class PairFilters:
    # N1
    select1_regex: Optional[str] = None
    pick1_list: Optional[str] = None
    limit1: Optional[int] = None
    # N2
    select2_regex: Optional[str] = None
    pick2_list: Optional[str] = None
    limit2_per_n1: Optional[int] = None
    # Comum
    filter_sentinels: bool = True


@dataclass(slots=True)
class MapPairsConfig:
    label1_regex: Optional[str] = None
    label2_regex: Optional[str] = None
    id1_regex: Optional[str] = None
    id2_regex: Optional[str] = None

    delay_ms_after_select: int = 500
    poll_timeout_ms: int = 3000
    poll_interval_ms: int = 250
    require_growth: bool = True       # exige aumento no número de opções?
    emit_change_events: bool = False  # disparar eventos change/input manualmente
    open_n2: bool = False             # tentar abrir dropdown custom N2 para coletar
    long_poll_until_growth: bool = True  # manter semântica anterior de “esperar crescimento”


# ----------------------- Helpers Internos -----------------------

_IGNORE_PLACEHOLDER_REGEX = re.compile(r'^(selecionar|selecione|todos?)\b', re.I)


def _hash_options(options: List[Dict[str, Any]]) -> str:
    try:
        data = json.dumps([(o.get("value"), o.get("text")) for o in options], ensure_ascii=False)
        return hashlib.sha1(data.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _filter_options(
    options: List[Dict[str, Any]],
    regex: Optional[str],
    pick_list: Optional[str],
    limit: Optional[int],
    filter_sentinels: bool
) -> List[Dict[str, Any]]:
    picks = {p.strip() for p in pick_list.split(",")} if pick_list else None
    rx = re.compile(regex, re.I) if regex else None
    out = []
    for o in options:
        txt = (o.get("text") or "").strip()
        val = (o.get("value") or "").strip()

        if filter_sentinels and is_sentinel_option(o):
            continue

        if picks:
            if (txt not in picks) and (val not in picks):
                continue
        elif rx:
            if not (rx.search(txt) or rx.search(val)):
                continue
        else:
            # sem filtros → aceita (mas pode remover placeholder se configurado)
            if filter_sentinels and _IGNORE_PLACEHOLDER_REGEX.search(txt):
                continue

        out.append(o)
        if limit and len(out) >= limit:
            break
    return out


def _pick_root(
    roots: List[DropdownRoot],
    label_regex: Optional[str],
    default_index: int,
    id_regex: Optional[str]
) -> Optional[DropdownRoot]:
    """
    Seleciona um root por prioridade:
      1. id_regex (se fornecido)
      2. label_regex
      3. posição default_index
    """
    if id_regex:
        rid = re.compile(id_regex, re.I)
        for r in roots:
            # ID pode estar em r.info.attrs.id
            attrs = (r.info or {}).get("attrs") or {}
            rid_attr = attrs.get("id") or r.id_attr
            if rid_attr and rid.search(rid_attr):
                return r

    if label_regex:
        rl = re.compile(label_regex, re.I)
        for r in roots:
            if r.label and rl.search(r.label):
                return r
        return None

    return roots[default_index] if len(roots) > default_index else (roots[0] if roots else None)


def _dispatch_change_events(handle):
    """
    Dispara eventos de change/input para frameworks que requerem.
    """
    try:
        handle.evaluate("""el => {
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('input', {bubbles:true}));
        }""")
    except Exception:
        pass


def _focus_then_blur(frame, handle):
    try:
        handle.focus()
        frame.wait_for_timeout(30)
        frame.evaluate("el => el.blur()", handle)
    except Exception:
        pass


def _collect_native(handle) -> List[Dict[str, Any]]:
    try:
        return collect_native_options(handle)
    except Exception:
        return []


# ----------------------- Classe Principal -----------------------

class DropdownMapperService:
    """
    Serviço principal de mapeamento de dropdowns e pares.

    Uso típico:
        mapper = DropdownMapperService(frame)
        all_data = mapper.map_all(MapAllConfig(open_custom=True))
        pairs_data = mapper.map_pairs(MapPairsConfig(label1_regex="Órg", label2_regex="Tipo"), PairFilters(...))

    Observação:
      - Esta implementação assume Playwright síncrono.
      - Para ambientes assíncronos, criar adaptador (futuro).
    """

    def __init__(self, frame):
        self.frame = frame

    # ---------- 1. Mapeamento de todos os dropdowns ----------

    def map_all(self, config: MapAllConfig | None = None) -> List[Dict[str, Any]]:
        """
        Retorna uma lista de dicts representando cada dropdown descoberto.
        Se open_custom=True, tenta abrir dropdowns customizados para coletar opções.
        """
        cfg = config or MapAllConfig()
        roots = discover_dropdown_roots(self.frame)
        out = []

        for r in roots:
            record = r.to_public_dict()
            options: List[Dict[str, Any]] = []

            try:
                # Nativo
                native = _collect_native(r.handle)
                if native:
                    options = native
                # Custom (abrir e coletar)
                elif cfg.open_custom:
                    options = ensure_open_then_collect_custom(self.frame, r.handle)
            except Exception as e:
                logger.debug("Falha coletando opções", extra={"label": r.label, "err": str(e)})

            if cfg.filter_sentinels:
                options = [o for o in options if not is_sentinel_option(o)]

            if not options and not cfg.include_empty:
                # Ainda incluímos o dropdown mesmo sem opções?
                # Decisão: incluir sim, mas options=[]
                pass

            record["options"] = options
            out.append(record)

        logger.info("map_all complete", extra={"dropdowns": len(out)})
        return out

    # ---------- 2. Mapeamento de Pares N1 -> N2 ----------

    def map_pairs(
        self,
        pair_config: MapPairsConfig,
        filters: PairFilters
    ) -> Dict[str, Any]:
        """
        Mapeia pares dependentes (N1 -> N2) de dois dropdowns (normalmente selects).
        Aplica filtros em N1 e N2 conforme objeto PairFilters.
        """
        roots = discover_dropdown_roots(self.frame)
        if not roots:
            return {"error": "No dropdown roots found", "pairs": []}

        root1 = _pick_root(roots, pair_config.label1_regex, 0, pair_config.id1_regex)
        root2 = _pick_root(roots, pair_config.label2_regex, 1, pair_config.id2_regex)

        if not (root1 and root2):
            return {
                "n1Label": root1.label if root1 else None,
                "n2Label": root2.label if root2 else None,
                "pairs": [],
                "error": "Could not identify both dropdowns",
                "root1Meta": self._root_meta(root1),
                "root2Meta": self._root_meta(root2)
            }

        # Coleta baseline de N2 antes de qualquer seleção
        baseline_n2 = _collect_native(root2.handle)
        baseline_hash = _hash_options(baseline_n2)

        # Coleta N1 total e filtra
        all_n1 = _collect_native(root1.handle)
        n1_filtered = _filter_options(
            all_n1,
            filters.select1_regex,
            filters.pick1_list,
            filters.limit1,
            filter_sentinels=filters.filter_sentinels
        )

        pairs = []
        timing = []
        previous_after_hash = None

        for opt1 in n1_filtered:
            start_t = time.time()

            # Snapshot N2 antes da seleção
            before_pre = _collect_native(root2.handle)
            before_hash = _hash_options(before_pre)

            ok = self._select_n1(root1, opt1, pair_config)
            if not ok:
                pairs.append({
                    "n1Option": opt1,
                    "n2Options": [],
                    "n2BeforeRaw": before_pre,
                    "n2AfterRaw": before_pre,
                    "n2ChangeInfo": {
                        "changed_vs_before_pre": False,
                        "changed_vs_global": False,
                        "changed_vs_previous": False,
                        "beforePreCount": len(before_pre),
                        "afterCount": len(before_pre),
                        "beforePreHash": before_hash,
                        "afterHash": before_hash,
                        "globalBaselineCount": len(baseline_n2)
                    },
                    "error": "select_n1_failed",
                    "globalAggregate": False
                })
                continue

            # Delay pós seleção
            try:
                self.frame.wait_for_timeout(pair_config.delay_ms_after_select)
            except Exception:
                pass

            # Abrir N2 se custom
            if pair_config.open_n2:
                try:
                    open_dropdown(self.frame, root2.handle)
                    self.frame.wait_for_timeout(120)
                except Exception:
                    pass

            # Poll para mudança
            after = polling.wait_for_options_change(
                self.frame,
                root2.handle,
                before_pre,
                timeout_ms=pair_config.poll_timeout_ms,
                poll_interval_ms=pair_config.poll_interval_ms,
                require_growth=pair_config.long_poll_until_growth
            )
            after_hash = _hash_options(after)

            n2_filtered = _filter_options(
                after,
                filters.select2_regex,
                filters.pick2_list,
                filters.limit2_per_n1,
                filter_sentinels=filters.filter_sentinels
            )

            change_info = {
                "changed_vs_before_pre": after_hash != before_hash,
                "changed_vs_global": after_hash != baseline_hash,
                "changed_vs_previous": (previous_after_hash is not None and after_hash != previous_after_hash),
                "beforePreCount": len(before_pre),
                "afterCount": len(after),
                "beforePreHash": before_hash,
                "afterHash": after_hash,
                "globalBaselineCount": len(baseline_n2)
            }

            pairs.append({
                "n1Option": opt1,
                "n2Options": n2_filtered,
                "n2BeforeRaw": before_pre,
                "n2AfterRaw": after,
                "n2ChangeInfo": change_info,
                "globalAggregate": (opt1.get("text") or "").strip().lower() == "todos"
            })

            previous_after_hash = after_hash

            timing.append({
                "n1Text": opt1.get("text"),
                "elapsedMs": round((time.time() - start_t) * 1000, 1),
                "afterCount": len(after),
                "filteredCount": len(n2_filtered),
                "changedPre": change_info["changed_vs_before_pre"]
            })

        result = {
            "n1Label": root1.label,
            "n2Label": root2.label,
            "pairs": pairs,
            "root1Meta": self._root_meta(root1),
            "root2Meta": self._root_meta(root2),
            "baselineGlobalCount": len(baseline_n2),
            "timingSummary": timing
        }
        logger.info(
            "map_pairs complete",
            extra={"n1": root1.label, "n2": root2.label, "pairs": len(pairs)}
        )
        return result

    # ----------------------- Métodos Internos -----------------------

    def _select_n1(self, root: DropdownRoot, opt: Dict[str, Any], pair_config: MapPairsConfig) -> bool:
        """
        Faz a seleção da opção N1 (após localizar value ou text).
        """
        value = opt.get("value") or opt.get("text")
        if not value:
            return False

        ok = select_in_native(root.handle, value)
        if not ok:
            return False

        if pair_config.emit_change_events:
            _dispatch_change_events(root.handle)
        _focus_then_blur(self.frame, root.handle)
        return True

    @staticmethod
    def _root_meta(root: Optional[DropdownRoot]) -> Optional[Dict[str, Any]]:
        if not root:
            return None
        attrs = (root.info or {}).get("attrs") or {}
        return {
            "id": root.id_attr or attrs.get("id"),
            "selector": root.selector,
            "label": root.label,
            "kind": root.kind,
            "index": root.index,
            "position": {"y": root.y, "x": root.x}
        }
