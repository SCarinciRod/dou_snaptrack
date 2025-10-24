#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Monkey patch para debug."""
import sys
sys.path.insert(0, 'src')

# Importar original
from dou_utils import bulletin_utils

# Salvar original
_original_summarize_item = bulletin_utils._summarize_item

# Wrapper para summarizer_fn
def _debug_summarizer(text, max_lines, mode, keywords):
    print(f"    [SUMMARIZER INPUT] len={len(text)}, first 80: {text[:80]}")
    result = summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)
    print(f"    [SUMMARIZER OUTPUT] len={len(result)}, first 80: {result[:80]}")
    return result

# Nova versão com debug
def _summarize_item_debug(it, summarizer_fn, summarize, keywords, max_lines, mode):
    titulo = it.get("titulo", "")
    
    # SEMPRE mostrar para TODOS os items
    print(f"\n[MONKEY] _summarize_item: {titulo[:40]}")
    print(f"  texto len: {len(it.get('texto', ''))}")
    
    result = _original_summarize_item(it, summarizer_fn, summarize, keywords, max_lines, mode)
    
    print(f"  snippet len: {len(result) if result else 0}")
    if result:
        print(f"  snippet[:80]: {result[:80]}")
    
    return result
    
    return result

# Aplicar monkey patch
bulletin_utils._summarize_item = _summarize_item_debug

# Agora importar e testar
import json
from dou_utils.content_fetcher import Fetcher
from dou_utils.summary_utils import clean_text_for_summary, summarize_text

with open('C:/Projetos/resultados/24-10-2025/teste24-10-2025_DO1_24-10-2025.json', encoding='utf-8') as f:
    data = json.load(f)

agg = data.get('itens', [])
Fetcher(timeout_sec=30, force_refresh=True, use_browser_if_short=True, short_len_threshold=800, browser_timeout_sec=30).enrich_items(agg, max_workers=2, overwrite=True, min_len=None)

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
    return _debug_summarizer(text, max_lines, mode, keywords)

from dou_utils.bulletin_utils import generate_bulletin
generate_bulletin(
    result,
    'C:/Projetos/MONKEY_PATCH_boletim.md',
    kind='md',
    summarize=True,
    summarizer=_summarizer,
    keywords=None,
    max_lines=7,
    mode='center'
)

print("\n\nBoletim gerado! Verificando...")
with open('C:/Projetos/MONKEY_PATCH_boletim.md', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if '522' in line:
            print(f"Linha {i}: {line.strip()}")
