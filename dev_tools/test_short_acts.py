from dou_utils.text_cleaning import strip_legalese_preamble, extract_article1_section
from dou_utils.summary_utils import clean_text_for_summary

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

# DELIBERAÇÃO ANTT Nº 397
deliberacao_html = """
A Diretoria Colegiada da Agência Nacional de Transportes Terrestres - ANTT, no
uso de suas atribuições, fundamentada no Voto-vista DLA - 014, de 23 de outubro
de 2025, e no que consta do processo nº 50500.169808/2024-23, decide:

Art. 1º Fica anulada a Decisão Supas nº 776, de 20 de maio de 2025, publicada no
Diário Oficial da União - DOU em 27 de maio de 2025, seção 1.

Art. 2º Fica deferido o pedido da Expresso São Luiz Ltda., CNPJ nº
01.543.354/0001-45, para modificar o Termo de Autorização - TAR nº MTAL0045020, linha
Sinop/MT - Maceió/AL, com a implantação das seções intermediárias numeradas de 158 a
249, no Anexo desta Deliberação.

Parágrafo único. A implantação de nova seção intermediária na linha implica no
reinício da contagem do período mínimo de atendimento da linha.

Art. 3º Fica alterado o Anexo da Decisão Supas nº 703, de 1º de outubro de 2024,
publicada no DOU em 9 de outubro de 2024, seção 1, que passa a vigorar conforme
o Anexo desta Deliberação.

Art. 4º Esta Deliberação entra em vigor na data de sua publicação.

GUILHERME THEO SAMPAIO
Diretor-Geral
"""

print("="*80)
print("TESTE 1: DECISÃO SUROD Nº 1.249")
print("="*80)
print(f"\nTexto original ({len(decisao_html)} chars)")

cleaned = clean_text_for_summary(decisao_html)
print(f"\nApós clean_text_for_summary ({len(cleaned)} chars):")
print(cleaned[:500])

print("\n" + "="*80)
print("TESTE 2: DELIBERAÇÃO ANTT Nº 397")
print("="*80)
print(f"\nTexto original ({len(deliberacao_html)} chars)")

cleaned2 = clean_text_for_summary(deliberacao_html)
print(f"\nApós clean_text_for_summary ({len(cleaned2)} chars):")
print(cleaned2[:500])
