# summary_utils.py
# Utilitários para geração de resumo automático de textos do DOU

import re
import unicodedata
from typing import List, Optional

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
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
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
    t = re.sub(r"\s+", " ", text).strip()
    patterns = [
        r"Este conteúdo não substitui.*?$",
        r"Publicado em\s*\d{1,2}/\d{1,2}/\d{2,4}.*?$",
        r"Imprensa Nacional.*?$",
        r"Ministério da.*?Diário Oficial.*?$",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.I)
    t = re.sub(r"^\s*(PORTARIA|RESOLUÇÃO|DECRETO|ATO|MENSAGEM)\s*[-–—]?\s*", "", t, flags=re.I)
    return t.strip()

def summarize_text(text: str, max_lines: int = 7, keywords: Optional[List[str]] = None, mode: str = "center") -> str:
    if not text:
        return ""
    base = clean_text_for_summary(text)
    sents = split_sentences(base)
    if not sents:
        return ""
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

    n = len(sents)
    pos = []
    for i in range(n):
        if mode == "lead":
            pos.append(1.0 - (i / n) * 0.8)
        else:
            x = (i - (n - 1) / 2) / (n / 2)
            pos.append(1.0 - (x * x))

    kscore = []
    for s in sents:
        st = s.lower()
        hits = sum(1 for k in kw_set if k and k in st)
        kscore.append(hits)

    scores = []
    for i, s in enumerate(sents):
        if mode == "keywords-first":
            w_k, w_l, w_p = 1.6, 1.0, 0.6
        elif mode == "lead":
            w_k, w_l, w_p = 1.0, 0.8, 1.6
        else:
            w_k, w_l, w_p = 1.4, 1.0, 1.2
        score = (w_k * kscore[i]) + (w_l * lex[i]) + (w_p * pos[i])
        if len(s) > 450:
            score -= 0.4
        if len(s) < 40 and kscore[i] == 0:
            score -= 0.5
        scores.append((score, i, s))

    scores.sort(key=lambda t: (-t[0], t[1]))
    picked_idx = sorted(i for _, i, _ in scores[:max_lines])

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
    return "\n".join(final[:max_lines]).strip()
