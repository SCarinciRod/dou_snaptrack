import json, tempfile
from pathlib import Path
from dou_utils.services.planning_service import PlanFromMapService

def _fake_mapping(tmp_path: Path):
    data = {
        "data": {
            "dropdowns": [
                { "label": "Orgão", "options": [
                    {"text": "Selecionar órgão", "value": ""},
                    {"text": "Min A", "value": "MA"},
                    {"text": "Min B", "value": "MB"},
                ]},
                { "label": "Tipo", "options": [
                    {"text": "Selecionar tipo", "value": ""},
                    {"text": "Portaria", "value": "PORT"},
                    {"text": "Resolução", "value": "RES"},
                ]}
            ]
        }
    }
    f = tmp_path / "mapping.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(f)

def test_plan_map_refactor(tmp_path):
    mp = _fake_mapping(tmp_path)
    svc = PlanFromMapService(mp)
    plan = svc.build(
        label1_regex=None,
        label2_regex=None,
        select1=None,
        pick1=None,
        limit1=None,
        select2=None,
        pick2=None,
        limit2=None,
        max_combos=None,
        secao="DO1",
        date="16-09-2025",
        defaults={},
        query=None
    )
    combos = plan["combos"]
    assert len(combos) == 4  # 2 x 2 (placeholders removidos)
    assert all(c["key1"] and c["key2"] for c in combos)
