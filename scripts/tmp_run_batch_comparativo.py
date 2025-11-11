from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure src on path early
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import sync_playwright  # type: ignore
from dou_snaptrack.cli.batch import run_batch  # type: ignore
from dou_snaptrack.cli.summary_config import SummaryConfig  # type: ignore

CFG_IN = Path('planos/comparativo.json')
if not CFG_IN.exists():
    print('[ERR] Plano comparativo.json não encontrado em planos/')
    sys.exit(2)

raw = json.loads(CFG_IN.read_text(encoding='utf-8'))
raw.setdefault('defaults', {})
# Garantir parâmetros desejados
raw["defaults"].setdefault("scrape_detail", False)
raw["defaults"].setdefault("detail_parallel", 1)
raw["defaults"].setdefault("max_links", 120)
for c in raw.get('combos') or []:
    if isinstance(c, dict):
        c.setdefault("max_links", 120)

TMP_CFG = Path("planos/_tmp_comparativo_run.json")
TMP_CFG.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
print("[Batch] Config temporária pronta:", TMP_CFG)

# Windows loop policy for Playwright stability
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

# Prefer Edge first (reduz chance de bloqueio corporativo)
os.environ["DOU_PREFER_EDGE"] = "1"
os.environ.pop("DOU_FAST_MODE", None)

OUT_DIR = Path("resultados")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUT_DIR / "comparativo_run.log"

with sync_playwright() as p:
    args = SimpleNamespace(
        config=str(TMP_CFG),
        out_dir=str(OUT_DIR),
        headful=False,
        slowmo=0,
        state_file=None,
        reuse_page=False,
        parallel=1,
    log_file=str(LOG_FILE),
    )
    run_batch(p, args, SummaryConfig(lines=0, mode='center', keywords=None))

REP_PATH = OUT_DIR / "batch_report.json"
if not REP_PATH.exists():
    print('[Batch] Relatório não encontrado. Encerrando.')
    sys.exit(3)
rep = json.loads(REP_PATH.read_text(encoding='utf-8'))
print("[Batch] Jobs OK:", rep.get("ok"), "Jobs FAIL:", rep.get("fail"))
print("[Batch] Arquivos gerados:", len(rep.get("outputs", [])))

# Contagem agregada de links
total_links = 0
pres_files = []
for f in OUT_DIR.glob("*_DO1_10-11-2025_*.json"):
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        total_links += int(data.get("total", 0) or 0)
        txt = f.read_text(encoding="utf-8")
        if "Presidência" in txt or "Presidencia" in txt:
            pres_files.append(f.name)
    except Exception:
        pass
print("[Batch] Soma total de links (DO1 10-11-2025):", total_links)
print("[Batch] Arquivos contendo Presidência:", pres_files)

if total_links <= 45:
    print("[Batch][ALERTA] Total <= 45 — problema pode persistir.")
else:
    print("[Batch][OK] Total > 45 — aumento detectado.")
