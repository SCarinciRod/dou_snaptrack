import json

json_path = "C:/Projetos/resultados/teste_10jobs/educacao_DO1_21-10-2025_4.json"
with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

itens = data.get("itens", [])
print(f"Total itens: {len(itens)}\n")

# Últimos 4 itens (as portarias problemáticas)
for i, item in enumerate(itens[-4:], start=len(itens)-3):
    title = item.get("title", "NO TITLE")
    summary = item.get("summary", "NO SUMMARY")
    
    print(f"=== Item {i}: {title[:60]} ===")
    print(f"Has summary: {bool(summary)}")
    print(f"Summary length: {len(summary) if summary else 0}")
    if summary:
        print(f"First 300 chars: {summary[:300]}")
        has_brasao = "Brasão" in summary[:400]
        print(f"Contains 'Brasão': {has_brasao}")
    print()
