"""
Report generation UI components for DOU SnapTrack.

This module provides the UI components for TAB3 "Gerar boletim".
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _index_aggregates_in_day(day_dir: Path) -> dict[str, list[Path]]:
    """Index aggregated JSON files in a day directory by plan name."""
    idx: dict[str, list[Path]] = {}
    try:
        for f in day_dir.glob("*_DO?_*.json"):
            name = f.name
            try:
                parts = name[:-5].split("_")  # drop .json
                if len(parts) < 3:
                    continue
                sec = parts[-2]
                date = parts[-1]
                plan = "_".join(parts[:-2])
                if not sec.upper().startswith("DO"):
                    continue
                # conferir se bate com a pasta (sanidade)
                if date != day_dir.name:
                    continue
            except Exception:
                continue
            idx.setdefault(plan, []).append(f)
    except Exception:
        pass
    return idx


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================
def render_report_generator() -> None:
    """Render the report generator UI (TAB3 "Gerar boletim")."""
    st.subheader("Boletim por Plano (agregados)")

    results_root = Path("resultados")
    results_root.mkdir(parents=True, exist_ok=True)

    # Formato e política padronizada de resumo (sem escolhas do usuário)
    st.caption(
        "Os resumos são gerados com parâmetros padronizados (modo center, 7 linhas) e captura profunda automática."
    )
    st.caption("Gere boletim a partir de agregados do dia: {plan}_{secao}_{data}.json (dentro da pasta da data)")

    # Ação auxiliar: agregação manual a partir de uma pasta de dia
    _render_manual_aggregation(results_root)

    # Seletor de data e geração de boletim
    _render_report_selection(results_root)

    # Botão de download do último boletim gerado
    _render_download_section()


def _render_manual_aggregation(results_root: Path) -> None:
    """Render the manual aggregation expander section."""
    with st.expander("Agregação manual (quando necessário)"):
        day_dirs = []
        try:
            day_dirs = [d for d in results_root.iterdir() if d.is_dir()]
        except Exception:
            day_dirs = []
        day_dirs = sorted(day_dirs, key=lambda p: p.name, reverse=True)

        if not day_dirs:
            st.info("Nenhuma pasta encontrada em 'resultados'. Execute um plano para gerar uma pasta do dia.")
        else:
            labels = [p.name for p in day_dirs]
            choice = st.selectbox("Pasta do dia para agregar", labels, index=0, key="agg_day_choice")
            choice_str = str(choice) if isinstance(choice, str) and choice else str(labels[0])
            chosen_dir = results_root / choice_str

            help_txt = "Use esta opção se a execução terminou sem gerar os arquivos agregados. Informe o nome do plano e agregue os JSONs da pasta escolhida."
            st.write(help_txt)

            manual_plan = st.text_input(
                "Nome do plano (para nome do arquivo agregado)",
                value=st.session_state.get("plan_name_ui", ""),
                key="agg_manual_plan",
            )

            if st.button("Gerar agregados agora", key="agg_manual_btn"):
                _mp = manual_plan or ""
                if not _mp.strip():
                    st.warning("Informe o nome do plano.")
                else:
                    try:
                        from dou_snaptrack.cli.reporting import aggregate_outputs_by_plan

                        written = aggregate_outputs_by_plan(str(chosen_dir), _mp.strip())
                        if written:
                            st.success(f"Gerados {len(written)} agregado(s):")
                            for w in written:
                                st.write(w)
                        else:
                            st.info("Nenhum arquivo de job encontrado para agregar.")
                    except Exception as e:
                        st.error(f"Falha ao agregar: {e}")


def _render_report_selection(results_root: Path) -> None:
    """Render the report selection and generation section."""
    # Seletor 1: escolher a pasta da data (resultados/<data>)
    day_dirs: list[Path] = []
    try:
        day_dirs = [d for d in results_root.iterdir() if d.is_dir()]
    except Exception:
        day_dirs = []
    day_dirs = sorted(day_dirs, key=lambda p: p.name, reverse=True)

    if not day_dirs:
        st.info("Nenhuma pasta encontrada em 'resultados'. Execute um plano com 'Nome do plano' para gerar agregados.")
    else:
        day_labels = [p.name for p in day_dirs]
        sel_day = st.selectbox("Data (pasta em resultados)", day_labels, index=0, key="agg_day_select")
        chosen_dir = results_root / str(sel_day)

        day_idx = _index_aggregates_in_day(chosen_dir)
        plan_names = sorted(day_idx.keys())

        if not plan_names:
            st.info("Nenhum agregado encontrado nessa data. Verifique se o plano foi executado com 'Nome do plano'.")
        else:
            # Seletor 2: escolher o plano dentro da pasta do dia
            sel_plan = st.selectbox("Plano (encontrado na data)", plan_names, index=0, key="agg_plan_select")
            files = day_idx.get(sel_plan, [])
            kind2 = st.selectbox("Formato (agregados)", ["docx", "md", "html"], index=1, key="kind_agg")

            # Nome sugerido (sem extensão)
            suggested_name = f"boletim_{sel_plan}_{sel_day}"
            out_name_input = st.text_input(
                "Nome do arquivo",
                suggested_name,
                help=f"Apenas o nome (sem extensão). Será salvo como .{kind2}"
            )

            # Sanitizar: remover caracteres inválidos e extensões que o usuário possa ter digitado
            import re
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', out_name_input.strip())
            # Remover extensão se usuário digitou
            for ext in ['.docx', '.md', '.html']:
                if clean_name.lower().endswith(ext):
                    clean_name = clean_name[:-len(ext)]
            clean_name = clean_name.strip() or "boletim"

            # Nome final com extensão correta
            out_name2 = f"{clean_name}.{kind2}"
            st.caption(f"📁 Será salvo em: `resultados/{out_name2}`")

            if st.button("Gerar boletim", type="primary", use_container_width=True):
                if not files:
                    st.error("Nenhum arquivo agregado encontrado para gerar boletim.")
                else:
                    with st.spinner(f"Gerando boletim {kind2.upper()}..."):
                        _generate_report(results_root, files, kind2, out_name2, str(sel_day))


def _generate_report(
    results_root: Path,
    files: list[Path],
    kind: str,
    out_name: str,
    sel_day: str,
) -> None:
    """Generate a report from aggregated files."""
    try:
        from dou_snaptrack.cli.reporting import report_from_aggregated

        out_path = results_root / out_name

        # Detectar seção a partir do primeiro arquivo
        secao_label = ""
        if files:
            try:
                parts = files[0].stem.split("_")
                if len(parts) >= 2:
                    secao_label = parts[-2]
            except Exception:
                pass

        # Garantir deep-mode ligado para relatório (não offline)
        os.environ["DOU_OFFLINE_REPORT"] = "0"

        # Browser fallback desabilitado no UI Streamlit (Playwright sync_api
        # não funciona bem dentro do event loop do Streamlit)
        report_from_aggregated(
            [str(p) for p in files],
            kind,
            str(out_path),
            date_label=sel_day,
            secao_label=secao_label,
            summary_lines=7,
            summary_mode="center",
            summary_keywords=None,
            order_desc_by_date=True,
            fetch_parallel=8,
            fetch_timeout_sec=30,
            fetch_force_refresh=True,
            fetch_browser_fallback=False,
            short_len_threshold=800,
        )

        data = out_path.read_bytes()
        st.success(f"Boletim gerado: {out_path}")

        # Guardar em memória para download e remoção posterior do arquivo físico
        try:
            st.session_state["last_bulletin_data"] = data
            st.session_state["last_bulletin_name"] = out_path.name
            st.session_state["last_bulletin_path"] = str(out_path)
            st.info("Use o botão abaixo para baixar; o arquivo local será removido após o download.")
        except Exception:
            # Fallback: se sessão não aceitar, manter botão direto (sem remoção automática)
            st.download_button(
                "Baixar boletim (plano)", data=data, file_name=out_path.name, key="dl_fallback"
            )
    except Exception as e:
        st.error(f"Falha ao gerar boletim por plano: {e}")


def _render_download_section() -> None:
    """Render the download button for the last generated report."""
    lb_data = st.session_state.get("last_bulletin_data")
    lb_name = st.session_state.get("last_bulletin_name")
    lb_path = st.session_state.get("last_bulletin_path")

    if lb_data and lb_name:
        clicked = st.download_button(
            "Baixar último boletim gerado",
            data=lb_data,
            file_name=str(lb_name),
            key="dl_last_bulletin",
        )
        if clicked:
            # Remover arquivo gerado no servidor após o download
            try:
                if lb_path:
                    p = Path(str(lb_path))
                    if p.exists():
                        p.unlink()
            except Exception as _e:
                st.warning(f"Não foi possível remover o arquivo local: {lb_path} — {_e}")

            # Limpar dados da sessão para evitar re-download e liberar memória
            for k in ("last_bulletin_data", "last_bulletin_name", "last_bulletin_path"):
                st.session_state.pop(k, None)
