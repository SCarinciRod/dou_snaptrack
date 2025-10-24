#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste completo do fluxo de geração de resumo."""
import sys
import json
sys.path.insert(0, 'src')

# 1. Carregar JSON
with open('C:/Projetos/resultados/24-10-2025/teste24-10-2025_DO1_24-10-2025.json', encoding='utf-8') as f:
    data = json.load(f)

agg = data.get('itens', [])
print(f"1. Carregado {len(agg)} items do JSON")

# 2. Enrich (buscar fulltext do DOU)
from dou_utils.content_fetcher import Fetcher
Fetcher(
    timeout_sec=30,
    force_refresh=True,
    use_browser_if_short=True,
    short_len_threshold=800,
    browser_timeout_sec=30
).enrich_items(agg, max_workers=2, overwrite=True, min_len=None)

print(f"\n2. Após enrich:")
print(f"   Item[2] texto length: {len(agg[2].get('texto', ''))}")
print(f"   Primeiros 150 chars: {agg[2].get('texto', '')[:150]}")

# 3. Limpar cabeçalhos DOU
from dou_utils.summary_utils import clean_text_for_summary
for it in agg:
    texto_bruto = it.get("texto") or ""
    if texto_bruto:
        it["texto"] = clean_text_for_summary(texto_bruto)

print(f"\n3. Após clean_text_for_summary:")
print(f"   Item[2] texto length: {len(agg[2].get('texto', ''))}")
print(f"   Primeiros 150 chars: {agg[2].get('texto', '')[:150]}")

# 4. Simular _summarize_item
from dou_utils.summary_utils import summarize_text

def test_summarizer(text: str, max_lines: int, mode: str, keywords):
    print(f"\n4. summarizer_fn chamado:")
    print(f"   Recebeu texto length: {len(text)}")
    print(f"   Primeiros 150 chars: {text[:150]}")
    resultado = summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)
    print(f"\n5. summarize_text retornou:")
    print(f"   Length: {len(resultado)}")
    print(f"   Conteúdo: {resultado}")
    return resultado

# Simular o que _summarize_item faz
it = agg[2]
base = it.get("texto") or it.get("ementa") or ""
print(f"\n_summarize_item:")
print(f"   base (it['texto']) length: {len(base)}")
print(f"   Primeiros 150 chars: {base[:150]}")

snippet = test_summarizer(base, 7, "center", None)

print(f"\n6. RESUMO FINAL: {snippet}")
