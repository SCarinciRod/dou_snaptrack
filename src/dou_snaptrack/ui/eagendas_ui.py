"""
E-Agendas UI module for SnapTrack DOU.

This module provides UI components for the E-Agendas tab including
hierarchy selection, query management, and document generation.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from collections.abc import Callable
from datetime import date as _date, datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from dou_snaptrack.ui.state import EAgendasState, ensure_eagendas_state

if TYPE_CHECKING:
    pass

# Module-level logger
logger = logging.getLogger("dou_snaptrack.ui.eagendas_ui")


# Lazy import for fetch_hierarchy to avoid circular imports
def _get_default_fetch_hierarchy():
    """Get the default fetch_hierarchy function via lazy import."""
    from dou_snaptrack.ui.eagendas_fetch import fetch_hierarchy
    return fetch_hierarchy


class EAgendasSession:
    """Manages E-Agendas session state."""

    @staticmethod
    def get_state() -> EAgendasState:
        """Get current E-Agendas state from session."""
        ensure_eagendas_state()
        return st.session_state.eagendas

    @staticmethod
    def add_query(query: dict[str, Any]) -> None:
        """Add a query to saved queries."""
        state = EAgendasSession.get_state()
        state.saved_queries.append(query)

    @staticmethod
    def remove_query(idx: int) -> None:
        """Remove query at index."""
        state = EAgendasSession.get_state()
        if 0 <= idx < len(state.saved_queries):
            state.saved_queries.pop(idx)

    @staticmethod
    def clear_queries() -> None:
        """Clear all saved queries."""
        EAgendasSession.get_state().saved_queries = []

    @staticmethod
    def set_date_start(date_str: str) -> None:
        """Set start date."""
        EAgendasSession.get_state().date_start = date_str

    @staticmethod
    def set_date_end(date_str: str) -> None:
        """Set end date."""
        EAgendasSession.get_state().date_end = date_str


def _auto_fetch_n2_on_n1_change(fetch_func: Callable, n1_value: str, n2_options_key: str) -> None:
    """Auto-fetch N2 (Agentes) when N1 (Órgão) changes.
    
    This function is called via on_change callback when user selects a different Órgão.
    It automatically loads the corresponding Agentes without requiring a button click.
    """
    if not n1_value:
        return

    # Fetch agentes for this órgão
    result = fetch_func(level=2, n1_value=n1_value)

    if result.get("success"):
        options = result.get("options", [])
        st.session_state[n2_options_key] = options
        # Clear current N2 selection since options changed
        if hasattr(st.session_state, "eagendas"):
            st.session_state.eagendas.current_n2 = ""
        # Mark that auto-fetch happened for toast notification
        st.session_state["_eagendas_auto_fetch_count"] = len(options)
    else:
        st.session_state[n2_options_key] = []
        st.session_state["_eagendas_auto_fetch_error"] = result.get("error", "Erro desconhecido")


def render_hierarchy_selector(
    title: str,
    load_button_text: str,
    load_key: str,
    options_key: str,
    select_key: str,
    current_key: str,
    label_key: str,
    level: int,
    fetch_hierarchy_func: Callable | None = None,
    parent_value: str | None = None,
    parent_label: str | None = None,  # noqa: ARG001 - kept for API compatibility
    n2_value: str | None = None,  # noqa: ARG001 - deprecated, kept for API compatibility
    auto_fetch_child: bool = False,  # When True, auto-fetch next level on selection change
    child_options_key: str | None = None,  # Key for child options (used with auto_fetch_child)
) -> None:
    """Render a hierarchy selector for E-Agendas.
    
    Modelo simplificado de 2 níveis:
    - Level 1: Órgão (N1)
    - Level 2: Agente (N2, direto do órgão, sem cargo intermediário)
    
    Args:
        title: Display title for this level
        load_button_text: Text for the load button
        load_key: Session state key for load button
        options_key: Session state key to store loaded options
        select_key: Session state key for selectbox
        current_key: Session state key path for current value
        label_key: Session state key to store selected label
        level: Hierarchy level (1=Órgão, 2=Agente)
        fetch_hierarchy_func: Function to fetch hierarchy options (default: eagendas_fetch.fetch_hierarchy)
        parent_value: Value of parent level (required for level 2)
        parent_label: Label of parent level (for display)
        n2_value: DEPRECATED - Ignored (modelo antigo com cargo foi removido)
        auto_fetch_child: If True, automatically fetch child level when selection changes (level 1 only)
        child_options_key: Session state key for child options (required if auto_fetch_child=True)
    """
    # Use default fetch function if not provided
    if fetch_hierarchy_func is None:
        fetch_hierarchy_func = _get_default_fetch_hierarchy()

    st.markdown(f"**{title}**")

    # Show auto-fetch notifications from previous run
    if level == 2:
        if "_eagendas_auto_fetch_count" in st.session_state:
            count = st.session_state.pop("_eagendas_auto_fetch_count")
            st.success(f"✅ {count} agentes carregados automaticamente")
        if "_eagendas_auto_fetch_error" in st.session_state:
            error = st.session_state.pop("_eagendas_auto_fetch_error")
            st.error(f"❌ Erro ao carregar agentes: {error}")

    # Determine if load button should be enabled
    # Modelo simplificado: level 1 sempre pode carregar, level 2 precisa de órgão
    can_load = True
    if level == 2 and not parent_value:
        can_load = False
        st.caption("Selecione um Órgão primeiro")

    # Load button
    if st.button(load_button_text, key=load_key, disabled=not can_load):
        with st.spinner(f"Carregando {title.lower()}..."):
            if level == 1:
                result = fetch_hierarchy_func(level=1)
            else:  # level == 2: Agentes direto do órgão
                result = fetch_hierarchy_func(level=2, n1_value=parent_value)

            if result.get("success"):
                options = result.get("options", [])
                st.session_state[options_key] = options
                if options:
                    st.success(f"✅ {len(options)} opções carregadas")
                else:
                    st.warning("⚠️ Nenhuma opção encontrada")
            else:
                st.error(f"❌ {result.get('error', 'Erro desconhecido')}")

    # Get current options
    options = st.session_state.get(options_key, [])

    if options:
        labels = [opt.get("label", opt.get("text", "")) for opt in options]
        values = [opt.get("value", "") for opt in options]

        # Get current selection index
        current_parts = current_key.split(".")
        if len(current_parts) == 2:
            current_val = getattr(st.session_state.get(current_parts[0]), current_parts[1], None)
        else:
            current_val = st.session_state.get(current_key)

        try:
            current_idx = values.index(current_val) if current_val in values else 0
        except (ValueError, IndexError):
            current_idx = 0

        # Track previous value for change detection (for auto-fetch)
        prev_key = f"_prev_{select_key}"
        prev_value = st.session_state.get(prev_key)

        # Selectbox with on_change for auto-fetch (level 1 only)
        if level == 1 and auto_fetch_child and child_options_key:
            selected_idx = st.selectbox(
                f"Selecione {title}:",
                range(len(labels)),
                format_func=lambda i: labels[i],
                index=current_idx,
                key=select_key,
                label_visibility="collapsed"
            )
        else:
            selected_idx = st.selectbox(
                f"Selecione {title}:",
                range(len(labels)),
                format_func=lambda i: labels[i],
                index=current_idx,
                key=select_key,
                label_visibility="collapsed"
            )

        selected_value = values[selected_idx]
        selected_label = labels[selected_idx]

        # Set value in eagendas state
        if len(current_parts) == 2 and current_parts[0] == "eagendas":
            setattr(st.session_state.eagendas, current_parts[1], selected_value)
        else:
            st.session_state[current_key] = selected_value

        st.session_state[label_key] = selected_label

        # Auto-fetch child options when N1 selection changes (level 1 only)
        if level == 1 and auto_fetch_child and child_options_key:
            if prev_value is not None and prev_value != selected_value:
                # Selection changed, trigger auto-fetch
                with st.spinner("Carregando agentes..."):
                    _auto_fetch_n2_on_n1_change(fetch_hierarchy_func, selected_value, child_options_key)
            # Update previous value tracker
            st.session_state[prev_key] = selected_value

        st.caption(f"Selecionado: {selected_label}")
    else:
        st.caption(f"Clique em '{load_button_text}' para carregar opções")


def render_date_period_selector() -> tuple[_date, _date]:
    """Render date period selector and return start/end dates."""
    st.markdown("### 2️⃣ Defina o Período de Pesquisa")
    st.caption("⚠️ O período deve ser definido a cada execução (não é salvo nas consultas)")

    col_date1, col_date2 = st.columns(2)
    state = EAgendasSession.get_state()

    with col_date1:
        try:
            parts = state.date_start.split("-")
            start_obj = _date(int(parts[2]), int(parts[1]), int(parts[0]))
        except Exception:
            start_obj = _date.today()

        date_start = st.date_input("Data de início:", value=start_obj, format="DD/MM/YYYY", key="eagendas_date_start")
        EAgendasSession.set_date_start(date_start.strftime("%d-%m-%Y"))

    with col_date2:
        try:
            parts = state.date_end.split("-")
            end_obj = _date(int(parts[2]), int(parts[1]), int(parts[0]))
        except Exception:
            end_obj = _date.today()

        date_end = st.date_input("Data de término:", value=end_obj, format="DD/MM/YYYY", key="eagendas_date_end")
        EAgendasSession.set_date_end(date_end.strftime("%d-%m-%Y"))

    # Validation
    if date_start > date_end:
        st.error("⚠️ A data de início deve ser anterior ou igual à data de término!")
    else:
        days_diff = (date_end - date_start).days
        st.caption(f"✅ Período selecionado: {days_diff + 1} dia(s)")

    return date_start, date_end


@st.fragment
def render_query_manager() -> None:
    """Render saved queries manager section.
    
    This function is decorated with @st.fragment to enable isolated reruns,
    improving performance by not reloading the entire page when adding/managing queries.
    """
    st.markdown("### 3️⃣ Consultas Salvas")
    st.caption("Salve combinações de servidores para executar múltiplas pesquisas")

    state = EAgendasSession.get_state()
    col_add, col_clear = st.columns([3, 1])

    with col_add:
        # Modelo simplificado: apenas órgão (n1) e agente (n2)
        can_add = all([
            state.current_n1,
            state.current_n2,
        ])
        if st.button("+ Adicionar Consulta Atual", disabled=not can_add, use_container_width=True):
            n1_label = st.session_state.get("eagendas_current_n1_label", "")
            n2_label = st.session_state.get("eagendas_current_n2_label", "")

            # Novo formato simplificado - agente está em n2 agora (era n3)
            # Mantemos n2/n3 labels para compatibilidade com listas antigas
            query = {
                "n1_label": n1_label,
                "n1_value": state.current_n1,
                "n2_label": "",  # Cargo não existe mais
                "n2_value": "",  # Cargo não existe mais
                "n3_label": n2_label,  # Agente (era n3, agora n2 no estado mas salvo como n3 por compatibilidade)
                "n3_value": state.current_n2,  # ID do agente
                "person_label": f"{n2_label} ({n1_label})",  # Nome do agente (Órgão)
            }
            EAgendasSession.add_query(query)
            st.success("✅ Consulta adicionada!")
            st.rerun()

    with col_clear:
        if st.button("🗑️ Limpar Todas", use_container_width=True):
            EAgendasSession.clear_queries()
            st.success("🗑️ Consultas removidas")
            st.rerun()


@st.fragment
def render_lista_manager() -> None:
    """Render agent list save/load manager.
    
    This function is decorated with @st.fragment to enable isolated reruns,
    improving performance when saving or loading agent lists.
    """
    st.markdown("#### 💾 Gerenciar Listas de Agentes")

    listas_dir = Path("planos") / "eagendas_listas"
    listas_dir.mkdir(parents=True, exist_ok=True)

    state = EAgendasSession.get_state()
    col_save, col_load = st.columns(2)

    with col_save:
        st.caption("💾 Salvar lista atual")
        lista_name = st.text_input(
            "Nome da lista:",
            placeholder="Ex: Ministros_CADE",
            key="eagendas_lista_name",
            help="Nome para identificar esta lista de agentes"
        )

        can_save = len(state.saved_queries) > 0 and lista_name.strip()
        if st.button("💾 Salvar Lista", disabled=not can_save, use_container_width=True):
            safe_name = "".join(c if c.isalnum() or c in "_ -" else "_" for c in lista_name.strip())
            file_path = listas_dir / f"{safe_name}.json"

            lista_data = {
                "nome": lista_name.strip(),
                "criado_em": _date.today().strftime("%Y-%m-%d"),
                "total_agentes": len(state.saved_queries),
                "queries": state.saved_queries
            }

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(lista_data, f, indent=2, ensure_ascii=False)
                st.success(f"✅ Lista '{lista_name}' salva com sucesso!")
                st.caption(f"📁 {file_path}")
            except Exception as e:
                st.error(f"❌ Erro ao salvar lista: {e}")

    with col_load:
        st.caption("📂 Carregar lista salva")
        lista_files = sorted(listas_dir.glob("*.json"))

        if lista_files:
            lista_options = []
            for file_path in lista_files:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)
                    nome = data.get("nome", file_path.stem)
                    total = data.get("total_agentes", len(data.get("queries", [])))
                    criado = data.get("criado_em", "")
                    lista_options.append({
                        "label": f"{nome} ({total} agentes) - {criado}",
                        "path": file_path,
                        "data": data
                    })
                except Exception:
                    continue

            if lista_options:
                selected_lista_label = st.selectbox(
                    "Selecione uma lista:",
                    [opt["label"] for opt in lista_options],
                    key="eagendas_lista_select"
                )

                col_load_btn, col_del_btn = st.columns(2)

                with col_load_btn:
                    if st.button("📂 Carregar", use_container_width=True):
                        selected_opt = next((opt for opt in lista_options if opt["label"] == selected_lista_label), None)
                        if selected_opt:
                            st.session_state.eagendas.saved_queries = selected_opt["data"]["queries"]
                            st.success(f"✅ Lista carregada: {selected_opt['data']['total_agentes']} agentes")
                            st.rerun()

                with col_del_btn:
                    if st.button("🗑️ Excluir", use_container_width=True, type="secondary"):
                        selected_opt = next((opt for opt in lista_options if opt["label"] == selected_lista_label), None)
                        if selected_opt:
                            try:
                                selected_opt["path"].unlink()
                                st.success("🗑️ Lista excluída")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao excluir: {e}")
            else:
                st.info("Nenhuma lista disponível")
        else:
            st.info("Nenhuma lista salva ainda")


def render_saved_queries_list() -> None:
    """Render the list of saved queries."""
    state = EAgendasSession.get_state()
    queries = state.saved_queries

    if queries:
        st.metric("Total de consultas", len(queries))
        with st.expander(f"📋 Ver todas ({len(queries)} consultas)", expanded=True):
            for idx, q in enumerate(queries):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{idx + 1}. {q['person_label']}")
                    # Modelo simplificado: mostra apenas órgão (cargo não existe mais)
                    st.caption(f"   Órgão: {q['n1_label']}")
                with col2:
                    if st.button("❌", key=f"del_query_{idx}"):
                        EAgendasSession.remove_query(idx)
                        st.rerun()
    else:
        st.info("Nenhuma consulta salva. Selecione um servidor e clique em 'Adicionar Consulta Atual'")


# Lazy import for execute_script_and_read_result
def _get_default_execute_script_func():
    """Get the default execute_script_and_read_result function via lazy import."""
    from dou_snaptrack.ui.subprocess_utils import execute_script_and_read_result
    return execute_script_and_read_result


def render_execution_section(
    date_start: _date,
    date_end: _date,
    execute_script_func: Callable | None = None,
) -> None:
    """Render the execution section for running queries.
    
    Args:
        date_start: Start date
        date_end: End date
        execute_script_func: Function to execute subprocess script (default: subprocess_utils.execute_script_and_read_result)
    """
    # Use default execute function if not provided
    if execute_script_func is None:
        execute_script_func = _get_default_execute_script_func()

    st.markdown("### 4️⃣ Executar Pesquisa")

    state = EAgendasSession.get_state()
    can_execute = len(state.saved_queries) > 0 and date_start <= date_end

    # Configuração de modo de execução
    col_exec1, col_exec2, col_exec3 = st.columns([3, 1, 1])

    with col_exec2:
        max_workers = st.number_input(
            "Workers",
            min_value=1,
            max_value=8,
            value=4,
            help="Número de navegadores paralelos (modo paralelo). 4 é um bom balanço entre velocidade e memória."
        )

    with col_exec3:
        use_sequential = st.checkbox(
            "Sequencial",
            value=False,
            help="Usar modo sequencial (mais lento, mas pode ser útil em caso de problemas com o paralelo)"
        )

    with col_exec1:
        if st.button("🚀 Executar Todas as Consultas", disabled=not can_execute, use_container_width=True):
            periodo_iso = {
                "inicio": date_start.strftime("%Y-%m-%d"),
                "fim": date_end.strftime("%Y-%m-%d")
            }

            queries = state.saved_queries
            num_queries = len(queries)

            progress_bar = st.progress(0.0)
            status_text = st.empty()

            # Determinar modo de execução e script
            if use_sequential:
                script_path = Path(__file__).parent / "eagendas_collect_subprocess.py"
                status_text.text(f"🔄 Iniciando coleta SEQUENCIAL ({num_queries} agentes)...")
            else:
                script_path = Path(__file__).parent / "eagendas_collect_parallel.py"
                actual_workers = min(max_workers, num_queries)
                if actual_workers > 1:
                    status_text.text(f"🚀 Iniciando coleta PARALELA ({actual_workers} workers, {num_queries} agentes)...")
                else:
                    status_text.text("🚀 Iniciando coleta de eventos via Playwright...")

            try:
                subprocess_input = {
                    "queries": queries,
                    "periodo": periodo_iso,
                    "max_workers": max_workers
                }

            progress_bar.progress(0.1)
            status_text.text("🌐 Navegando no E-Agendas...")

            collect_timeout = int(os.environ.get("DOU_UI_EAGENDAS_COLLECT_TIMEOUT", "600"))
            logger.debug("Executando coleta E-Agendas subprocess %s (timeout=%s)", script_path, collect_timeout)

            data, stderr = execute_script_func(
                script_path=str(script_path),
                input_text=json.dumps(subprocess_input),
                timeout=collect_timeout
            )

            if not data:
                error_msg = stderr or "Erro ao executar coleta (sem saída JSON)"
                logger.error("Coleta E-Agendas falhou: %s stderr_len=%s", error_msg, len(stderr or ""))
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Erro durante coleta: {error_msg}")
                if stderr:
                    with st.expander("🔍 Logs do processo"):
                        st.code(stderr)
            else:
                response = data
                if not isinstance(response, dict):
                    progress_bar.empty()
                    status_text.empty()
                    st.error("❌ Resposta inválida do subprocess")
                elif not response.get("success"):
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"❌ Coleta falhou: {response.get('error', 'Erro desconhecido')}")
                    if "traceback" in response:
                        with st.expander("🔍 Traceback"):
                            st.code(response["traceback"])
                else:
                    events_data = response.get("data", {})
                    agentes_data = events_data.get("agentes", [])
                    metadata = events_data.get("metadata", {})
                    total_eventos = metadata.get("total_eventos", 0)
                    tempo_execucao = metadata.get("tempo_execucao_segundos", 0)
                    workers_usados = metadata.get("workers_utilizados", 1)
                    parallel_mode = metadata.get("parallel_mode", False)

                    progress_bar.progress(1.0)
                    status_text.text("✅ Coleta concluída!")

                    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
                    json_path = Path("resultados") / f"eagendas_eventos_{periodo_iso['inicio']}_{periodo_iso['fim']}_{timestamp}.json"
                    json_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(events_data, f, indent=2, ensure_ascii=False)

                    # Mensagem de sucesso com info de performance
                    if parallel_mode:
                        st.success(f"✅ Coleta PARALELA concluída! {len(agentes_data)} agentes em {tempo_execucao:.1f}s ({workers_usados} workers)")
                    else:
                        st.success(f"✅ Coleta concluída! {len(agentes_data)} agentes processados")
                    
                    # Métricas expandidas
                    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                    with col_r1:
                        st.metric("Agentes", len(agentes_data))
                    with col_r2:
                        st.metric("Eventos", total_eventos)
                    with col_r3:
                        st.metric("Período", f"{(date_end - date_start).days + 1} dias")
                    with col_r4:
                        if tempo_execucao > 0:
                            st.metric("Tempo", f"{tempo_execucao:.1f}s")
                        else:
                            st.metric("Workers", workers_usados)

                    st.info(f"📁 Dados salvos em: `{json_path.name}`")
                    st.session_state["last_eagendas_json"] = str(json_path)

                    if stderr:
                        with st.expander("📋 Logs da coleta"):
                            st.code(stderr)

        except subprocess.TimeoutExpired:
            progress_bar.empty()
            status_text.empty()
            st.error("❌ Timeout: A coleta demorou mais de 5 minutos")
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Erro durante execução: {e}")
            import traceback
            with st.expander("🔍 Detalhes do erro"):
                st.code(traceback.format_exc())

    if not can_execute:
        if len(state.saved_queries) == 0:
            st.warning("⚠️ Adicione pelo menos uma consulta para executar")
        if date_start > date_end:
            st.warning("⚠️ Corrija o período de pesquisa")


def render_document_generator(date_start: _date, date_end: _date) -> None:
    """Render the document generation section.
    
    Args:
        date_start: Start date for document title
        date_end: End date for document title
    """
    import sys

    st.markdown("### 5️⃣ Gerar Documento DOCX")
    st.caption("Gere um documento Word com as agendas coletadas, organizadas por agente")

    json_to_use = None
    is_example = False

    if "last_eagendas_json" in st.session_state:
        last_json = Path(st.session_state["last_eagendas_json"])
        if last_json.exists():
            json_to_use = last_json
        else:
            del st.session_state["last_eagendas_json"]

    if json_to_use is None:
        json_example = Path("resultados") / "eagendas_eventos_exemplo.json"
        if json_example.exists():
            json_to_use = json_example
            is_example = True

    if json_to_use:
        col_doc1, col_doc2 = st.columns([3, 1])

        with col_doc1:
            if is_example:
                st.info("📝 Dados de exemplo disponíveis para teste")
            else:
                st.success(f"📊 Dados coletados prontos: `{json_to_use.name}`")

        with col_doc2:
            btn_label = "📄 Gerar Documento" if is_example else "📄 Gerar DOCX"
            if st.button(btn_label, key="gen_doc_btn", use_container_width=True):
                from dou_snaptrack.adapters.eagendas_adapter import generate_eagendas_document_from_json

                if generate_eagendas_document_from_json is None:
                    st.error("❌ **Módulo python-docx não encontrado ou corrompido**")
                    st.warning("🔧 Este é um problema comum no Windows com lxml corrompido")

                    with st.expander("🔍 Detalhes do erro"):
                        st.code("O módulo eagendas_document não pôde ser carregado (lxml corrompido)", language="text")
                        st.code(f"Python: {sys.executable}", language="text")

                    st.divider()
                    st.markdown("**💡 Solução recomendada:**")
                    fix_cmd = f'"{sys.executable}" -m pip uninstall -y lxml python-docx\n"{sys.executable}" -m pip install --no-cache-dir lxml python-docx'
                    st.code(fix_cmd, language="powershell")
                    st.caption("Execute os comandos acima no PowerShell, reinicie a UI e tente novamente")
                else:
                    try:
                        if is_example:
                            out_path = Path("resultados") / "eagendas_agentes_exemplo.docx"
                            doc_title = "Agendas de Agentes Públicos - Exemplo"
                        else:
                            out_path = json_to_use.with_suffix(".docx")
                            doc_title = f"Agendas E-Agendas - {date_start.strftime('%d/%m/%Y')} a {date_end.strftime('%d/%m/%Y')}"

                        with st.spinner("Gerando documento DOCX..."):
                            result = generate_eagendas_document_from_json(
                                json_path=json_to_use,
                                out_path=out_path,
                                include_metadata=True,
                                title=doc_title
                            )

                        st.success("✅ Documento gerado com sucesso!")
                        st.metric("Agentes", result["agents"])
                        st.metric("Eventos", result["events"])
                        st.caption(result["period"])

                        with open(out_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Baixar Documento DOCX",
                                data=f,
                                file_name=out_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )

                        try:
                            with open(out_path, "rb") as _df:
                                st.session_state["last_eagendas_doc_bytes"] = _df.read()
                            st.session_state["last_eagendas_doc_name"] = out_path.name
                            st.session_state["last_eagendas_doc_path"] = str(out_path)
                        except Exception:
                            pass

                    except Exception as e:
                        st.error(f"❌ Erro ao gerar documento: {e}")
                        with st.expander("🔍 Traceback completo"):
                            import traceback
                            st.code(traceback.format_exc())
    else:
        st.info("💡 Execute a coleta de eventos primeiro ou use o script de teste para gerar dados de exemplo")
        st.code("python scripts/test_eagendas_document.py", language="bash")


def render_document_download() -> None:
    """Render download button for previously generated document."""
    _doc_bytes = st.session_state.get("last_eagendas_doc_bytes")
    _doc_name = st.session_state.get("last_eagendas_doc_name")
    _doc_path = st.session_state.get("last_eagendas_doc_path")

    if _doc_bytes and _doc_name:
        st.divider()
        dl_clicked = st.download_button(
            label="⬇️ Baixar último DOCX gerado",
            data=_doc_bytes,
            file_name=_doc_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="dl_last_eagendas_doc"
        )
        if dl_clicked:
            try:
                if _doc_path:
                    Path(_doc_path).unlink(missing_ok=True)
                    st.toast("🗑️ Arquivo DOCX removido do servidor")
            except Exception as _e:
                st.warning(f"Não foi possível remover o arquivo local: {_doc_path} — {_e}")

            try:
                if "last_eagendas_json" in st.session_state:
                    json_path_str = st.session_state["last_eagendas_json"]
                    json_p = Path(json_path_str)
                    if json_p.exists():
                        json_p.unlink(missing_ok=True)
                        st.toast(f"🗑️ JSON de dados ({json_p.name}) removido")
                    st.session_state.pop("last_eagendas_json", None)
            except Exception:
                pass

            for k in ("last_eagendas_doc_bytes", "last_eagendas_doc_name", "last_eagendas_doc_path"):
                st.session_state.pop(k, None)
