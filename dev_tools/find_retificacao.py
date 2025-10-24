import json

# Buscar RETIFICAÇÃO nos JSONs
json_files = [
    "C:/Projetos/resultados/testeLuiza_performance/job1_DO1_21-10-2025_1.json",
    "C:/Projetos/resultados/testeLuiza_performance/job2_DO1_21-10-2025_2.json",
    "C:/Projetos/resultados/testeLuiza_performance/job3_DO1_21-10-2025_3.json",
]

for json_file in json_files:
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    
    itens = data.get("itens", [])
    for item in itens:
        title = item.get("title", "")
        if "RETIFICAÇÃO" in title.upper() or "RETIFICACAO" in title.upper():
            print(f"JSON: {json_file}")
            print(f"Title: {title}")
            fulltext = item.get("fulltext", "")
            print(f"Fulltext length: {len(fulltext)}")
            print(f"First 600 chars:\n{fulltext[:600]}\n")
            print("=" * 70)
