# summary_utils.py
# Utilitários para geração de resumo automático de textos do DOU

import re
import unicodedata

from .text_cleaning import extract_article1_section, remove_dou_metadata, strip_legalese_preamble

# Padrões regex pré-compilados para performance
_WHITESPACE_PATTERN = re.compile(r"\s+")
_ABBREV_SR_PATTERN = re.compile(r"\b(Sr|Sra|Dr|Dra)\.")
_ABBREV_ETAL_PATTERN = re.compile(r"\b(et al)\.", re.IGNORECASE)
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[\.\!\?;])\s+")
_ARTICLE1_PATTERN = re.compile(r"\b(?:Art\.?|Artigo)\s*1(º|o)?\b", re.IGNORECASE)
_DOC_TYPE_PREFIX_PATTERN = re.compile(
    r"^\s*(PORTARIA|RESOLUÇÃO|DECRETO|ATO|MENSAGEM|DESPACHO|EXTRATO|COMUNICADO)\s*[-]?\s*",
    re.IGNORECASE
)
_PRIORITY_VERB_PATTERN = re.compile(
    r"\b(decis[aã]o:|nego\s+provimento|defiro|indefer[io]|determino|autorizo|autoriza|habilita|desabilita|estabelece|fica\s+estabelecido|prorroga|renova|entra\s+em\s+vigor)\b",
    re.IGNORECASE
)
_ENUMERATION_PATTERN = re.compile(r"^\s*(?:[IVXLCDM]{1,6}|\d+|[a-z]\)|[A-Z]\))\s*[-)\s]+", re.IGNORECASE)
_MONEY_PATTERN = re.compile(r"R\$\s?\d", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\bde\s+[A-Za-zçáéíóúãõâêô]+\s+de\s+\d{4}\b", re.IGNORECASE)
# Padrão para detectar sentenças que parecem cabeçalhos/metadados do DOU
_DOU_HEADER_SENTENCE = re.compile(
    r"(brasão.*?diário oficial|publicado em.*?edição.*?seção|órgão.*?ministério.*?publicado)",
    re.IGNORECASE
)

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return _WHITESPACE_PATTERN.sub(" ", s.strip().lower())

def split_sentences(pt_text: str) -> list[str]:
    if not pt_text:
        return []
    text = pt_text
    # Remover ponto de abreviações comuns sem usar look-behind variável
    text = _ABBREV_SR_PATTERN.sub(r"\1", text)
    text = _ABBREV_ETAL_PATTERN.sub(r"\1", text)
    parts = _SENTENCE_SPLIT_PATTERN.split(text)
    sents = [_WHITESPACE_PATTERN.sub(" ", s).strip() for s in parts if s and s.strip()]
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

def clean_text_for_summary(text: str) -> str:
    """Remove cabeçalhos DOU, metadados e juridiquês, retornando texto limpo para sumarização.

    Args:
        text: Texto completo do ato/publicação

    Returns:
        Texto limpo, preferencialmente do Art. 1º se existir
    """
    if not text:
        return ""

    # CRÍTICO: Remover cabeçalho DOU inline ANTES de tudo
    # Padrão: Brasão...Diário Oficial...Publicado/Edição...Seção/Página...Órgão:...até tipo do ato
    # Captura múltiplos níveis de órgão (ex: Ministério/Universidade/Pró-Reitoria/Departamento)
    # Lookahead aceita tipo do ato COM ou SEM qualificador (PORTARIA Nº ou só RETIFICAÇÃO)
    # Expandido para incluir DECISÃO e outros tipos comuns
    t = re.sub(
        r"^.*?(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:[^\n]*?\s*(?=(?:PORTARIA|DECRETO|DESPACHO|RESOLUÇÃO|ATO|EXTRATO|PAUTA|DELIBERAÇÃO|ALVARÁ|RETIFICAÇÃO|SÚMULA|DECISÃO|ORDEM|EDITAL|AVISO|INSTRUÇÃO|Portaria|Decreto|Despacho|Decisão|MENSAGEM|Mensagem|Retificação|Súmula)(?:\s|$))",
        "",
        text,
        count=1,
        flags=re.I | re.DOTALL
    )

    # Limpar resíduo comum "do Ministro" após remoção do cabeçalho
    if len(t) < len(text):  # Apenas se regex removeu algo
        t = re.sub(r"^(?:do|da|de)\s+\w+\s+", "", t, count=1, flags=re.I)

    # Se a regex não encontrou padrão DOU, tentar fallback conservador
    # MAS APENAS se o texto tem múltiplas linhas E contém padrões típicos de cabeçalho
    if t == text:  # Regex não removeu nada
        lines_count = len(t.split('\n'))
        has_metadata_pattern = bool(re.search(r"(?:Brasão|Publicado em|Edição|Órgão).*?(?:Seção|Página)", t, re.I | re.DOTALL))
        # Só aplicar remove_dou_metadata se há múltiplas linhas E padrões de metadata
        if lines_count > 3 and has_metadata_pattern:
            t = remove_dou_metadata(t)
        # Senão, o texto já está limpo (ex: Art. 1º vindo de extract já processado)

    t = strip_legalese_preamble(t)
    t = _WHITESPACE_PATTERN.sub(" ", t).strip()

    # Padrões adicionais para limpeza
    patterns = [
        r"Este conteúdo não substitui.*?$",
        r"Imprensa Nacional.*?$",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.I | re.DOTALL)

    t = _DOC_TYPE_PREFIX_PATTERN.sub("", t)
    t = t.strip()

    # Preferir conteúdo do Art. 1º quando existir (para atos articulados)
    a1 = extract_article1_section(t)
    result = (a1 or t).strip()

    return result

def _has_article_markers(text: str) -> bool:
    if not text:
        return False
    return _ARTICLE1_PATTERN.search(text) is not None

def _detect_genre_header(text: str) -> str:
    """Detecta gênero aproximado a partir do cabeçalho do texto bruto.

    Retorna um rótulo simples como 'despacho', 'aviso', 'extrato', 'comunicado', 'mensagem', 'portaria', 'decreto', etc.,
    ou string vazia quando não detectado.
    """
    if not text:
        return ""
    head = text.strip()[:2000]
    head_up = head.upper()
    for g in ("DESPACHO", "AVISO", "EXTRATO", "COMUNICADO", "MENSAGEM", "PORTARIA", "DECRETO", "RESOLU", "ATO"):
        if g in head_up:
            return g.lower()
    return ""

def _find_priority_sentence(sents: list[str]) -> tuple[int, str] | None:
    """Procura uma sentença com verbos decisórios comuns (útil para DESPACHO/atos sem artigos)."""
    if not sents:
        return None
    window = sents[: min(10, len(sents))]
    for i, s in enumerate(window):
        if _PRIORITY_VERB_PATTERN.search(s or ""):
            return (i, s)
    return None

def summarize_text(text: str, max_lines: int = 7, keywords: list[str] | None = None, mode: str = "center") -> str:
    """Sumariza texto removendo cabeçalhos DOU e selecionando sentenças relevantes."""
    if not text:
        return ""

    base = clean_text_for_summary(text)
    sents = split_sentences(base)

    # Robust fallback: se não houver sentenças, sintetizar a partir das primeiras palavras
    if not sents:
        words = re.findall(r"\w+[\w-]*", base)
        if not words:
            return ""
        chunk = " ".join(words[: max(12, max_lines * 14)]).strip()
        return chunk + ("" if chunk.endswith(".") else ".")

    if len(sents) <= max_lines:
        return "\n".join(sents[:max_lines])

    kws = [k.strip().lower() for k in (keywords or []) if k.strip()]
    kw_set = set(kws)

    def tokens(s: str):
        raw = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return [w for w in re.findall(r"[a-z0-9]+", raw.lower()) if len(w) >= 3]

    lex = []
    for s in sents:
        toks = tokens(s)
        unique = len(set(toks))
        lex.append(unique / (1 + len(toks)))

    # Ajuste de modo: preferir 'center' por padrão; forçar 'lead' apenas para 'despacho'
    mode_local = (mode or "center").lower()
    genre = _detect_genre_header(text)
    if genre == "despacho":
        mode_local = "lead"

    n = len(sents)
    pos = []
    for i in range(n):
        if mode_local == "lead":
            pos.append(1.0 - (i / n) * 0.85)
        else:
            x = (i - (n - 1) / 2) / (n / 2)
            pos.append(1.0 - (x * x))

    kscore = []
    for s in sents:
        st = s.lower()
        hits = sum(1 for k in kw_set if k and k in st)
        kscore.append(hits)

    scores = []
    # Dar um bônus para frases com verbos decisórios (sempre que aparecerem)
    pri_idx = _find_priority_sentence(sents)

    for i, s in enumerate(sents):
        if mode_local == "keywords-first":
            w_k, w_l, w_p = 1.6, 1.0, 0.6
        elif mode_local == "lead":
            w_k, w_l, w_p = 1.0, 0.8, 1.6
        else:
            w_k, w_l, w_p = 1.4, 1.0, 1.2
        score = (w_k * kscore[i]) + (w_l * lex[i]) + (w_p * pos[i])
        if len(s) > 450:
            score -= 0.4
        if len(s) < 40 and kscore[i] == 0:
            score -= 0.5
        # Bônus por frases decisórias
        if pri_idx and i == pri_idx[0]:
            score += 0.9
        # Bônus por valores/datas
        if _MONEY_PATTERN.search(s):
            score += 0.4
        if _DATE_PATTERN.search(s):
            score += 0.2
        # PENALIDADE FORTE para sentenças que parecem cabeçalhos do DOU
        if _DOU_HEADER_SENTENCE.search(s):
            score -= 2.0
        # Penalidade adicional por menções a "Edição", "Seção", "Página" isoladas
        s_low = s.lower()
        metadata_count = sum([
            "edição" in s_low or "edicao" in s_low,
            "seção" in s_low or "secao" in s_low,
            "página" in s_low or "pagina" in s_low,
            "publicado em" in s_low,
            "brasão" in s_low or "brasao" in s_low
        ])
        if metadata_count >= 2:
            score -= 1.5
        # Penalidade por enumeração/itens de lista normativos
        if _ENUMERATION_PATTERN.search(s):
            score -= 0.7
        scores.append((score, i, s))

    scores.sort(key=lambda t: (-t[0], t[1]))
    picked_idx = sorted(i for _, i, _ in scores[:max_lines])

    # Garantir inclusão da sentença prioritária, se houver espaço e ainda não selecionada
    if pri_idx and pri_idx[0] not in picked_idx:
        picked_idx = sorted(([*picked_idx, pri_idx[0]])[: max_lines])

    if len(picked_idx) < max_lines:
        need = max_lines - len(picked_idx)
        pool = [i for i in range(n) if i not in picked_idx]
        anchor = scores[0][1]
        pool.sort(key=lambda i: abs(i - anchor))
        picked_idx.extend(pool[:need])
        picked_idx = sorted(set(picked_idx))[:max_lines]

    out_lines = [sents[i].strip() for i in picked_idx]
    final, seen = [], set()
    for ln in out_lines:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(ln)
        if len(final) >= max_lines:
            break
    # Fallback derradeiro: se ainda ficou vazio por algum motivo, usar as primeiras sentenças (lead)
    if not final:
        lead = sents[:max_lines]
        if lead:
            return "\n".join(lead).strip()
    return "\n".join(final[:max_lines]).strip()
