from dou_utils.core.combos import generate_cartesian, build_dynamic_n2

def test_generate_cartesian_basic():
    n1 = [{"text": "A", "value": "A"}, {"text": "B", "value": "B"}]
    n2 = [{"text": "X", "value": "X"}]
    combos = generate_cartesian(n1, n2)
    assert len(combos) == 2
    keys = {(c["key1"], c["key2"]) for c in combos}
    assert ("A", "X") in keys and ("B", "X") in keys

def test_dynamic_n2():
    n1 = [{"text": "A", "value": "A"}, {"text": "B", "value": "B"}]
    dyn = build_dynamic_n2(n1, max_combos=1)
    assert len(dyn) == 1
    assert dyn[0]["_dynamicN2"] is True
