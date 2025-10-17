from __future__ import annotations

import hashlib
import os
import re
import gzip
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import urllib.request
import urllib.error

from .log_utils import get_logger

logger = get_logger(__name__)


class Fetcher:
    """Pequeno utilitário para buscar HTML com cache em disco, com opção de forçar atualização e fallback via navegador."""

    def __init__(
        self,
        cache_dir: str = "logs/_cache/summary",
        timeout_sec: int = 10,
        force_refresh: bool = False,
        use_browser_if_short: bool = False,
        short_len_threshold: int = 800,
        browser_timeout_sec: int = 20,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_sec = timeout_sec
        self.force_refresh = force_refresh
        self.use_browser_if_short = use_browser_if_short
        self.short_len_threshold = short_len_threshold
        self.browser_timeout_sec = browser_timeout_sec
        # LRU de processo para reduzir I/O repetido (até 512 páginas)
        self._mem_cache: "OrderedDict[str, str]" = OrderedDict()
        self._mem_cache_max = 512

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        # Usar gzip para reduzir footprint
        return self.cache_dir / f"{h}.html.gz"

    def _read_cache_file(self, p: Path) -> str:
        # Suporta tanto .gz quanto legado .html
        try:
            if p.suffix == ".gz" and p.exists():
                with gzip.open(p, "rt", encoding="utf-8", errors="ignore") as fp:
                    return fp.read()
            # legado: mesmo nome sem .gz
            raw = p.with_suffix("")
            if raw.exists():
                return raw.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def _write_cache_file(self, p: Path, html: str) -> None:
        try:
            with gzip.open(p, "wt", encoding="utf-8") as fp:
                fp.write(html)
        except Exception:
            pass

    def fetch_html(self, url: str) -> str:
        if not url or not url.startswith("http"):
            return ""
        cp = self._cache_path(url)
        # Cache em memória
        if not self.force_refresh:
            try:
                if url in self._mem_cache:
                    html = self._mem_cache.pop(url)
                    # move para o fim (mais recente)
                    self._mem_cache[url] = html
                    return html
            except Exception:
                pass
            # Se existir no disco, ler e popular LRU
            if cp.exists():
                html = self._read_cache_file(cp)
                if html:
                    try:
                        self._mem_cache[url] = html
                        if len(self._mem_cache) > self._mem_cache_max:
                            self._mem_cache.popitem(last=False)
                    except Exception:
                        pass
                    return html
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read()
                try:
                    html = raw.decode("utf-8", errors="ignore")
                except Exception:
                    try:
                        html = raw.decode("latin-1", errors="ignore")
                    except Exception:
                        html = ""
        except (urllib.error.URLError, Exception):
            return ""
        try:
            if not self.force_refresh:
                self._write_cache_file(cp, html)
                # Popular LRU
                try:
                    self._mem_cache[url] = html
                    if len(self._mem_cache) > self._mem_cache_max:
                        self._mem_cache.popitem(last=False)
                except Exception:
                    pass
        except Exception:
            pass
        return html

    def fetch_html_browser(self, url: str) -> str:
        """Tenta carregar a página com um navegador (Playwright) para capturar conteúdo dinâmico.

        Retorna HTML ou vazio se indisponível.
        """
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception:
            logger.info("[ENRICH] browser fallback not available (playwright not installed)")
            return ""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.browser_timeout_sec * 1000)
                    page.goto(url, wait_until="networkidle")
                    try:
                        page.wait_for_timeout(500)
                    except Exception:
                        pass
                    html = page.content()
                finally:
                    browser.close()
        except Exception as e:
            logger.info(f"[ENRICH] browser fetch failed: {e}")
            return ""
        return html or ""

    def fetch_text_browser(self, url: str) -> str:
        """Carrega a página com navegador e tenta extrair texto visível dos principais contêineres,
        incluindo shadow DOM quando possível. Retorna texto plano.
        """
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception:
            logger.info("[ENRICH] browser fallback not available (playwright not installed)")
            return ""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_default_timeout(self.browser_timeout_sec * 1000)
                    page.goto(url, wait_until="domcontentloaded")
                    # Pequeno atraso para render estável
                    try:
                        page.wait_for_timeout(500)
                    except Exception:
                        pass

                    js = r"""
                    (() => {
                        const selectors = [
                            'article', 'main article', '.texto-dou', '.publicacao-conteudo', '.single-full', '#materia', '.materia'
                        ];
                        function collectFrom(root, sel) {
                            try {
                                return Array.from(root.querySelectorAll(sel)).map(e => (e.innerText||'').trim()).filter(Boolean).join('\n');
                            } catch(e) { return ''; }
                        }
                        const seen = new Set();
                        function walk(node, acc) {
                            for (const sel of selectors) {
                                const txt = collectFrom(node, sel);
                                if (txt) acc.push(txt);
                            }
                            const walker = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT);
                            let n;
                            while (n = walker.nextNode()) {
                                if (n.shadowRoot && !seen.has(n.shadowRoot)) {
                                    seen.add(n.shadowRoot);
                                    walk(n.shadowRoot, acc);
                                }
                            }
                        }
                        const acc = [];
                        walk(document, acc);
                        let out = acc.join('\n').trim();
                        if (!out) {
                            const a = document.querySelector('article');
                            if (a && a.innerText) out = a.innerText.trim();
                        }
                        if (!out) {
                            const m = document.querySelector('main');
                            if (m && m.innerText) out = m.innerText.trim();
                        }
                        if (!out && document.body) {
                            out = (document.body.innerText||'').trim();
                        }
                        return out || '';
                    })()
                    """
                    try:
                        text = page.evaluate(js)
                    except Exception:
                        text = ""
                    # Limitar tamanho extremo
                    if text and len(text) > 200000:
                        text = text[:200000]
                finally:
                    browser.close()
        except Exception as e:
            logger.info(f"[ENRICH] browser text fetch failed: {e}")
            return ""
        return text or ""

    @staticmethod
    def extract_text_from_html(html: str) -> str:
        if not html:
            return ""
        # Remover scripts/styles
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
        # Tentar article, depois main, depois body
        m = re.search(r"<article[^>]*>([\s\S]*?)</article>", html, flags=re.I)
        if not m:
            m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
        if not m:
            m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, flags=re.I)
        chunk = m.group(1) if m else html
        # Heurística legacy: tentar blocos com classes/ids típicos do DOU
        if len(chunk) < 800:
            # classes comuns
            m_cls = re.search(r"<(div|section|article)[^>]*class=\"[^\"]*(texto-dou|publicacao-conteudo|single-full|materia)[^\"]*\"[^>]*>([\s\S]*?)</\\1>", html, flags=re.I)
            if m_cls and len(m_cls.group(3)) > len(chunk):
                chunk = m_cls.group(3)
            # ids comuns
            m_id = re.search(r"<(div|section|article)[^>]*id=\"(materia|content|conteudo)\"[^>]*>([\s\S]*?)</\\1>", html, flags=re.I)
            if m_id and len(m_id.group(3)) > len(chunk):
                chunk = m_id.group(3)
        # Se o chunk ainda for muito genérico, tentar concatenar parágrafos <p>
        if len(chunk) < 500:
            ps = re.findall(r"<p[^>]*>([\s\S]*?)</p>", html, flags=re.I)
            if ps:
                chunk = "\n".join(ps)
        # Remover tags
        text = re.sub(r"<[^>]+>", " ", chunk)
        # Normalizar espaços e reduzir tamanho
        text = re.sub(r"\s+", " ", text).strip()
        # Aumentar limite para capturar atos longos
        return text[:20000]

    def enrich_items_missing_text(self, items: List[Dict], max_workers: int = 8) -> int:
        """Busca HTML para itens sem 'texto'/'ementa' e preenche 'texto' se extrair corpo.

        Retorna quantidade de itens preenchidos.
        """
        targets: List[Tuple[Dict, str]] = []
        for it in items:
            if it.get("texto") or it.get("ementa"):
                continue
            url = it.get("detail_url") or it.get("link") or ""
            if not url:
                continue
            if url.startswith("/"):
                url = f"https://www.in.gov.br{url}"
            if not url.startswith("http"):
                continue
            targets.append((it, url))

        if not targets:
            logger.info("[ENRICH] no targets without text")
            return 0

        filled = 0
        def _work(pair: Tuple[Dict, str]) -> Tuple[Dict, str, str]:
            it, url = pair
            html = self.fetch_html(url)
            body = self.extract_text_from_html(html)
            if self.use_browser_if_short and (not body or len(body) < self.short_len_threshold):
                # Tentar texto direto via navegador (mais robusto para conteúdo dinâmico)
                fetch_text = getattr(self, "fetch_text_browser", None)
                text_b = str(fetch_text(url)) if callable(fetch_text) else ""
                if text_b and len(text_b) > len(body):
                    body = text_b
                else:
                    html_b = self.fetch_html_browser(url)
                    if html_b:
                        body_b = self.extract_text_from_html(html_b)
                        if len(body_b) > len(body):
                            body = body_b
            return it, url, body

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_work, pair): pair for pair in targets}
            for fut in as_completed(futs):
                try:
                    it, url, body = fut.result()
                    if body:
                        it["texto"] = body
                        filled += 1
                except Exception:
                    continue
        logger.info(f"[ENRICH] filled {filled}/{len(targets)} missing texts")
        return filled

    def enrich_items(
        self,
        items: List[Dict],
        max_workers: int = 8,
        overwrite: bool = False,
        min_len: Optional[int] = None,
    ) -> int:
        """Busca HTML e extrai corpo para um conjunto de itens.

        - overwrite=True: sempre sobrescreve `texto` com o extraído, quando possível.
        - overwrite=False: somente preenche quando faltar `texto`.
        - min_len: se informado, itens com `texto` menor que esse valor também serão alvo.

        Retorna quantidade de itens que tiveram `texto` atualizado/preenchido.
        """
        targets: List[Tuple[Dict, str]] = []
        for it in items:
            txt = (it.get("texto") or it.get("ementa") or "").strip()
            need = False
            if overwrite:
                need = True
            elif not txt:
                need = True
            elif min_len is not None and len(txt) < min_len:
                need = True
            if not need:
                continue
            url = it.get("detail_url") or it.get("link") or ""
            if not url:
                continue
            if url.startswith("/"):
                url = f"https://www.in.gov.br{url}"
            if not url.startswith("http"):
                continue
            targets.append((it, url))

        if not targets:
            return 0

        updated = 0
        def _work(pair: Tuple[Dict, str]) -> Tuple[Dict, str, str]:
            it, url = pair
            html = self.fetch_html(url)
            body = self.extract_text_from_html(html)
            if self.use_browser_if_short and (not body or len(body) < self.short_len_threshold):
                fetch_text = getattr(self, "fetch_text_browser", None)
                text_b = str(fetch_text(url)) if callable(fetch_text) else ""
                if text_b and len(text_b) > len(body):
                    body = text_b
                else:
                    html_b = self.fetch_html_browser(url)
                    if html_b:
                        body_b = self.extract_text_from_html(html_b)
                        if len(body_b) > len(body):
                            body = body_b
            return it, url, body

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_work, pair): pair for pair in targets}
            for fut in as_completed(futs):
                try:
                    it, url, body = fut.result()
                    if body:
                        it["texto"] = body
                        updated += 1
                except Exception:
                    continue
        logger.info(f"[ENRICH] updated {updated}/{len(targets)} items (overwrite={overwrite}, min_len={min_len})")
        return updated
