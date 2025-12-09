"""
Plan Editor UI module for SnapTrack DOU.

This module provides UI components for building, editing, and managing
DOU scraping plans in the Streamlit interface.
"""
from __future__ import annotations

import json
import time
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from dou_snaptrack.ui.state import PlanState, ensure_dirs, ensure_state

if TYPE_CHECKING:
    pass

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
    from dou_snaptrack.ui.pages.dou_fetch import fetch_n1_options
    return fetch_n1_options


def _get_default_fetch_n2_func():
    """Lazy loader for default fetch_n2_options function."""
    from dou_snaptrack.ui.pages.dou_fetch import fetch_n2_options
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


@st.fragment
def render_plan_discovery(
    fetch_n1_func=None,
    fetch_n2_func=None,
    secao: str = None,
    date: str = None,
) -> None:
    """Render the plan discovery section (N1/N2 selection).
    
    This function is decorated with @st.fragment to enable isolated reruns,
    improving performance by not reloading the entire page when user interacts
    with this section.
    
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

    # Callback para auto-carregar N2 quando N1 muda
    def _on_n1_change():
        """Auto-fetch N2 options when N1 selection changes."""
        selected_n1 = st.session_state.get("sel_n1_live")
        if selected_n1:
            # Marcar que precisamos carregar N2
            st.session_state["_pending_n2_fetch"] = selected_n1

    # Load N1 button
    if st.button("Carregar Órgãos"):
        with st.spinner("Obtendo lista de Órgãos do DOU…"):
            fetch_refresh = st.session_state.get("plan_fetch_refresh_token", 0.0)
            n1_candidates = fetch_n1_func(secao, date, refresh_token=fetch_refresh)
        st.session_state["live_n1"] = n1_candidates
        # Limpar seleção anterior
        st.session_state.pop("_pending_n2_fetch", None)
        for key in list(st.session_state.keys()):
            if key.startswith("live_n2_for_"):
                del st.session_state[key]

    n1_list = st.session_state.get("live_n1", [])
    if n1_list:
        # Selectbox com callback para auto-carregar N2
        n1 = st.selectbox(
            "Órgão",
            n1_list,
            key="sel_n1_live",
            on_change=_on_n1_change,
        )

        # Auto-fetch N2 se houver mudança pendente
        pending_n1 = st.session_state.get("_pending_n2_fetch")
        n2_cache_key = f"live_n2_for_{n1}"

        # Carregar N2 automaticamente se:
        # 1. Há uma mudança pendente E
        # 2. Ainda não temos N2 cached para este N1
        if pending_n1 and pending_n1 == n1 and n2_cache_key not in st.session_state:
            with st.spinner(f"Carregando suborganizações de '{n1}'…"):
                fetch_refresh = st.session_state.get("plan_fetch_refresh_token", 0.0)
                n2_list = fetch_n2_func(secao, date, str(n1), limit2=None, refresh_token=fetch_refresh)
            st.session_state[n2_cache_key] = n2_list
            st.session_state.pop("_pending_n2_fetch", None)
            if n2_list:
                st.caption(f"✅ {len(n2_list)} suborganizações encontradas.")
            else:
                st.caption("ℹ️ Nenhuma suborganização encontrada (use 'Órgão sem Suborganizações').")
    else:
        n1 = None
        st.info("Clique em 'Carregar Órgãos' para listar os órgãos disponíveis.")

    # Get cached N2 list
    n2_list: list[str] = []
    if n1:
        n2_list = st.session_state.get(f"live_n2_for_{n1}", [])

    # Botão manual para recarregar N2 (caso precise forçar refresh)
    col_n2_actions = st.columns([3, 1])
    with col_n2_actions[1]:
        if st.button("↻", key="refresh_n2_btn", help="Recarregar suborganizações", disabled=not n1):
            if n1:
                with st.spinner("Recarregando…"):
                    fetch_refresh = time.time()  # Force refresh
                    n2_list = fetch_n2_func(secao, date, str(n1), limit2=None, refresh_token=fetch_refresh)
                st.session_state[f"live_n2_for_{n1}"] = n2_list
                st.rerun()

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


@st.fragment
def render_plan_loader() -> None:
    """Render the saved plan loader section.
    
    This function is decorated with @st.fragment to enable isolated reruns,
    avoiding full page reloads when loading saved plans.
    """
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
                        
                        # Reset pagina do editor
                        st.session_state["plan_editor_page"] = 0

                        st.success(f"Plano '{selected_plan.stem}' carregado com {len(plan.combos)} combos!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao carregar plano: {e}")

            with col_info:
                meta = plan_entries[selected_idx]
                st.caption(f"📅 Data: {meta.get('data') or 'N/A'}")
                st.caption(f"📰 Seção: {meta.get('secao') or 'N/A'}")
                st.caption(f"📦 Combos: {meta.get('combos', 0)}")
                size_kb = meta.get("size_kb")
                if size_kb is not None:
                    st.caption(f"💾 Tamanho: {size_kb} KB")


def render_plan_editor_table() -> None:
    """Render the combo editor table with pagination - versao moderna e limpa."""
    import pandas as pd

    plan = PlanEditorSession.get_plan()

    if not plan.combos:
        st.info("Nenhum combo no plano. Adicione combos ou carregue um plano salvo.")
        return

    num_combos = len(plan.combos)
    
    # CSS customizado para visual moderno
    st.markdown("""
    <style>
    .pagination-container {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 8px;
        padding: 12px 0;
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        border-radius: 10px;
        margin: 10px 0;
    }
    .page-info {
        font-weight: 600;
        color: #1f2937;
        padding: 0 16px;
    }
    .combo-count {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 14px;
        display: inline-block;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<span class="combo-count">{num_combos} combos no plano</span>', unsafe_allow_html=True)

    # Pagination setup
    use_pagination = num_combos > COMBOS_PER_PAGE

    if use_pagination:
        if "plan_editor_page" not in st.session_state:
            st.session_state.plan_editor_page = 0

        total_pages = (num_combos + COMBOS_PER_PAGE - 1) // COMBOS_PER_PAGE
        current_page = st.session_state.plan_editor_page

        if current_page >= total_pages:
            current_page = total_pages - 1
            st.session_state.plan_editor_page = current_page
        if current_page < 0:
            current_page = 0
            st.session_state.plan_editor_page = 0

        # Paginacao moderna
        col1, col2, col3, col4, col5 = st.columns([1, 1, 3, 1, 1])
        
        with col1:
            st.button("⏮", key="pg_first", disabled=current_page == 0, 
                     on_click=lambda: st.session_state.update({"plan_editor_page": 0}),
                     use_container_width=True)
        with col2:
            st.button("◀", key="pg_prev", disabled=current_page == 0,
                     on_click=lambda: st.session_state.update({"plan_editor_page": current_page - 1}),
                     use_container_width=True)
        with col3:
            st.markdown(
                f'<div style="text-align:center;padding:8px;background:#f0f2f6;border-radius:8px;">'
                f'<b>{current_page + 1}</b> / {total_pages}</div>',
                unsafe_allow_html=True
            )
        with col4:
            st.button("▶", key="pg_next", disabled=current_page >= total_pages - 1,
                     on_click=lambda: st.session_state.update({"plan_editor_page": current_page + 1}),
                     use_container_width=True)
        with col5:
            st.button("⏭", key="pg_last", disabled=current_page >= total_pages - 1,
                     on_click=lambda: st.session_state.update({"plan_editor_page": total_pages - 1}),
                     use_container_width=True)

        start_idx = current_page * COMBOS_PER_PAGE
        end_idx = min(start_idx + COMBOS_PER_PAGE, num_combos)
        combos_slice = plan.combos[start_idx:end_idx]
        page_offset = start_idx
    else:
        combos_slice = plan.combos
        page_offset = 0
        start_idx = 0
        end_idx = num_combos

    # Tabela com checkboxes usando data_editor simplificado
    rows = []
    for local_idx, combo in enumerate(combos_slice):
        global_idx = page_offset + local_idx
        orgao_label = _resolve_combo_label(combo, "label1", "key1")
        sub_label = _resolve_combo_label(combo, "label2", "key2")
        rows.append({
            "Sel": False,
            "ID": global_idx,
            "Orgao": orgao_label,
            "Sub-orgao": sub_label,
        })

    df_display = pd.DataFrame(rows)

    # Editor com checkboxes
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=min(450, 38 * len(rows) + 40),
        column_config={
            "Sel": st.column_config.CheckboxColumn(
                "",
                help="Marque para remover",
                width="small",
                default=False,
            ),
            "ID": st.column_config.NumberColumn(
                "ID",
                width="small",
                disabled=True,
            ),
            "Orgao": st.column_config.TextColumn(
                "Orgao",
                width="large",
                disabled=True,
            ),
            "Sub-orgao": st.column_config.TextColumn(
                "Sub-orgao", 
                width="large",
                disabled=True,
            ),
        },
        disabled=["ID", "Orgao", "Sub-orgao"],
        key=f"combo_editor_{page_offset}_{len(combos_slice)}",
    )

    # Contar selecionados
    selected_count = int(edited_df["Sel"].sum()) if "Sel" in edited_df.columns else 0
    
    st.markdown("---")
    
    # Botao unico de acao
    col_btn, col_info = st.columns([2, 3])
    
    with col_btn:
        btn_text = f"Remover {selected_count} selecionado(s)" if selected_count > 0 else "Salvar alteracoes"
        btn_type = "primary"
        
        if st.button(btn_text, use_container_width=True, type=btn_type):
            if selected_count > 0:
                # Remover selecionados
                ids_to_remove = set()
                for _, row in edited_df.iterrows():
                    if row["Sel"]:
                        ids_to_remove.add(int(row["ID"]))
                
                new_combos = [
                    combo for i, combo in enumerate(plan.combos)
                    if i not in ids_to_remove
                ]
                st.session_state.plan.combos = new_combos
                
                # Ajustar pagina se necessario
                new_total = len(new_combos)
                if new_total > 0 and use_pagination:
                    new_total_pages = (new_total + COMBOS_PER_PAGE - 1) // COMBOS_PER_PAGE
                    if st.session_state.plan_editor_page >= new_total_pages:
                        st.session_state.plan_editor_page = max(0, new_total_pages - 1)
                
                st.toast(f"{selected_count} combo(s) removido(s)!", icon="✅")
            else:
                # Salvar no arquivo
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
                        st.toast("Plano salvo com sucesso!", icon="💾")
                        st.session_state["plan_list_refresh_token"] = time.time()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.toast("Salvo em memoria. Use 'Salvar Plano' abaixo para persistir.", icon="💾")
            st.rerun()
    
    with col_info:
        if selected_count > 0:
            st.warning(f"⚠️ {selected_count} combo(s) marcado(s) para remocao")
        elif use_pagination:
            st.caption(f"Exibindo {start_idx + 1}-{end_idx} de {num_combos}")


def render_plan_saver() -> None:
    """Render the plan saver section."""
    st.divider()
    st.subheader("💾 Salvar Plano")

    plans_dir, _ = ensure_dirs()
    plan = PlanEditorSession.get_plan()

    # Nome sugerido baseado na data do plano (sem path nem extensão)
    suggested_name = f"plan_{str(plan.date or '').replace('/', '-').replace(' ', '_')}"
    plan_name_input = st.text_input(
        "Nome do arquivo",
        suggested_name,
        help="Apenas o nome do arquivo (sem extensão). Será salvo em 'planos/' como .json"
    )

    # Sanitizar: remover caracteres inválidos e extensões que o usuário possa ter digitado
    import re
    clean_name = re.sub(r'[<>:"/\\|?*]', '_', plan_name_input.strip())
    # Remover extensão se usuário digitou
    if clean_name.lower().endswith('.json'):
        clean_name = clean_name[:-5]
    clean_name = clean_name.strip() or "plano_sem_nome"

    # Mostrar caminho final
    final_path = plans_dir / f"{clean_name}.json"
    st.caption(f"📁 Será salvo em: `{final_path}`")

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

        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Plano salvo em {final_path}")
        st.session_state["plan_list_refresh_token"] = time.time()


# Backward compatibility exports
list_saved_plan_files = _list_saved_plan_files
build_combos = _build_combos
resolve_combo_label = _resolve_combo_label
