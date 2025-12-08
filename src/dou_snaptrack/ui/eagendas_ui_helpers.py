"""Helper functions for E-Agendas UI rendering.

This module contains extracted functions from render_hierarchy_selector to reduce complexity.
"""

from __future__ import annotations

from typing import Any


def show_auto_fetch_notifications(level: int, st_module) -> None:
    """Show auto-fetch notifications from previous run.
    
    Args:
        level: Hierarchy level
        st_module: Streamlit module
    """
    if level == 2:
        if "_eagendas_auto_fetch_count" in st_module.session_state:
            count = st_module.session_state.pop("_eagendas_auto_fetch_count")
            st_module.success(f"✅ {count} agentes carregados automaticamente")
        if "_eagendas_auto_fetch_error" in st_module.session_state:
            error = st_module.session_state.pop("_eagendas_auto_fetch_error")
            st_module.error(f"❌ Erro ao carregar agentes: {error}")


def can_load_level(level: int, parent_value: str | None) -> bool:
    """Determine if load button should be enabled.
    
    Args:
        level: Hierarchy level
        parent_value: Parent value (required for level 2)
        
    Returns:
        True if can load
    """
    if level == 2 and not parent_value:
        return False
    return True


def load_hierarchy_options(level: int, fetch_func, parent_value: str | None, st_module) -> None:
    """Load hierarchy options via fetch function.
    
    Args:
        level: Hierarchy level
        fetch_func: Function to fetch options
        parent_value: Parent value (for level 2)
        st_module: Streamlit module
    """
    if level == 1:
        result = fetch_func(level=1)
    else:  # level == 2
        result = fetch_func(level=2, n1_value=parent_value)
    
    return result


def get_current_selection_index(current_key: str, values: list[str], st_module) -> int:
    """Get current selection index from session state.
    
    Args:
        current_key: Session state key path
        values: List of option values
        st_module: Streamlit module
        
    Returns:
        Current selection index
    """
    current_parts = current_key.split(".")
    if len(current_parts) == 2:
        current_val = getattr(st_module.session_state.get(current_parts[0]), current_parts[1], None)
    else:
        current_val = st_module.session_state.get(current_key)
    
    try:
        return values.index(current_val) if current_val in values else 0
    except (ValueError, IndexError):
        return 0


def set_selected_value(current_key: str, selected_value: str, st_module) -> None:
    """Set selected value in session state.
    
    Args:
        current_key: Session state key path
        selected_value: Value to set
        st_module: Streamlit module
    """
    current_parts = current_key.split(".")
    if len(current_parts) == 2 and current_parts[0] == "eagendas":
        setattr(st_module.session_state.eagendas, current_parts[1], selected_value)
    else:
        st_module.session_state[current_key] = selected_value


def should_auto_fetch(level: int, auto_fetch: bool, prev_value: Any, selected_value: str) -> bool:
    """Determine if should auto-fetch child options.
    
    Args:
        level: Hierarchy level
        auto_fetch: Auto-fetch flag
        prev_value: Previous selection value
        selected_value: Current selection value
        
    Returns:
        True if should auto-fetch
    """
    return level == 1 and auto_fetch and prev_value is not None and prev_value != selected_value
