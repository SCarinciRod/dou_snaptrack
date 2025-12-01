"""
Sidebar UI module for SnapTrack DOU.

This module provides sidebar components for application maintenance,
diagnostics, and pairs file management.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    pass

# Module-level logger
logger = logging.getLogger("dou_snaptrack.ui.sidebar")


def render_pairs_maintenance() -> None:
    """Render the pairs file maintenance section in the sidebar."""
    from dou_snaptrack.utils.pairs_updater import get_pairs_file_info, update_pairs_file_async

    st.divider()
    with st.expander("🔧 Manutenção do Artefato", expanded=False):
        st.caption("Gerenciar pairs_DO1_full.json")

        info = get_pairs_file_info()

        if info["exists"]:
            st.metric("Status", "✅ Existe" if not info["is_stale"] else "⚠️ Obsoleto")
            if info["age_days"] is not None:
                st.metric("Idade", f"{info['age_days']:.1f} dias")
            if info["n1_count"]:
                st.metric("Órgãos (N1)", info["n1_count"])
            if info["pairs_count"]:
                st.metric("Pares (N1→N2)", info["pairs_count"])
            if info["last_update"]:
                st.caption(f"Última atualização: {info['last_update'][:19]}")
        else:
            st.warning("⚠️ Arquivo não encontrado")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Atualizar Agora", key="update_pairs_btn", use_container_width=True):
                _run_pairs_update(update_pairs_file_async)

        with col2:
            if st.button("Info", key="info_pairs_btn", use_container_width=True):
                st.json(info, expanded=True)

            st.caption("Arquivo do boletim removido do servidor. Os JSONs permanecem em 'resultados/'.")


def _run_pairs_update(update_pairs_file_async) -> None:
    """Execute pairs file update with progress feedback.
    
    Args:
        update_pairs_file_async: Async function to update pairs file
    """
    with st.spinner("Scraping DOU para atualizar pares..."):
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def progress_callback(pct: float, msg: str):
            progress_bar.progress(pct)
            status_text.text(msg)

        try:
            result = asyncio.run(
                update_pairs_file_async(
                    limit1=5,  # Limitar para teste rápido
                    progress_callback=progress_callback,
                )
            )
        except Exception as e:
            result = {"success": False, "error": f"{type(e).__name__}: {e}"}

        progress_bar.empty()
        status_text.empty()

        if result.get("success"):
            st.success(
                f"✅ Atualizado! {result.get('n1_count', 0)} órgãos, {result.get('pairs_count', 0)} pares"
            )
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")


def render_diagnostics_section() -> None:
    """Render system diagnostics section in the sidebar."""
    with st.expander("🔍 Diagnósticos do Sistema", expanded=False):
        st.caption("Informações úteis para depuração")

        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🐍 Verificar Python", key="diag_python_btn", use_container_width=True):
                import sys
                st.code(f"Versão: {sys.version}")
                st.code(f"Executável: {sys.executable}")

        with col2:
            if st.button("📦 Verificar Playwright", key="diag_pw_btn", use_container_width=True):
                try:
                    import playwright
                    st.success(f"✅ Playwright instalado")
                    st.caption(f"Versão: {playwright.__version__}")
                except ImportError as e:
                    st.error(f"❌ Playwright não disponível: {e}")


def render_help_section() -> None:
    """Render help and documentation links in the sidebar."""
    st.divider()
    with st.expander("❓ Ajuda", expanded=False):
        st.markdown("""
        **Guia Rápido:**
        
        1. **TAB DOU**: Monta planos de coleta do Diário Oficial
        2. **TAB E-Agendas**: Coleta agendas de servidores públicos
        
        **Teclas de Atalho:**
        - `Ctrl+Enter`: Executa ação principal
        - `Esc`: Cancela operação atual
        
        **Links Úteis:**
        - [DOU Imprensa Nacional](https://www.in.gov.br/web/dou/-/diario-oficial-da-uniao)
        - [E-Agendas](https://eagendas.cgu.gov.br/)
        """)


def render_sidebar() -> None:
    """Render the complete sidebar with all sections."""
    with st.sidebar:
        render_pairs_maintenance()
        render_diagnostics_section()
        render_help_section()
