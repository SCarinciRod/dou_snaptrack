# 05_cascade_cli.py (v6.1 - Pipeline 00 -> 05 Plan/Batch)
# Cascata DOU + Coleta + Detalhamento + Batch/Presets + Repetidor + Boletim
# Melhorias: seleção por rótulo, scroll robusto, captura edicao/pagina, faixa de datas,
# dedup (state-file), boletim HTML/MD, e novo modo PLAN para gerar batch a partir do mapa (00).

# Bootstrap de caminho: quando executado por caminho (python .../dou_snaptrack/05_cascade_cli.py),
# o sys.path não inclui a pasta 'src'. Insira 'src' para permitir imports de
# 'dou_snaptrack' e 'dou_utils'.
import sys as _sys
from pathlib import Path as _Path
_SRC_ROOT = _Path(__file__).resolve().parents[1]
if str(_SRC_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_SRC_ROOT))

import argparse
import json
import re
import sys
import unicodedata
import hashlib
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse

from dou_snaptrack.utils.browser import fmt_date

import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)

# (selectors import removido; 05 apenas orquestra e não acessa DOM diretamente)
    # Nota: helpers de navegação/DOM foram movidos para módulos em dou_snaptrack/cli e dou_utils.

    # (helpers de DOM removidos deste arquivo)

# (helpers de seleção removidos — agora pertencem aos módulos cli.*)


    # (localizadores de dropdown removidos — delegados para cli e dou_utils)


    # (sanitize_filename removido — função disponível em cli.batch/dou_utils)

    # (URL helpers removidos — não utilizados aqui)

# ------------------------- Frames e roots -------------------------
    # (find_best_frame removido — responsabilidade de cli/utils)

    # (coleta de roots removida — responsabilidade de cli/utils)

# ------------------------- Listbox / Combobox helpers -------------------------
    # (helpers listbox removidos)

    # (helpers listbox removidos)

    # (helpers de abertura de dropdown removidos)


    # (scroll helpers removidos)

    # (leitura de opções abertas removida)

# ------------------------- <select> helpers -------------------------
    # (helpers <select> removidos)

    # (leitura de <select> removida)

    # (seleção por <select>/custom removida)
# ------------------------- API unificada -------------------------
    # (helpers de rótulo removidos)

    # (procura por rótulo removida)

    # (leitura de opções de dropdown removida)

    # (seleção por key removida)

    # (seleção custom removida)

# ------------------------- Busca (query) -------------------------
    # (aplicação de query movida para dou_utils)

# ------------------------- Coleta de links -------------------------
    # (coleta de links movida para dou_utils)

# ------------------------- Detalhamento -------------------------
    # (helpers de leitura de detalhe removidos)

    # (parsers de meta removidos)

    # (busca por dt/dd removida)

    # (coleta de artigo removida)


    # (scrape de detalhe movido para dou_utils)

# ------------------------- Debug -------------------------
    # (dump de debug não é mais responsabilidade deste arquivo)
# ------------------------- Impressão (list) -------------------------
    # (impressão de listas removida)

# ------------------------- Fluxos delegados (list/run via cli modules) -------------------------

# ------------------------- Boletim -------------------------
    # (boletim agora é responsabilidade de cli.runner/cli.batch)
    
# ------------------------- PLANEJAMENTO A PARTIR DO MAPA (00) -------------------------
    # (parsing de URL não utilizado — removido)

    # (escolha de root do mapa — removido)

    # (_filter_opts removido — responsabilidade de cli/plan_live e cli/plan_from_pairs)

    # (_trim_placeholders removido — responsabilidade de mapeadores)

    # (_build_keys removido — responsabilidade de cli.plan_live)

        # (plan_from_map removido — usar PlanFromMapService no modo plan)

    # (plan_from_pairs removido — agora em dou_snaptrack.cli.plan_from_pairs)


    # (plan_live local removido — use cli.plan_live.build_plan_live)


    # (segmentador de sentenças removido)

    # (limpeza de texto para resumo removida)

    # (resumo por extração removido — centralizado em dou_utils)

# ------------------------- Batch / Presets -------------------------
def iter_dates(args_data: Optional[str], since: int, range_arg: Optional[str]):
    if range_arg:
        a, b = [s.strip() for s in range_arg.split(":")]
        d0 = datetime.strptime(a, "%d-%m-%Y").date()
        d1 = datetime.strptime(b, "%d-%m-%Y").date()
        step = timedelta(days=1)
        cur = d0
        while cur <= d1:
            yield cur.strftime("%d-%m-%Y")
            cur += step
        return
    base = datetime.strptime(fmt_date(args_data), "%d-%m-%Y").date()
    for off in range(0, max(0, since) + 1):
        d = base - timedelta(days=off)
        yield d.strftime("%d-%m-%Y")

    # (sem funções batch aqui; delegação total para dou_snaptrack.cli.batch)

def flow_report(in_dir: str, kind: str, out_path: str, date_label: Optional[str] = None, secao_label: Optional[str] = None):
    from dou_snaptrack.cli.reporting import consolidate_and_report
    consolidate_and_report(in_dir, kind, out_path, date_label=date_label or "", secao_label=secao_label or "")


# ------------------------- Presets -------------------------
def load_presets(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"presets": {}}

def save_presets(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def build_preset_from_args(args) -> Dict[str, Any]:
    return {
        "mode": "run",
        "data": args.data,
        "secao": args.secao,
        "key1_type": args.key1_type, "key1": args.key1,
        "key2_type": args.key2_type, "key2": args.key2,
        "key3_type": args.key3_type, "key3": args.key3,
        "label1": args.label1, "label2": args.label2, "label3": args.label3,
        "query": args.query,
        "max_links": args.max_links,
        "max_scrolls": args.max_scrolls,
        "scroll_pause_ms": args.scroll_pause_ms,
        "stable_rounds": args.stable_rounds,
        "scrape_detail": args.scrape_detail,
        "detail_timeout": args.detail_timeout,
        "fallback_date_if_missing": args.fallback_date_if_missing if hasattr(args, 'fallback_date_if_missing') else False,
        "debug_dump": args.debug_dump,
        "state_file": args.state_file,
        "bulletin": args.bulletin,
        "bulletin_out": args.bulletin_out,
    }

# ------------------------- Main CLI -------------------------
def main():
    ap = argparse.ArgumentParser(description="Cascata DOU v6.1 (00->plan->batch/run + boletim + dedup)")
    ap.add_argument("--mode", choices=["list", "run", "batch", "plan", "report", "plan-live", "plan-from-pairs"], required=True)
    ap.add_argument("--level", type=int, default=1, help="Para list: 1\n2\n3")

    # filtros
    ap.add_argument("--key1-type", choices=["value", "dataValue", "dataIndex", "text"])
    ap.add_argument("--key1")
    ap.add_argument("--key2-type", choices=["value", "dataValue", "dataIndex", "text"])
    ap.add_argument("--key2")
    ap.add_argument("--key3-type", choices=["value", "dataValue", "dataIndex", "text"])
    ap.add_argument("--key3")

    # rótulos
    ap.add_argument("--label1", help="Rótulo do nível 1 (ex.: 'Órgão')")
    ap.add_argument("--label2", help="Rótulo do nível 2 (ex.: 'Secretaria\nUnidade')")
    ap.add_argument("--label3", help="Rótulo do nível 3 (ex.: 'Tipo do Ato')")

    # gerais
    ap.add_argument("--query", default=None)
    ap.add_argument("--max-links", type=int, default=30)
    ap.add_argument("--max-scrolls", type=int, default=40, help="Máximo de scrolls para carregar resultados")
    ap.add_argument("--scroll-pause-ms", type=int, default=350, help="Pausa entre scrolls (ms)")
    ap.add_argument("--stable-rounds", type=int, default=3, help="Rodadas de estabilidade para parar scroll")
    ap.add_argument("--secao", default="DO1")
    ap.add_argument("--data", default=None, help="DD-MM-AAAA (default: hoje)")
    ap.add_argument("--since", type=int, default=0, help="Executa também N dias para trás (0 = apenas a data)")
    ap.add_argument("--range", help="Faixa de datas: DD-MM-AAAA:DD-MM-AAAA")
    ap.add_argument("--out", default="out_{date}.json")

    # detalhes
    ap.add_argument("--scrape-detail", action="store_true", help="Abrir cada link e extrair metadados do detalhe")
    ap.add_argument("--detail-timeout", type=int, default=60_000, help="Timeout (ms) por detalhe")
    ap.add_argument("--fallback-date-if-missing", action="store_true",
                    help="Se data_publicacao não for encontrada, usa a data da edição (--data)")

    # dedup e boletim
    ap.add_argument("--state-file", help="JSONL de estado para deduplicação por hash")
    ap.add_argument("--bulletin", choices=["html", "md", "docx"], help="Gera boletim (html/md/docx) agrupado por órgão/tipo")
    ap.add_argument("--bulletin-out", help="Arquivo de saída do boletim (ex.: boletim_ri_{date}.html)")

    # batch
    ap.add_argument("--config", help="Arquivo JSON de configuração (mode=batch)")
    ap.add_argument("--out-dir", help="Diretório base de saída para batch")
    ap.add_argument("--reuse-page", action="store_true", help="(batch) Reutiliza uma mesma aba por data/seção para todos os jobs")

    # presets
    ap.add_argument("--save-preset", help="Nome do preset a salvar (dos args atuais de run)")
    ap.add_argument("--preset", help="Nome do preset a carregar e executar (mode=run)")
    ap.add_argument("--presets-file", default="presets.json", help="Arquivo de presets (default: presets.json)")
    ap.add_argument("--save-preset-no-date", action="store_true", help="Salva preset sem a data (usa 'hoje' ao executar)")

    # PLAN
    ap.add_argument("--map-file", help="JSON gerado pela rotina 00 (mapa da página com opções dos dropdowns)")
    ap.add_argument("--plan-out", default="batch_config.json", help="Arquivo de saída do plano/batch gerado")
    ap.add_argument("--execute-plan", action="store_true", help="Após gerar o plano, executar o batch automaticamente")
    ap.add_argument("--select1", help="Regex para filtrar opções do nível 1 (por texto)")
    ap.add_argument("--select2", help="Regex para filtrar opções do nível 2 (por texto)")
    ap.add_argument("--select3", help="Regex para filtrar opções do nível 3 (por texto)")
    ap.add_argument("--pick1", help="Lista fixa (vírgula) de opções do nível 1 (match por texto)")
    ap.add_argument("--pick2", help="Lista fixa (vírgula) de opções do nível 2 (match por texto)")
    ap.add_argument("--pick3", help="Lista fixa (vírgula) de opções do nível 3 (match por texto)")
    ap.add_argument("--limit1", type=int, help="Limite de opções no nível 1")
    ap.add_argument("--limit2", type=int, help="Limite de opções no nível 2")
    ap.add_argument("--limit3", type=int, help="Limite de opções no nível 3")
    ap.add_argument("--key1-type-default", choices=["text","value","dataValue","dataIndex"], default="text")
    ap.add_argument("--key2-type-default", choices=["text","value","dataValue","dataIndex"], default="text")
    ap.add_argument("--key3-type-default", choices=["text","value","dataValue","dataIndex"], default="text")
    ap.add_argument("--no-level3", action="store_true", help="(obsoleto no plan: N3 é ignorado)")
    ap.add_argument("--plan-verbose", action="store_true", help="Mostra diagnóstico detalhado durante o plan")
    ap.add_argument("--max-combos", type=int, help="(plan) Corta o produto L1×L2 para no máximo N")  # IMPORTANTE: defina só UMA vez!

    # PLAN from pairs
    ap.add_argument("--pairs-file", help="JSON de pares N1->N2 gerado pelo 00_map_pairs.py")
    ap.add_argument("--limit2-per-n1", type=int, help="Limite de N2 por N1 (ao gerar combos a partir dos pares)")

    # ambiente
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--slowmo", type=int, default=0)
    ap.add_argument("--debug-dump", action="store_true", help="Salvar screenshot/DOM em caso de erro")

    # Resumo (globais)
    ap.add_argument("--summary-sentences", type=int, default=3, help="Nº de frases no resumo (default: 3)")
    ap.add_argument("--summary-keywords", help="Lista de palavras de interesse separadas por ponto e vírgula (;)")
    ap.add_argument("--summary-keywords-file", help="Arquivo .txt com palavras de interesse (uma por linha)")
    ap.add_argument("--summary-lines", type=int, help="Nº de linhas do resumo (preferido). Se não for passado, usa --summary-sentences.")
    ap.add_argument("--summary-mode", choices=["center", "lead", "keywords-first"], default="center",
                    help="Estratégia de resumo: center (padrão), lead ou keywords-first")

    # REPORT
    ap.add_argument("--in-dir", help="(report) Pasta com os JSONs (saídas dos jobs)")
    ap.add_argument("--report-out", help="(report) Caminho do boletim final (docx/md/html)")

    args = ap.parse_args()
    # Nova configuração de resumo: exigir cli.summary_config (sem globais)
    try:
        from dou_snaptrack.cli.summary_config import setup_summary_from_args as _setup_summary_from_args
        SUMMARY_CFG = _setup_summary_from_args(args)
    except Exception:
        print("[Erro] Configuração de resumo indisponível (cli.summary_config).")
        sys.exit(2)

    # Salvar preset (opcional)
    if args.save_preset:
        preset_path = Path(args.presets_file)
        store = load_presets(preset_path)
        if not hasattr(args, "fallback_date_if_missing"):
            args.fallback_date_if_missing = False
        pr = build_preset_from_args(args)
        if args.save_preset_no_date:
            pr["data"] = None
        store["presets"][args.save_preset] = pr
        save_presets(preset_path, store)
        print(f"[OK] Preset salvo: {args.save_preset} em {preset_path}")

    # REPORT (sem fallback)
    if args.mode == "report":
        if not args.in_dir or not args.report_out or not args.bulletin:
            print("[Erro] --in-dir, --report-out e --bulletin são obrigatórios no mode=report"); sys.exit(1)
        from dou_snaptrack.cli.reporting import consolidate_and_report
        consolidate_and_report(args.in_dir, args.bulletin, args.report_out, date_label=args.data or "", secao_label=args.secao or "")
        return

    # plan-from-pairs (não precisa Playwright; só se --execute-plan)
    if args.mode == "plan-from-pairs":
        if not args.pairs_file:
            print("[Erro] --pairs-file obrigatório em mode=plan-from-pairs"); sys.exit(1)
        try:
            from dou_snaptrack.cli.plan_from_pairs import build_plan_from_pairs
            cfg = build_plan_from_pairs(args.pairs_file, args)
            Path(args.plan_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] Plano (from-pairs) gerado em: {args.plan_out} (combos={len(cfg.get('combos', []))})")
            if args.execute_plan:
                print("[Exec] Rodando batch com o plano recém-gerado...")
                args.config = args.plan_out
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    from dou_snaptrack.cli.batch import run_batch
                    run_batch(p, args, SUMMARY_CFG)
        except Exception as e:
            print(f"[ERRO][plan-from-pairs] {e}")
            if getattr(args, "plan_verbose", False):
                raise
            sys.exit(1)
        return

    # batch (precisa Playwright) - sem fallback
    if args.mode == "batch":
        if not args.config:
            print("[Erro] --config obrigatório em mode=batch"); sys.exit(1)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            from dou_snaptrack.cli.batch import run_batch
            run_batch(p, args, SUMMARY_CFG)
        return

    # Demais modos usam Playwright (list/run/plan/plan-live)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # plan-live gera o plano dinâmico e opcionalmente já executa (via cli.plan_live)
        if args.mode == "plan-live":
            try:
                from dou_snaptrack.cli.plan_live import build_plan_live
                cfg = build_plan_live(p, args)
                Path(args.plan_out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[OK] Plano (live) gerado em: {args.plan_out} (combos={len(cfg.get('combos', []))})")
                if args.execute_plan:
                    print("[Exec] Rodando batch com o plano recém-gerado...")
                    args.config = args.plan_out
                    from dou_snaptrack.cli.batch import run_batch
                    run_batch(p, args, SUMMARY_CFG)
            except Exception as e:
                print(f"[ERRO][plan-live] {e}")
                if getattr(args, "plan_verbose", False):
                    raise
                sys.exit(1)
            return

        # Single run/list
        browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)
        try:
            if args.preset:
                preset_path = Path(args.presets_file)
                store = load_presets(preset_path)
                pr = (store.get("presets") or {}).get(args.preset)
                if not pr:
                    print(f"[Erro] Preset '{args.preset}' não encontrado em {preset_path}")
                    sys.exit(1)
                for k, v in pr.items():
                    if getattr(args, k, None) in (None, False):
                        setattr(args, k, v)

            if args.mode == "list":
                data = fmt_date(args.data)
                from dou_snaptrack.cli.listing import run_list
                run_list(
                    context, data, args.secao, args.level,
                    args.key1, args.key1_type, args.key2, args.key2_type,
                    args.out, args.debug_dump,
                    label1=args.label1, label2=args.label2, label3=args.label3
                )
                return

            if args.mode == "run":
                for d in iter_dates(args.data, args.since, args.range):
                    missing = []
                    if not args.key1 or not args.key1_type: missing.append("key1/key1-type")
                    if not args.key2 or not args.key2_type: missing.append("key2/key2-type")
                    if missing:
                        print("[Erro] Parâmetros faltando:", ", ".join(missing)); sys.exit(1)

                    out_path = args.out.replace("{date}", d.replace("/", "-"))
                    bulletin_out = args.bulletin_out.replace("{date}", d.replace("/", "-")) if args.bulletin_out else None

                    from dou_snaptrack.cli.runner import run_once
                    run_once(
                        context, d, args.secao,
                        args.key1, args.key1_type, args.key2, args.key2_type, args.key3, args.key3_type,
                        args.query, args.max_links, out_path,
                        args.scrape_detail, args.detail_timeout, args.fallback_date_if_missing,
                        label1=args.label1, label2=args.label2, label3=args.label3,
                        max_scrolls=args.max_scrolls, scroll_pause_ms=args.scroll_pause_ms, stable_rounds=args.stable_rounds,
                        state_file=args.state_file, bulletin=args.bulletin, bulletin_out=bulletin_out,
                        summary=SUMMARY_CFG
                    )
                return

            if args.mode == "plan":
                if not args.map_file:
                    print("[Erro] --map-file obrigatório em mode=plan"); sys.exit(1)
                try:
                    try:
                        from dou_utils.services.planning_service import PlanFromMapService
                    except Exception:
                        print("[Erro] Serviço de planejamento indisponível.")
                        sys.exit(1)
                    svc = PlanFromMapService(args.map_file)
                    # defaults básicos herdados dos argumentos atuais
                    defaults = {
                        "scrape_detail": bool(args.scrape_detail),
                        "summary_lines": int(getattr(args, "summary_lines", 5) or 5),
                        "summary_mode": getattr(args, "summary_mode", "center") or "center",
                        "bulletin": args.bulletin or "docx",
                        "bulletin_out": args.bulletin_out or "boletim_{secao}_{date}_{idx}.docx",
                    }
                    date_label = fmt_date(args.data)
                    cfg = svc.build(
                        label1_regex=args.label1,
                        label2_regex=args.label2,
                        select1=args.select1,
                        pick1=args.pick1,
                        limit1=args.limit1,
                        select2=args.select2,
                        pick2=args.pick2,
                        limit2=args.limit2,
                        max_combos=args.max_combos,
                        secao=args.secao,
                        date=date_label,
                        defaults=defaults,
                        query=args.query,
                        enable_level3=bool(args.key3_type_default or args.select3 or args.pick3 or args.limit3),
                        label3_regex=args.label3,
                        select3=args.select3,
                        pick3=args.pick3,
                        limit3=args.limit3,
                        filter_sentinels=True,
                        dynamic_n2=False,
                    )
                    Path(args.plan_out).parent.mkdir(parents=True, exist_ok=True)
                    Path(args.plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[OK] Plano (map) gerado em: {args.plan_out} (combos={len(cfg.get('combos', []))})")
                    if args.execute_plan:
                        print("[Exec] Rodando batch com o plano recém-gerado...")
                        args.config = args.plan_out
                        from dou_snaptrack.cli.batch import run_batch
                        run_batch(p, args, SUMMARY_CFG)
                except Exception as e:
                    print(f"[ERRO][plan] {e}")
                    if getattr(args, "plan_verbose", False):
                        raise
                    sys.exit(1)
                return

            print(f"[Erro] Modo desconhecido: {args.mode}")
            sys.exit(1)

        finally:
            try:
                browser.close()
            except Exception:
                pass

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Abortado pelo usuário]")
        sys.exit(130)
