# Compatibility module - re-exports from dou_snaptrack.ui.pages.eagendas_ui
# This file exists for backward compatibility with existing imports
"""E-Agendas UI module - now in dou_snaptrack.ui.pages/."""

from dou_snaptrack.ui.pages.eagendas_ui import *  # noqa: F401, F403
from dou_snaptrack.ui.pages.eagendas_ui import (
    render_hierarchy_selector,
    render_date_period_selector,
    render_query_manager,
    render_lista_manager,
    render_saved_queries_list,
    render_execution_section,
    render_document_generator,
    render_document_download,
)

__all__ = [
    "render_hierarchy_selector",
    "render_date_period_selector",
    "render_query_manager",
    "render_lista_manager",
    "render_saved_queries_list",
    "render_execution_section",
    "render_document_generator",
    "render_document_download",
]
