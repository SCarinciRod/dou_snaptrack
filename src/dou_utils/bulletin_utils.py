"""
bulletin_utils.py
Geração de boletins em DOCX, Markdown e HTML com agrupamento por (órgão, tipo_ato)
e sumarização (simples ou avançada) opcional.

Função principal:
  generate_bulletin(result_dict, out_path, kind="docx", summarize=False,
                    summarizer=None, keywords=None, max_lines=5, mode="center")
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional, Tuple
from collections import defaultdict
import html as html_lib
from pathlib import Path

from .log_utils import get_logger

logger = get_logger(__name__)

def _extract_article1_section(text: str) -> str:
    """Tenta extrair somente o conteúdo do Art. 1º (ou Artigo 1º).

    Heurística:
    - Busca início por "Art. 1º", "Art. 1o", "Artigo 1º" (case-insensitive)
    - Corta até antes de "Art. 2º/2o/Artigo 2º" ou final do texto
    """
    import re
    if not text:
        return ""
    t = text
    # normalizar espaços para facilitar o recorte
    t = re.sub(r"\s+", " ", t).strip()

    # localizar início do art. 1º (com ou sem o prefixo "Art." ou "Artigo")
    m1 = re.search(r"\b(?:(?:Art\.?|Artigo)\s*)?1(º|o)?\b[:\-]?", t, flags=re.I)
    if not m1:
        return ""
    start = m1.start()

    # localizar início do art. 2º a partir do fim do match 1 (com ou sem prefixo)
    rest = t[m1.end():]
    m2 = re.search(r"\b(?:(?:Art\.?|Artigo)\s*)?2(º|o)?\b", rest, flags=re.I)
    if m2:
        end = m1.end() + m2.start()
    else:
        end = len(t)

    return t[start:end].strip()


def _strip_legalese_preamble(text: str) -> str:
    """Remove trechos iniciais de formalidades jurídicas e corta até a parte dispositiva.

    Heurísticas:
    - Descarta tudo até (e incluindo) marcadores como "resolve:", "resolvo:", "decide:".
    - Remove cabeçalhos como "O MINISTRO...", "A MINISTRA...", "no uso de suas atribuições".
    - Remove blocos iniciados por "tendo em vista", "considerando", "nos termos", "com fundamento".
    - Normaliza "Art. 1º" para "1º" (remove o token "Art.").
    """
    import re
    if not text:
        return ""

    t = text
    # Normalizar quebras para facilitar recortes
    t = re.sub(r"\s+", " ", t).strip()

    low = t.lower()
    markers = ["resolve:", "resolvo:", "decide:", "decido:", "torna público:", "torno público:", "torna publico:", "torno publico:"]
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

    # Normalizar "Art." prefixo antes do ordinal
    t = re.sub(r"\bArt\.?\s*(\d+º?)", r"\1", t, flags=re.I)
    return t.strip()


def _first_sentences(text: str, max_sents: int = 2) -> str:
    import re
    sents = [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
    if not sents:
        return ""
    out = ". ".join(sents[:max_sents])
    return out + ("" if out.endswith(".") else ".")


def _make_bullet_title_from_text(text: str, max_len: int = 140) -> Optional[str]:
    """Gera um título amigável a partir do texto já limpo de juridiquês."""
    import re
    if not text:
        return None
    head = _first_sentences(text, 1)
    if not head:
        return None
    head = re.sub(r"^\d+º\s+", "", head).strip()  # remove ordinal inicial
    return head[:max_len]


def _default_simple_summarizer(text: str, max_lines: int, mode: str, keywords=None) -> str:
    """
    Sumarizador simples fallback quando nenhum outro é fornecido.
    Aplica limpeza de preâmbulo jurídico e extrai frases do início ou centro.
    """
    import re
    clean = _strip_legalese_preamble(text)
    # priorizar somente o Art. 1º, se existir
    a1 = _extract_article1_section(clean)
    base = a1 or clean
    sents = [s.strip() for s in re.split(r"[.!?]\s+", base) if s.strip()]

    if not sents:
        return ""

    if mode in ("head", "lead"):
        result = ". ".join(sents[:max_lines])
        return result + ("" if result.endswith(".") else ".")

    # mode "center"
    mid = max(0, (len(sents) // 2) - (max_lines // 2))
    chunk = sents[mid: mid + max_lines]
    result = ". ".join(chunk)
    return result + ("" if result.endswith(".") else ".")


def _mk_suffix(it: Dict[str, Any]) -> str:
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


def _summarize_item(
    it: Dict[str, Any], 
    summarizer_fn: Optional[Callable], 
    summarize: bool, 
    keywords: Optional[List[str]], 
    max_lines: int, 
    mode: str
) -> Optional[str]:
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
        return None
    # Limpar juridiquês e tentar extrair somente o Art. 1º antes de resumir
    try:
        base = _strip_legalese_preamble(base)
        a1 = _extract_article1_section(base)
        if a1:
            base = a1
    except Exception:
        pass
        
    try:
        return summarizer_fn(base, max_lines, mode, keywords)
    except TypeError:
        # Compatibilidade com summarizers que aceitam (text, max_lines, mode) apenas
        try:
            return summarizer_fn(base, max_lines, mode)
        except Exception as e:
            logger.warning(f"Erro ao sumarizar: {e}")
            return None
    except Exception as e:
        logger.warning(f"Erro ao sumarizar: {e}")
        return None


class BulletinGenerator(ABC):
    """Classe base abstrata para geradores de boletim em diferentes formatos."""
    
    def __init__(
        self,
        result: Dict[str, Any],
        out_path: str,
        summarizer_fn: Optional[Callable],
        summarize: bool,
        keywords: Optional[List[str]],
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
        
    def _group_items(self) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """Agrupa itens por (órgão, tipo_ato)."""
        grouped = defaultdict(list)
        for it in self.result.get("itens", []):
            org = it.get("orgao") or "Sem órgão"
            tipo = it.get("tipo_ato") or "Sem tipo"
            grouped[(org, tipo)].append(it)
        return grouped
        
    def generate(self) -> Dict[str, Any]:
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
        pass


class DocxBulletinGenerator(BulletinGenerator):
    """Gerador de boletim em formato DOCX."""
    
    def _generate_content(self) -> int:
        try:
            from docx import Document
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
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
                cleaned = _strip_legalese_preamble(base_text) if base_text else ""
                # Título preferencial: derivado do texto limpo; fallback para friendly/listagem
                bullet_title = _make_bullet_title_from_text(cleaned) if cleaned else None
                titulo = bullet_title or it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
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
                cleaned = _strip_legalese_preamble(base_text) if base_text else ""
                bullet_title = _make_bullet_title_from_text(cleaned) if cleaned else None
                titulo = bullet_title or it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
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
                cleaned = _strip_legalese_preamble(base_text) if base_text else ""
                bullet_title = _make_bullet_title_from_text(cleaned) if cleaned else None
                titulo = bullet_title or it.get("title_friendly") or it.get("titulo") or it.get("titulo_listagem") or "Sem título"
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
                if snippet:
                    summarized += 1
                    parts.append(f"<div><strong>Resumo:</strong> {html_lib.escape(snippet)}</div>")
                    
                parts.append("</li>")
                
            parts.append("</ul>")
            
        # Escrever arquivo HTML
        Path(self.out_path).write_text("\n".join(parts), encoding="utf-8")
        return summarized


def generate_bulletin(
    result: Dict[str, Any],
    out_path: str,
    kind: str = "docx",
    summarize: bool = False,
    summarizer: Optional[Callable[[str, int, str, Optional[List[str]]], str]] = None,
    keywords: Optional[List[str]] = None,
    max_lines: int = 5,
    mode: str = "center"
) -> Dict[str, Any]:
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
