"""
Script de teste para plan_live_eagendas_async.

Testa geração de combos navegando no site e-agendas com limites restritos.
"""
from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dou_snaptrack.cli.plan_live_eagendas_async import build_plan_eagendas_sync_wrapper


def test_eagendas_async_smoke():
    """Teste smoke: gerar plan com 2 órgãos, 2 cargos, 2 agentes."""
    print("=" * 80)
    print("TESTE: plan_live_eagendas_async (smoke)")
    print("=" * 80)

    args = Namespace(
        headful=True,  # Mostrar navegador para debug
        slowmo=500,    # Slow motion para visualização
        limit1=2,      # 2 órgãos
        limit2=2,      # 2 cargos por órgão
        limit3=2,      # 2 agentes por cargo
        select1=None,
        pick1=None,
        select2=None,
        pick2=None,
        select3=None,
        pick3=None,
        plan_out="planos/eagendas_plan_test_async.json",
        plan_verbose=True,
    )

    try:
        plan = build_plan_eagendas_sync_wrapper(args)

        print("\n" + "=" * 80)
        print("RESULTADO DO TESTE")
        print("=" * 80)
        print("✅ Plan gerado com sucesso!")
        print("\nEstatísticas:")
        print(f"  Órgãos: {plan['stats']['total_orgaos']}")
        print(f"  Cargos: {plan['stats']['total_cargos']}")
        print(f"  Agentes: {plan['stats']['total_agentes']}")
        print(f"  Total combos: {plan['stats']['total_combos']}")

        print("\n📄 Plan salvo em: planos/eagendas_plan_test_async.json")

        # Mostrar primeiros 3 combos
        print("\n🔍 Primeiros 3 combos:")
        for i, combo in enumerate(plan["combos"][:3], 1):
            print(f"\n  Combo {i}:")
            print(f"    Órgão: {combo['orgao_label']}")
            print(f"    Cargo: {combo['cargo_label']}")
            print(f"    Agente: {combo['agente_label']}")

        return True

    except Exception as e:
        print(f"\n❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_eagendas_async_smoke()
    sys.exit(0 if success else 1)
