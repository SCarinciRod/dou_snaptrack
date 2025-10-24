import re

text = "Brasão do Brasil Diário Oficial da União Publicado em: 21/10/2025 | Edição: 201 | Seção: 1 | Página: 5 Órgão: Atos do Poder Executivo RETIFICAÇÃO Na Retificação"

pattern = r"^.*?(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:[^\n]*?\s*(?=(?:PORTARIA|DECRETO|DESPACHO|RESOLUÇÃO|ATO|EXTRATO|PAUTA|DELIBERAÇÃO|ALVARÁ|RETIFICAÇÃO|SÚMULA|Portaria|Decreto|Despacho|MENSAGEM|Mensagem|Retificação|Súmula)(?:\s|$))"

result = re.sub(pattern, "", text, count=1, flags=re.I | re.DOTALL)

print(f"Original ({len(text)} chars):")
print(text)
print(f"\nDepois do regex ({len(result)} chars):")
print(result)
print(f"\nFuncionou? {len(result) < len(text)}")
