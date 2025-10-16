from __future__ import annotations

from typing import List, Optional

from .text_cleaning import (
    strip_legalese_preamble,
    extract_article1_section,
    cap_sentences,
)

from .log_utils import get_logger

logger = get_logger(__name__)

try:
    # Preferir summary_utils existente
    from .summary_utils import summarize_text as _inner_summarize  # type: ignore
except Exception:
    _inner_summarize = None  # type: ignore


def summarize_text(text: str, max_lines: int, mode: str, keywords: Optional[List[str]] = None) -> str:
    """Wrapper estável para chamar summarize_text com ordem correta dos parâmetros.

    Adapta assinatura para (text, max_lines, keywords, mode) quando possível.
    """
    if not text:
        return ""
    if _inner_summarize:
        try:
            # summary_utils.summarize_text(text, max_lines=7, keywords=None, mode="center")
            return _inner_summarize(text, max_lines=max_lines, keywords=keywords, mode=mode)  # type: ignore
        except TypeError:
            try:
                return _inner_summarize(text, max_lines, mode)  # type: ignore
            except Exception as e:  # pragma: no cover
                logger.warning(f"summarize_text fallback error: {e}")
        except Exception as e:  # pragma: no cover
            logger.warning(f"summarize_text error: {e}")
    # Fallback simples: limpa juridiquês e retorna as primeiras/centrais frases
    base = strip_legalese_preamble(text or "")
    a1 = extract_article1_section(base)
    core = a1 or base or (text or "")
    if (mode or "center").lower() in ("lead", "head"):
        # primeiras sentenças
        return cap_sentences(core, max_lines)
    # centro aproximado: pegar cap_sentences já cumpre o limite e mantém concisão
    return cap_sentences(core, max_lines)
