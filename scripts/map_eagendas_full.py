"""
Mapeamento COMPLETO de pares Órgão → Cargo → Agente Público do e-agendas.
Gera artefato JSON confiável para uso em produção.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Forçar UTF-8 (adiantado para toda a execução)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dou_snaptrack.mappers.eagendas_pairs import (  # noqa: E402
    map_eagendas_pairs as map_eagendas_pairs_legacy,
)
from dou_snaptrack.mappers.eagendas_pairs_optimized import (  # noqa: E402
    map_eagendas_pairs_optimized as map_eagendas_pairs_opt,
)
from dou_snaptrack.utils.browser import (  # noqa: E402
    build_url,
    goto,
    launch_browser,
    new_context,
)
from dou_snaptrack.utils.dom import find_best_frame  # noqa: E402
from dou_snaptrack.utils.selectize import (  # noqa: E402
    selectize_get_options_count,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mapeamento completo e-agendas → artefatos de pares")
    ap.add_argument("--optimized", action="store_true", help="Usar mapper otimizado (recomendado)")
    ap.add_argument("--headful", action="store_true", help="Mostrar navegador durante execução")
    ap.add_argument("--slowmo", type=int, default=0, help="Delay entre ações (ms)")
    ap.add_argument("--limit-orgaos", type=int, default=0, help="Limitar número de órgãos (0 = todos)")
    ap.add_argument("--limit-cargos", type=int, default=0, help="Limitar cargos por órgão (0 = todos)")
    ap.add_argument("--debug", action="store_true", help="Emitir logs de progresso detalhados e tempos")
    # Paralelização
    ap.add_argument("--workers", type=int, default=0, help="Executar mapeamento em paralelo (N processos)")
    ap.add_argument("--shard-count", type=int, default=0, help="Total de shards (usado internamente)")
    ap.add_argument("--shard-index", type=int, default=0, help="Índice do shard (usado internamente)")
    ap.add_argument("--output-file", type=str, default="", help="Caminho do artefato de saída (opcional)")
    ap.add_argument("--skip-latest", action="store_true", help="Não atualizar o arquivo 'latest' (útil para shards)")
    # Performance
    ap.add_argument(
        "--no-block-resources",
        action="store_true",
        help="Não bloquear imagens, fontes, mídia e analytics (por padrão bloqueia para ganhar velocidade)",
    )
    return ap.parse_args(argv or sys.argv[1:])


def _merge_shard_results(json_paths: list[Path]) -> dict:
    merged = {
        "url": "https://eagendas.cgu.gov.br",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hierarchy": [],
        "stats": {
            "total_orgaos": 0,
            "total_cargos": 0,
            "total_agentes": 0,
            "orgaos_sem_cargos": 0,
            "cargos_sem_agentes": 0,
        },
    }
    # Leitura com json.load (evita criar string gigante na memória)
    for p in json_paths:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        # Hierarquia: concatenar
        merged["hierarchy"].extend(data.get("hierarchy", []) or [])
        # Stats: somar campos numéricos conhecidos
        st = data.get("stats", {}) or {}
        for k in merged["stats"]:
            with contextlib.suppress(Exception):
                merged["stats"][k] += int(st.get(k, 0) or 0)
    return merged


def main():
    ns = _parse_args()
    print("=" * 80)
    print("MAPEAMENTO COMPLETO E-AGENDAS")
    print("=" * 80)
    print(f"\nData/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Parâmetros
    HEADFUL = bool(ns.headful)  # Navegador OCULTO por padrão
    SLOWMO = int(ns.slowmo or 0)  # Sem slowmo por padrão

    # Limites para mapeamento completo
    LIMIT_ORGAOS = (ns.limit_orgaos or None)  # None = todos (227 órgãos)
    LIMIT_CARGOS_PER_ORGAO = (ns.limit_cargos or None)  # None = todos

    print("\nParâmetros:")
    print(f"  Navegador visível: {HEADFUL}")
    print(f"  Slowmo: {SLOWMO}ms")
    print(f"  Limite órgãos: {LIMIT_ORGAOS or 'TODOS'}")
    print(f"  Limite cargos/órgão: {LIMIT_CARGOS_PER_ORGAO or 'TODOS'}")

    print("\n⚠️  MAPEAMENTO COMPLETO INICIADO (modo headless)")
    print("   Estimativa: ~4.500-10.000 combos, pode levar várias horas")
    print("   Progresso será exibido em tempo real...")
    print("")

    # Determinar número de workers (auto quando <=0)
    workers = int(ns.workers or 0)
    shard_cnt_cli = int(ns.shard_count or 0)
    if shard_cnt_cli == 0 and workers <= 1:
        try:
            import os as _os
            auto = max(2, (_os.cpu_count() or 2))
            # Se o usuário limitou órgãos, não faz sentido exceder
            if LIMIT_ORGAOS:
                auto = min(auto, int(LIMIT_ORGAOS))
            workers = auto
            print(f"[Auto] Workers detectados: {workers} (cpu_count)\n")
        except Exception:
            workers = 0

    # Modo orquestrador: spawn de múltiplos processos workers
    if workers > 1 and shard_cnt_cli == 0:
        print(f"[Orquestrador] Iniciando {workers} workers em paralelo...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shard_paths: list[Path] = []
        procs = []
        import os as _os
        from subprocess import Popen

        this_script = Path(__file__).resolve()
        for i in range(workers):
            out_path = Path(f"artefatos/pairs_eagendas_shard_{i}_of_{workers}_{timestamp}.json")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shard_paths.append(out_path)
            args = [
                sys.executable,
                str(this_script),
                "--optimized",
                "--shard-count", str(workers),
                "--shard-index", str(i),
                "--output-file", str(out_path),
                "--skip-latest",
            ]
            if HEADFUL:
                args.append("--headful")
            if SLOWMO:
                args.extend(["--slowmo", str(SLOWMO)])
            if ns.debug:
                args.append("--debug")
            if LIMIT_ORGAOS:
                args.extend(["--limit-orgaos", str(LIMIT_ORGAOS)])
            if LIMIT_CARGOS_PER_ORGAO:
                args.extend(["--limit-cargos", str(LIMIT_CARGOS_PER_ORGAO)])
            print(f"[Orquestrador] Worker {i+1}/{workers}: salvando em {out_path}")
            # Evitar lock de arquivo de log em Windows: desabilitar file handler nos workers
            env = _os.environ.copy()
            env.setdefault("DOU_DISABLE_FILE_LOG", "1")
            procs.append(Popen(args, env=env))

        # Aguardar todos terminarem
        for i, proc in enumerate(procs, 1):
            code = proc.wait()
            print(f"[Orquestrador] Worker {i}/{workers} finalizado com código {code}")

        # Mesclar resultados (medir tempo)
        print("[Orquestrador] Mesclando artefatos de shards...")
        t0 = time.perf_counter()
        merged = _merge_shard_results(shard_paths)
        t_merge = time.perf_counter() - t0

        # Gravação do combinado e latest em formato identado e UTF-8 correto
        timestamp2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"artefatos/pairs_eagendas_{timestamp2}.json")
        formatted = json.dumps(merged, ensure_ascii=False, indent=2)
        output_file.write_text(formatted, encoding="utf-8")
        print(f"\n✅ Artefato combinado salvo: {output_file.absolute()}")

        latest_file = Path("artefatos/pairs_eagendas_latest.json")
        latest_file.write_text(formatted, encoding="utf-8")
        print(f"✅ Versão 'latest' atualizada: {latest_file.absolute()}")

        t_write = time.perf_counter() - t0 - t_merge
        if ns.debug:
            print(f"[Perf] Merge: {t_merge:0.2f}s | Escrita: {t_write:0.2f}s")

        # Limpar shards individuais para evitar acúmulo de JSONs temporários
        # Limpeza resiliente com retries + fallback por padrão nomeado
        removed = 0
        for sp in shard_paths:
            sp = Path(sp)
            ok = False
            for _ in range(5):
                try:
                    sp.unlink(missing_ok=True)  # type: ignore[arg-type]
                    ok = True
                    break
                except Exception:
                    time.sleep(0.2)
            if ok:
                removed += 1
            else:
                print(f"[Warn] Não foi possível remover shard: {sp}")

        # Fallback: varrer quaisquer shards restantes com o mesmo timestamp/worker pattern
        try:
            pattern = f"pairs_eagendas_shard_*_of_{workers}_{timestamp}.json"
            for extra in Path("artefatos").glob(pattern):
                try:
                    extra.unlink()
                    removed += 1
                except Exception:
                    print(f"[Warn] Não foi possível remover shard (fallback): {extra}")
        except Exception:
            pass

        if removed:
            print(f"🧹 Shards removidos: {removed} arquivo(s)")

        # Estatísticas combinadas
        stats = merged.get("stats", {})
        print("\n" + "=" * 80)
        print("ESTATÍSTICAS FINAIS (COMBINADAS)")
        print("=" * 80)
        print(f"  Total de órgãos processados: {stats.get('total_orgaos', 0)}")
        print(f"  Total de cargos mapeados: {stats.get('total_cargos', 0)}")
        print(f"  Total de agentes públicos: {stats.get('total_agentes', 0)}")

        # Contagem de pares
        total_pares = 0
        for orgao in merged.get("hierarchy", []) or []:
            for cargo in orgao.get("cargos", []) or []:
                total_pares += len(cargo.get("agentes", []) or [])
        print(f"  Total de pares (ÓrgãoxCargoxAgente): {total_pares}")
        return

    print("[1/4] Iniciando navegador...")
    p, browser = launch_browser(headful=HEADFUL, slowmo=SLOWMO)

    try:
        context = new_context(browser)
        # Bloqueio de recursos para acelerar (imagens, fontes, mídia, analytics)
        if not ns.no_block_resources:
            try:
                def _should_block(req_url: str, rtype: str) -> bool:
                    u = req_url.lower()
                    if rtype in ("image", "font", "media", "stylesheet"):
                        return True
                    blocked_hosts = (
                        "google-analytics.com",
                        "googletagmanager.com",
                        "doubleclick.net",
                        "facebook.com",
                        "facebook.net",
                        "hotjar.com",
                        "matomo",
                        "clarity.ms",
                        "cloudflareinsights.com",
                    )
                    return any(h in u for h in blocked_hosts)

                def _route_handler(route, request):  # type: ignore[no-untyped-def]
                    try:
                        if _should_block(request.url, request.resource_type):
                            return route.abort()
                    except Exception:
                        pass
                    return route.continue_()

                context.route("**/*", _route_handler)
                if ns.debug:
                    print("[Perf] Bloqueio de recursos habilitado (imagens, fontes, mídia, analytics)")
            except Exception as _e:
                if ns.debug:
                    print(f"[Perf] Falha ao habilitar bloqueio de recursos: {_e}")
        page = context.new_page()
        # Aumentar timeout padrão para lidar com carregamentos lentos do e-agendas
        page.set_default_timeout(45000)

        print("[2/4] Navegando para e-agendas...")
        url = build_url("eagendas")
        goto(page, url)

        if ns.debug:
            # Diagnóstico rápido de presença de elementos e contagem inicial de opções
            try:
                frame = find_best_frame(page.context)
                dd_ids = {"orgao": "slcOrgs", "cargo": "slcCargos", "agente": "slcOcupantes"}
                for nome, dd_id in dd_ids.items():
                    try:
                        exists = bool(frame.locator(f"#{dd_id}").count())
                        count = selectize_get_options_count(frame, dd_id)
                        print(f"[DEBUG] DD {nome} #{dd_id} | existe={exists} | options={count}")
                    except Exception as _e:
                        print(f"[DEBUG] Falha ao inspecionar DD {nome} #{dd_id}: {_e}")
                # Listar selects/inputs candidatos na frame
                try:
                    info = frame.evaluate(
                        """
                        () => {
                            const els = Array.from(document.querySelectorAll('select, input'));
                            return els.map((el, idx) => ({
                                idx,
                                tag: el.tagName.toLowerCase(),
                                id: el.id || null,
                                name: el.name || null,
                                cls: el.className || null,
                                hasSelectize: !!el.selectize,
                            }));
                        }
                        """
                    ) or []
                    print(f"[DEBUG] Elementos candidatos na frame: {len(info)}")
                    for item in info[:20]:
                        print(f"[DEBUG]  - {item}")
                except Exception as _e:
                    print(f"[DEBUG] Falha ao listar elementos: {_e}")
            except Exception as _e:
                print(f"[DEBUG] Falha no diagnóstico de frame/Selectize: {_e}")

        print("[3/4] Iniciando mapeamento...")
        print("\n" + "-" * 80)

        start_ts = time.perf_counter()

        def _progress(cur: int, total: int, msg: str) -> None:
            try:
                elapsed = time.perf_counter() - start_ts
                # Log simples e compacto por órgão
                print(f"[PROGRESS] {cur}/{total} | {elapsed:0.1f}s | {msg}")
            except Exception:
                pass

        if ns.optimized:
            result = map_eagendas_pairs_opt(
                page=page,
                limit_orgaos=LIMIT_ORGAOS,
                limit_cargos_per_orgao=LIMIT_CARGOS_PER_ORGAO,
                verbose=True,
                timeout_ms=45000,
                progress_callback=_progress if ns.debug else None,
                shard_count=int(ns.shard_count or 1),
                shard_index=int(ns.shard_index or 0),
            )
        else:
            result = map_eagendas_pairs_legacy(
                page=page,
                limit_orgaos=LIMIT_ORGAOS,
                limit_cargos_per_orgao=LIMIT_CARGOS_PER_ORGAO,
                verbose=True,
            )

        print("-" * 80)
        print("\n[4/4] Salvando resultados...")

        # Salvar com timestamp (ou caminho customizado)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(ns.output_file) if ns.output_file else Path(f"artefatos/pairs_eagendas_{timestamp}.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        output_file.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        elapsed_total = time.perf_counter() - start_ts
        print(f"\n✅ Artefato salvo: {output_file.absolute()}")
        print(f"Tempo total: {elapsed_total:0.1f}s")

        # Estatísticas
        print("\n" + "=" * 80)
        print("ESTATÍSTICAS FINAIS")
        print("=" * 80)
        stats = result.get("stats", {})
        print(f"  Total de órgãos processados: {stats.get('total_orgaos', 0)}")
        print(f"  Total de cargos mapeados: {stats.get('total_cargos', 0)}")
        print(f"  Total de agentes públicos: {stats.get('total_agentes', 0)}")

        # Contar pares únicos
        total_pares = 0
        hierarchy = result.get("hierarchy", [])
        for orgao in hierarchy:
            for cargo in orgao.get("cargos", []):
                agentes = cargo.get("agentes", [])
                total_pares += len(agentes)

        print(f"  Total de pares (ÓrgãoxCargoxAgente): {total_pares}")

        # Salvar também versão "latest"
        if not ns.skip_latest:
            latest_file = Path("artefatos/pairs_eagendas_latest.json")
            latest_file.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"\n✅ Versão 'latest' atualizada: {latest_file.absolute()}")

        print("\n" + "=" * 80)
        print("MAPEAMENTO CONCLUÍDO COM SUCESSO!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Mapeamento interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro durante mapeamento: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n[Cleanup] Fechando navegador...")
        with contextlib.suppress(Exception):
            browser.close()
        with contextlib.suppress(Exception):
            p.stop()


if __name__ == "__main__":
    main()
