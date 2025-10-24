#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'src')

# Copiar a função _summarize_item COMPLETA e adicionar prints
from typing import Dict, Any, Optional, Callable, List

def _summarize_item_debug(
    it: Dict[str, Any], 
    summarizer_fn: Optional[Callable], 
    summarize: bool, 
    keywords: Optional[List[str]], 
    max_lines: int, 
    mode: str
) -> Optional[str]:
    import logging
    logger = logging.getLogger(__name__)
    
    titulo = it.get("titulo", "")
    print(f"\n[DEBUG START] {titulo[:50]}")
    
    if not summarize or not summarizer_fn:
        print("  → Retornou None (summarize=False ou sem summarizer_fn)")
        return None
        
    base = it.get("texto") or it.get("ementa") or ""
    print(f"  base (it['texto']) length: {len(base)}")
    print(f"  base[:100]: {base[:100]}")
    
    if not base:
        print("  → base vazio, usando fallback")
        return None
    
    # Modo derivado
    derived_mode = (mode or "center").lower()
    try:
        tipo = (it.get("tipo_ato") or "").strip().lower()
        if tipo.startswith("decreto") or tipo.startswith("portaria") or tipo.startswith("resolu") or tipo.startswith("despacho"):
            derived_mode = "lead"
            print(f"  tipo_ato='{tipo}' → derived_mode='lead'")
    except Exception as e:
        pass

    print(f"  Chamando summarizer_fn(base={len(base)}, max_lines={max_lines}, mode='{derived_mode}')")
    
    snippet = None
    try:
        snippet = summarizer_fn(base, max_lines, derived_mode, keywords)
        print(f"  summarizer_fn retornou: {len(snippet) if snippet else 0} chars")
        if snippet:
            print(f"  snippet[:100]: {snippet[:100]}")
    except Exception as e:
        print(f"  ERRO ao chamar summarizer_fn: {e}")
        return None
    
    if not snippet or not snippet.strip():
        print("  → snippet vazio, retornando None")
        return None
    
    return snippet

# Aplicar monkey patch
from dou_utils import bulletin_utils
bulletin_utils._summarize_item = _summarize_item_debug

# Agora o teste
import json
from dou_utils.content_fetcher import Fetcher
from dou_utils.summary_utils import clean_text_for_summary, summarize_text

with open('C:/Projetos/resultados/24-10-2025/teste24-10-2025_DO1_24-10-2025.json', encoding='utf-8') as f:
    data = json.load(f)

agg = data.get('itens', [])
print(f"Enriching {len(agg)} items...")
Fetcher(timeout_sec=30, force_refresh=True, use_browser_if_short=True, short_len_threshold=800, browser_timeout_sec=30).enrich_items(agg, max_workers=2, overwrite=True, min_len=None)

print("\nCleaning texto fields...")
for it in agg:
    texto_bruto = it.get("texto") or ""
    if texto_bruto:
        it["texto"] = clean_text_for_summary(texto_bruto)

result = {
    "data": "24-10-2025",
    "secao": "DO1",
    "total": len(agg),
    "itens": agg
}

def _summarizer(text, max_lines, mode, keywords):
    return summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)

from dou_utils.bulletin_utils import generate_bulletin
print("\n\nGenerating bulletin...")
generate_bulletin(
    result,
    'C:/Projetos/DEBUG_FULL_boletim.md',
    kind='md',
    summarize=True,
    summarizer=_summarizer,
    keywords=None,
    max_lines=7,
    mode='center'
)

print("\n\nDONE! Checking resultado...")
with open('C:/Projetos/DEBUG_FULL_boletim.md', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if '522' in line:
            print(f"Linha {i}: {line.strip()}")
            break
