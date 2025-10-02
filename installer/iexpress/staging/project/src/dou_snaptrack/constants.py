from __future__ import annotations

# Base do DOU
BASE_DOU = "https://www.in.gov.br/leiturajornal"

# Seletores de raiz para dropdowns (além de get_by_role('combobox') e <select>)
DROPDOWN_ROOT_SELECTORS = [
    "[role=combobox]", "select",
    "[aria-haspopup=listbox]", "[aria-expanded][role=button]",
    "div[class*=select]", "div[class*=dropdown]", "div[class*=combobox]"
]

# IDs canônicos do DOU
LEVEL_IDS = {
    1: ["slcOrgs"],      # Órgão (N1)
    2: ["slcOrgsSubs"],  # Subordinada/Unidade (N2)
}
