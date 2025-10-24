import json
import sys

# Carregar JSON
with open('C:/Projetos/resultados/24-10-2025/teste24-10-2025_DO1_24-10-2025.json', encoding='utf-8') as f:
    data = json.load(f)

# Encontrar item 522 (índice 2)
items = data.get('itens', [])
item_522 = items[2]  # PORTARIA DIRAP Nº 522

print("=== ITEM 522 ===")
print(f"Título: {item_522.get('titulo', '')[:100]}")
texto = item_522.get('texto', '')
print(f"Texto length: {len(texto)}")
print("\nPrimeiros 800 caracteres do texto:")
print(texto[:800])
print("\n" + "="*80)

# Testar clean_text_for_summary
from dou_utils.summary_utils import clean_text_for_summary
texto_limpo = clean_text_for_summary(texto)
print("\nApós clean_text_for_summary (primeiros 500 chars):")
print(texto_limpo[:500])
print("\n" + "="*80)

# Testar summarize_text
from dou_utils.summary_utils import summarize_text
resumo = summarize_text(texto_limpo, max_lines=7)
print("\nResumo gerado:")
print(resumo)
