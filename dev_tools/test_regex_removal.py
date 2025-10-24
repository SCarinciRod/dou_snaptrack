import re
from dou_utils.text_cleaning import strip_legalese_preamble, extract_article1_section, remove_dou_metadata

texto = "Art. 1º Prorrogar por 30 (trinta) dias o prazo que consta no art. 4º da Decisão SUROD nº 846, de 22 de julho de 2025, publicada no Diário Oficial da União de 25 de julho de 2025, Seção 1, que impõe, em caráter cautelar, à Concessionária de Rodovias Minas Gerais Goiás S.A. - Ecovias Minas Goiás a obrigação de contratar verificador, totalizando, assim, 120 (cento e vinte) dias de prazo."

print("=" * 80)
print("TESTE: Por que clean_text_for_summary retorna vazio?")
print("=" * 80)

print(f"\n1. Texto original ({len(texto)} chars):")
print(f"   {texto}\n")

# Simular o que clean_text_for_summary faz
print("2. Aplicando regex de remoção de cabeçalho DOU...")
t = re.sub(
    r"^.*?(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:[^\n]*?\s*(?=(?:PORTARIA|DECRETO|DESPACHO|RESOLUÇÃO|ATO|EXTRATO|PAUTA|DELIBERAÇÃO|ALVARÁ|RETIFICAÇÃO|SÚMULA|DECISÃO|ORDEM|EDITAL|AVISO|INSTRUÇÃO|Portaria|Decreto|Despacho|Decisão|MENSAGEM|Mensagem|Retificação|Súmula)(?:\s|$))",
    "",
    texto,
    count=1,
    flags=re.I | re.DOTALL
)
print(f"   Texto após regex ({len(t)} chars):")
print(f"   '{t}'\n")

if t == texto:
    print("   ✅ Regex não removeu nada (correto - não há cabeçalho DOU)")
else:
    print(f"   ⚠️ Regex removeu {len(texto) - len(t)} chars")

print("\n3. Testando se há match do padrão...")
match = re.search(
    r"(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:",
    texto,
    flags=re.I | re.DOTALL
)
print(f"   Match de cabeçalho DOU: {bool(match)}")

if match:
    print(f"   Posição: {match.start()} - {match.end()}")
    print(f"   Conteúdo: '{texto[match.start():match.end()]}'")

# Verificar se o problema é a palavra "Seção" no texto
print("\n4. Procurando palavras-chave no texto...")
keywords = ["Brasão", "Diário Oficial", "Publicado em", "Edição", "Seção", "Página", "Órgão"]
for kw in keywords:
    if kw.lower() in texto.lower():
        pos = texto.lower().find(kw.lower())
        print(f"   ✓ '{kw}' encontrado na posição {pos}")
        print(f"     Contexto: '...{texto[max(0,pos-30):pos+len(kw)+30]}...'")
