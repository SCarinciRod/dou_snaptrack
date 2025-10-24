import re
from dou_utils.text_cleaning import strip_legalese_preamble, extract_article1_section

# DECISÃO SUROD Nº 1.249
decisao_html = """
O SUPERINTENDENTE DE INFRAESTRUTURA RODOVIÁRIA DA AGÊNCIA NACIONAL DE
TRANSPORTES TERRESTRES - ANTT, no uso das atribuições que lhe conferem os arts. 32 da
Resolução ANTT nº 5.976, de 7 de abril de 2022, e 25 da Resolução ANTT nº 5.977, de
7 de abril de 2022, e considerando o disposto no art. 49 da Resolução ANTT nº
6.053, de 31 de outubro de 2024, bem como o que consta do Processo nº
50500.037709/2025-64, decide:

Art. 1º Prorrogar por 30 (trinta) dias o prazo que consta no art. 4º da Decisão
SUROD nº 846, de 22 de julho de 2025, publicada no Diário Oficial da União de 25
de julho de 2025, Seção 1, que impõe, em caráter cautelar, à Concessionária de
Rodovias Minas Gerais Goiás S.A. - Ecovias Minas Goiás a obrigação de contratar
verificador, totalizando, assim, 120 (cento e vinte) dias de prazo.

Art. 2º Suspender, até ulterior decisão, a obrigatoriedade de contratação do
Organismo de Inspeção Acreditado (OIA) para as atividades relacionadas a obras e
parâmetros de desempenho constantes do Produto E do Termo de Referência aprovado
pela Decisão SUROD nº 662/2025, mantendo-se, contudo, a obrigação de contratação
do OIA para as atividades vinculadas aos projetos incluídas no mesmo produto.

Art. 3º Esta Decisão entra em vigor na data de sua publicação.

FERNANDO DE FREITAS BEZERRA
"""

print("=" * 80)
print("TESTE: DECISÃO SUROD Nº 1.249")
print("=" * 80)

# Passo 1: strip_legalese_preamble
print("\n1. Aplicando strip_legalese_preamble...")
step1 = strip_legalese_preamble(decisao_html)
print(f"   Resultado ({len(step1)} chars):")
print(f"   {step1[:300]}...\n")

# Passo 2: extract_article1_section
print("2. Aplicando extract_article1_section...")
step2 = extract_article1_section(step1)
print(f"   Resultado ({len(step2)} chars):")
print(f"   {step2[:500]}\n")

# Debug: verificar se está encontrando Art. 1º e Art. 2º
normalized = re.sub(r"\s+", " ", step1).strip()
m1 = re.search(r"\b(?:Art\.?|Artigo)\s*1(º|o)?\b[:\-]?", normalized, flags=re.I)
m2_rest = normalized[m1.end():] if m1 else normalized
m2 = re.search(r"\b(?:Art\.?|Artigo)\s*2(º|o)?\b", m2_rest, flags=re.I)

print("3. Debug - Detecção de artigos:")
print(f"   Art. 1º encontrado? {bool(m1)}")
if m1:
    print(f"   Posição: {m1.start()} - {m1.end()}")
    print(f"   Match: '{normalized[m1.start():m1.end()]}'")
    print(f"   Contexto: '{normalized[m1.start():m1.end()+100]}'")

print(f"\n   Art. 2º encontrado? {bool(m2)}")
if m2:
    print(f"   Posição no resto: {m2.start()} - {m2.end()}")
    print(f"   Match: '{m2_rest[m2.start():m2.end()]}'")
    print(f"   Contexto: '{m2_rest[max(0,m2.start()-50):m2.end()+50]}'")

# Verificar se o problema é a menção "art. 4º" dentro do Art. 1º
print("\n4. Verificando menções internas de artigos:")
internal_refs = re.findall(r"\bart\.\s*\d+º", normalized, flags=re.I)
print(f"   Referências encontradas: {internal_refs}")
