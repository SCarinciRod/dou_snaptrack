import re
from dou_utils.text_cleaning import strip_legalese_preamble, extract_article1_section, remove_dou_metadata, _WHITESPACE_PATTERN
from dou_utils.summary_utils import _DOC_TYPE_PREFIX_PATTERN

texto = "Art. 1º Prorrogar por 30 (trinta) dias o prazo que consta no art. 4º da Decisão SUROD nº 846, de 22 de julho de 2025, publicada no Diário Oficial da União de 25 de julho de 2025, Seção 1, que impõe, em caráter cautelar, à Concessionária de Rodovias Minas Gerais Goiás S.A. - Ecovias Minas Goiás a obrigação de contratar verificador, totalizando, assim, 120 (cento e vinte) dias de prazo."

print("=" * 80)
print("SIMULANDO clean_text_for_summary PASSO A PASSO")
print("=" * 80)

print(f"\n0. Texto original ({len(texto)} chars):")
print(f"   {texto[:150]}...\n")

# Passo 1: Regex DOU
print("1. Aplicando regex de remoção de cabeçalho DOU...")
t = re.sub(
    r"^.*?(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:[^\n]*?\s*(?=(?:PORTARIA|DECRETO|DESPACHO|RESOLUÇÃO|ATO|EXTRATO|PAUTA|DELIBERAÇÃO|ALVARÁ|RETIFICAÇÃO|SÚMULA|DECISÃO|ORDEM|EDITAL|AVISO|INSTRUÇÃO|Portaria|Decreto|Despacho|Decisão|MENSAGEM|Mensagem|Retificação|Súmula)(?:\s|$))",
    "",
    texto,
    count=1,
    flags=re.I | re.DOTALL
)
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 2: Limpar resíduo "do Ministro"
print("2. Limpando resíduo 'do Ministro'...")
if len(t) < len(texto):
    t = re.sub(r"^(?:do|da|de)\s+\w+\s+", "", t, count=1, flags=re.I)
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 3: Fallback remove_dou_metadata
print("3. Fallback: remove_dou_metadata (se regex não removeu nada)...")
if t == texto:
    t = remove_dou_metadata(t)
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 4: strip_legalese_preamble
print("4. Aplicando strip_legalese_preamble...")
t = strip_legalese_preamble(t)
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 5: Normalizar espaços
print("5. Normalizando espaços...")
t = _WHITESPACE_PATTERN.sub(" ", t).strip()
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 6: Padrões adicionais
print("6. Aplicando padrões adicionais de limpeza...")
patterns = [
    r"Este conteúdo não substitui.*?$",
    r"Imprensa Nacional.*?$",
]
for pat in patterns:
    antes = len(t)
    t = re.sub(pat, "", t, flags=re.I | re.DOTALL)
    if len(t) != antes:
        print(f"   Pattern '{pat[:30]}...' removeu {antes - len(t)} chars")
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 7: Remover prefixo de tipo de documento
print("7. Removendo prefixo de tipo de documento...")
t = _DOC_TYPE_PREFIX_PATTERN.sub("", t)
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 8: Strip
print("8. Strip final...")
t = t.strip()
print(f"   Resultado ({len(t)} chars): {t[:150]}...\n")

# Passo 9: Extrair Art. 1º
print("9. Extraindo Art. 1º...")
a1 = extract_article1_section(t)
print(f"   Art. 1º ({len(a1)} chars): {a1[:150]}...\n")

# Passo 10: Resultado final
print("10. Resultado final (a1 or t)...")
result = (a1 or t).strip()
print(f"    Final ({len(result)} chars): {result[:150]}...")

if not result:
    print("\n❌ RESULTADO VAZIO!")
else:
    print("\n✅ Resultado OK")
