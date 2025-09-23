#!# cli.py
# Interface de linha de comando unificada para DOU Snaptrack

import argparse
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

from utils.date import fmt_date
from mappers.page_mapper import map_page, save_map, dump_debug
from mappers.pairs_mapper import map_pairs, save_pairs

def main():
    parser = argparse.ArgumentParser(description="DOU Snaptrack - Ferramenta modular para mapeamento e coleta do DOU")
    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")
    
    # Comando map-page (baseado no 00_map_page.py)
    map_page_parser = subparsers.add_parser("map-page", help="Mapeia uma página (dropdowns e elementos)")
    group = map_page_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="URL completa")
    group.add_argument("--dou", action="store_true", help="Usar Leitura do Jornal do DOU")
    map_page_parser.add_argument("--data", default=None, help="(DOU) DD-MM-AAAA, default: hoje")
    map_page_parser.add_argument("--secao", default="DO1", help="(DOU) DO1|DO2|DO3")
    map_page_parser.add_argument("--open-combos", action="store_true", help="Abrir dropdowns e coletar opções")
    map_page_parser.add_argument("--out", default="page_map.json", help="Arquivo de saída JSON")
    map_page_parser.add_argument("--headful", action="store_true", help="Modo visível (não headless)")
    map_page_parser.add_argument("--slowmo", type=int, default=0, help="Desaceleração em ms")
    map_page_parser.add_argument("--debug-dump", action="store_true", help="Salvar screenshot/HTML para debug")
    map_page_parser.add_argument("--max-per-type", type=int, default=120, help="Limite por categoria")
    
    # Comando map-pairs (baseado no 00_map_pairs.py)
    map_pairs_parser = subparsers.add_parser("map-pairs", help="Mapeia pares N1->N2 (para cada N1, captura N2)")
    map_pairs_parser.add_argument("--secao", required=True, help="Seção do DOU (DO1|DO2|DO3)")
    map_pairs_parser.add_argument("--data", required=True, help="DD-MM-AAAA")
    map_pairs_parser.add_argument("--out", required=True, help="Arquivo de saída JSON")
    map_pairs_parser.add_argument("--label1", help="Regex do rótulo do N1 (ex.: 'Órgão|Orgao')")
    map_pairs_parser.add_argument("--label2", help="Regex do rótulo do N2 (ex.: 'Secretaria|Unidade|Subordinad')")
    map_pairs_parser.add_argument("--pick1", help="Lista fixa (vírgula) de rótulos de N1")
    map_pairs_parser.add_argument("--limit1", type=int, help="Limite de itens N1")
    map_pairs_parser.add_argument("--select1", help="Regex para filtrar rótulos de N1")
    map_pairs_parser.add_argument("--select2", help="Regex para filtrar rótulos de N2")
    map_pairs_parser.add_argument("--pick2", help="Lista fixa (vírgula) de rótulos de N2")
    map_pairs_parser.add_argument("--limit2-per-n1", type=int, help="Limite de itens N2 por N1")
    map_pairs_parser.add_argument("--headful", action="store_true", help="Modo visível (não headless)")
    map_pairs_parser.add_argument("--slowmo", type=int, default=0, help="Desaceleração em ms")
    map_pairs_parser.add_argument("--verbose", action="store_true", help="Modo verboso")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
        
    with sync_playwright() as p:
        if args.command == "map-page":
            browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
            page = context.new_page()
            try:
                result = map_page(context, args)
                save_map(result, args.out)
                if args.debug_dump:
                    dump_debug(page, "debug_map")
            finally:
                browser.close()
                
        elif args.command == "map-pairs":
            browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
            try:
                result = map_pairs(context, args)
                save_pairs(result, args.out)
            finally:
                browser.close()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[Abortado]")
        sys.exit(130)
