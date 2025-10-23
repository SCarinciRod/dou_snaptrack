"""
Lists of default selectors for dropdown roots, listboxes and options.

Refactored:
- Converted to tuples (immutability)
- Added docstrings and rationale ordering
- Provided combined export for debugging
"""

from __future__ import annotations

# Order: semantic ARIA roles first, then generic/class-based, then framework-specific
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
    """
    Returns all selector tuples (root, listbox, option)
    Useful for debugging / introspection.
    """
    return DROPDOWN_ROOT_SELECTORS, LISTBOX_SELECTORS, OPTION_SELECTORS
