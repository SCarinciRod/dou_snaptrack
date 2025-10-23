from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from .log_utils import get_logger

logger = get_logger(__name__)

# Padrões regex pré-compilados para performance
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_NEWLINE_PATTERN = re.compile(r"[\r\n]+")
_DOU_METADATA_1 = re.compile(r"\b(di[áa]rio oficial da uni[aã]o|imprensa nacional)\b", re.IGNORECASE)
_DOU_METADATA_2 = re.compile(r"\b(publicado em|edi[cç][aã]o|se[cç][aã]o|p[aá]gina|[oó]rg[aã]o)\b", re.IGNORECASE)
_DOU_METADATA_3 = re.compile(r"\b(bras[aã]o)\b", re.IGNORECASE)
_DOU_DISCLAIMER = re.compile(r"este conte[úu]do n[aã]o substitui", re.IGNORECASE)
_DOU_LAYOUT = re.compile(r"borda do rodap[eé]|logo da imprensa|rodap[eé]", re.IGNORECASE)
_HEADER_DATE_PATTERN = re.compile(r"\b(MENSAGEM\s+N[ºO]|N[ºO]\s+\d|de\s+\d{1,2}\s+de)\b", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_MULTI_DOT_PATTERN = re.compile(r"\.+")
_TRAILING_WORD_PATTERN = re.compile(r"\s+\S*$")
_ORDINAL_PREFIX_PATTERN = re.compile(r"^\d+º\s+")


def remove_dou_metadata(text: str) -> str:
    """Remove linhas e trechos típicos de metadados do DOU para não poluir resumos.

    Filtra cabeçalhos como "Diário Oficial da União", "Publicado em:",
    "Edição", "Seção", "Página", "Órgão", "Imprensa Nacional", etc.
    Mantém demais linhas intactas.
    """
    if not text:
        return ""

    # Remover tags HTML simples que possam estar presentes
    t = _HTML_TAG_PATTERN.sub(" ", text)
    lines = _NEWLINE_PATTERN.split(t)
    cleaned: list[str] = []
    for ln in lines:
        low = ln.strip().lower()
        if not low:
            continue
        # Padrões de metadados do DOU a remover
        if _DOU_METADATA_1.search(low):
            continue
        if _DOU_METADATA_2.search(low):
            continue
        if _DOU_METADATA_3.search(low):
            continue
        # Disclaimers e elementos de layout
        if _DOU_DISCLAIMER.search(low):
            continue
        if _DOU_LAYOUT.search(low):
            continue
        cleaned.append(ln)

    return "\n".join(cleaned)


def split_doc_header(text: str) -> Tuple[Optional[str], str]:
    """Localiza o cabeçalho do ato em qualquer ponto das primeiras linhas e retorna (header, body)."""
    if not text:
        return None, ""

    # Remover tags HTML simples e normalizar quebras
    raw = _HTML_TAG_PATTERN.sub(" ", text)
    # Limitar a janela de busca para desempenho, mas suficientemente ampla
    raw_window = raw[:4000]
    lines = _NEWLINE_PATTERN.split(raw_window)
    head_candidates = []
    for ln in lines[:50]:
        s = ln.strip()
        if not s:
            continue
        # Não descarte linhas com metadados — o cabeçalho pode estar nelas
        head_candidates.append(s)
    blob = "\n".join(head_candidates)

    # Alternativas com e sem acentuação
    doc_alt = [
        "PORTARIA CONJUNTA", "INSTRUÇÃO NORMATIVA", "INSTRUCAO NORMATIVA", "DECRETO-LEI",
        "MEDIDA PROVISÓRIA", "MEDIDA PROVISORIA", "ORDEM DE SERVIÇO", "ORDEM DE SERVICO",
        "RESOLUÇÃO", "RESOLUCAO", "DELIBERAÇÃO", "DELIBERACAO", "RETIFICAÇÃO", "RETIFICACAO",
        "COMUNICADO", "MENSAGEM", "EXTRATO", "PARECER", "DESPACHO", "EDITAL", "DECRETO",
        "PORTARIA", "LEI", "ATO", "AVISO"
    ]
    doc_alt_sorted = sorted(doc_alt, key=len, reverse=True)

    # Encontrar primeira ocorrência de qualquer tipo dentro do blob
    found = None
    start_idx = None
    upper_blob = blob.upper()
    for dt in doc_alt_sorted:
        i = upper_blob.find(dt)
        if i != -1 and (start_idx is None or i < start_idx):
            start_idx = i
            found = dt
    if start_idx is None:
        # fallback: primeira linha com alta proporção de maiúsculas
        for s in head_candidates:
            letters = [ch for ch in s if ch.isalpha()]
            if not letters:
                continue
            upp = sum(1 for ch in letters if ch.isupper())
            if upp / max(1, len(letters)) >= 0.6 and len(s) >= 10:
                header = s
                # body é o restante após esta linha aproximada
                idx = raw.find(s)
                if idx != -1:
                    body = raw[idx + len(s):].lstrip(" \t\r\n—-:")
                    return header, body
                return header, raw
        return None, text

    # Determinar fim do cabeçalho: até primeiro ponto final ou quebra de linha subsequente
    after = blob[start_idx:]
    # Tentar englobar múltiplas linhas até primeiro ponto final
    header_lines = []
    remain = after
    while True:
        ln = remain.split("\n", 1)[0]
        header_lines.append(ln.strip())
        # parar se achou ponto final
        if "." in ln:
            break
        # adicionar próxima linha somente se parecer parte do cabeçalho
        tail = remain[len(ln) + (1 if "\n" in remain else 0):]
        if not tail:
            break
        nxt = tail.split("\n", 1)[0].strip()
        if _HEADER_DATE_PATTERN.search(nxt):
            remain = tail
            continue
        # se a próxima linha ainda for majoritariamente maiúscula, considerar também
        letters = [ch for ch in nxt if ch.isalpha()]
        upp = sum(1 for ch in letters if ch.isupper()) if letters else 0
        if letters and upp / len(letters) >= 0.6:
            remain = tail
            continue
        break
    header = _WHITESPACE_PATTERN.sub(" ", " ".join(header_lines)).strip()

    # Construir body removendo o header da primeira ocorrência no raw original
    # Usar uma busca case-insensitive para achar a mesma fatia
    pattern = re.escape(header[:80])  # usar prefixo para casar de forma robusta
    m_body = re.search(pattern, raw, flags=re.I)
    if m_body:
        body = raw[m_body.end():].lstrip(" \t\r\n—-:")
    else:
        body = raw

    return header, body


def extract_doc_header_line(it: Dict[str, Any]) -> Optional[str]:
    """Compat: extrai apenas o header do texto do item, com fallback em campos do item."""
    text = it.get("texto") or it.get("ementa") or ""
    header, _ = split_doc_header(text)
    if header:
        return header

    # Fallback para campos do item
    candidates: list[str] = []
    for key in ("titulo", "titulo_listagem", "title_friendly"):
        v = it.get(key)
        if v:
            candidates.append(str(v).strip())
    blob = " ".join(candidates)

    tipo = (it.get("tipo_ato") or "").strip()
    if tipo:
        m = re.search(r"\bN[ºO]\s*[\w\-./]+", blob, flags=re.I)
        if m:
            return f"{tipo.upper()} {m.group(0)}"[:200]
        return tipo.upper()[:200]
    return None


def extract_article1_section(text: str) -> str:
    """Tenta extrair somente o conteúdo do Art. 1º (ou Artigo 1º)."""
    if not text:
        return ""
    t = text
    # normalizar espaços para facilitar o recorte
    t = re.sub(r"\s+", " ", t).strip()

    # localizar início do art. 1º (com ou sem o prefixo "Art." ou "Artigo")
    m1 = re.search(r"\b(?:Art\.?|Artigo)\s*1(º|o)?\b[:\-]?", t, flags=re.I)
    if not m1:
        return ""
    start = m1.start()

    # localizar início do art. 2º a partir do fim do match 1 (com ou sem prefixo)
    rest = t[m1.end():]
    m2 = re.search(r"\b(?:Art\.?|Artigo)\s*2(º|o)?\b", rest, flags=re.I)
    if m2:
        end = m1.end() + m2.start()
    else:
        end = len(t)

    return t[start:end].strip()


def strip_legalese_preamble(text: str) -> str:
    """Remove trechos iniciais de formalidades jurídicas e corta até a parte dispositiva."""
    if not text:
        return ""

    t = text
    # Normalizar quebras para facilitar recortes
    t = re.sub(r"\s+", " ", t).strip()

    low = t.lower()
    markers = [
        "resolve:", "resolvo:", "decide:", "decido:",
        "torna público:", "torno público:", "torna publico:", "torno publico:"
    ]
    cut_idx = -1
    for m in markers:
        i = low.find(m)
        if i >= 0:
            cut_idx = max(cut_idx, i + len(m))
            break
    if cut_idx >= 0:
        t = t[cut_idx:].lstrip(" -:;—")
        low = t.lower()

    # Remover preâmbulos comuns no início
    preambles = [
        r"^(o|a)\s+minist[roa]\s+de\s+estado.*?\b",  # O MINISTRO DE ESTADO...
        r"no\s+uso\s+de\s+suas\s+atribui[cç][oõ]es.*?\b",
        r"tendo\s+em\s+vista.*?\b",
        r"considerando.*?\b",
        r"nos\s+termos\s+do.*?\b",
        r"com\s+fundamento\s+no.*?\b",
        r"de\s+acordo\s+com.*?\b",
    ]
    for pat in preambles:
        t = re.sub(pat, "", t, flags=re.I)
        t = t.strip(" -:;— ")

    # Importante: preservar marcadores "Art."/"Artigo" para permitir recorte posterior do Art. 1º
    # (a normalização que removia "Art." impedia extract_article1_section de localizar os artigos)
    return t.strip()


def first_sentences(text: str, max_sents: int = 2) -> str:
    sents = [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
    if not sents:
        return ""
    out = ". ".join(sents[:max_sents])
    return out + ("" if out.endswith(".") else ".")


def cap_sentences(text: str, max_sents: int) -> str:
    """Corta o texto para no máximo N frases simples, preservando ponto final."""
    if max_sents <= 0 or not text:
        return text or ""
    sents = [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
    if not sents:
        # Fallback quando não há pontuação: sintetizar a partir das primeiras palavras
        words = re.findall(r"\w+[\w-]*", text)
        if not words:
            return ""
        # Aproximar "max_sents" por blocos de ~12 palavras cada
        max_words = max(8, max_sents * 12)
        out = " ".join(words[:max_words]).strip()
        return out + ("" if out.endswith(".") else ".")
    out = ". ".join(sents[:max_sents]).strip()
    # Limite adicional em caracteres para evitar trechos extensos
    char_limit = max(180, max_sents * 240)
    if len(out) > char_limit:
        # cortar em limite de palavra
        cut = out[:char_limit]
        cut = re.sub(r"\s+\S*$", "", cut).strip()
        out = cut or out[:char_limit].strip()
    return out + ("" if out.endswith(".") else ".")


def final_clean_snippet(snippet: str) -> str:
    """Limpa eventuais resíduos no snippet: metadados, espaços e múltiplos pontos."""
    if not snippet:
        return ""
    s = remove_dou_metadata(snippet)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\.+", ".", s)
    return s


def make_bullet_title_from_text(text: str, max_len: int = 140) -> Optional[str]:
    """Gera um título amigável a partir do texto já limpo de juridiquês."""
    if not text:
        return None
    head = first_sentences(text, 1)
    if not head:
        return None
    head = re.sub(r"^\d+º\s+", "", head).strip()  # remove ordinal inicial
    return head[:max_len]
