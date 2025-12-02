from __future__ import annotations

import os

# =============================================================================
# URL BASES
# =============================================================================
BASE_DOU = "https://www.in.gov.br/leiturajornal"
EAGENDAS_URL = "https://eagendas.cgu.gov.br/"

# =============================================================================
# TIMEOUTS - NAVEGAÇÃO (milissegundos)
# =============================================================================
# Timeout padrão para operações de página
TIMEOUT_PAGE_DEFAULT = 20_000          # 20s - operações gerais de página
TIMEOUT_PAGE_LONG = 45_000             # 45s - páginas lentas
TIMEOUT_PAGE_SLOW = 60_000             # 60s - páginas lentas (E-Agendas)
TIMEOUT_PAGE_VERY_SLOW = 90_000        # 90s - operações muito lentas

# Timeout para elementos aparecerem
TIMEOUT_ELEMENT_SHORT = 3_000          # 3s - elementos rápidos (alias)
TIMEOUT_ELEMENT_DEFAULT = 10_000       # 10s - elementos normais
TIMEOUT_ELEMENT_FAST = 5_000           # 5s - elementos rápidos
TIMEOUT_ELEMENT_NORMAL = 10_000        # 10s - elementos normais
TIMEOUT_ELEMENT_SLOW = 15_000          # 15s - elementos lentos
TIMEOUT_ELEMENT_VERY_SLOW = 30_000     # 30s - elementos muito lentos

# Timeout de navegação
TIMEOUT_NAVIGATION = 30_000            # 30s - navegação entre páginas

# =============================================================================
# TIMEOUTS - ESPERAS FIXAS (milissegundos)
# Usar apenas quando wait_for_selector não é possível
# =============================================================================
WAIT_MICRO = 50                        # 50ms - micro pausa
WAIT_TINY = 150                        # 150ms - pausa mínima
WAIT_SHORT = 200                       # 200ms - pausa curta
WAIT_MEDIUM = 500                      # 500ms - pausa média
WAIT_LONG = 1_000                      # 1s - pausa longa
WAIT_EXTRA_LONG = 2_000                # 2s - pausa extra longa
WAIT_ANIMATION = 300                   # 300ms - esperar animação
WAIT_NETWORK_IDLE = 2_000              # 2s - esperar rede ficar idle
WAIT_ANGULAR_INIT = 3_000              # 3s - AngularJS inicializar
WAIT_ANGULAR_LOAD = 5_000              # 5s - AngularJS carregar dados
WAIT_SELECTIZE_POPULATE = 4_000        # 4s - Selectize popular dropdown
WAIT_DROPDOWN_REPOPULATE = 3_000       # 3s - dropdown repopular após mudança

# =============================================================================
# TIMEOUTS - SUBPROCESSOS (segundos)
# =============================================================================
TIMEOUT_SUBPROCESS = int(os.environ.get("DOU_UI_SUBPROCESS_TIMEOUT", "120"))
TIMEOUT_SUBPROCESS_DEFAULT = TIMEOUT_SUBPROCESS  # Alias
TIMEOUT_SUBPROCESS_SHORT = 10          # 10s - operações rápidas
TIMEOUT_SUBPROCESS_LONG = 900          # 15min - operações em lote

# =============================================================================
# CACHE TTL (segundos)
# =============================================================================
CACHE_TTL_SHORT = 300                  # 5min
CACHE_TTL_MEDIUM = 900                 # 15min
CACHE_TTL_LONG = 3600                  # 1h
CACHE_TTL_SESSION = 3600               # 1h (alias para sessão)
CACHE_TTL_DAY = 86400                  # 24h

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

# Legacy alias (deprecated - use TIMEOUT_SUBPROCESS_DEFAULT)
DEFAULT_SUBPROCESS_TIMEOUT = TIMEOUT_SUBPROCESS_DEFAULT

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
