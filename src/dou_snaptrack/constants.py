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

# URL do E-Agendas
EAGENDAS_URL = "https://eagendas.cgu.gov.br/"

# IDs específicos do E-Agendas (a serem mapeados conforme necessário)
EAGENDAS_LEVEL_IDS = {
    1: [],  # A definir após mapeamento
    2: [],  # A definir após mapeamento
}

# Seletores específicos do E-Agendas
EAGENDAS_SELECTORS = {
    "search_button": ["Pesquisar", "Buscar", "Procurar", "Search"],
}
