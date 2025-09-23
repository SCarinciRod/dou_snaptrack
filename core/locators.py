"""
Constantes e seletores para localização de elementos na página.
"""

# Seletores padrões usados ao mapear/abrir dropdowns (raiz do controle)
DROPDOWN_ROOT_SELECTORS = [
    "[role=combobox]",
    "select",
    "[aria-haspopup=listbox]",
    "[aria-expanded][role=button]",
    "div[class*=select]",
    "div[class*=dropdown]",
    "div[class*=combobox]",
]

# Seletores dos containers de lista (listbox/menus de opções)
LISTBOX_SELECTORS = [
    "[role=listbox]",
    "ul[role=listbox]",
    "div[role=listbox]",
    "ul[role=menu]",
    "div[role=menu]",
    ".ng-dropdown-panel",
    ".p-dropdown-items",
    ".select2-results__options",
    ".rc-virtual-list",
]

# Seletores de itens de opção
OPTION_SELECTORS = [
    "[role=option]",
    "li[role=option]",
    ".ng-option",
    ".p-dropdown-item",
    ".select2-results__option",
    "[data-value]",
    "[data-index]",
]

# IDs canônicos do DOU por nível (usado em resoluções/fallback)
LEVEL_IDS = {
    1: ["slcOrgs"],        # Órgão (N1)
    2: ["slcOrgsSubs"],    # Subordinada/Unidade (N2)
    3: ["slcTipo"],        # Tipo do ato (N3 - opcional)
}

# IDs preferidos para o mapeador de pares (ajuste conforme seu mapa)
N1_IDS = ["slcOrgs", "orgaoPrincipal", "orgs"]
N2_IDS = ["slcOrgsSubs", "orgaoSubordinado", "subs"]
