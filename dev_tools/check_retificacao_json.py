import json

json_path = "C:/Projetos/resultados/testeLuiza_performance/job1_DO1_21-10-2025_1.json"
with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

item = [i for i in data["itens"] if "retificacao-663692822" in i.get("link", "")][0]

print(f"Item keys: {list(item.keys())}")
print(f"\nHas summary: {bool(item.get('summary'))}")
print(f"Has texto: {bool(item.get('texto'))}")
print(f"Has fulltext: {bool(item.get('fulltext'))}")

if item.get("summary"):
    print(f"\nSummary ({len(item['summary'])} chars): {item['summary'][:300]}")
if item.get("texto"):
    print(f"\nTexto ({len(item['texto'])} chars): {item['texto'][:300]}")
