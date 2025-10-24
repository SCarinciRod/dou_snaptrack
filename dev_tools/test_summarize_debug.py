from dou_utils.summary_utils import summarize_text, clean_text_for_summary, split_sentences

texto = "Art. 1º Prorrogar por 30 (trinta) dias o prazo que consta no art. 4º da Decisão SUROD nº 846, de 22 de julho de 2025, publicada no Diário Oficial da União de 25 de julho de 2025, Seção 1, que impõe, em caráter cautelar, à Concessionária de Rodovias Minas Gerais Goiás S.A. - Ecovias Minas Goiás a obrigação de contratar verificador, totalizando, assim, 120 (cento e vinte) dias de prazo."

print("=" * 80)
print("TESTE: Sumarização da DECISÃO SUROD")
print("=" * 80)

print(f"\n1. Texto original ({len(texto)} chars):")
print(f"   {texto[:200]}...\n")

print("2. Aplicando clean_text_for_summary...")
cleaned = clean_text_for_summary(texto)
print(f"   Resultado ({len(cleaned)} chars):")
print(f"   {cleaned[:200]}...\n")

print("3. Dividindo em sentenças...")
sents = split_sentences(cleaned)
print(f"   Total de sentenças: {len(sents)}")
for i, s in enumerate(sents):
    print(f"   [{i}] ({len(s)} chars): {s[:100]}...")

print("\n4. Aplicando summarize_text (max_lines=7, mode='center')...")
result = summarize_text(texto, max_lines=7, mode='center')
print(f"   Resultado ({len(result)} chars):")
print(f"   '{result}'\n")

if not result:
    print("❌ PROBLEMA: Sumarização retornou string vazia!")
    print("\n5. Testando com mode='lead'...")
    result_lead = summarize_text(texto, max_lines=7, mode='lead')
    print(f"   Resultado ({len(result_lead)} chars):")
    print(f"   '{result_lead}'\n")
else:
    print("✅ Sumarização funcionou!")
