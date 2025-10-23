from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

from dou_utils.core.sentinel_utils import is_sentinel_option
from dou_utils.core.option_filter import filter_options
from dou_utils.core.combos import generate_cartesian, build_dynamic_n2, build_combos_plan

try:
    from dou_utils.log_utils import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return logging.getLogger(name)

logger = get_logger(__name__)


def _strip_accents(s: str) -> str:
    if not isinstance(s, str):
        return s or ""
    nf = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nf if unicodedata.category(ch) != "Mn")


def _pattern_has_accents(pat: str) -> bool:
    if not pat:
        return False
    s = unicodedata.normalize("NFC", pat)
    return any(unicodedata.category(ch) == "Mn" for ch in unicodedata.normalize("NFD", s))


def _text_fields(dd: Dict[str, Any]) -> List[str]:
    fields = []
    for k in ("label", "name", "ariaLabel", "placeholder", "title"):
        v = dd.get(k)
        if isinstance(v, str) and v.strip():
            fields.append(v.strip())
    return fields


def _looks_like_dropdown_list(lst: Any) -> bool:
    if not isinstance(lst, list) or not lst:
        return False
    # Heurística: lista de dicts com 'options' (lista de dicts com text/value) ou que tenham 'label'/'name'
    hits = 0
    for el in lst:
        if isinstance(el, dict):
            opts = el.get("options")
            if isinstance(opts, list) and (opts and isinstance(opts[0], dict) and ("text" in opts[0] or "value" in opts[0])):
                hits += 1
            elif any(k in el for k in ("label", "name")):
                hits += 1
    # Considere válido se maioria dos elementos parecem dropdowns
    return hits >= max(1, len(lst) // 2)


def _deep_find_dropdown_lists(obj: Any, acc: List[List[Dict[str, Any]]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _looks_like_dropdown_list(v):
                acc.append(v)  # type: ignore
            _deep_find_dropdown_lists(v, acc)
    elif isinstance(obj, list):
        for it in obj:
            _deep_find_dropdown_lists(it, acc)


def _looks_like_pairs_list(lst: Any) -> bool:
    if not isinstance(lst, list) or not lst:
        return False
    # Heurística: itens com n1Option dict e n2Options list
    good = 0
    for el in lst:
        if isinstance(el, dict):
            if isinstance(el.get("n1Option"), dict) and isinstance(el.get("n2Options"), list):
                good += 1
    return good >= max(1, len(lst) // 2)


def _deep_find_pairs_lists(obj: Any, acc: List[List[Dict[str, Any]]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == "pairs" and isinstance(v, list) and _looks_like_pairs_list(v):
                acc.append(v)  # type: ignore
            _deep_find_pairs_lists(v, acc)
    elif isinstance(obj, list):
        for it in obj:
            _deep_find_pairs_lists(it, acc)


class DropdownExtractor:
    @staticmethod
    def extract_from_raw(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Procura arrays de dropdowns em múltiplos caminhos e também via busca profunda.
        Prioridade:
          1) Campos diretos comuns (root/data/mapping)
          2) Busca profunda por listas que aparentem ser dropdowns
        """
        candidates: List[List[Dict[str, Any]]] = []

        def push(val):
            if isinstance(val, list) and val:
                if _looks_like_dropdown_list(val):
                    candidates.append(val)

        data = raw.get("data") if isinstance(raw, dict) else None
        mapping = data.get("mapping") if isinstance(data, dict) else None

        # Tentativas diretas
        push(raw.get("dropdowns"))
        push(raw.get("dropdownRoots"))
        if isinstance(data, dict):
            push(data.get("dropdowns"))
            push(data.get("dropdownRoots"))
        if isinstance(mapping, dict):
            push(mapping.get("dropdowns"))
            push(mapping.get("dropdownRoots"))

        # Busca profunda se nada encontrado
        if not candidates:
            deep: List[List[Dict[str, Any]]] = []
            _deep_find_dropdown_lists(raw, deep)
            candidates.extend(deep)

        if not candidates:
            raise RuntimeError("Nenhum array de dropdowns encontrado no mapping JSON.")

        # Heurística: escolher a maior lista (mais provável ser a principal)
        best = max(candidates, key=lambda lst: len(lst))
        return best


class PlanFromMapService:
    """
    Refatorado para usar filter_options + combos, com extração robusta de dropdowns.
    """
    def __init__(self, map_json_path: str | Path):
        p = Path(map_json_path)
        if not p.exists():
            raise FileNotFoundError(f"Mapping não encontrado: {p}")
        self._raw = json.loads(p.read_text(encoding="utf-8"))
        self._dropdowns = DropdownExtractor.extract_from_raw(self._raw)

    def list_dropdowns(self) -> List[Dict[str, Any]]:
        out = []
        for dd in self._dropdowns:
            labels = _text_fields(dd)
            opts = dd.get("options") or []
            out.append({
                "label": next(iter(labels), ""),
                "allLabels": labels,
                "optionsCount": len(opts)
            })
        return out

    def build(
        self,
        label1_regex: Optional[str],
        label2_regex: Optional[str],
        select1: Optional[str],
        pick1: Optional[str],
        limit1: Optional[int],
        select2: Optional[str],
        pick2: Optional[str],
        limit2: Optional[int],
        max_combos: Optional[int],
        secao: str,
        date: str,
        defaults: Dict[str, Any],
        query: Optional[str],
        enable_level3: Optional[bool] = None,
        label3_regex: Optional[str] = None,
        select3: Optional[str] = None,
        pick3: Optional[str] = None,
        limit3: Optional[int] = None,
        filter_sentinels: bool = True,
        dynamic_n2: bool = False,
        **_
    ) -> Dict[str, Any]:

        d1 = self._match_dropdown(label1_regex, 0)
        d2 = self._match_dropdown(label2_regex, 1)
        d3 = self._match_dropdown(label3_regex, 2) if enable_level3 else None

        if not d1:
            labels = ["/".join(_text_fields(dd)) or f"[{i}]" for i, dd in enumerate(self._dropdowns)]
            raise RuntimeError(f"Dropdown N1 não encontrado. Disponíveis: {labels}")

        opts1 = self._prep_opts(d1, select1, pick1, limit1, filter_sentinels)

        if dynamic_n2:
            combos = build_dynamic_n2(opts1, max_combos)
            return build_combos_plan(date, secao, defaults, query, combos, dynamic_n2=True)

        if not d2:
            logger.warning("Dropdown N2 ausente; gerando somente N1.")
            combos = generate_cartesian(opts1, [], None, max_combos)
            return build_combos_plan(date, secao, defaults, query, combos)

        opts2 = self._prep_opts(d2, select2, pick2, limit2, filter_sentinels)

        opts3: List[Dict[str, Any]] = []
        use_level3 = False
        if enable_level3 and d3:
            opts3 = self._prep_opts(d3, select3, pick3, limit3, filter_sentinels)
            use_level3 = True if opts3 else False

        combos = generate_cartesian(opts1, opts2, opts3 if use_level3 else None, max_combos)
        logger.info("PlanFromMapService combos=%s", len(combos))
        return build_combos_plan(date, secao, defaults, query, combos)

    # -------- Helpers --------

    def _match_dropdown(self, label_regex: Optional[str], idx: int):
        if label_regex:
            rx = re.compile(label_regex, re.IGNORECASE)
            fold_ok = not _pattern_has_accents(label_regex)
            for dd in self._dropdowns:
                fields = _text_fields(dd)
                hay = " | ".join(fields)
                if rx.search(hay):
                    return dd
                if fold_ok:
                    if rx.search(_strip_accents(hay)):
                        return dd
            return None
        return self._dropdowns[idx] if idx < len(self._dropdowns) else None

    def _prep_opts(self, dropdown: Dict[str, Any],
                   select_regex: Optional[str],
                   pick_list: Optional[str],
                   limit: Optional[int],
                   filter_sentinels: bool) -> List[Dict[str, Any]]:
        opts = dropdown.get("options") or []
        return filter_options(
            opts,
            select_regex=select_regex,
            pick_list=pick_list,
            limit=limit,
            drop_sentinels=filter_sentinels,
            is_sentinel_fn=is_sentinel_option
        )


class PlanFromPairsService:
    """
    Refatorado para reutilizar filter_options + combos.
    Aceita 'pairs' em qualquer profundidade do JSON.
    """
    def __init__(self, pairs_json_path: str | Path):
        p = Path(pairs_json_path)
        if not p.exists():
            raise FileNotFoundError(f"Arquivo pairs não encontrado: {p}")
        self._raw = json.loads(p.read_text(encoding="utf-8"))
        self._pairs = self._extract_pairs()

    def build(
        self,
        select1: Optional[str],
        pick1: Optional[str],
        limit1: Optional[int],
        select2: Optional[str],
        pick2: Optional[str],
        limit2_per_n1: Optional[int],
        max_combos: Optional[int],
        secao: str,
        date: str,
        defaults: Dict[str, Any],
        query: Optional[str],
        enable_level3: bool = False,
        select3: Optional[str] = None,
        pick3: Optional[str] = None,
        filter_sentinels: bool = True,
        **_
    ) -> Dict[str, Any]:

        # Construir mapa N1 -> lista de N2
        n1_map: Dict[str, Dict[str, Any]] = {}
        for pair in self._pairs:
            n1o = pair.get("n1Option") or {}
            n2opts = pair.get("n2Options") or []
            n1val = str(n1o.get("value") or n1o.get("text") or "")
            if not n1val:
                continue
            if n1val not in n1_map:
                n1_map[n1val] = {"n1": n1o, "n2raw": n2opts}

        # Filtrar N1
        all_n1 = [v["n1"] for v in n1_map.values()]
        n1_filtered = filter_options(
            all_n1,
            select_regex=select1,
            pick_list=pick1,
            limit=limit1,
            drop_sentinels=filter_sentinels,
            is_sentinel_fn=is_sentinel_option
        )

        # Para cada N1, filtrar N2 e gerar combos
        combos: List[Dict[str, Any]] = []
        for n1o in n1_filtered:
            n1val = n1o.get("value") or n1o.get("text")
            if not n1val:
                continue
            base_n2 = n1_map.get(str(n1val), {}).get("n2raw", [])
            n2_filtered = filter_options(
                base_n2,
                select_regex=select2,
                pick_list=pick2,
                limit=limit2_per_n1,
                drop_sentinels=filter_sentinels,
                is_sentinel_fn=is_sentinel_option
            )
            # N3 futuro
            for n2o in n2_filtered:
                combos.append({
                    "key1": n1o.get("value"),
                    "label1": n1o.get("text"),
                    "key2": n2o.get("value"),
                    "label2": n2o.get("text"),
                })
                if max_combos and len(combos) >= max_combos:
                    break
            if max_combos and len(combos) >= max_combos:
                break

        logger.info("PlanFromPairsService combos=%s", len(combos))
        return build_combos_plan(date, secao, defaults, query, combos)

    def _extract_pairs(self) -> List[Dict[str, Any]]:
        # Busca direta comum
        data = self._raw.get("data")
        if isinstance(data, dict) and isinstance(data.get("pairs"), list) and _looks_like_pairs_list(data["pairs"]):
            return data["pairs"]
        if isinstance(self._raw.get("pairs"), list) and _looks_like_pairs_list(self._raw["pairs"]):
            return self._raw["pairs"]

        # Busca profunda
        found: List[List[Dict[str, Any]]] = []
        _deep_find_pairs_lists(self._raw, found)
        if found:
            # escolha a maior lista válida
            best = max(found, key=lambda lst: len(lst))
            return best

        raise RuntimeError("Pairs JSON sem lista 'pairs'.")
