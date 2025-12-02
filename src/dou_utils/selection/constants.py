"""
Default CSS/ARIA selectors for dropdown detection.

Order: semantic ARIA roles first, then generic/class-based, then framework-specific.
"""
from __future__ import annotations

# Sentinel prefix for placeholder options
SENTINELA_PREFIX = "selecionar "

# Root selectors for finding dropdown triggers
DROPDOWN_ROOT_SELECTORS: tuple[str, ...] = (
    "[role=combobox]",
    "select",
    "[aria-haspopup=listbox]",
    "[aria-expanded][role=button]",
    "div[class*=select]",
    "div[class*=dropdown]",
    "div[class*=combobox]",
    # Framework specific
    ".ant-select",           # Ant Design
    ".MuiAutocomplete-root", # Material UI
    ".dropdown",             # Bootstrap-like
)

# Selectors for opened listbox/menu containers
LISTBOX_SELECTORS: tuple[str, ...] = (
    "[role=listbox]",
    "ul[role=listbox]",
    "div[role=listbox]",
    "ul[role=menu]",
    "div[role=menu]",
    ".ng-dropdown-panel",
    ".p-dropdown-items",
    ".select2-results__options",
    ".rc-virtual-list",
    # Framework specific
    ".ant-select-dropdown",
    ".MuiAutocomplete-popper",
    ".dropdown-menu",
)

# Selectors for individual option items
OPTION_SELECTORS: tuple[str, ...] = (
    "[role=option]",
    "li[role=option]",
    ".ng-option",
    ".p-dropdown-item",
    ".select2-results__option",
    "[data-value]",
    "[data-index]",
    # Framework specific
    ".ant-select-item",
    ".MuiAutocomplete-option",
    "li.dropdown-item",
)


def all_selectors() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return all selector tuples (root, listbox, option).
    
    Useful for debugging / introspection.
    """
    return DROPDOWN_ROOT_SELECTORS, LISTBOX_SELECTORS, OPTION_SELECTORS
