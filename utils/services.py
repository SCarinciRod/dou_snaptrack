# utils/text.py
# Funções de processamento de texto

import re
import unicodedata
from typing import Optional, List, Dict, Any

def normalize_text(s: Optional[str]) -> str:
    """Normaliza texto removendo acentos e transformando para lowercase."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())

def trim_placeholders(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove opções de placeholder comuns em dropdowns."""
    bad = {
        "selecionar organizacao principal",
        "selecionar organização principal",
        "selecionar organizacao subordinada",
        "selecionar organização subordinada",
        "selecionar tipo do ato",
        "selecionar",
        "todos",
    }
    out = []
    for o in options or []:
        t = normalize_text(o.get("text") or "")
        if t in bad: 
            continue
        out.append(o)
    return out

def filter_opts(options: List[Dict[str, Any]], select_regex: Optional[str], 
                pick_list: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    """
    Aplica filtros às opções:
      - select_regex: regex normal; se nada bater, fallback por tokens normalizados.
      - pick_list: lista de labels exatos (separados por vírgula).
      - limit: trunca no tamanho informado.
    """
    opts = options or []
    out = opts

    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in opts if pat.search(o.get("text") or "")]
        except re.error:
            out = []
        if not out:  # fallback por tokens normalizados
            tokens = [t.strip() for t in select_regex.splitlines() if t.strip()]
            tokens_norm = [normalize_text(t) for t in tokens]
            tmp = []
            for o in opts:
                nt = normalize_text(o.get("text") or "")
                if any(tok and tok in nt for tok in tokens_norm):
                    tmp.append(o)
            out = tmp

    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]

    if limit and limit > 0:
        out = out[:limit]

    return out

def sanitize_filename(name: str) -> str:
    """Sanitiza um texto para uso em nome de arquivo."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    return re.sub(r'\s+', "_", name.strip())

def _split_sentences(pt_text: str) -> List[str]:
    """Divide texto em português em sentenças."""
    # Implementação aqui...
    return []  # Implemente conforme necessário

def _clean_text_for_summary(text: str) -> str:
    """Limpa texto para sumarização."""
    # Implementação aqui...
    return text  # Implemente conforme necessário
