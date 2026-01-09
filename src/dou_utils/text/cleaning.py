from __future__ import annotations

import re
from typing import Any

from dou_utils.log_utils import get_logger

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
_NUMERO_PATTERN = re.compile(r"\bN[ºO]\s*[\w\-./]+", re.I)
_ARTIGO_1_PATTERN = re.compile(r"\b(?:Art\.?|Artigo)\s*1(º|o)?\b[:\-]?", re.I)
_ARTIGO_2_PATTERN = re.compile(r"\b(?:Art\.?|Artigo)\s*2(º|o)?\b", re.I)
_LEADING_PUNCT_PATTERN = re.compile(r"^[\s\-:;—]+")
_BOTH_PUNCT_PATTERN = re.compile(r"^[\s\-:;—]+|[\s\-:;—]+$")
_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]\s+")
_WORDS_PATTERN = re.compile(r"\w+[\w-]*")


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


def split_doc_header(text: str) -> tuple[str | None, str]:
    """Localiza o cabeçalho do ato em qualquer ponto das primeiras linhas e retorna (header, body)."""
    from .helpers import (
        extract_body_from_raw,
        extract_header_lines,
        find_document_type_index,
        find_uppercase_line_header,
        get_document_types,
        prepare_text_window,
    )

    if not text:
        return None, ""

    # Prepare text window
    raw = _HTML_TAG_PATTERN.sub(" ", text)
    blob, head_candidates = prepare_text_window(raw)

    # Find document type
    doc_types = get_document_types()
    start_idx = find_document_type_index(blob, doc_types)

    # Fallback to uppercase heuristic
    if start_idx is None:
        header, body = find_uppercase_line_header(head_candidates, raw)
        if header:
            return header, body
        return None, text

    # Extract header lines
    after = blob[start_idx:]
    header_lines = extract_header_lines(after)
    header = _WHITESPACE_PATTERN.sub(" ", " ".join(header_lines)).strip()

    # Extract body
    body = extract_body_from_raw(header, raw)

    return header, body


def extract_doc_header_line(it: dict[str, Any]) -> str | None:
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
        m = _NUMERO_PATTERN.search(blob)
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
    t = _WHITESPACE_PATTERN.sub(" ", t).strip()

    # localizar início do art. 1º (com ou sem o prefixo "Art." ou "Artigo")
    m1 = _ARTIGO_1_PATTERN.search(t)
    if not m1:
        return ""
    start = m1.start()

    # localizar início do art. 2º a partir do fim do match 1 (com ou sem prefixo)
    rest = t[m1.end():]
    m2 = _ARTIGO_2_PATTERN.search(rest)
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
    t = _WHITESPACE_PATTERN.sub(" ", t).strip()

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
        t = _LEADING_PUNCT_PATTERN.sub('', t[cut_idx:])
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
        t = _BOTH_PUNCT_PATTERN.sub('', t)

    # Importante: preservar marcadores "Art."/"Artigo" para permitir recorte posterior do Art. 1º
    # (a normalização que removia "Art." impedia extract_article1_section de localizar os artigos)
    return t.strip()


def first_sentences(text: str, max_sents: int = 2) -> str:
    sents = [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]
    if not sents:
        return ""
    out = ". ".join(sents[:max_sents])
    return out + ("" if out.endswith(".") else ".")


def cap_sentences(text: str, max_sents: int) -> str:
    """Corta o texto para no máximo N frases simples, preservando ponto final."""
    if max_sents <= 0 or not text:
        return text or ""
    sents = [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]
    if not sents:
        # Fallback quando não há pontuação: sintetizar a partir das primeiras palavras
        words = _WORDS_PATTERN.findall(text)
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
        cut = _TRAILING_WORD_PATTERN.sub("", cut).strip()
        out = cut or out[:char_limit].strip()
    return out + ("" if out.endswith(".") else ".")


def final_clean_snippet(snippet: str) -> str:
    """Limpa eventuais resíduos no snippet: metadados, espaços e múltiplos pontos."""
    if not snippet:
        return ""
    s = remove_dou_metadata(snippet)
    s = _WHITESPACE_PATTERN.sub(" ", s).strip()
    s = _MULTI_DOT_PATTERN.sub(".", s)
    return s


def make_bullet_title_from_text(text: str, max_len: int = 140) -> str | None:
    """Gera um título amigável a partir do texto já limpo de juridiquês."""
    if not text:
        return None
    head = first_sentences(text, 1)
    if not head:
        return None
    head = _ORDINAL_PREFIX_PATTERN.sub("", head).strip()  # remove ordinal inicial
    return head[:max_len]
