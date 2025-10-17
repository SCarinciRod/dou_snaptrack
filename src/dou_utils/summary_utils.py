# summary_utils.py
# Utilitários para geração de resumo automático de textos do DOU

import re
import unicodedata
from typing import List, Optional, Tuple
from .text_cleaning import remove_dou_metadata, strip_legalese_preamble, extract_article1_section

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.strip().lower())

def split_sentences(pt_text: str) -> List[str]:
    if not pt_text:
        return []
    text = pt_text
    # Remover ponto de abreviações comuns sem usar look-behind variável
    text = re.sub(r"\b(Sr|Sra|Dr|Dra)\.", r"\1", text)
    text = re.sub(r"\b(et al)\.", r"\1", text, flags=re.I)
    parts = re.split(r"(?<=[\.\!\?;])\s+", text)
    sents = [re.sub(r"\s+", " ", s).strip() for s in parts if s and s.strip()]
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
    if not text:
        return ""
    # Remover metadados do DOU e formalidades jurídicas básicas
    t = remove_dou_metadata(text)
    t = strip_legalese_preamble(t)
    t = re.sub(r"\s+", " ", t).strip()
    patterns = [
        r"Este conteúdo não substitui.*?$",
        r"Publicado em\s*\d{1,2}/\d{1,2}/\d{2,4}.*?$",
        r"Imprensa Nacional.*?$",
        r"Ministério da.*?Diário Oficial.*?$",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.I)
    t = re.sub(r"^\s*(PORTARIA|RESOLUÇÃO|DECRETO|ATO|MENSAGEM|DESPACHO|EXTRATO|COMUNICADO)\s*[-–—]?\s*", "", t, flags=re.I)
    t = t.strip()
    # Preferir conteúdo do Art. 1º quando existir (para atos articulados)
    a1 = extract_article1_section(t)
    return (a1 or t).strip()

def _has_article_markers(text: str) -> bool:
    if not text:
        return False
    return re.search(r"\b(?:Art\.?|Artigo)\s*1(º|o)?\b", text, flags=re.I) is not None

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

def _find_priority_sentence(sents: List[str]) -> Optional[Tuple[int, str]]:
    """Procura uma sentença com verbos decisórios comuns (útil para DESPACHO/atos sem artigos)."""
    if not sents:
        return None
    pat = re.compile(r"\b(decis[aã]o:|nego\s+provimento|defiro|indefer[io]|determino|autorizo|autoriza|habilita|desabilita|estabelece|fica\s+estabelecido|prorroga|renova|entra\s+em\s+vigor)\b", re.I)
    window = sents[: min(10, len(sents))]
    for i, s in enumerate(window):
        if pat.search(s or ""):
            return (i, s)
    return None

def summarize_text(text: str, max_lines: int = 7, keywords: Optional[List[str]] = None, mode: str = "center") -> str:
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

    # Padrões de enumeração a penalizar (listas tipo I -, II -, alíneas, incisos)
    enum_pat = re.compile(r"^\s*(?:[IVXLCDM]{1,6}|\d+|[a-z]\)|[A-Z]\))\s*[-–—)]\s+", re.I)
    money_pat = re.compile(r"R\$\s?\d", re.I)
    date_pat = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\bde\s+[A-Za-zçáéíóúãõâêô]+\s+de\s+\d{4}\b", re.I)

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
        if money_pat.search(s):
            score += 0.4
        if date_pat.search(s):
            score += 0.2
        # Penalidade por enumeração/itens de lista normativos
        if enum_pat.search(s):
            score -= 0.7
        scores.append((score, i, s))

    scores.sort(key=lambda t: (-t[0], t[1]))
    picked_idx = sorted(i for _, i, _ in scores[:max_lines])

    # Garantir inclusão da sentença prioritária, se houver espaço e ainda não selecionada
    if pri_idx and pri_idx[0] not in picked_idx:
        picked_idx = sorted((picked_idx + [pri_idx[0]])[: max_lines])

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
