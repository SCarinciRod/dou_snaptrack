import json
import tempfile
from pathlib import Path
from dou_utils.services.planning_service import PlanFromMapService

def _fake_map_file(tmp_path: Path):
    data = {
        "data": {
            "dropdowns": [
                {
                    "label": "Orgão",
                    "options": [
                        {"text": "Selecionar órgão", "value": ""},
                        {"text": "Ministério A", "value": "MA"},
                        {"text": "Ministério B", "value": "MB"},
                    ]
                },
                {
                    "label": "Tipo do Ato",
                    "options": [
                        {"text": "Selecionar tipo", "value": ""},
                        {"text": "Portaria", "value": "PORT"},
                        {"text": "Resolução", "value": "RES"},
                    ]
                }
            ]
        }
    }
    f = tmp_path / "map.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(f)

def test_plan_from_map_basic(tmp_path):
    map_file = _fake_map_file(tmp_path)
    svc = PlanFromMapService(map_file)
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
        date="01-01-2025",
        defaults={},
        query=None,
        enable_level3=False,
    )
    combos = plan["combos"]
    # Deve excluir placeholders
    assert all(c["key1"] for c in combos)
    assert all(c["key2"] for c in combos)
    # 2 válidos N1 x 2 válidos N2 = 4
    assert len(combos) == 4
