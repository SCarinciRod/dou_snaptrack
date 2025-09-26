"""
settings.py
Configurações centrais e imutáveis (dataclasses) para todos os módulos.
Inclui compatibilidade retroativa com campos esperados por log_utils:
 - log_file
 - log_level (property apontando para level)
"""

from __future__ import annotations
from dataclasses import dataclass
import os

# ---------------- Timeouts ----------------
@dataclass(frozen=True)
class TimeoutConfig:
    default_timeout_ms: int = int(os.getenv("DOU_DEFAULT_TIMEOUT_MS", "60000"))
    nav_timeout_ms: int = int(os.getenv("DOU_NAV_TIMEOUT_MS", "60000"))

# ---------------- Scroll ----------------
@dataclass(frozen=True)
class ScrollConfig:
    max_scrolls: int = int(os.getenv("DOU_MAX_SCROLLS", "40"))
    scroll_pause_ms: int = int(os.getenv("DOU_SCROLL_PAUSE_MS", "350"))
    stable_rounds: int = int(os.getenv("DOU_STABLE_ROUNDS", "3"))

# ---------------- Dropdown ----------------
@dataclass(frozen=True)
class DropdownConfig:
    max_per_type: int = int(os.getenv("DOU_MAX_DROPDOWNS_PER_TYPE", "50"))
    open_delay_ms: int = int(os.getenv("DOU_DROPDOWN_OPEN_DELAY_MS", "120"))

# ---------------- Summary básico ----------------
@dataclass(frozen=True)
class SummaryConfig:
    default_lines: int = int(os.getenv("DOU_SUMMARY_LINES", "5"))
    default_mode: str = os.getenv("DOU_SUMMARY_MODE", "center")

# ---------------- Arquivos ----------------
@dataclass(frozen=True)
class FileConfig:
    out_dir: str = os.getenv("DOU_DEFAULT_OUT_DIR", "out")

# ---------------- Busca ----------------
@dataclass(frozen=True)
class SearchConfig:
    max_links_default: int = int(os.getenv("DOU_MAX_LINKS_DEFAULT", "30"))

# ---------------- Cookies ----------------
@dataclass(frozen=True)
class CookieConfig:
    auto_close: bool = os.getenv("DOU_COOKIE_AUTO_CLOSE", "1") == "1"

# ---------------- Logging ----------------
@dataclass(frozen=True)
class LoggingConfig:
    level: str = os.getenv("DOU_LOG_LEVEL", "INFO")
    json: bool = os.getenv("DOU_LOG_JSON", "0") == "1"
    log_file: str = os.getenv("DOU_LOG_FILE", "logs/dou.log")
    max_bytes: int = int(os.getenv("DOU_LOG_MAX_BYTES", "1048576"))      # 1MB
    backup_count: int = int(os.getenv("DOU_LOG_BACKUP_COUNT", "3"))

    # Compat retro: alguns módulos usam log_level
    @property
    def log_level(self) -> str:
        return self.level

# ---------------- Scraping avançado ----------------
@dataclass(frozen=True)
class AdvancedScrapeConfig:
    enabled_default: bool = os.getenv("DOU_ADV_SCRAPE_DEFAULT", "1") == "1"
    dropdown_strategy_order: tuple = (
        "already_open",
        "click",
        "force_click",
        "icon_click",
        "keyboard",
        "double_click",
    )

# ---------------- Planejamento ----------------
@dataclass(frozen=True)
class PlanningConfig:
    repopulation_timeout_ms: int = int(os.getenv("DOU_REPOP_TIMEOUT_MS", "15000"))
    repopulation_poll_ms: int = int(os.getenv("DOU_REPOP_POLL_MS", "200"))

# ---------------- Summarização avançada ----------------
@dataclass(frozen=True)
class AdvancedSummaryConfig:
    default_mode: str = os.getenv("DOU_ADV_SUMMARY_MODE", "center")
    default_lines: int = int(os.getenv("DOU_ADV_SUMMARY_LINES", "5"))
    penalty_long: float = float(os.getenv("DOU_ADV_SUMMARY_PENALTY_LONG", "0.4"))
    penalty_short: float = float(os.getenv("DOU_ADV_SUMMARY_PENALTY_SHORT", "0.4"))

# ---------------- Settings globais ----------------
@dataclass(frozen=True)
class Settings:
    timeouts: TimeoutConfig = TimeoutConfig()
    scroll: ScrollConfig = ScrollConfig()
    dropdown: DropdownConfig = DropdownConfig()
    summary: SummaryConfig = SummaryConfig()
    files: FileConfig = FileConfig()
    search: SearchConfig = SearchConfig()
    cookies: CookieConfig = CookieConfig()
    logging: LoggingConfig = LoggingConfig()
    advanced: AdvancedScrapeConfig = AdvancedScrapeConfig()
    planning: PlanningConfig = PlanningConfig()
    adv_summary: AdvancedSummaryConfig = AdvancedSummaryConfig()

SETTINGS = Settings()
