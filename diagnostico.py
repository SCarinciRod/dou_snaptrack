# plan_sanity_check.py
import json, re, sys
from pathlib import Path

def main(map_file):
    mp = json.loads(Path(map_file).read_text(encoding='utf-8'))
    drops = mp.get('dropdowns', [])
    if not drops:
        print("[ERRO] Sem 'dropdowns' no mapa. Gere a 00 com --open-combos."); return
    print(f"[INFO] dropdowns: {len(drops)}")
    for i,d in enumerate(drops,1):
        lab = (d.get('label') or '').strip()
        attrs = (d.get('info') or {}).get('attrs') or {}
        did = attrs.get('id')
        kind = d.get('kind')
        opts = d.get('options') or []
        print(f"{i:02d} kind={kind:8} id={did or '-':12} label='{lab}' options={len(opts)}")
        if i<=3:
            for o in (opts[:10]):
                print("   -", (o.get('text') or o.get('value') or o.get('dataValue') or str(o))[:120])
    print("\nSugestões de labels (tente no --labelX):")
    labs = [((d.get('label') or '').strip()) for d in drops if (d.get('label') or '').strip()]
    for s in sorted(set(labs))[:10]:
        print("  •", s)

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("Uso: python plan_sanity_check.py <map.json>"); sys.exit(2)
    main(sys.argv[1])
