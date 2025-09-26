"""
advanced_summary.py
Resumo por extração com múltiplos modos e ponderações.

Modos:
 - center          : peso para sentenças centrais
 - lead            : peso para sentenças iniciais (estilo notícia)
 - keywords-first  : prioriza sentenças com maior densidade de keywords
 - hybrid          : equilíbrio entre center e keywords
 - density         : favorece alta variedade lexical (diversidade)
 
Parâmetros:
 - max_lines: nº de sentenças desejadas
 - keywords: lista textual (case-insensitive)
 - penalty_long / penalty_short: penalizações adaptativas
 - normalize: se True normaliza pontuação em [0,1]
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Set


# Configurações por modo de resumo
@dataclass(frozen=True)
class SummaryWeights:
    keyword: float  # peso para ocorrência de palavras-chave
    lexical: float  # peso para diversidade lexical
    position: float  # peso para posição na estrutura do texto


SUMMARY_MODE_WEIGHTS = {
    "center": SummaryWeights(keyword=1.3, lexical=1.0, position=1.2),
    "lead": SummaryWeights(keyword=1.0, lexical=0.9, position=1.5),
    "keywords-first": SummaryWeights(keyword=1.8, lexical=0.9, position=1.0),
    "density": SummaryWeights(keyword=1.0, lexical=1.5, position=1.0),
    "hybrid": SummaryWeights(keyword=1.5, lexical=1.1, position=1.1),
}

# Default para modos não reconhecidos
DEFAULT_WEIGHTS = SummaryWeights(keyword=1.3, lexical=1.0, position=1.2)


def normalize_space(s: str) -> str:
    """Remove espaços extras e normaliza para um único espaço."""
    return re.sub(r"\s+", " ", (s or "").strip())


def to_ascii_tokens(s: str) -> List[str]:
    """Converte texto para tokens ASCII em minúsculas (removendo acentos)."""
    if not s:
        return []
    s_norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[a-z0-9]+", s_norm.lower())


def split_sentences(pt_text: str) -> List[str]:
    """
    Divide texto em sentenças, tratando abreviações comuns em português.
    Retorna lista de sentenças normalizadas.
    """
    if not pt_text:
        return []
    # Remover abreviações comuns que geram splits falsos
    txt = re.sub(r"(?<=\b(Sr|Sra|Dr|Dra|Prof|Art))\.", "", pt_text)
    parts = re.split(r"(?<=[\.\!\?])\s+", txt)
    
    return [normalize_space(p) for p in parts if normalize_space(p)]


def lexical_diversity(sent: str) -> float:
    """Calcula a diversidade lexical (proporção de tokens únicos)."""
    toks = to_ascii_tokens(sent)
    if not toks:
        return 0.0
    return len(set(toks)) / len(toks)


def keyword_hits(sent: str, kws: List[str]) -> int:
    """Conta ocorrências de palavras-chave na sentença."""
    st = sent.lower()
    return sum(1 for k in kws if k and k.lower() in st)


def position_weight(i: int, n: int, mode: str) -> float:
    """
    Calcula peso baseado na posição da sentença de acordo com o modo.
    
    Args:
        i: índice da sentença
        n: total de sentenças
        mode: modo de sumarização
        
    Returns:
        Peso entre 0.0 e 1.0
    """
    if n <= 1:
        return 1.0
        
    if mode == "lead":
        # decaimento linear
        return 1.0 - (i / (n * 1.1))
        
    if mode == "center":
        # parabólico: pico no centro
        x = (i - (n - 1) / 2) / (n / 2)
        return 1.0 - (x * x)
        
    if mode == "density":
        return 1.0  # posição neutra
        
    if mode == "keywords-first":
        return 0.9
        
    if mode == "hybrid":
        # entre center e lead
        c = position_weight(i, n, "center")
        l = position_weight(i, n, "lead")
        return (c + l) / 2.0
        
    return 1.0


def calculate_sentence_scores(
    sents: List[str],
    n: int,
    mode: str,
    kws: List[str],
    penalty_long: float,
    penalty_short: float,
    min_len_keep: int
) -> List[Tuple[float, int, str]]:
    """
    Calcula scores para cada sentença baseado no modo e parâmetros.
    
    Returns:
        Lista de tuplas (score, índice, sentença)
    """
    weights = SUMMARY_MODE_WEIGHTS.get(mode, DEFAULT_WEIGHTS)
    scores: List[Tuple[float, int, str]] = []
    
    for i, s in enumerate(sents):
        lex = lexical_diversity(s)
        kscore = keyword_hits(s, kws)
        posw = position_weight(i, n, mode)

        # Cálculo do score base ponderado
        score = (weights.keyword * kscore) + (weights.lexical * lex) + (weights.position * posw)

        # Aplicar penalizações adaptativas
        L = len(s)
        if L > 450:  # Sentenças muito longas
            score -= penalty_long
        if L < min_len_keep and kscore == 0:  # Sentenças curtas sem keywords
            score -= penalty_short

        scores.append((score, i, s))
        
    return scores


def summarize_advanced(
    text: str,
    max_lines: int = 5,
    mode: str = "center",
    keywords: Optional[List[str]] = None,
    penalty_long: float = 0.4,
    penalty_short: float = 0.4,
    min_len_keep: int = 30,
    normalize: bool = False
) -> str:
    """
    Gera um resumo por extração de sentenças do texto original.
    
    Args:
        text: Texto a ser resumido
        max_lines: Número máximo de sentenças no resumo
        mode: Modo de sumarização (center, lead, keywords-first, density, hybrid)
        keywords: Lista de palavras-chave para priorização
        penalty_long: Penalização para sentenças muito longas
        penalty_short: Penalização para sentenças curtas sem keywords
        min_len_keep: Comprimento mínimo para não aplicar penalização
        normalize: Se True, normaliza scores (não altera resultado)
        
    Returns:
        Texto resumido como uma string com linhas separadas por \n
    """
    if not text:
        return ""
        
    base = normalize_space(text)
    sents = split_sentences(base)
    
    if not sents:
        return ""
        
    # Se o texto já é menor que o máximo, retorna como está
    if len(sents) <= max_lines:
        return "\n".join(sents[:max_lines])

    # Normaliza e filtra keywords
    kws = [k.strip().lower() for k in (keywords or []) if k.strip()]
    
    # Calcula scores para cada sentença
    scores = calculate_sentence_scores(
        sents=sents,
        n=len(sents),
        mode=mode,
        kws=kws,
        penalty_long=penalty_long,
        penalty_short=penalty_short,
        min_len_keep=min_len_keep
    )

    # Ordena por maior score / menor índice
    scores.sort(key=lambda t: (-t[0], t[1]))
    chosen_idx = sorted(i for _, i, _ in scores[:max_lines])

    # Extrai sentenças escolhidas na ordem original do texto
    chosen = [sents[i].strip() for i in chosen_idx]
    
    # Deduplicação leve
    final = []
    seen: Set[str] = set()
    
    for c in chosen:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            final.append(c)
        if len(final) >= max_lines:
            break

    return "\n".join(final[:max_lines])
