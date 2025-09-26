import json
from pathlib import Path
from dou_utils.batch_utils import sanitize_filename

def plan_from_map(map_file: str, args) -> dict:
    mp = json.loads(Path(map_file).read_text(encoding="utf-8"))
    dropdowns = mp.get("dropdowns") or []
    data = mp.get("data") or args.data
    secao = mp.get("secao") or args.secao or "DO1"

    def get_options(drop):
        return [o for o in drop.get("options", []) if o.get("text") and "selecionar" not in o.get("text").lower()]

    root1 = dropdowns[0] if len(dropdowns) > 0 else {}
    root2 = dropdowns[1] if len(dropdowns) > 1 else {}

    opts1 = get_options(root1)
    opts2 = get_options(root2)

    combos = []
    for o1 in opts1:
        for o2 in opts2:
            combos.append({
                "key1_type": "text",
                "key1": o1["text"],
                "key2_type": "text",
                "key2": o2["text"],
                "key3_type": None,
                "key3": None,
                "label1": root1.get("label", ""),
                "label2": root2.get("label", ""),
                "label3": "",
            })

    cfg = {
        "data": data,
        "secaoDefault": secao,
        "defaults": {
            "scrape_detail": True,
            "summary_lines": 5,
            "summary_mode": "center",
            "bulletin": "docx",
            "bulletin_out": "boletim_{secao}_{date}_{idx}.docx"
        },
        "topics": [{
            "name": "RI",
            "query": args.query or "regulação"
        }],
        "combos": combos,
        "output": {
            "pattern": "job_{secao}_{date}_{idx}.json",
            "report": "batch_report.json",
            "bulletin": "boletim_{secao}_{date}_{idx}.docx"
        }
    }

    return cfg
