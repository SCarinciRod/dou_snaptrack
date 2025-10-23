from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse

_ACT_TYPES = [
    "decreto", "portaria", "instrução normativa", "instrucao normativa",
    "resolução", "resolucao", "despacho", "edital", "aviso", "ato",
    "lei", "medida provisória", "medida provisoria", "ordem", "instrução",
]


def _looks_numeric_title(t: str) -> bool:
    s = (t or "").strip()
    if not s:
        return True
    # Poucas letras e muitos dígitos/sinais
    letters = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", s))
    digits = len(re.findall(r"\d", s))
    return (digits >= letters and digits >= 3) or bool(re.search(r"\bn[ºo°]\b", s, re.I))


def _slug_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        seg = path.strip("/").split("/")[-1]
        seg = unquote(seg or "")
        # remover ids hash longos no final
        seg = re.sub(r"-[a-f0-9]{6,}$", "", seg, flags=re.I)
        seg = seg.replace("_", "-")
        return seg
    except Exception:
        return ""


def _humanize_slug(seg: str) -> str:
    s = (seg or "").strip("-/")
    s = s.replace("-", " ")
    # limpar múltiplos espaços e tokens técnicos
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\b(art|artigo|capitulo|capítulo|secao|seção)\b\.?", "", s, flags=re.I)
    s = re.sub(r"\b(n|no|nº|n°|numero|núm|num)\b\.?", "nº", s, flags=re.I)
    s = s.strip()
    # capitalização leve (preserva siglas inteiras)
    words = []
    for w in s.split(" "):
        if len(w) <= 3 and w.isupper():
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join([w for w in words if w])


def _detect_act_type(text: str) -> str | None:
    t = (text or "").lower()
    for k in _ACT_TYPES:
        if k in t:
            # normalizar acentuação básica nas chaves conhecidas
            if k == "instrucao normativa":
                return "Instrução Normativa"
            if k == "resolucao":
                return "Resolução"
            if k == "medida provisoria":
                return "Medida Provisória"
            return k[:1].upper() + k[1:]
    return None


def make_friendly_title(item: dict[str, Any], date: str | None = None, secao: str | None = None, max_len: int = 140) -> str:
    raw_title = (item.get("titulo") or item.get("title") or "").strip()
    link = item.get("detail_url") or item.get("link") or ""
    act_type = _detect_act_type(raw_title) or _detect_act_type(link) or ""
    if not act_type:
        # Se o texto é muito numérico, tentar inferir pelo slug
        if _looks_numeric_title(raw_title):
            slug = _slug_from_url(link)
            act_type = _detect_act_type(slug) or ""

    # Se o título já parece descritivo, apenas limpar e truncar
    def _clean_title(t: str) -> str:
        t2 = re.sub(r"\s+", " ", t).strip()
        return t2[:max_len]

    if raw_title and not _looks_numeric_title(raw_title):
        return _clean_title(raw_title)

    # Construir a partir do slug quando possível
    slug = _slug_from_url(link)
    if slug:
        human = _humanize_slug(slug)
        if act_type and not human.lower().startswith(act_type.lower()):
            human = f"{act_type}: {human}"
        return _clean_title(human)

    # Fallback: combinar tipo + número do título, se existir
    num = None
    m = re.search(r"(\d{1,6}[./]?\d{0,4})", raw_title)
    if m:
        num = m.group(1)
    if act_type and num:
        return _clean_title(f"{act_type} nº {num}")
    if act_type:
        return _clean_title(act_type)
    # Último recurso: retornar o próprio título truncado
    return _clean_title(raw_title or "Documento do DOU")


def enrich_items_friendly_titles(items: list[dict[str, Any]], date: str | None = None, secao: str | None = None, max_len: int = 140) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items or []:
        try:
            friendly = make_friendly_title(it, date=date, secao=secao, max_len=max_len)
            it = {**it, "title_friendly": friendly}
        except Exception:
            pass
        out.append(it)
    return out
