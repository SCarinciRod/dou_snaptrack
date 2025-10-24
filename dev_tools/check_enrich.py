import json

json_files = [
    "C:/Projetos/resultados/testeLuiza_performance/job1_DO1_21-10-2025_1.json",
    "C:/Projetos/resultados/testeLuiza_performance/job2_DO1_21-10-2025_2.json",
    "C:/Projetos/resultados/testeLuiza_performance/job3_DO1_21-10-2025_3.json",
]

print("Verificando enriquecimento dos JSONs:\n")
total_itens = 0
total_com_fulltext = 0

for json_file in json_files:
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    
    itens = data.get("itens", [])
    com_fulltext = sum(1 for i in itens if i.get("fulltext") or i.get("texto"))
    
    print(f"{json_file.split('/')[-1]:45s} - {len(itens):2d} itens, {com_fulltext:2d} com fulltext")
    
    total_itens += len(itens)
    total_com_fulltext += com_fulltext

print(f"\n{'TOTAL':45s} - {total_itens:2d} itens, {total_com_fulltext:2d} com fulltext ({100*total_com_fulltext/total_itens:.0f}%)")
