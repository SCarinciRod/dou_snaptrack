from dou_utils.core.option_filter import filter_options
from dou_utils.core.sentinel_utils import is_sentinel_option

options = [
    {"text": "Selecionar órgão", "value": ""},
    {"text": "Ministério A", "value": "MA"},
    {"text": "Ministério B", "value": "MB"},
    {"text": "Agência X", "value": "AX"},
]

def test_filter_drop_sentinels():
    out = filter_options(options, drop_sentinels=True, is_sentinel_fn=is_sentinel_option)
    assert len(out) == 3
    assert all(o["value"] for o in out)

def test_filter_pick_list():
    out = filter_options(options, pick_list="MA,AX", drop_sentinels=True, is_sentinel_fn=is_sentinel_option)
    vals = {o["value"] for o in out}
    assert vals == {"MA", "AX"}

def test_filter_regex():
    out = filter_options(options, select_regex="Ministerio", drop_sentinels=True, is_sentinel_fn=is_sentinel_option)
    assert len(out) == 2

def test_filter_limit():
    out = filter_options(options, drop_sentinels=True, is_sentinel_fn=is_sentinel_option, limit=1)
    assert len(out) == 1
