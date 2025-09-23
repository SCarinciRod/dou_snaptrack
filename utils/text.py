import re
import unicodedata
from typing import Optional

def normalize_text(s: Optional[str]) -> str:
    """
    Normaliza texto: remove acentos, converte para minúsculas e padroniza espaços.
    """
    if s is None:
        return ""
    # Normalização NFKD + remoção de caracteres não-ASCII
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Padroniza espaços
    return re.sub(r"\s+", " ", s.strip().lower())

def sanitize_filename(name: str) -> str:
    """
    Remove caracteres inválidos para nomes de arquivo.
    """
    name = re.sub(r'[\\/:*?"<>\|\r\n\t]+', "_", name)
    return name[:180].strip("_ ") or "out"

def _split_sentences(pt_text: str) -> list:
    """
    Segmentação simples e robusta para PT-BR.
    Evita quebrar em abreviações comuns e normaliza espaços.
    """
    if not pt_text:
        return []
    text = pt_text

    # Protege abreviações comuns (Sr., Sra., Dr., Dra., et al.)
    text = re.sub(r"(?<=\bSr|Sra|Dr|Dra)\.", "", text)
    text = re.sub(r"(?<=\bet al)\.", "", text, flags=re.I)

    # Quebra por fim de frase . ! ?
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    sents = [re.sub(r"\s+", " ", s).strip() for s in parts if s and s.strip()]
    
    # Remove duplicadas consecutivas e linhas muito curtas "ocosas"
    cleaned = []
    seen = set()
    for s in sents:
        if len(s) < 20 and not any(ch.isalpha() for ch in s):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)
    return cleaned

def _clean_text_for_summary(text: str) -> str:
    """
    Remove boilerplates comuns e normaliza espaços.
    Não é agressivo para evitar perda de conteúdo.
    """
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()

    # Remover cabeçalhos/rodapés comuns
    patterns = [
        r"Este conteúdo não substitui.*?$",
        r"Publicado em\s*\d{1,2}/\d{1,2}/\d{2,4}.*?$",
        r"Imprensa Nacional.*?$",
        r"Ministério da.*?Diário Oficial.*?$",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.I)

    # Remover repetições de título no início (rótulos)
    t = re.sub(r"^(?:\s*PORTARIA|RESOLUÇÃO|DECRETO|ATO|MENSAGEM)\s*[-–—]?\s*", "", t, flags=re.I)
    return t.strip()

def _css_escape(s: str) -> str:
    """Escape mínimo para seletores CSS com IDs arbitrários."""
    return re.sub(r'(\\.#:[\\>+~*^$|])', r'\\\1', s or "")
