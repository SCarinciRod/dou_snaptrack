"""
Script de teste COMPLETO para e-agendas: seleção + calendário + extração.

Fluxo:
1. Navega para e-agendas.cgu.gov.br
2. Seleciona Órgão → Cargo → Agente Público (usando Selectize)
3. Clica em "Mostrar agenda"
4. Navega pelo calendário detectando dias com eventos
5. Extrai compromissos de cada dia
6. Gera relatório consolidado

TESTE: Usa limites pequenos para validação rápida
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from playwright.async_api import async_playwright

from dou_snaptrack.constants import EAGENDAS_URL
from dou_snaptrack.utils.eagendas_calendar import (
    click_mostrar_agenda_async,
    collect_events_for_period_async,
    format_events_report,
)


async def test_eagendas_full_flow():
    """Teste completo do fluxo e-agendas."""
    print("=" * 80)
    print("TESTE COMPLETO: E-AGENDAS (Seleção + Calendário + Extração)")
    print("=" * 80)

    async with async_playwright() as p:
        # Launch browser
        print("\n1️⃣  Lançando navegador...")
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,  # Headful para visualização
            slow_mo=500,     # Slow motion
        )
        context = await browser.new_context(ignore_https_errors=True)
        context.set_default_timeout(90_000)
        page = await context.new_page()

        try:
            # Navegar para e-agendas
            print(f"\n2️⃣  Navegando para {EAGENDAS_URL}")
            await page.goto(EAGENDAS_URL, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(3000)

            print("\n3️⃣  Selecionando filtros (Órgão → Cargo → Agente)...")
            print("   ⚠️  NOTA: Implementação de seleção Selectize será adicionada")
            print("   Por ora, aguarde interação manual ou use URL pré-filtrada\n")

            # OPÇÃO 1: Usar URL já filtrada para teste rápido
            # Descomentar para pular seleção manual:
            test_url = (
                "https://eagendas.cgu.gov.br/?"
                "_token=GOc3mMDrPZ8yi1hte2pfwVXBZLVMgXIzGVqdQRJM"
                "&filtro_orgaos_ativos=on"
                "&filtro_orgao=1163"
                "&filtro_cargos_ativos=on"
                "&filtro_cargo=DIRETOR+DE+GOVERNAN%C3%87A+DO+SETOR+ESPACIAL+%28DGSE%29"
                "&filtro_apos_ativos=on"
                "&filtro_servidor=16323"
                "&cargo_confianca_id="
                "&is_cargo_vago=false#divcalendar"
            )
            print("   INFO: Usando URL pré-filtrada para teste...")
            await page.goto(test_url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(3000)

            # Verificar se calendário já apareceu (URL pode carregar direto)
            calendar_visible = await page.locator("#divcalendar, .fc-view-container").first.count() > 0

            if not calendar_visible:
                # Clicar em "Mostrar agenda"
                print("\n4️⃣  Clicando em 'Mostrar agenda'...")
                ok = await click_mostrar_agenda_async(page, wait_calendar_ms=5000)

                if not ok:
                    print("❌ Falha ao carregar calendário")
                    return False
            else:
                print("\n4️⃣  ✅ Calendário já visível (URL pré-carregada)")

            # Definir período de extração
            # Usar mês atual para teste
            today = date.today()
            start_date = today.replace(day=1)  # Primeiro dia do mês
            end_date = today + timedelta(days=30)  # Próximos 30 dias

            print(f"\n5️⃣  Coletando eventos do período: {start_date} → {end_date}")

            # Coletar eventos
            events_by_day = await collect_events_for_period_async(
                page,
                start_date=start_date,
                end_date=end_date,
                return_to_month_view=True
            )

            # Gerar relatório
            print("\n6️⃣  Gerando relatório...")
            report = format_events_report(events_by_day)
            print("\n" + report)

            # Salvar JSON
            import json
            output_file = Path("resultados") / f"eagendas_eventos_{start_date}_{end_date}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            output_data = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "stats": {
                    "total_days": len(events_by_day),
                    "total_events": sum(len(e) for e in events_by_day.values()),
                },
                "events": events_by_day,
            }

            output_file.write_text(
                json.dumps(output_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            print(f"\n💾 Resultado salvo em: {output_file}")

            # Aguardar para visualização
            print("\n⏸️  Aguardando 10 segundos para visualização...")
            await page.wait_for_timeout(10_000)

            print("\n✅ TESTE CONCLUÍDO COM SUCESSO!")
            return True

        except Exception as e:
            print(f"\n❌ Erro durante teste: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await browser.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("ATENÇÃO: Este teste usa navegador headful (visível)")
    print("Certifique-se de ter Chrome/Edge instalado")
    print("=" * 80 + "\n")

    success = asyncio.run(test_eagendas_full_flow())
    sys.exit(0 if success else 1)
