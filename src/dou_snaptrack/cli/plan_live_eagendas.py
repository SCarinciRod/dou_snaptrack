"""
Plan live para e-agendas: gera combinações Órgão → Cargo → Agente Público.

Diferente do DOU (N1→N2), e-agendas tem 3 níveis:
- N1: Órgão (root)
- N2: Cargo (dependente de N1)
- N3: Agente Público (dependente de N2)

O plan_live carrega os pares do artefato JSON gerado por map_eagendas_full.py
e cria combos para processamento em lote.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_eagendas_pairs(pairs_file: str | Path | None = None) -> dict[str, Any]:
    """
    Carrega o artefato de pares Órgão→Cargo→Agente.

    Args:
        pairs_file: Caminho para arquivo JSON. Se None, usa artefatos/pairs_eagendas_latest.json

    Returns:
        Dict com estrutura:
        {
            "stats": {...},
            "hierarchy": [
                {
                    "orgao": "...",
                    "orgao_value": "...",
                    "cargos": [
                        {
                            "cargo": "...",
                            "cargo_value": "...",
                            "agentes": [
                                {
                                    "agente": "...",
                                    "agente_value": "..."
                                },
                                ...
                            ]
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    if pairs_file is None:
        pairs_file = Path(__file__).parent.parent.parent.parent / "artefatos" / "pairs_eagendas_latest.json"

    pairs_path = Path(pairs_file)
    if not pairs_path.exists():
        raise FileNotFoundError(
            f"Artefato de pares não encontrado: {pairs_path}\n"
            f"Execute: python scripts/map_eagendas_full.py"
        )

    data = json.loads(pairs_path.read_text(encoding='utf-8'))
    return data


def build_plan_eagendas(
    pairs_file: str | Path | None = None,
    limit_orgaos: int | None = None,
    limit_cargos_per_orgao: int | None = None,
    limit_agentes_per_cargo: int | None = None,
    select_orgaos: list[str] | None = None,
    verbose: bool = False
) -> dict[str, Any]:
    """
    Gera plan de combos para e-agendas a partir do artefato de pares.

    Args:
        pairs_file: Caminho para artefato JSON (None = latest)
        limit_orgaos: Limite de órgãos a processar (None = todos)
        limit_cargos_per_orgao: Limite de cargos por órgão (None = todos)
        limit_agentes_per_cargo: Limite de agentes por cargo (None = todos)
        select_orgaos: Lista de valores de órgãos específicos (None = todos)
        verbose: Se True, imprime estatísticas

    Returns:
        Dict com:
        {
            "source": "e-agendas",
            "pairs_file": "...",
            "filters": {...},
            "combos": [
                {
                    "orgao_value": "...",
                    "orgao_label": "...",
                    "cargo_value": "...",
                    "cargo_label": "...",
                    "agente_value": "...",
                    "agente_label": "..."
                },
                ...
            ],
            "stats": {
                "total_orgaos": X,
                "total_cargos": Y,
                "total_agentes": Z,
                "total_combos": Z  # mesmo que agentes
            }
        }
    """
    if verbose:
        print(f"[plan-eagendas] Carregando pares: {pairs_file or 'latest'}")

    data = load_eagendas_pairs(pairs_file)
    hierarchy = data.get("hierarchy", [])

    # Filtros
    if select_orgaos:
        hierarchy = [o for o in hierarchy if o.get("orgao_value") in select_orgaos]

    if limit_orgaos:
        hierarchy = hierarchy[:limit_orgaos]

    combos: list[dict[str, Any]] = []
    stats_orgaos = 0
    stats_cargos = 0
    stats_agentes = 0

    for orgao_data in hierarchy:
        orgao_label = orgao_data.get("orgao", "")
        orgao_value = orgao_data.get("orgao_value", "")
        cargos = orgao_data.get("cargos", [])

        if limit_cargos_per_orgao:
            cargos = cargos[:limit_cargos_per_orgao]

        stats_orgaos += 1

        for cargo_data in cargos:
            cargo_label = cargo_data.get("cargo", "")
            cargo_value = cargo_data.get("cargo_value", "")
            agentes = cargo_data.get("agentes", [])

            if limit_agentes_per_cargo:
                agentes = agentes[:limit_agentes_per_cargo]

            stats_cargos += 1

            for agente_data in agentes:
                agente_label = agente_data.get("agente", "")
                agente_value = agente_data.get("agente_value", "")

                combos.append({
                    "orgao_value": orgao_value,
                    "orgao_label": orgao_label,
                    "cargo_value": cargo_value,
                    "cargo_label": cargo_label,
                    "agente_value": agente_value,
                    "agente_label": agente_label,
                })
                stats_agentes += 1

    plan = {
        "source": "e-agendas",
        "pairs_file": str(pairs_file) if pairs_file else "pairs_eagendas_latest.json",
        "filters": {
            "limit_orgaos": limit_orgaos,
            "limit_cargos_per_orgao": limit_cargos_per_orgao,
            "limit_agentes_per_cargo": limit_agentes_per_cargo,
            "select_orgaos": select_orgaos,
        },
        "combos": combos,
        "stats": {
            "total_orgaos": stats_orgaos,
            "total_cargos": stats_cargos,
            "total_agentes": stats_agentes,
            "total_combos": len(combos),
        }
    }

    if verbose:
        print("[plan-eagendas] Estatísticas:")
        print(f"  Órgãos: {stats_orgaos}")
        print(f"  Cargos: {stats_cargos}")
        print(f"  Agentes: {stats_agentes}")
        print(f"  Total de combos: {len(combos)}")

    return plan


def save_plan_eagendas(
    plan: dict[str, Any],
    output_file: str | Path,
    verbose: bool = False
) -> None:
    """
    Salva plan de combos em arquivo JSON.

    Args:
        plan: Dict retornado por build_plan_eagendas()
        output_file: Caminho para salvar JSON
        verbose: Se True, imprime confirmação
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    if verbose:
        print(f"[plan-eagendas] Plan salvo: {output_path.absolute()}")


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    import sys

    # Exemplo 1: Plan completo (todos os pares)
    print("=" * 80)
    print("EXEMPLO 1: Plan completo")
    print("=" * 80)

    try:
        plan_full = build_plan_eagendas(verbose=True)
        save_plan_eagendas(
            plan_full,
            "planos/eagendas_plan_full.json",
            verbose=True
        )
        print("\n✅ Plan completo gerado!")
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\nExecute primeiro:")
        print("  python scripts/map_eagendas_full.py")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("EXEMPLO 2: Plan com limites (teste)")
    print("=" * 80)

    plan_test = build_plan_eagendas(
        limit_orgaos=2,
        limit_cargos_per_orgao=3,
        limit_agentes_per_cargo=2,
        verbose=True
    )
    save_plan_eagendas(
        plan_test,
        "planos/eagendas_plan_test.json",
        verbose=True
    )
    print("\n✅ Plan de teste gerado!")

    print("\n" + "=" * 80)
    print("EXEMPLO 3: Plan para órgãos específicos")
    print("=" * 80)

    # Obter primeiro órgão do artefato para exemplo
    data = load_eagendas_pairs()
    if data["hierarchy"]:
        first_orgao_value = data["hierarchy"][0].get("orgao_value")

        plan_specific = build_plan_eagendas(
            select_orgaos=[first_orgao_value],
            verbose=True
        )
        save_plan_eagendas(
            plan_specific,
            "planos/eagendas_plan_specific.json",
            verbose=True
        )
        print("\n✅ Plan específico gerado!")

    print("\n" + "=" * 80)
    print("TODOS OS PLANS GERADOS COM SUCESSO!")
    print("=" * 80)
