import json
import sys
sys.path.insert(0, "C:/Projetos/src")

from dou_utils.summary_utils import clean_text_for_summary

json_path = "C:/Projetos/resultados/testeLuiza_performance/job1_DO1_21-10-2025_1.json"
with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

# Encontrar retificação
itens = data.get("itens", [])
item = [i for i in itens if "retificacao-663692822" in i.get("link", "")][0]

fulltext = item.get("fulltext", "")
print(f"Fulltext original ({len(fulltext)} chars):")
print(fulltext[:800])
print("\n" + "=" * 70 + "\n")

# Testar clean
cleaned = clean_text_for_summary(fulltext)
print(f"Após clean_text_for_summary ({len(cleaned)} chars):")
print(cleaned[:800])
print("\n" + "=" * 70 + "\n")

# Checar se tem Brasão
has_brasao = "Brasão" in cleaned[:400]
print(f"Ainda tem 'Brasão'? {has_brasao}")
