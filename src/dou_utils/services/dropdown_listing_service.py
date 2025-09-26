from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..page_utils import goto as _goto, try_visualizar_em_lista, find_best_frame
from ..core.dropdown_discovery import discover_dropdown_roots, DropdownRoot
from ..core.dropdown_actions import (
    collect_native_options,
    ensure_open_then_collect_custom,
    select_by_text,
    select_by_value,
)
from ..core.polling import wait_repopulation


@dataclass
class ListLevelParams:
    date: str
    secao: str
    level: int
    key1: Optional[str] = None
    key1_type: Optional[str] = None
    key2: Optional[str] = None
    key2_type: Optional[str] = None
    label1: Optional[str] = None
    label2: Optional[str] = None
    label3: Optional[str] = None


class DropdownListingService:
    def __init__(self, context):
        self.context = context

    def list_level(self, params: ListLevelParams) -> Dict[str, Any]:
        page = self.context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)
        try:
            url = f"https://www.in.gov.br/leiturajornal?data={params.date}&secao={params.secao}"
            _goto(page, url)
            try_visualizar_em_lista(page)
            frame = find_best_frame(self.context)

            def _resolve(roots: List[DropdownRoot], label_regex: Optional[str], fallback_index: int) -> Optional[DropdownRoot]:
                import re
                if label_regex:
                    try:
                        pat = re.compile(label_regex, re.I)
                        for r in roots:
                            if r.label and pat.search(r.label):
                                return r
                    except re.error:
                        pass
                if len(roots) > fallback_index:
                    return roots[fallback_index]
                return roots[0] if roots else None

            # Descobrir roots atuais
            roots1 = discover_dropdown_roots(frame)
            if not roots1:
                return {"ok": False, "level": params.level, "reason": "no_roots"}

            r1 = _resolve(roots1, params.label1, 0)
            lab1 = r1.label if r1 else ""
            opts1 = (
                collect_native_options(r1.handle) if r1 and r1.kind == "select"
                else (ensure_open_then_collect_custom(frame, r1.handle) if r1 else [])
            )

            if params.level == 1:
                return {"ok": True, "level": 1, "label": lab1, "options": opts1}

            # Seleciona N1
            if not (params.key1 and params.key1_type and r1 and self._select_simple(frame, r1, params.key1, params.key1_type)):
                return {"ok": False, "level": 1, "label1": lab1, "reason": "select_n1_failed"}

            # Re-descobrir roots para N2
            roots2 = discover_dropdown_roots(frame)
            r2 = _resolve(roots2, params.label2, 1)
            if not r2:
                return {"ok": False, "level": 2, "label1": lab1, "reason": "no_root_n2"}

            prev2 = len(collect_native_options(r2.handle) if r2.kind == "select" else [])
            if prev2:
                wait_repopulation(frame, r2.handle, prev2, timeout_ms=15_000, poll_interval_ms=250)
            opts2 = (
                collect_native_options(r2.handle) if r2.kind == "select"
                else ensure_open_then_collect_custom(frame, r2.handle)
            )
            lab2 = r2.label or ""

            if params.level == 2:
                return {"ok": True, "level": 2, "label1": lab1, "label2": lab2, "options": opts2}

            # N3 (se solicitado)
            if not (params.key2 and params.key2_type and self._select_simple(frame, r2, params.key2, params.key2_type)):
                return {"ok": False, "level": 2, "label1": lab1, "label2": lab2, "reason": "select_n2_failed"}

            # Após selecionar N2, buscar N3
            roots3 = discover_dropdown_roots(frame)
            # Excluir handles já usados
            ex_handles = {id(r1.handle)}
            ex_handles.add(id(r2.handle))
            rest3 = [r for r in roots3 if id(r.handle) not in ex_handles]
            r3 = _resolve(rest3, params.label3, 2)
            if not r3:
                return {"ok": False, "level": 3, "label1": lab1, "label2": lab2, "reason": "no_root_n3"}

            prev3 = len(collect_native_options(r3.handle) if r3.kind == "select" else [])
            if prev3:
                wait_repopulation(frame, r3.handle, prev3, timeout_ms=15_000, poll_interval_ms=250)
            opts3 = (
                collect_native_options(r3.handle) if r3.kind == "select"
                else ensure_open_then_collect_custom(frame, r3.handle)
            )
            lab3 = r3.label or ""

            return {"ok": True, "level": 3, "label1": lab1, "label2": lab2, "label3": lab3, "options": opts3}
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _select_simple(self, frame, root: DropdownRoot, key: str, key_type: str) -> bool:
        """Seleção simples suficiente para o fluxo de listagem.
        - Para <select>: suporta value e text; fallback para text.
        - Para custom: tenta abrir e clicar opção por texto exato.
        """
        try:
            if root.kind == "select":
                if key_type == "value":
                    return select_by_value(root.handle, str(key))
                # default text
                return select_by_text(root.handle, str(key))

            # Custom: abrir e clicar opção por texto
            ensure_open_then_collect_custom(frame, root.handle)
            try:
                opt = frame.get_by_role("option", name=str(key)).first
                if opt and opt.count() > 0 and opt.is_visible():
                    opt.click(timeout=4000)
                    frame.page.wait_for_load_state("networkidle", timeout=60_000)
                    return True
            except Exception:
                pass
        except Exception:
            return False
        return False
