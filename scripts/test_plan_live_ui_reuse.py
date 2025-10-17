from types import SimpleNamespace
from dou_snaptrack.ui.app import _get_cached_playwright_and_browser
from dou_snaptrack.cli.plan_live import build_plan_live

if __name__ == "__main__":
    res = _get_cached_playwright_and_browser()
    args = SimpleNamespace(
        secao='DO1',
        data='12-09-2025',
        plan_out=None,
        select1=None,
        select2=None,
        select3=None,
        pick1=None,
        pick2=None,
        pick3=None,
        limit1=3,
        limit2=3,
        limit3=None,
        key1_type_default='text',
        key2_type_default='text',
        key3_type_default='text',
        plan_verbose=True,
        query=None,
        headful=False,
        slowmo=0,
    )
    cfg = build_plan_live(None, args, browser=res.browser)
    print('[TEST] combos via UI browser reuse =', len(cfg.get('combos', [])))
