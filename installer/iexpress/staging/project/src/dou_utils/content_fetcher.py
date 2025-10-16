from __future__ import annotations

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import urllib.request
import urllib.error

from .log_utils import get_logger

logger = get_logger(__name__)


class Fetcher:
    """Pequeno utilitário para buscar HTML com cache em disco e timeout leve."""

    def __init__(self, cache_dir: str = "logs/_cache/summary", timeout_sec: int = 10):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_sec = timeout_sec

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / f"{h}.html"

    def fetch_html(self, url: str) -> str:
        if not url or not url.startswith("http"):
            return ""
        cp = self._cache_path(url)
        if cp.exists():
            try:
                return cp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
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
            cp.write_text(html, encoding="utf-8", errors="ignore")
        except Exception:
            pass
        return html

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
