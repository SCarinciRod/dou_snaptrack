"""
bulletin_utils.py
Geração de boletins em DOCX, Markdown e HTML com agrupamento por (órgão, tipo_ato)
e sumarização (simples ou avançada) opcional.

Função principal:
  generate_bulletin(result_dict, out_path, kind="docx", summarize=False,
                    summarizer=None, keywords=None, max_lines=5, mode="center")
"""

from __future__ import annotations

import html as html_lib
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .log_utils import get_logger
from .text_cleaning import (
    cap_sentences as _cap_sentences,
    extract_article1_section as _extract_article1_section,
    extract_doc_header_line as _extract_doc_header_line,
    final_clean_snippet as _final_clean_snippet,
    remove_dou_metadata as _remove_dou_metadata,
    split_doc_header as _split_doc_header,
    strip_legalese_preamble as _strip_legalese_preamble,
)

logger = get_logger(__name__)


def _default_simple_summarizer(text: str, max_lines: int, mode: str, keywords=None) -> str:
    """
    Sumarizador simples fallback quando nenhum outro é fornecido.
    Aplica limpeza de preâmbulo jurídico e extrai frases do início ou centro.
    """
    clean = _strip_legalese_preamble(text)
    # priorizar somente o Art. 1º, se existir
    a1 = _extract_article1_section(clean)
    base = a1 or clean
    sents = [s.strip() for s in re.split(r"[.!?]\s+", base) if s.strip()]

    if not sents:
        # Fallback: se não houver pontuação, sintetizar com primeiras palavras
        words = re.findall(r"\w+[\w-]*", base)
        if not words:
            return ""
        chunk = " ".join(words[: max(5, max_lines * 8)])
        return chunk.strip() + "."

    if mode in ("head", "lead"):
        result = ". ".join(sents[:max_lines])
        return result + ("" if result.endswith(".") else ".")

    # mode "center"
    mid = max(0, (len(sents) // 2) - (max_lines // 2))
    chunk = sents[mid: mid + max_lines]
    result = ". ".join(chunk)
    return result + ("" if result.endswith(".") else ".")


def _mk_suffix(it: dict[str, Any]) -> str:
    """
    Cria um sufixo padronizado com metadados do item (data, seção, edição, página).

    Returns:
        String formatada com metadados, ou string vazia se não houver dados
    """
    parts = []

    if it.get("data_publicacao"):
        parts.append(it["data_publicacao"])

    if it.get("secao"):
        parts.append(it["secao"])

    if it.get("edicao"):
        parts.append(f"Edição {it['edicao']}")

    if it.get("pagina"):
        parts.append(f"p. {it['pagina']}")

    return (" — " + " • ".join(parts)) if parts else ""


def _minimal_summary_from_item(it: dict[str, Any]) -> str | None:
    """Último recurso para obter um resumo mínimo a partir do cabeçalho ou título.

    Retorna uma string curta e limpa ou None.
    """
    try:
        head = _extract_doc_header_line(it)
    except Exception as e:
        logger.debug(f"Failed to extract doc header: {e}")
        head = None
    if head:
        return _final_clean_snippet(head)
    t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
    if t:
        return _final_clean_snippet(str(t))
    return None


def _summarize_item(
    it: dict[str, Any],
    summarizer_fn: Callable | None,
    summarize: bool,
    keywords: list[str] | None,
    max_lines: int,
    mode: str
) -> str | None:
    """
    Aplica sumarização a um item se summarize=True e summarizer_fn disponível.
    Lida com diferentes assinaturas de summarizer_fn.

    Returns:
        String resumida ou None se não foi possível resumir
    """
    if not summarize or not summarizer_fn:
        return None

    base = it.get("texto") or it.get("ementa") or ""
    if not base:
        # Último recurso: tentar construir resumo a partir de header ou título
        head = _extract_doc_header_line(it)
        if head:
            return _final_clean_snippet(head)
        t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
        return _final_clean_snippet(str(t)) if t else None
    # Separar cabeçalho do corpo para o resumo não repetir o cabeçalho do ato
    use_base = base
    try:
        header, body = _split_doc_header(base)
        # Só usar o body se ele tiver conteúdo razoável (evita ficar vazio quando só há título)
        if body and len(body.strip()) >= 30:
            use_base = body
    except Exception as e:
        logger.debug(f"Failed to split doc header: {e}")
    # Remover metadados do DOU, limpar juridiquês e tentar extrair somente o Art. 1º
    try:
        clean = _remove_dou_metadata(use_base)
        clean = _strip_legalese_preamble(clean)
        a1 = _extract_article1_section(clean)
        base_eff = a1 or clean
        if not base_eff:
            # fallback: tentar com o texto original limpo (sem remover cabeçalho)
            clean2 = _strip_legalese_preamble(_remove_dou_metadata(base))
            base_eff = clean2 or base
        base = base_eff
    except Exception as e:
        logger.debug(f"Failed to clean/extract article: {e}")

    # Modo derivado por tipo de ato: usar 'lead' para atos normativos e despachos
    derived_mode = (mode or "center").lower()
    try:
        tipo = (it.get("tipo_ato") or "").strip().lower()
        if tipo.startswith("decreto") or tipo.startswith("portaria") or tipo.startswith("resolu") or tipo.startswith("despacho"):
            derived_mode = "lead"
    except Exception as e:
        logger.debug(f"Failed to derive mode from tipo_ato: {e}")

    snippet = None
    method_tag = ""
    try:
        # Chamada preferida: (text, max_lines, mode, keywords)
        snippet = summarizer_fn(base, max_lines, derived_mode, keywords)
        method_tag = "summarizer"
    except TypeError:
        # Tentar alternativa (text, max_lines, keywords, mode)
        try:
            snippet = summarizer_fn(base, max_lines, keywords, derived_mode)  # type: ignore
            method_tag = "summarizer_alt"
        except TypeError:
            # Tentar legado (text, max_lines, mode)
            try:
                snippet = summarizer_fn(base, max_lines, derived_mode)  # type: ignore
                method_tag = "summarizer_legacy"
            except Exception as e:
                logger.warning(f"Erro ao sumarizar: {e}")
                snippet = None
    except Exception as e:
        logger.warning(f"Erro ao sumarizar: {e}")
        snippet = None
    # Se o summarizer retornar vazio, tentar fallback com a base original
    try:
        if not snippet:
            alt = _strip_legalese_preamble(_remove_dou_metadata(base)) if base else base
            if alt and alt != base:
                try:
                    snippet = summarizer_fn(alt, max_lines, derived_mode, keywords)
                    method_tag = method_tag or "summarizer_altbase"
                except TypeError:
                    try:
                        snippet = summarizer_fn(alt, max_lines, keywords, derived_mode)  # type: ignore
                        method_tag = method_tag or "summarizer_altbase_alt"
                    except TypeError:
                        snippet = summarizer_fn(alt, max_lines, derived_mode)  # type: ignore
                        method_tag = method_tag or "summarizer_altbase_legacy"
    except Exception:
        pass

    # Se ainda não houver snippet, aplicar fallback com sumarizador simples padrão
    if not snippet:
        try:
            snippet = _default_simple_summarizer(base, max_lines, derived_mode, keywords)
            method_tag = method_tag or "default_simple"
        except Exception:
            snippet = None

    # Se ainda não houver snippet, construir a partir de header ou título
    if not snippet:
        head = None
        try:
            head = _extract_doc_header_line(it)
        except Exception:
            head = None
        if head:
            snippet = head
            method_tag = method_tag or "header_line"
        else:
            t = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
            if t:
                snippet = str(t)
                method_tag = method_tag or "title_fallback"

    # Pós-processamento: limitar a N frases e limpar resíduos/metadata
    if snippet:
        # Remover ruídos comuns no início do resumo (ANEXO, NR, códigos)
        try:
            snippet = re.sub(r"^(ANEXO(\s+[IVXLCDM]+)?|NR)\b[:\-\s]*", "", snippet, flags=re.I).strip()
        except Exception:
            pass
        snippet = _cap_sentences(snippet, max_lines)
        snippet = _final_clean_snippet(snippet)
        # Salvaguarda: se após o pós-processamento o resumo ficar vazio, reconstruir com header/título
        if not snippet.strip():
            head2 = None
            try:
                head2 = _extract_doc_header_line(it)
            except Exception:
                head2 = None
            if head2:
                snippet = _final_clean_snippet(head2)
                method_tag = method_tag or "header_line_cleanup"
            else:
                t2 = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or ""
                if t2:
                    snippet = _final_clean_snippet(str(t2))
                    method_tag = method_tag or "title_cleanup"
                else:
                    # Último recurso: usar sumarizador simples no texto-base
                    try:
                        snippet = _default_simple_summarizer(base or "", max_lines, derived_mode, keywords)
                        snippet = _final_clean_snippet(snippet)
                        method_tag = method_tag or "default_simple_cleanup"
                    except Exception:
                        snippet = ""
    # Garantir resumo mínimo e registrar metadados
    if not snippet or not snippet.strip():
        min_snip = _minimal_summary_from_item(it)
        if min_snip:
            snippet = _final_clean_snippet(min_snip)
            method_tag = method_tag or "minimal_header_title"
        elif base:
            # reduzir base à 1 frase curta como último recurso
            snippet = _cap_sentences(base, max(1, min(2, max_lines)))
            method_tag = method_tag or "cap_from_base"
        else:
            snippet = ""

    try:
        it.setdefault("_summary_meta", {})
        it["_summary_meta"].update({
            "mode_used": derived_mode,
            "method": method_tag or "unknown",
            "len": len(snippet or ""),
        })
    except Exception:
        pass
    return snippet


class BulletinGenerator(ABC):
    """Classe base abstrata para geradores de boletim em diferentes formatos."""

    def __init__(
        self,
        result: dict[str, Any],
        out_path: str,
        summarizer_fn: Callable | None,
        summarize: bool,
        keywords: list[str] | None,
        max_lines: int,
        mode: str
    ):
        self.result = result
        self.out_path = out_path
        self.summarizer_fn = summarizer_fn
        self.summarize = summarize
        self.keywords = keywords
        self.max_lines = max_lines
        self.mode = mode
        self.date = result.get("data", "")
        self.secao = result.get("secao", "")

        # Agrupar itens por (órgão, tipo_ato)
        self.grouped = self._group_items()

    def _group_items(self) -> dict[tuple[str, str], list[dict[str, Any]]]:
        """Agrupa itens por (órgão, tipo_ato)."""
        grouped = defaultdict(list)
        for it in self.result.get("itens", []):
            org = it.get("orgao") or "Sem órgão"
            tipo = it.get("tipo_ato") or "Sem tipo"
            grouped[(org, tipo)].append(it)
        return grouped

    def generate(self) -> dict[str, Any]:
        """
        Gera o boletim no formato específico e retorna metadados.

        Returns:
            Dict com metadados: groups, items, summarized, output
        """
        # Preparar diretório de saída
        Path(self.out_path).parent.mkdir(parents=True, exist_ok=True)

        # Geração específica por formato
        summarized = self._generate_content()

        return {
            "groups": len(self.grouped),
            "items": sum(len(v) for v in self.grouped.values()),
            "summarized": summarized,
            "output": self.out_path
        }

    @abstractmethod
    def _generate_content(self) -> int:
        """
        Implementação específica da geração de conteúdo para cada formato.

        Returns:
            Número de itens sumarizados
        """


class DocxBulletinGenerator(BulletinGenerator):
    """Gerador de boletim em formato DOCX."""

    def _generate_content(self) -> int:
        try:
            from docx import Document
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
        except ImportError:
            logger.error("Módulo python-docx não encontrado. Instale com: pip install python-docx")
            raise

        def add_hyperlink(paragraph, url: str, text: str, color="0000FF", underline=True):
            """Adiciona hyperlink a um parágrafo no DOCX."""
            try:
                r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
            except Exception:
                return

            hyperlink = OxmlElement('w:hyperlink')
            hyperlink.set(qn('r:id'), r_id)

            new_run = OxmlElement('w:r')
            rPr = OxmlElement('w:rPr')

            if color:
                c = OxmlElement('w:color')
                c.set(qn('w:val'), color)
                rPr.append(c)

            if underline:
                u = OxmlElement('w:u')
                u.set(qn('w:val'), 'single')
                rPr.append(u)

            new_run.append(rPr)
            t = OxmlElement('w:t')
            t.text = text
            new_run.append(t)
            hyperlink.append(new_run)
            paragraph._p.append(hyperlink)

        # Criar documento e adicionar título
        doc = Document()
        doc.add_heading(f"Boletim DOU — {self.date} ({self.secao})", 0)

        # Contador de itens sumarizados
        summarized = 0

        # Para cada grupo (órgão + tipo de ato)
        for (org, tipo), arr in self.grouped.items():
            doc.add_heading(f"{org} — {tipo}", level=1)

            # Para cada item no grupo
            for it in arr:
                base_text = it.get("texto") or it.get("ementa") or ""
                _strip_legalese_preamble(_remove_dou_metadata(base_text)) if base_text else ""
                # Manter texto do link inalterado (sem derivar título do corpo)
                titulo = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
                durl = it.get("detail_url") or it.get("link") or ""
                pdf = it.get("pdf_url") or ""
                suffix = _mk_suffix(it)

                # Adicionar título com links
                p = doc.add_paragraph(style="List Bullet")
                if durl:
                    add_hyperlink(p, durl, titulo)
                else:
                    p.add_run(titulo)

                if pdf:
                    p.add_run(" [")
                    add_hyperlink(p, pdf, "PDF")
                    p.add_run("]")

                if suffix:
                    p.add_run(suffix)

                # Adicionar resumo se disponível
                snippet = _summarize_item(it, self.summarizer_fn, self.summarize,
                                         self.keywords, self.max_lines, self.mode)
                if not snippet and self.summarize:
                    snippet = _minimal_summary_from_item(it)
                if snippet:
                    summarized += 1
                    pr = doc.add_paragraph()
                    r = pr.add_run("Resumo: ")
                    r.bold = True
                    pr.add_run(snippet)

        # Salvar documento
        doc.save(self.out_path)
        return summarized


class MarkdownBulletinGenerator(BulletinGenerator):
    """Gerador de boletim em formato Markdown."""

    def _generate_content(self) -> int:
        lines = [f"# Boletim DOU — {self.date} ({self.secao})", ""]
        summarized = 0

        for (org, tipo), arr in self.grouped.items():
            lines.append(f"## {org} — {tipo}")
            lines.append("")

            for it in arr:
                base_text = it.get("texto") or it.get("ementa") or ""
                _strip_legalese_preamble(_remove_dou_metadata(base_text)) if base_text else ""
                # Manter texto do link inalterado
                titulo = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
                durl = it.get("detail_url") or it.get("link") or ""
                pdf = it.get("pdf_url") or ""
                suffix = _mk_suffix(it)

                # Link markdown para o título
                base_line = f"- [{titulo}]({durl})" if durl else f"- {titulo}"

                # Adicionar link para PDF se disponível
                if pdf:
                    base_line += f" [PDF]({pdf})"

                if suffix:
                    base_line += suffix

                lines.append(base_line)

                # Adicionar resumo se disponível
                snippet = _summarize_item(it, self.summarizer_fn, self.summarize,
                                         self.keywords, self.max_lines, self.mode)
                if not snippet and self.summarize:
                    snippet = _minimal_summary_from_item(it)
                if snippet:
                    summarized += 1
                    lines.append(f"  \n  _Resumo:_ {snippet}")

                lines.append("")

        # Escrever arquivo markdown
        Path(self.out_path).write_text("\n".join(lines), encoding="utf-8")
        return summarized


class HtmlBulletinGenerator(BulletinGenerator):
    """Gerador de boletim em formato HTML."""

    def _generate_content(self) -> int:
        parts = [f"<h1>Boletim DOU — {html_lib.escape(self.date)} ({html_lib.escape(self.secao)})</h1>"]
        summarized = 0

        for (org, tipo), arr in self.grouped.items():
            parts.append(f"<h2>{html_lib.escape(org)} — {html_lib.escape(tipo)}</h2>")
            parts.append("<ul>")

            for it in arr:
                base_text = it.get("texto") or it.get("ementa") or ""
                _strip_legalese_preamble(_remove_dou_metadata(base_text)) if base_text else ""
                # Manter texto do link inalterado
                titulo = it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
                durl = it.get("detail_url") or it.get("link") or ""
                pdf = it.get("pdf_url") or ""
                suffix = _mk_suffix(it)

                # Link HTML para título
                title_html = html_lib.escape(titulo)
                if durl:
                    title_html = f'<a href="{html_lib.escape(durl)}">{title_html}</a>'

                # Link para PDF
                pdf_html = f' <a href="{html_lib.escape(pdf)}">[PDF]</a>' if pdf else ""

                parts.append(f"<li>{title_html}{pdf_html}{html_lib.escape(suffix)}")

                # Adicionar resumo se disponível
                snippet = _summarize_item(it, self.summarizer_fn, self.summarize,
                                         self.keywords, self.max_lines, self.mode)
                if not snippet and self.summarize:
                    snippet = _minimal_summary_from_item(it)
                if snippet:
                    summarized += 1
                    parts.append(f"<div><strong>Resumo:</strong> {html_lib.escape(snippet)}</div>")

                parts.append("</li>")

            parts.append("</ul>")

        # Escrever arquivo HTML
        Path(self.out_path).write_text("\n".join(parts), encoding="utf-8")
        return summarized


def generate_bulletin(
    result: dict[str, Any],
    out_path: str,
    kind: str = "docx",
    summarize: bool = False,
    summarizer: Callable[[str, int, str, list[str] | None], str] | None = None,
    keywords: list[str] | None = None,
    max_lines: int = 5,
    mode: str = "center"
) -> dict[str, Any]:
    """
    Gera boletim e retorna metadados.

    Args:
        result: Dicionário com dados do resultado (data, secao, itens)
        out_path: Caminho para arquivo de saída
        kind: Formato do boletim (docx, md, html)
        summarize: Se True, inclui resumo para cada item
        summarizer: Função de sumarização personalizada
        keywords: Lista de palavras-chave para sumarização
        max_lines: Número máximo de linhas no resumo
        mode: Modo de sumarização (center, head)

    Returns:
        Dict com metadados: {groups, items, summarized, output}
    """
    # Definir summarizer_fn
    summarizer_fn = summarizer
    if summarize and summarizer_fn is None:
        summarizer_fn = _default_simple_summarizer  # fallback

    # Criar gerador apropriado conforme formato
    if kind == "docx":
        generator = DocxBulletinGenerator(
            result, out_path, summarizer_fn, summarize, keywords, max_lines, mode
        )
    elif kind == "md":
        generator = MarkdownBulletinGenerator(
            result, out_path, summarizer_fn, summarize, keywords, max_lines, mode
        )
    elif kind == "html":
        generator = HtmlBulletinGenerator(
            result, out_path, summarizer_fn, summarize, keywords, max_lines, mode
        )
    else:
        raise ValueError(f"Formato '{kind}' não suportado. Use: docx|md|html")

    # Gerar e retornar metadados
    return generator.generate()
