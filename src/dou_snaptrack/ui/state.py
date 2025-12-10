"""
State management for DOU SnapTrack UI.

This module contains the state containers and session management functions
used by the Streamlit UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any

import streamlit as st


@dataclass
class PlanState:
    """State container for DOU plan editing."""
    date: str
    secao: str
    combos: list[dict[str, Any]]
    defaults: dict[str, Any]


@dataclass
class EAgendasState:
    """State container for E-Agendas queries."""
    saved_queries: list[dict[str, Any]]
    current_n1: str | None
    current_n2: str | None
    current_n3: str | None
    date_start: str
    date_end: str


def ensure_state() -> None:
    """Ensure DOU plan state exists in session."""
    if "plan" not in st.session_state:
        st.session_state.plan = PlanState(
            date=_date.today().strftime("%d-%m-%Y"),
            secao="DO1",
            combos=[],
            defaults={
                "scrape_detail": False,
                "summary_lines": 0,
                "summary_mode": "center",
            },
        )


def ensure_eagendas_state() -> None:
    """Ensure E-Agendas state exists in session."""
    if "eagendas" not in st.session_state:
        st.session_state.eagendas = EAgendasState(
            saved_queries=[],
            current_n1=None,
            current_n2=None,
            current_n3=None,
            date_start=_date.today().strftime("%d-%m-%Y"),
            date_end=_date.today().strftime("%d-%m-%Y"),
        )


def ensure_dirs() -> tuple[Path, Path]:
    """Ensure plans and results directories exist.

    Returns:
        Tuple of (plans_dir, results_dir) paths.
    """
    plans_dir = Path("planos")
    results_dir = Path("resultados")
    plans_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    return plans_dir, results_dir


def get_plan() -> PlanState:
    """Get current plan state, ensuring it exists."""
    ensure_state()
    return st.session_state.plan


def get_eagendas() -> EAgendasState:
    """Get current E-Agendas state, ensuring it exists."""
    ensure_eagendas_state()
    return st.session_state.eagendas


def reset_plan() -> None:
    """Reset plan state to defaults."""
    st.session_state.plan = PlanState(
        date=_date.today().strftime("%d-%m-%Y"),
        secao="DO1",
        combos=[],
        defaults={
            "scrape_detail": False,
            "summary_lines": 0,
            "summary_mode": "center",
        },
    )


def reset_eagendas() -> None:
    """Reset E-Agendas state to defaults."""
    st.session_state.eagendas = EAgendasState(
        saved_queries=[],
        current_n1=None,
        current_n2=None,
        current_n3=None,
        date_start=_date.today().strftime("%d-%m-%Y"),
        date_end=_date.today().strftime("%d-%m-%Y"),
    )


class SessionManager:
    """Centralizes access to st.session_state for plan and E-Agendas state management."""

    @staticmethod
    def ensure() -> None:
        """Ensure both plan and E-Agendas states exist."""
        ensure_state()
        ensure_eagendas_state()

    @staticmethod
    def get_plan() -> PlanState:
        """Get current plan state, ensuring it exists."""
        SessionManager.ensure()
        return st.session_state.plan

    @staticmethod
    def set_plan_date(date_str: str) -> None:
        """Set the plan date."""
        SessionManager.get_plan().date = date_str

    @staticmethod
    def set_plan_secao(secao: str) -> None:
        """Set the plan section (DO1, DO2, DO3)."""
        SessionManager.get_plan().secao = secao

    @staticmethod
    def add_combos(combos: list[dict]) -> None:
        """Add combos to the current plan."""
        if not combos:
            return
        SessionManager.get_plan().combos.extend(combos)

    @staticmethod
    def clear_combos() -> None:
        """Clear all combos from the current plan."""
        SessionManager.get_plan().combos = []

    @staticmethod
    def update_combos_from_edited_df(edited_df) -> None:
        """Update combo labels from edited DataFrame."""
        plan = SessionManager.get_plan()
        total = len(edited_df) if edited_df is not None else 0
        for idx, combo in enumerate(plan.combos):
            if idx >= total:
                break
            try:
                row = edited_df.iloc[idx]
                combo["label1"] = row.get("Órgão", combo.get("label1"))
                combo["label2"] = row.get("Sub-órgão", combo.get("label2"))
            except Exception:
                continue

    @staticmethod
    def add_eagendas_query(query: dict) -> None:
        """Add a query to E-Agendas saved queries."""
        SessionManager.ensure()
        st.session_state.eagendas.saved_queries.append(query)

    @staticmethod
    def clear_eagendas_queries() -> None:
        """Clear all E-Agendas saved queries."""
        SessionManager.ensure()
        st.session_state.eagendas.saved_queries = []

    @staticmethod
    def remove_eagendas_query(idx: int) -> None:
        """Remove an E-Agendas query by index."""
        SessionManager.ensure()
        try:
            st.session_state.eagendas.saved_queries.pop(idx)
        except Exception:
            pass

    @staticmethod
    def set_eagendas_date_start(date_str: str) -> None:
        """Set E-Agendas start date."""
        SessionManager.ensure()
        st.session_state.eagendas.date_start = date_str

    @staticmethod
    def set_eagendas_date_end(date_str: str) -> None:
        """Set E-Agendas end date."""
        SessionManager.ensure()
        st.session_state.eagendas.date_end = date_str
