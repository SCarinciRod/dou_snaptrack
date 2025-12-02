"""
Exceções customizadas para o projeto DOU SnapTrack.

Hierarquia de exceções:

    DouSnapTrackError (base)
    ├── BrowserError
    │   ├── BrowserNotFoundError
    │   └── BrowserLaunchError
    ├── ScrapingError
    │   ├── PageLoadError
    │   ├── ElementNotFoundError
    │   └── DropdownError
    ├── NetworkError
    │   ├── TimeoutError
    │   └── ConnectionError
    └── DataError
        ├── ParseError
        └── ValidationError

Exemplo:
    >>> try:
    ...     page.goto(url, timeout=30000)
    ... except PlaywrightTimeoutError:
    ...     raise PageLoadError(f"Timeout ao carregar {url}")
"""

from __future__ import annotations


class DouSnapTrackError(Exception):
    """
    Exceção base para todas as exceções do projeto.

    Todas as exceções customizadas devem herdar desta classe
    para permitir captura genérica quando necessário.
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# =============================================================================
# BROWSER ERRORS
# =============================================================================


class BrowserError(DouSnapTrackError):
    """Erros relacionados ao browser Playwright."""

    pass


class BrowserNotFoundError(BrowserError):
    """
    Chrome/Edge não encontrado no sistema.

    Ocorre quando nenhum browser compatível está instalado
    ou os caminhos configurados são inválidos.
    """

    def __init__(self, message: str = "Nenhum browser compatível encontrado"):
        super().__init__(message)


class BrowserLaunchError(BrowserError):
    """
    Falha ao iniciar o browser.

    Pode ocorrer por permissões, recursos insuficientes,
    ou problemas com o Playwright.
    """

    pass


# =============================================================================
# SCRAPING ERRORS
# =============================================================================


class ScrapingError(DouSnapTrackError):
    """Erros durante scraping de páginas."""

    pass


class PageLoadError(ScrapingError):
    """
    Falha ao carregar página.

    Pode indicar URL inválida, servidor fora do ar,
    ou problemas de rede.
    """

    def __init__(self, url: str, reason: str = ""):
        message = f"Falha ao carregar página: {url}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"url": url})
        self.url = url


class ElementNotFoundError(ScrapingError):
    """
    Elemento não encontrado na página.

    Pode indicar mudança na estrutura do site
    ou carregamento incompleto.
    """

    def __init__(self, selector: str, context: str = ""):
        message = f"Elemento não encontrado: {selector}"
        if context:
            message += f" em {context}"
        super().__init__(message, details={"selector": selector})
        self.selector = selector


class DropdownError(ScrapingError):
    """
    Erro ao manipular dropdown.

    Específico para problemas com seletores de órgão/subordinada.
    """

    def __init__(self, dropdown_id: str, action: str, reason: str = ""):
        message = f"Erro no dropdown '{dropdown_id}' ao {action}"
        if reason:
            message += f": {reason}"
        super().__init__(message, details={"dropdown_id": dropdown_id, "action": action})


# =============================================================================
# NETWORK ERRORS
# =============================================================================


class NetworkError(DouSnapTrackError):
    """Erros de rede/conexão."""

    pass


class TimeoutError(NetworkError):
    """
    Timeout em operação de rede.

    Não confundir com builtins.TimeoutError.
    Use: from dou_snaptrack.utils.exceptions import TimeoutError as SnapTrackTimeout
    """

    def __init__(self, operation: str, timeout_ms: int = 0):
        message = f"Timeout após {timeout_ms}ms em: {operation}"
        super().__init__(message, details={"operation": operation, "timeout_ms": timeout_ms})
        self.operation = operation
        self.timeout_ms = timeout_ms

    def __reduce__(self):
        """Support for pickle serialization."""
        return (self.__class__, (self.operation, self.timeout_ms))


class ConnectionError(NetworkError):
    """
    Falha de conexão.

    Não confundir com builtins.ConnectionError.
    Use: from dou_snaptrack.utils.exceptions import ConnectionError as SnapTrackConnectionError
    """

    def __init__(self, url: str, reason: str = ""):
        message = f"Falha de conexão com: {url}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"url": url})
        self.url = url


# =============================================================================
# DATA ERRORS
# =============================================================================


class DataError(DouSnapTrackError):
    """Erros de dados/validação."""

    pass


class ParseError(DataError):
    """
    Erro ao parsear dados.

    JSON inválido, HTML malformado, etc.
    """

    def __init__(self, data_type: str, reason: str = ""):
        message = f"Erro ao parsear {data_type}"
        if reason:
            message += f": {reason}"
        super().__init__(message, details={"data_type": data_type})


class ValidationError(DataError):
    """
    Dados não passaram na validação.

    Campos obrigatórios faltando, formatos inválidos, etc.
    """

    def __init__(self, field: str, value: str, expected: str = ""):
        message = f"Valor inválido para '{field}': {value}"
        if expected:
            message += f" (esperado: {expected})"
        super().__init__(message, details={"field": field, "value": value})


# =============================================================================
# SUBPROCESS ERRORS
# =============================================================================


class SubprocessError(DouSnapTrackError):
    """Erros em execução de subprocessos."""

    def __init__(self, command: str, exit_code: int, stderr: str = ""):
        message = f"Subprocess falhou (exit code {exit_code}): {command}"
        if stderr:
            message += f"\n{stderr[:500]}"
        super().__init__(message, details={"command": command, "exit_code": exit_code})
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr

    def __reduce__(self):
        """Support for pickle serialization."""
        return (self.__class__, (self.command, self.exit_code, self.stderr))


# =============================================================================
# HELPER: Converter exceções Playwright
# =============================================================================


def wrap_playwright_error(error: Exception, context: str = "") -> DouSnapTrackError:
    """
    Converte exceções do Playwright para exceções do projeto.

    Args:
        error: Exceção original do Playwright.
        context: Contexto adicional para a mensagem.

    Returns:
        Exceção apropriada do projeto.

    Example:
        >>> try:
        ...     page.goto(url)
        ... except Exception as e:
        ...     raise wrap_playwright_error(e, f"carregando {url}")
    """
    error_str = str(error).lower()

    # Check selector/locator BEFORE timeout ("locator timeout" should be ElementNotFoundError)
    if "selector" in error_str or "locator" in error_str:
        return ElementNotFoundError(context or "seletor desconhecido")
    if "timeout" in error_str:
        return TimeoutError(context or "operação Playwright", timeout_ms=0)
    if "net::" in error_str or "connection" in error_str:
        return ConnectionError(context or "URL desconhecida", str(error))

    return ScrapingError(f"{context}: {error}" if context else str(error))
