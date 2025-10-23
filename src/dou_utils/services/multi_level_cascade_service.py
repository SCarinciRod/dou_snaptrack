"""
multi_level_cascade_service.py
Orquestra seleção hierárquica N1 -> N2 -> (N3 opcional) antes da coleta de links.

Requer que o frame já esteja posicionado na página correta (edição / seção).
Usa selection_utils + dropdown_strategies para seleção robusta e espera de repopulação.

Fluxo:
 1. Resolve roots (heurística simples combobox/select).
 2. Seleciona N1 (key1/key1_type).
 3. Aguarda repopulação e re-resolve N2.
 4. Seleciona N2.
 5. (Opcional) Repete para N3.
 6. Retorna metadados com sucesso/falhas.

Compatível com combos vindos de expand_batch_config contendo:
  key1_type, key1, key2_type, key2, (opcional) key3_type, key3
  label1/label2/label3 (podem auxiliar heurística)
"""

from __future__ import annotations

import re
from typing import Any

from ..log_utils import get_logger
from ..selection_utils import read_rich_options, select_option_robust, wait_repopulation

logger = get_logger(__name__)


class MultiLevelCascadeSelector:
    def __init__(self, frame):
        self.frame = frame

    def run(
        self,
        key1: str,
        key1_type: str,
        key2: str,
        key2_type: str,
        label1: str | None = None,
        label2: str | None = None,
        key3: str | None = None,
        key3_type: str | None = None,
        label3: str | None = None,
        repop_timeout_ms: int = 15_000,
        repop_poll_ms: int = 250
    ) -> dict[str, Any]:
        """
        Executa seleção hierárquica. Retorna dicionário:
          {
            "ok": bool,
            "level_fail": (None|1|2|3),
            "selected": { "key1":..., "key2":..., "key3":... },
            "labels": { "label1":..., "label2":..., "label3":... }
          }
        """
        roots_initial = self._discover_roots()
        if len(roots_initial) < 2:
            return {"ok": False, "level_fail": 1, "selected": {}, "labels": {}}

        r1 = self._resolve_root(roots_initial, label1, fallback_index=0)
        if not r1:
            return {"ok": False, "level_fail": 1, "selected": {}, "labels": {}}

        if not select_option_robust(self.frame, r1["handle"], key1, key1_type):
            return {
                "ok": False,
                "level_fail": 1,
                "selected": {"key1": key1},
                "labels": {"label1": r1.get("label")}
            }

        # Re-resolve N2
        roots_after_n1 = self._discover_roots()
        r2 = self._resolve_root(roots_after_n1, label2, fallback_index=1)
        if not r2:
            return {
                "ok": False,
                "level_fail": 2,
                "selected": {"key1": key1},
                "labels": {"label1": r1.get("label")}
            }

        prev_n2 = len(read_rich_options(self.frame, r2["handle"]))
        wait_repopulation(self.frame, r2["handle"], prev_n2, timeout_ms=repop_timeout_ms, poll_interval_ms=repop_poll_ms)

        if not select_option_robust(self.frame, r2["handle"], key2, key2_type):
            return {
                "ok": False,
                "level_fail": 2,
                "selected": {"key1": key1, "key2": key2},
                "labels": {"label1": r1.get("label"), "label2": r2.get("label")}
            }

        labels = {"label1": r1.get("label"), "label2": r2.get("label")}
        selected = {"key1": key1, "key2": key2}

        # N3 opcional
        if key3 and key3_type:
            roots_after_n2 = self._discover_roots()
            # heurística: tentar achar root diferente dos já usados
            r3 = self._resolve_root_excluding(roots_after_n2, label3, exclude=[r1, r2], fallback_index=2)
            if not r3:
                return {
                    "ok": False,
                    "level_fail": 3,
                    "selected": selected,
                    "labels": labels
                }

            prev_n3 = len(read_rich_options(self.frame, r3["handle"]))
            wait_repopulation(self.frame, r3["handle"], prev_n3, timeout_ms=repop_timeout_ms, poll_interval_ms=repop_poll_ms)

            if not select_option_robust(self.frame, r3["handle"], key3, key3_type):
                return {
                    "ok": False,
                    "level_fail": 3,
                    "selected": {**selected, "key3": key3},
                    "labels": {**labels, "label3": r3.get("label")}
                }

            labels["label3"] = r3.get("label")
            selected["key3"] = key3

        return {
            "ok": True,
            "level_fail": None,
            "selected": selected,
            "labels": labels
        }

    # ----------------- Helpers internos -----------------
    def _discover_roots(self):
        roots = []
        seen = set()
        cb = self.frame.get_by_role("combobox")
        try:
            c = cb.count()
        except Exception:
            c = 0
        for i in range(min(c, 60)):
            h = cb.nth(i)
            try:
                box = h.bounding_box()
                if not box:
                    continue
                key = ("cb", i, round(box["y"], 2), round(box["x"], 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({"handle": h, "kind": "combobox", "label": self._label_of(h)})
            except Exception:
                continue
        sel = self.frame.locator("select")
        try:
            s = sel.count()
        except Exception:
            s = 0
        for i in range(min(s, 60)):
            h = sel.nth(i)
            try:
                box = h.bounding_box()
                if not box:
                    continue
                key = ("select", i, round(box["y"], 2), round(box["x"], 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({"handle": h, "kind": "select", "label": self._label_of(h)})
            except Exception:
                continue
        return roots

    def _label_of(self, locator):
        try:
            aria = locator.get_attribute("aria-label")
            if aria:
                return aria.strip()
        except Exception:
            pass
        try:
            _id = locator.get_attribute("id")
            if _id:
                lab = self.frame.evaluate(
                    """
                    (id) => {
                        const l = document.querySelector(`label[for="${id}"]`);
                        return l ? l.textContent.trim() : null;
                    }
                    """,
                    _id
                )
                if lab:
                    return lab
        except Exception:
            pass
        try:
            prev = locator.locator("xpath=preceding::label[1]").first
            if prev and prev.count() > 0 and prev.is_visible():
                t = (prev.text_content() or "").strip()
                if t:
                    return t
        except Exception:
            pass
        return ""

    def _resolve_root(self, roots, label_regex: str | None, fallback_index: int):
        if label_regex:
            try:
                pat = re.compile(label_regex, re.I)
                for r in roots:
                    if r.get("label") and pat.search(r["label"]):
                        return r
            except re.error:
                pass
        if len(roots) > fallback_index:
            return roots[fallback_index]
        return roots[0] if roots else None

    def _resolve_root_excluding(self, roots, label_regex, exclude, fallback_index):
        ex_handles = {id(r["handle"]) for r in exclude if r}
        filtered = [r for r in roots if id(r["handle"]) not in ex_handles]
        return self._resolve_root(filtered, label_regex, fallback_index)
