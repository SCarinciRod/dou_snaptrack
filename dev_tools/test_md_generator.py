#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste do gerador de boletim Markdown."""
import sys
import json
sys.path.insert(0, 'src')

# Preparar dados
with open('C:/Projetos/resultados/24-10-2025/teste24-10-2025_DO1_24-10-2025.json', encoding='utf-8') as f:
    data = json.load(f)

agg = data.get('itens', [])

# Enrich + limpar
from dou_utils.content_fetcher import Fetcher
from dou_utils.summary_utils import clean_text_for_summary

Fetcher(timeout_sec=30, force_refresh=True, use_browser_if_short=True, short_len_threshold=800, browser_timeout_sec=30).enrich_items(agg, max_workers=2, overwrite=True, min_len=None)

for it in agg:
    texto_bruto = it.get("texto") or ""
    if texto_bruto:
        it["texto"] = clean_text_for_summary(texto_bruto)

# Criar result dict
result = {
    "data": "24-10-2025",
    "secao": "DO1",
    "total": len(agg),
    "itens": agg
}

print(f"Preparado result com {len(agg)} items")
print(f"Item[2] texto length: {len(agg[2].get('texto', ''))}")
print(f"Item[2] primeiros 100 chars: {agg[2].get('texto', '')[:100]}")

# Gerar boletim
from dou_utils.summary_utils import summarize_text as _summarize_text

def _summarizer(text: str, max_lines: int, mode: str, keywords):
    return _summarize_text(text, max_lines=max_lines, keywords=keywords, mode=mode)

from dou_utils.bulletin_utils import generate_bulletin

print("\nChamando generate_bulletin...")
generate_bulletin(
    result,
    'C:/Projetos/TEST_MD_boletim.md',
    kind='md',
    summarize=True,
    summarizer=_summarizer,
    keywords=None,
    max_lines=7,
    mode='center'
)

print("\nBoletim gerado! Verificando conteúdo...")

# Ler e verificar
with open('C:/Projetos/TEST_MD_boletim.md', encoding='utf-8') as f:
    content = f.read()

# Procurar a linha da Portaria 522
lines = content.split('\n')
for i, line in enumerate(lines):
    if '522' in line:
        print(f"\nLinha {i}: {line}")
        # Mostrar próximas 3 linhas
        for j in range(i+1, min(i+4, len(lines))):
            print(f"Linha {j}: {lines[j]}")
        break
