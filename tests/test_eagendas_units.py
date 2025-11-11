"""
Testes unitários para módulos e-agendas (sem requerer navegador).

Testa:
- Imports
- Funções utilitárias
- Formatação de relatórios
- Validação de estruturas de dados
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Teste 1: Validar imports."""
    print("\n" + "=" * 80)
    print("TESTE 1: Imports")
    print("=" * 80)

    try:
        from dou_snaptrack.cli.plan_live_eagendas_async import build_plan_eagendas_async  # noqa: F401
        from dou_snaptrack.utils.eagendas_calendar import (  # noqa: F401
            click_mostrar_agenda_async,
            collect_events_for_period_async,
            extract_day_events_async,
            format_events_report,
            get_days_with_events_async,
            switch_calendar_view_async,
        )

        print("✅ Todos os imports bem-sucedidos")
        return True
    except Exception as e:
        print(f"❌ Erro ao importar: {e}")
        return False


def test_format_events_report():
    """Teste 2: Formatação de relatório."""
    print("\n" + "=" * 80)
    print("TESTE 2: format_events_report")
    print("=" * 80)

    from dou_snaptrack.utils.eagendas_calendar import format_events_report

    # Caso 1: Eventos válidos
    events = {
        "2025-11-15": [
            {
                "date": "2025-11-15",
                "title": "Reunião com Diretoria",
                "time": "14:00 - 16:00",
                "type": "Reunião",
                "details": "Discussão de projetos",
            },
            {
                "date": "2025-11-15",
                "title": "Audiência Pública",
                "time": "18:00",
                "type": "Audiência",
                "details": "",
            },
        ],
        "2025-11-20": [
            {
                "date": "2025-11-20",
                "title": "Viagem a Brasília",
                "time": "09:00",
                "type": "Viagem",
                "details": "Reunião interministerial",
            }
        ],
    }

    report = format_events_report(events)

    # Validações
    assert "2025-11-15" in report, "Data 15/11 não encontrada"
    assert "2025-11-20" in report, "Data 20/11 não encontrada"
    assert "Reunião com Diretoria" in report, "Título não encontrado"
    assert "14:00 - 16:00" in report, "Horário não encontrado"
    assert "Reunião" in report, "Tipo de evento não encontrado"
    assert "Total: 2 dias" in report, "Estatística incorreta"
    assert "Total de eventos: 3" in report, "Contagem de eventos incorreta"

    print("✅ Formatação OK")
    print(f"\n{report}")

    # Caso 2: Sem eventos
    empty_report = format_events_report({})
    assert "Nenhum compromisso encontrado" in empty_report, "Mensagem de vazio incorreta"

    print("✅ Caso vazio OK")
    return True


def test_data_structures():
    """Teste 3: Estruturas de dados."""
    print("\n" + "=" * 80)
    print("TESTE 3: Estruturas de Dados")
    print("=" * 80)

    # Estrutura de evento esperada
    event = {
        "date": "2025-11-15",
        "title": "Teste",
        "time": "14:00",
        "type": "Reunião",
        "details": "Descrição",
    }

    # Validar campos obrigatórios
    required_fields = ["date", "title", "time", "type", "details"]
    for field in required_fields:
        assert field in event, f"Campo obrigatório '{field}' ausente"

    print("✅ Estrutura de evento válida")

    # Estrutura de dia com eventos
    day_info = {
        "day": 15,
        "date": "2025-11-15",
        "date_obj": date(2025, 11, 15),
        "has_events": True,
        "handle": None,  # Placeholder (seria Locator em runtime)
        "day_link": None,
    }

    required_day_fields = ["day", "date", "date_obj", "has_events"]
    for field in required_day_fields:
        assert field in day_info, f"Campo obrigatório '{field}' ausente"

    print("✅ Estrutura de dia válida")
    return True


def test_filter_logic():
    """Teste 4: Lógica de filtros (importada de plan_live_eagendas_async)."""
    print("\n" + "=" * 80)
    print("TESTE 4: Lógica de Filtros")
    print("=" * 80)

    # Import interno da função de filtro
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from dou_snaptrack.cli.plan_live_eagendas_async import _filter_opts

    # Mock de opções
    opts = [
        {"text": "Ministério da Fazenda", "value": "1"},
        {"text": "Ministério da Saúde", "value": "2"},
        {"text": "Ministério da Educação", "value": "3"},
        {"text": "Agência Espacial Brasileira", "value": "4"},
    ]

    # Teste 1: Sem filtros (retorna todos)
    result = _filter_opts(opts, None, None, None)
    assert len(result) == 4, "Sem filtros deveria retornar todos"
    print("✅ Sem filtros: OK")

    # Teste 2: Filtro por regex
    result = _filter_opts(opts, r"Ministério.*", None, None)
    assert len(result) == 3, "Regex deveria filtrar 3 ministérios"
    print("✅ Filtro regex: OK")

    # Teste 3: Filtro por pick (lista específica)
    result = _filter_opts(opts, None, ["Ministério da Fazenda", "Agência Espacial Brasileira"], None)
    assert len(result) == 2, "Pick deveria retornar exatamente 2"
    print("✅ Filtro pick: OK")

    # Teste 4: Limite
    result = _filter_opts(opts, None, None, 2)
    assert len(result) == 2, "Limite deveria truncar em 2"
    print("✅ Filtro limite: OK")

    # Teste 5: Combinação (regex + limite)
    result = _filter_opts(opts, r"Ministério.*", None, 2)
    assert len(result) == 2, "Combo regex+limite deveria retornar 2"
    print("✅ Filtro combinado: OK")

    return True


def run_all_tests():
    """Executa todos os testes."""
    print("\n" + "=" * 80)
    print("SUITE DE TESTES: E-AGENDAS (Unitários)")
    print("=" * 80)

    tests = [
        ("Imports", test_imports),
        ("Formatação de Relatórios", test_format_events_report),
        ("Estruturas de Dados", test_data_structures),
        ("Lógica de Filtros", test_filter_logic),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ ERRO em {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} testes passaram")

    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        return True
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
