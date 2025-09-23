# Constantes de seletores para uso em todo o projeto

# Seletores padrões usados ao mapear/abrir dropdowns
DROPDOWN_ROOT_SELECTORS = [
    "[role=combobox]",
    "select",
    "[aria-haspopup=listbox]",
    "[aria-expanded][role=button]",
    "div[class*=select]",
    "div[class*=dropdown]",
    "div[class*=combobox]",
]

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

OPTION_SELECTORS = [
    "[role=option]",
    "li[role=option]",
    ".ng-option",
    ".p-dropdown-item",
    ".select2-results__option",
    "[data-value]",
    "[data-index]",
]

# IDs padrão do DOU para cada nível
LEVEL_IDS = {
    1: ["slcOrgs"],       # Organização Principal (Órgão)
    2: ["slcOrgsSubs"],   # Organização Subordinada / Unidade / Secretaria
    3: ["slcTipo"],       # Tipo do Ato
}

# IDs canônicos do DOU (quando presentes)
CASCADE_LEVEL_IDS = {
    1: ["slcOrgs"],       # Órgão (N1)
    2: ["slcOrgsSubs"],   # Subordinada/Unidade (N2)
}
