import os, sys, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dou_utils.content_fetcher import Fetcher
from dou_utils.bulletin_utils import _summarize_item, _minimal_summary_from_item
from dou_utils.summarize import summarize_text as _summarize_text

def main(agg_path: str, threshold: int = 1200, timeout: int = 45, parallel: int = 6):
    os.environ['DOU_OFFLINE_REPORT'] = '0'
    p = Path(agg_path)
    data = json.loads(p.read_text(encoding='utf-8'))
    items = data.get('itens', [])
    fch = Fetcher(timeout_sec=timeout, force_refresh=True, use_browser_if_short=True, short_len_threshold=threshold, browser_timeout_sec=max(20, timeout))
    fch.enrich_items(items, max_workers=parallel, overwrite=True, min_len=None)

    miss = []
    stats = []
    for it in items:
        title = (it.get('title_friendly') or it.get('titulo') or it.get('titulo_listagem') or '')
        txt = (it.get('texto') or it.get('ementa') or '')
        sn = _summarize_item(it, _summarize_text, True, None, 3, 'lead')
        if not sn:
            sn = _minimal_summary_from_item(it)
        stats.append((title[:100], len(txt), 1 if (sn and sn.strip()) else 0))
        if not (sn and sn.strip()):
            miss.append(title[:120])
    total = len(stats)
    summarized = sum(s[2] for s in stats)
    print({
        'total': total,
        'summarized': summarized,
        'missing_titles': miss,
        'lens': stats,
    })

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--agg', required=True)
    ap.add_argument('--thr', type=int, default=1200)
    ap.add_argument('--timeout', type=int, default=45)
    ap.add_argument('--parallel', type=int, default=6)
    args = ap.parse_args()
    main(args.agg, args.thr, args.timeout, args.parallel)
