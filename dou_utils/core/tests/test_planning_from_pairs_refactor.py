import json, tempfile
from pathlib import Path
from dou_utils.services.planning_service import PlanFromPairsService

def _fake_pairs(tmp_path: Path):
    data = {
        "data": {
            "pairs": [
                {
                    "n1Option": {"text": "Min A", "value": "MA"},
                    "n2Options": [
                        {"text": "Portaria", "value": "PORT"},
                        {"text": "Resolução", "value": "RES"},
                    ]
                },
                {
                    "n1Option": {"text": "Min B", "value": "MB"},
                    "n2Options": [
                        {"text": "Portaria", "value": "PORT"},
                        {"text": "Resolução", "value": "RES"},
                    ]
                }
            ]
        }
    }
    f = tmp_path / "pairs.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(f)

def test_plan_pairs_refactor(tmp_path):
    pf = _fake_pairs(tmp_path)
    svc = PlanFromPairsService(pf)
    plan = svc.build(
        select1=None, pick1=None, limit1=None,
        select2=None, pick2=None, limit2_per_n1=None,
        max_combos=None,
        secao="DO1", date="16-09-2025",
        defaults={}, query=None
    )
    combos = plan["combos"]
    assert len(combos) == 4
    assert combos[0]["key1"] in {"MA", "MB"}
