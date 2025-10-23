from __future__ import annotations
import re
import unicodedata
from typing import Optional

# Regex pré-compilado para performance
_FILENAME_INVALID_CHARS = re.compile(r'[\\/:*?"<>\|\r\n\t]+')

def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())


def sanitize_filename(name: str, max_len: int = 180) -> str:
    """Normaliza e limpa nome de arquivo, removendo caracteres inválidos.
    
    Args:
        name: Nome original a ser sanitizado
        max_len: Tamanho máximo do nome (default=180)
        
    Returns:
        Nome de arquivo sanitizado e seguro para sistema de arquivos
        
    Examples:
        >>> sanitize_filename("meu/arquivo*.txt")
        'meu_arquivo_.txt'
        >>> sanitize_filename("", max_len=50)
        'out'
    """
    if not name:
        return "out"
    
    # Remove caracteres inválidos para nomes de arquivo (Windows e Unix)
    cleaned = _FILENAME_INVALID_CHARS.sub("_", name)
    
    # Remove espaços/underscores do início e fim
    cleaned = cleaned.strip("_ ")
    
    # Truncar se necessário
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip("_ ")
    
    # Garantir que não está vazio após limpeza
    return cleaned or "out"
