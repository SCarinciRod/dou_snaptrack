
import json, sys
p=r'artefatos\\batch_config.json'
cfg=json.load(open(p,'r',encoding='utf-8'))
print('combos =',len(cfg.get('combos',[])))
print('defaults keys =',list((cfg.get('defaults') or {}).keys()))

