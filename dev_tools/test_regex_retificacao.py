import re

text = "Brasão do Brasil Diário Oficial da União Publicado em: 21/10/2025 | Edição: 201 | Seção: 1 | Página: 5 Órgão: Atos do Poder Executivo RETIFICAÇÃO Na Retificação do Decreto nº 12.676"

print(f"Original ({len(text)} chars):")
print(text)
print("\n" + "=" * 70 + "\n")

# Regex atual
pattern = r"^.*?(?:Brasão|Diário Oficial da União).*?(?:Publicado em|Edição).*?(?:Seção|Página).*?Órgão:[^\n]*?\s*(?=(?:PORTARIA|DECRETO|DESPACHO|RESOLUÇÃO|ATO|EXTRATO|PAUTA|DELIBERAÇÃO|ALVARÁ|RETIFICAÇÃO|SÚMULA|Portaria|Decreto|Despacho|MENSAGEM|Mensagem|Retificação|Súmula)(?:\s|$))"

result = re.sub(pattern, "", text, count=1, flags=re.I | re.DOTALL)

print(f"Após regex ({len(result)} chars):")
print(result)
print("\n" + "=" * 70 + "\n")

# Testar match
match = re.search(pattern, text, flags=re.I | re.DOTALL)
if match:
    print(f"Match encontrado até posição {match.end()}")
    print(f"Texto matched: {text[:match.end()]}")
else:
    print("NENHUM MATCH!")
