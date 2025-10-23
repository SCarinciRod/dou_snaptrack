from __future__ import annotations

try:
    from dou_utils.bulletin_utils import generate_bulletin  # type: ignore
except Exception:  # pragma: no cover
    def generate_bulletin(*args, **_kwargs):  # type: ignore
        raise RuntimeError("Geração de boletim indisponível")

try:
    from dou_utils.summarize import summarize_text  # type: ignore
except Exception:  # pragma: no cover
    def summarize_text(text: str, max_lines: int = 0, keywords=None, mode: str = "center") -> str:  # type: ignore
        return text
