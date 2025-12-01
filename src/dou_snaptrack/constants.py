from __future__ import annotations

import os

# =============================================================================
# URL BASES
# =============================================================================
BASE_DOU = "https://www.in.gov.br/leiturajornal"
EAGENDAS_URL = "https://eagendas.cgu.gov.br/"

# =============================================================================
# DOU SELECTORS AND IDS
# =============================================================================
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

# =============================================================================
# E-AGENDAS SELECTORS AND IDS
# =============================================================================
EAGENDAS_LEVEL_IDS = {
    1: [],  # A definir após mapeamento
    2: [],  # A definir após mapeamento
}

EAGENDAS_SELECTORS = {
    "search_button": ["Pesquisar", "Buscar", "Procurar", "Search"],
}

# =============================================================================
# UI ENVIRONMENT VARIABLES
# =============================================================================
# Environment variable names (centralized for maintainability)
RESULT_JSON_ENV = "RESULT_JSON_PATH"
ALLOW_TLS_BYPASS_ENV = "DOU_UI_ALLOW_TLS_BYPASS"
SAVE_DEBUG_SCRIPT_ENV = "DOU_UI_SAVE_DEBUG_SCRIPT"
STDOUT_FALLBACK_ENV = "DOU_UI_ALLOW_STDOUT_FALLBACK"

# Subprocess timeout (seconds). Can be overridden by env var.
DEFAULT_SUBPROCESS_TIMEOUT = int(os.environ.get("DOU_UI_SUBPROCESS_TIMEOUT", "120"))

# =============================================================================
# COOKIE HANDLING
# =============================================================================
COOKIE_BUTTON_TEXTS = ["ACEITO", "ACEITAR", "OK", "ENTENDI", "CONCORDO", "FECHAR", "ACEITO TODOS"]

# =============================================================================
# PLAYWRIGHT CONFIGURATION
# =============================================================================
# Default browser channels to try (in order)
BROWSER_CHANNELS = ["chrome", "msedge"]

# System browser paths (Windows)
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
EDGE_PATHS = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
