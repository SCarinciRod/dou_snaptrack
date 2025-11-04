"""
Mapeamento COMPLETO de pares Órgão → Cargo → Agente Público do e-agendas.
Gera artefato JSON confiável para uso em produção.
"""
from __future__ import annotations
import sys
import json
import io
from pathlib import Path
from datetime import datetime

# Forçar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dou_snaptrack.utils.browser import launch_browser, new_context, goto, build_url
from dou_snaptrack.mappers.eagendas_pairs import map_eagendas_pairs


def main():
    print("=" * 80)
    print("MAPEAMENTO COMPLETO E-AGENDAS")
    print("=" * 80)
    print(f"\nData/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Parâmetros
    HEADFUL = False  # Navegador OCULTO para performance
    SLOWMO = 0       # Sem slowmo para máxima velocidade
    
    # Limites para mapeamento completo
    LIMIT_ORGAOS = None  # None = todos (227 órgãos)
    LIMIT_CARGOS_PER_ORGAO = None  # None = todos
    
    print(f"\nParâmetros:")
    print(f"  Navegador visível: {HEADFUL}")
    print(f"  Slowmo: {SLOWMO}ms")
    print(f"  Limite órgãos: {LIMIT_ORGAOS or 'TODOS'}")
    print(f"  Limite cargos/órgão: {LIMIT_CARGOS_PER_ORGAO or 'TODOS'}")
    
    print("\n⚠️  MAPEAMENTO COMPLETO INICIADO (modo headless)")
    print("   Estimativa: ~4.500-10.000 combos, pode levar várias horas")
    print("   Progresso será exibido em tempo real...")
    print("")
    
    print("[1/4] Iniciando navegador...")
    p, browser = launch_browser(headful=HEADFUL, slowmo=SLOWMO)
    
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_timeout(5000)  # ⚡ REDUZIDO: 5s (vs 60s default)
        
        print("[2/4] Navegando para e-agendas...")
        url = build_url('eagendas')
        goto(page, url)
        
        print("[3/4] Iniciando mapeamento...")
        print("\n" + "-" * 80)
        
        result = map_eagendas_pairs(
            page=page,
            limit_orgaos=LIMIT_ORGAOS,
            limit_cargos_per_orgao=LIMIT_CARGOS_PER_ORGAO,
            verbose=True
        )
        
        print("-" * 80)
        print("\n[4/4] Salvando resultados...")
        
        # Salvar com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"artefatos/pairs_eagendas_{timestamp}.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        output_file.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        print(f"\n✅ Artefato salvo: {output_file.absolute()}")
        
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
        
        print(f"  Total de pares (Órgão×Cargo×Agente): {total_pares}")
        
        # Salvar também versão "latest"
        latest_file = Path("artefatos/pairs_eagendas_latest.json")
        latest_file.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding='utf-8'
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
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


if __name__ == '__main__':
    main()
