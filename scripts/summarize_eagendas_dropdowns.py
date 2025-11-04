import json
from pathlib import Path

p = Path('artefatos/eagendas_page_map.json')
if not p.exists():
    print('page_map not found:', p)
    raise SystemExit(1)

d = json.loads(p.read_text(encoding='utf-8'))
print('scannedUrl:', d.get('scannedUrl'))

downs = d.get('dropdowns', [])
print('dropdowns found:', len(downs))
print()

for i, dd in enumerate(downs, 1):
    label = dd.get('label') or ''
    kind = dd.get('kind')
    sel = dd.get('rootSelector')
    info = dd.get('info') or {}
    visible = info.get('visible')
    box = info.get('box')
    opts = info.get('options') or []
    print(f"[{i}] label={label!r}, kind={kind}, selector={sel}, visible={visible}, options={len(opts)}")
    if box:
        print(f"    box={box}")
    for j, o in enumerate(opts[:3], 1):
        print(f"    opt{j}: text={o.get('text')!r}, value={o.get('value')!r}")
    print()