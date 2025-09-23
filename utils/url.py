from urllib.parse import urljoin, urlparse

def origin_of(url: str) -> str:
    """
    Obtém a origem (scheme://host) de uma URL.
    
    Args:
        url: URL para extrair a origem
        
    Returns:
        String contendo a origem da URL
    """
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return "https://www.in.gov.br"

def abs_url(base_or_page_url: str, href: str) -> str:
    """
    Converte uma URL relativa em absoluta.
    
    Args:
        base_or_page_url: URL base
        href: URL relativa ou absoluta
        
    Returns:
        URL absoluta
    """
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    base = origin_of(base_or_page_url)
    return urljoin(base + "/", href)
