"""
Plan Editor UI module for SnapTrack DOU.

This module provides UI components for building, editing, and managing
DOU scraping plans in the Streamlit interface.
"""
from __future__ import annotations

import contextlib
import json
import time
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from dou_snaptrack.ui.state import PlanState, ensure_dirs, ensure_state

if TYPE_CHECKING:
    import pandas as pd

# Module-level logger
import logging
logger = logging.getLogger("dou_snaptrack.ui.plan_editor")

# Constants
COMBOS_PER_PAGE = 15


# ---------------------------------------------------------------------------
# Lazy import helpers for default fetch functions
# ---------------------------------------------------------------------------

def _get_default_fetch_n1_func():
    """Lazy loader for default fetch_n1_options function."""
    from dou_snaptrack.ui.dou_fetch import fetch_n1_options
    return fetch_n1_options


def _get_default_fetch_n2_func():
    """Lazy loader for default fetch_n2_options function."""
    from dou_snaptrack.ui.dou_fetch import fetch_n2_options
    return fetch_n2_options


def _resolve_combo_label(combo: dict, label_key: str, fallback_key: str) -> str:
    """Resolve label from combo dict, falling back to key if label is empty."""
    label = combo.get(label_key, "")
    if not label:
        label = combo.get(fallback_key, "")
    return str(label) if label else ""


def _build_combos(n1: str, n2_list: list[str], key_type: str = "text") -> list[dict[str, Any]]:
    """Build combo dictionaries from N1 and list of N2 values."""
    return [
        {
            "key1_type": key_type,
            "key1": n1,
            "key2_type": key_type,
            "key2": n2,
            "key3_type": None,
            "key3": None,
            "label1": n1,
            "label2": n2,
            "label3": "",
        }
        for n2 in n2_list
    ]


def _list_saved_plan_files(refresh_token: float = 0.0) -> list[dict[str, Any]]:
    """List saved plan files with metadata.
    
    Args:
        refresh_token: Cache invalidation token
        
    Returns:
        List of dicts with plan metadata (path, stem, combos, data, secao, etc.)
    """
    _ = refresh_token  # Used for cache invalidation
    plans_dir, _ = ensure_dirs()
    entries = []
    
    try:
        for p in sorted(plans_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                combos = data.get("combos", [])
                entries.append({
                    "path": str(p),
                    "stem": p.stem,
                    "combos": len(combos),
                    "data": data.get("data", ""),
                    "secao": data.get("secaoDefault", ""),
                    "size_kb": round(p.stat().st_size / 1024, 1),
                })
            except Exception:
                continue
    except Exception:
        pass
    
    return entries


class PlanEditorSession:
    """Manages plan editor session state."""
    
    @staticmethod
    def get_plan() -> PlanState:
        """Get current plan from session state."""
        ensure_state()
        return st.session_state.plan
    
    @staticmethod
    def add_combos(combos: list[dict[str, Any]]) -> None:
        """Add combos to current plan."""
        if combos:
            PlanEditorSession.get_plan().combos.extend(combos)
    
    @staticmethod
    def clear_combos() -> None:
        """Clear all combos from current plan."""
        PlanEditorSession.get_plan().combos = []
    
    @staticmethod
    def get_page() -> int:
        """Get current editor page."""
        if "plan_editor_page" not in st.session_state:
            st.session_state.plan_editor_page = 0
        return st.session_state.plan_editor_page
    
    @staticmethod
    def set_page(page: int) -> None:
        """Set current editor page."""
        st.session_state.plan_editor_page = max(0, page)


def render_plan_discovery(
    fetch_n1_func=None,
    fetch_n2_func=None,
    secao: str = None,
    date: str = None,
) -> None:
    """Render the plan discovery section (N1/N2 selection).
    
    Args:
        fetch_n1_func: Function to fetch N1 options (optional, defaults to dou_fetch.fetch_n1_options)
        fetch_n2_func: Function to fetch N2 options (optional, defaults to dou_fetch.fetch_n2_options)
        secao: Current section (DO1, DO2, DO3) - if None, reads from session state
        date: Current date string - if None, reads from session state
    """
    # Resolve defaults
    if fetch_n1_func is None:
        fetch_n1_func = _get_default_fetch_n1_func()
    if fetch_n2_func is None:
        fetch_n2_func = _get_default_fetch_n2_func()
    if secao is None:
        secao = str(st.session_state.plan.secao or "")
    if date is None:
        date = str(st.session_state.plan.date or "")
    
    st.subheader("Monte sua Pesquisa")
    
    # Load N1 button
    if st.button("Carregar"):
        with st.spinner("Obtendo lista de Órgãos do DOU…"):
            fetch_refresh = st.session_state.get("plan_fetch_refresh_token", 0.0)
            n1_candidates = fetch_n1_func(secao, date, refresh_token=fetch_refresh)
        st.session_state["live_n1"] = n1_candidates

    n1_list = st.session_state.get("live_n1", [])
    if n1_list:
        n1 = st.selectbox("Órgão", n1_list, key="sel_n1_live")
    else:
        n1 = None
        st.info("Clique em 'Carregar' para listar os órgãos.")

    # Load N2 based on N1
    n2_list: list[str] = []
    can_load_n2 = bool(n1)
    
    if st.button("Carregar Organizações Subordinadas (todas)") and can_load_n2:
        with st.spinner("Obtendo lista completa do DOU…"):
            fetch_refresh = st.session_state.get("plan_fetch_refresh_token", 0.0)
            n2_list = fetch_n2_func(secao, date, str(n1), limit2=None, refresh_token=fetch_refresh)
        st.session_state["live_n2_for_" + str(n1)] = n2_list
        st.caption(f"{len(n2_list)} suborganizações encontradas para '{n1}'.")
    
    if n1:
        n2_list = st.session_state.get("live_n2_for_" + str(n1), [])

    sel_n2 = st.multiselect("Organização Subordinada", options=n2_list)
    
    cols_add = st.columns(2)
    with cols_add[0]:
        if st.button("Adicionar ao plano", disabled=not (n1 and sel_n2)):
            add = _build_combos(str(n1), sel_n2)
            PlanEditorSession.add_combos(add)
            st.success(f"Adicionados {len(add)} combos ao plano.")
    
    with cols_add[1]:
        add_n1_only = n1 and not n2_list
        if st.button("Orgão sem Suborganizações", disabled=not add_n1_only):
            add = _build_combos(str(n1), ["Todos"])
            PlanEditorSession.add_combos(add)
            st.success("Adicionado N1 com N2='Todos'.")


def render_plan_loader() -> None:
    """Render the saved plan loader section."""
    with st.expander("📂 Carregar Plano Salvo para Editar"):
        plans_dir, _ = ensure_dirs()
        refresh_token = st.session_state.get("plan_list_refresh_token", 0.0)
        
        head_actions = st.columns([3, 1])
        with head_actions[1]:
            if st.button("↻ Atualizar", key="refresh_plan_editor", help="Recarrega a lista de planos salvos"):
                st.session_state["plan_list_refresh_token"] = time.time()
                st.rerun()

        plan_entries = _list_saved_plan_files(refresh_token)

        if not plan_entries:
            st.info("Nenhum plano salvo disponível.")
        else:
            labels = [f"{entry['stem']} ({entry['combos']} combos)" for entry in plan_entries]

            selected_idx = st.selectbox(
                "Selecione um plano para editar:",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key="edit_plan_selector"
            )

            col_load, col_info = st.columns([1, 2])
            
            with col_load:
                if st.button("📥 Carregar para Edição", use_container_width=True):
                    try:
                        selected_plan = Path(plan_entries[selected_idx]["path"])
                        cfg = json.loads(selected_plan.read_text(encoding="utf-8"))

                        plan = PlanEditorSession.get_plan()
                        plan.date = cfg.get("data", _date.today().strftime("%d-%m-%Y"))
                        plan.secao = cfg.get("secaoDefault", "DO1")
                        plan.combos = cfg.get("combos", [])
                        plan.defaults = cfg.get("defaults", {
                            "scrape_detail": False,
                            "summary_lines": 0,
                            "summary_mode": "center",
                        })

                        plan_name = cfg.get("plan_name", selected_plan.stem)
                        st.session_state["plan_name_ui"] = plan_name
                        st.session_state["loaded_plan_path"] = str(selected_plan)

                        st.success(f"✅ Plano '{selected_plan.stem}' carregado com {len(plan.combos)} combos!")
                    except Exception as e:
                        st.error(f"❌ Erro ao carregar plano: {e}")

            with col_info:
                meta = plan_entries[selected_idx]
                st.caption(f"📅 Data: {meta.get('data') or 'N/A'}")
                st.caption(f"📰 Seção: {meta.get('secao') or 'N/A'}")
                st.caption(f"📦 Combos: {meta.get('combos', 0)}")
                size_kb = meta.get("size_kb")
                if size_kb is not None:
                    st.caption(f"💾 Tamanho: {size_kb} KB")


def render_plan_editor_table() -> None:
    """Render the combo editor table with pagination."""
    import pandas as pd
    
    st.markdown("#### 📋 Plano Atual")

    plan = PlanEditorSession.get_plan()
    
    if not plan.combos:
        st.info("📭 Nenhum combo no plano. Use as opções acima para adicionar combos ou carregar um plano salvo.")
        return

    num_combos = len(plan.combos)
    st.caption(f"Total: **{num_combos} combos**")

    # Pagination setup
    use_pagination = num_combos > COMBOS_PER_PAGE

    if use_pagination:
        if "plan_editor_page" not in st.session_state:
            st.session_state.plan_editor_page = 0

        total_pages = (num_combos + COMBOS_PER_PAGE - 1) // COMBOS_PER_PAGE
        current_page = st.session_state.plan_editor_page

        # Ensure valid page
        if current_page >= total_pages:
            current_page = total_pages - 1
            st.session_state.plan_editor_page = current_page
        if current_page < 0:
            current_page = 0
            st.session_state.plan_editor_page = 0

        # Pagination controls
        st.markdown(f"**Página {current_page + 1} de {total_pages}** ({COMBOS_PER_PAGE} combos por página)")

        nav_cols = st.columns([1, 1, 2, 1, 1])
        with nav_cols[0]:
            if st.button("⏮️ Início", disabled=current_page == 0, key="plan_page_first"):
                st.session_state.plan_editor_page = 0
                st.rerun()
        with nav_cols[1]:
            if st.button("◀️ Anterior", disabled=current_page == 0, key="plan_page_prev"):
                st.session_state.plan_editor_page = current_page - 1
                st.rerun()
        with nav_cols[2]:
            page_options = list(range(1, total_pages + 1))
            selected_page = st.selectbox(
                "Ir para página:",
                page_options,
                index=current_page,
                key="plan_page_selector",
                label_visibility="collapsed"
            )
            if selected_page - 1 != current_page:
                st.session_state.plan_editor_page = selected_page - 1
                st.rerun()
        with nav_cols[3]:
            if st.button("▶️ Próxima", disabled=current_page >= total_pages - 1, key="plan_page_next"):
                st.session_state.plan_editor_page = current_page + 1
                st.rerun()
        with nav_cols[4]:
            if st.button("⏭️ Fim", disabled=current_page >= total_pages - 1, key="plan_page_last"):
                st.session_state.plan_editor_page = total_pages - 1
                st.rerun()

        # Calculate slice indices
        start_idx = current_page * COMBOS_PER_PAGE
        end_idx = min(start_idx + COMBOS_PER_PAGE, num_combos)
        combos_slice = plan.combos[start_idx:end_idx]
        page_offset = start_idx
    else:
        combos_slice = plan.combos
        page_offset = 0
        current_page = 0
        total_pages = 1
        start_idx = 0
        end_idx = num_combos

    # Build display data
    display_data = []
    for local_idx, combo in enumerate(combos_slice):
        global_idx = page_offset + local_idx
        orgao_label = _resolve_combo_label(combo, "label1", "key1")
        sub_label = _resolve_combo_label(combo, "label2", "key2")
        display_data.append({
            "Remover?": False,
            "ID": global_idx,
            "Órgão": orgao_label,
            "Sub-órgão": sub_label,
        })

    df_display = pd.DataFrame(display_data)

    # Editable table
    editor_key = f"plan_combos_editor_{st.session_state.get('loaded_plan_path', 'new')}_{current_page}_{len(combos_slice)}"
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Remover?": st.column_config.CheckboxColumn(
                "Remover?",
                help="Marque para remover este combo",
                default=False,
                width="small"
            ),
            "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "Órgão": st.column_config.TextColumn("Órgão", width="large"),
            "Sub-órgão": st.column_config.TextColumn("Sub-órgão", width="large"),
        },
        hide_index=True,
        key=editor_key,
        disabled=["ID"]
    )

    if use_pagination:
        st.caption(f"📄 Mostrando combos {start_idx + 1} a {end_idx} de {num_combos}")

    # Action buttons
    st.markdown("**Ações:**")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Salvar Edições", use_container_width=True, type="primary",
                    help="Aplica as mudanças de texto da página atual"):
            all_combos = plan.combos.copy()
            for _, row in edited_df.iterrows():
                global_idx = int(row["ID"])
                if 0 <= global_idx < len(all_combos):
                    all_combos[global_idx]["label1"] = row["Órgão"]
                    all_combos[global_idx]["label2"] = row["Sub-órgão"]
            st.session_state.plan.combos = all_combos

            loaded_path = st.session_state.get("loaded_plan_path")
            if loaded_path:
                try:
                    cfg_to_save = {
                        "data": plan.date,
                        "secaoDefault": plan.secao,
                        "defaults": plan.defaults,
                        "combos": plan.combos,
                        "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"},
                    }
                    _pname = st.session_state.get("plan_name_ui")
                    if isinstance(_pname, str) and _pname.strip():
                        cfg_to_save["plan_name"] = _pname.strip()
                    Path(loaded_path).write_text(json.dumps(cfg_to_save, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success("✅ Edições salvas no arquivo!")
                    st.session_state["plan_list_refresh_token"] = time.time()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar no arquivo: {e}")
            else:
                st.success("✅ Edições salvas (em memória)! Use 'Salvar plano' para persistir em arquivo.")
            st.rerun()

    with col2:
        selected_count = int(edited_df["Remover?"].sum())
        btn_label = f"🗑️ Remover Marcados ({selected_count})"
        if st.button(btn_label, use_container_width=True, disabled=selected_count == 0,
                    help="Remove combos marcados nesta página"):
            ids_to_remove = set()
            for _, row in edited_df.iterrows():
                if row["Remover?"]:
                    ids_to_remove.add(int(row["ID"]))

            new_combos = [
                combo for i, combo in enumerate(plan.combos)
                if i not in ids_to_remove
            ]
            st.session_state.plan.combos = new_combos

            new_total = len(new_combos)
            if use_pagination and new_total > 0:
                new_total_pages = (new_total + COMBOS_PER_PAGE - 1) // COMBOS_PER_PAGE
                if st.session_state.plan_editor_page >= new_total_pages:
                    st.session_state.plan_editor_page = max(0, new_total_pages - 1)

            st.success(f"✅ {selected_count} combo(s) removido(s)")
            st.rerun()

    with col3:
        if st.button("🗑️ Limpar Tudo", use_container_width=True, help="Remove TODOS os combos"):
            PlanEditorSession.clear_combos()
            st.session_state.plan_editor_page = 0
            st.success("🗑️ Plano limpo")
            st.rerun()


def render_plan_saver() -> None:
    """Render the plan saver section."""
    st.divider()
    st.subheader("💾 Salvar Plano")
    
    plans_dir, _ = ensure_dirs()
    plan = PlanEditorSession.get_plan()
    
    suggested = plans_dir / f"plan_{str(plan.date or '').replace('/', '-').replace(' ', '_')}.json"
    plan_path = st.text_input("Salvar como", str(suggested))
    
    if st.button("Salvar plano"):
        cfg = {
            "data": plan.date,
            "secaoDefault": plan.secao,
            "defaults": plan.defaults,
            "combos": plan.combos,
            "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"},
        }
        _pname = st.session_state.get("plan_name_ui")
        if isinstance(_pname, str) and _pname.strip():
            cfg["plan_name"] = _pname.strip()
        
        ppath = Path(plan_path)
        ppath.parent.mkdir(parents=True, exist_ok=True)
        ppath.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Plano salvo em {plan_path}")
        st.session_state["plan_list_refresh_token"] = time.time()


# Backward compatibility exports
list_saved_plan_files = _list_saved_plan_files
build_combos = _build_combos
resolve_combo_label = _resolve_combo_label
