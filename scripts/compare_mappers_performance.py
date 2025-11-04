"""
Script de comparação de performance: mapper original vs otimizado.

Testa com 3 órgãos para validar velocidade.
"""
import sys
import time
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from playwright.sync_api import sync_playwright
from dou_snaptrack.mappers.eagendas_pairs import map_eagendas_pairs
from dou_snaptrack.mappers.eagendas_pairs_fast import map_eagendas_pairs_fast


def run_comparison():
    """Executa ambos mappers e compara performance."""
    
    print("="*80)
    print("TESTE DE PERFORMANCE: E-AGENDAS MAPPER")
    print("="*80)
    print()
    
    with sync_playwright() as p:
        # Iniciar browser
        print("Iniciando browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            ignore_https_errors=True
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        
        # Navegar para e-agendas
        print("Navegando para e-agendas...")
        page.goto("https://eagendas.cgu.gov.br/")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)  # Aguardar carregamento completo
        
        # Teste 1: Mapper ORIGINAL (3 órgãos)
        print("\n" + "-"*80)
        print("TESTE 1: MAPPER ORIGINAL (eagendas_pairs.py)")
        print("-"*80)
        
        start_orig = time.time()
        try:
            result_orig = map_eagendas_pairs(
                page,
                limit_orgaos=3,  # Apenas 3 para teste rápido
                limit_cargos_per_orgao=2,
                verbose=True
            )
            end_orig = time.time()
            time_orig = end_orig - start_orig
            
            print(f"\n✅ ORIGINAL completado em {time_orig:.2f}s")
            print(f"   Órgãos: {len(result_orig.get('hierarchy', []))}")
            print(f"   Cargos: {result_orig['stats']['total_cargos']}")
            print(f"   Agentes: {result_orig['stats']['total_agentes']}")
            
        except Exception as e:
            print(f"\n❌ ORIGINAL falhou: {e}")
            time_orig = None
            result_orig = None
        
        # Recarregar página para reset
        print("\nRecarregando página para teste 2...")
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        
        # Teste 2: Mapper OTIMIZADO (3 órgãos)
        print("\n" + "-"*80)
        print("TESTE 2: MAPPER OTIMIZADO (eagendas_pairs_fast.py)")
        print("-"*80)
        
        start_fast = time.time()
        try:
            result_fast = map_eagendas_pairs_fast(
                page,
                limit_orgaos=3,  # Mesmo limite
                limit_cargos_per_orgao=2,
                verbose=True
            )
            end_fast = time.time()
            time_fast = end_fast - start_fast
            
            print(f"\n✅ OTIMIZADO completado em {time_fast:.2f}s")
            print(f"   Órgãos: {len(result_fast.get('hierarchy', []))}")
            print(f"   Cargos: {result_fast['stats']['total_cargos']}")
            print(f"   Agentes: {result_fast['stats']['total_agentes']}")
            
        except Exception as e:
            print(f"\n❌ OTIMIZADO falhou: {e}")
            import traceback
            traceback.print_exc()
            time_fast = None
            result_fast = None
        
        # Fechar browser
        browser.close()
        
        # Comparação final
        print("\n" + "="*80)
        print("COMPARAÇÃO DE PERFORMANCE")
        print("="*80)
        
        if time_orig and time_fast:
            speedup = time_orig / time_fast
            savings = time_orig - time_fast
            
            print(f"\n📊 Resultados:")
            print(f"   Original:   {time_orig:7.2f}s")
            print(f"   Otimizado:  {time_fast:7.2f}s")
            print(f"   Economia:   {savings:7.2f}s ({savings/time_orig*100:.1f}%)")
            print(f"   Speedup:    {speedup:.2f}x")
            
            # Projeção para 227 órgãos
            print(f"\n🔮 Projeção para 227 órgãos:")
            
            time_per_orgao_orig = time_orig / 3
            time_per_orgao_fast = time_fast / 3
            
            total_orig_proj = time_per_orgao_orig * 227
            total_fast_proj = time_per_orgao_fast * 227
            
            print(f"   Original estimado:   {total_orig_proj/60:.1f} min ({total_orig_proj/3600:.1f}h)")
            print(f"   Otimizado estimado:  {total_fast_proj/60:.1f} min ({total_fast_proj/3600:.1f}h)")
            print(f"   Economia projetada:  {(total_orig_proj - total_fast_proj)/60:.1f} min ({speedup:.1f}x mais rápido)")
            
            # Validar dados idênticos
            if result_orig and result_fast:
                orgaos_match = len(result_orig.get('hierarchy', [])) == len(result_fast.get('hierarchy', []))
                cargos_match = result_orig['stats']['total_cargos'] == result_fast['stats']['total_cargos']
                agentes_match = result_orig['stats']['total_agentes'] == result_fast['stats']['total_agentes']
                
                print(f"\n✔️ Validação de dados:")
                print(f"   Órgãos match:  {'✅' if orgaos_match else '❌'}")
                print(f"   Cargos match:  {'✅' if cargos_match else '❌'}")
                print(f"   Agentes match: {'✅' if agentes_match else '❌'}")
                
                if orgaos_match and cargos_match and agentes_match:
                    print(f"\n✅ SUCESSO: Mapper otimizado retorna dados idênticos e é {speedup:.1f}x mais rápido!")
                else:
                    print(f"\n⚠️ AVISO: Dados divergem, necessário investigar")
        
        elif time_fast:
            print(f"\n⚠️ Original falhou, mas otimizado funcionou em {time_fast:.2f}s")
        elif time_orig:
            print(f"\n⚠️ Otimizado falhou, mas original funcionou em {time_orig:.2f}s")
        else:
            print(f"\n❌ Ambos falharam")
        
        print("\n" + "="*80)


if __name__ == "__main__":
    run_comparison()
