"""
Executor de combos para o e-agendas a partir de um plan JSON.

Fluxo:
- Carrega um plan gerado por plan_live_eagendas.build_plan_eagendas().
- Abre o site do e-agendas.
- Para cada combo: seleciona Órgão → Cargo → Agente Público usando helpers de Selectize.
- Ponto de extensão: após a seleção, executar ação desejada (ex.: clicar em "Pesquisar" e coletar dados).

Obs.: Este é um esqueleto inicial para validarmos a automação de seleção. Ajustes finos
de selectores/labels do e-agendas poderão ser necessários no ambiente real.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from dou_snaptrack.constants import EAGENDAS_SELECTORS
from dou_snaptrack.mappers.eagendas_selectize import (
    find_selectize_by_label,
    get_selectize_options,
    is_selectize_disabled,
    open_selectize_dropdown,
    select_selectize_option,
)
from dou_snaptrack.utils.browser import build_url, goto, launch_browser, new_context


def _load_plan(plan_path: str | Path) -> dict[str, Any]:
    p = Path(plan_path)
    if not p.exists():
        raise FileNotFoundError(f"Plan não encontrado: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _select_by_value_or_text(page, frame, label: str, value: str | None, text: str | None) -> bool:
    """Abre o dropdown associado ao label e seleciona por value (preferido) ou texto.

    Retorna True se conseguiu selecionar, False caso contrário.
    """
    ctrl = find_selectize_by_label(frame, label)
    if not ctrl:
        print(f"[WARN] Controle '{label}' não encontrado")
        return False

    if is_selectize_disabled(ctrl):
        print(f"[WARN] Controle '{label}' está desabilitado")
        return False

    if not open_selectize_dropdown(page, ctrl, wait_ms=1500):
        print(f"[WARN] Não foi possível abrir dropdown '{label}'")
        return False

    opts = get_selectize_options(frame, include_empty=False)
    if not opts:
        print(f"[WARN] Sem opções disponíveis para '{label}'")
        return False

    # Preferência: match por value; fallback por texto
    picked = None
    if value:
        for o in opts:
            if (o.get("value") or "") == value:
                picked = o
                break
    if not picked and text:
        tnorm = (text or "").strip().lower()
        for o in opts:
            ot = (o.get("text") or "").strip().lower()
            if ot == tnorm:
                picked = o
                break

    if not picked and text:
        # fallback: tenta por prefixo de texto
        tnorm = (text or "").strip().lower()
        for o in opts:
            ot = (o.get("text") or "").strip().lower()
            if ot.startswith(tnorm[:10]):
                picked = o
                break

    if not picked:
        print(f"[WARN] Opção não encontrada em '{label}' (value='{value}' text='{text}')")
        return False

    ok = select_selectize_option(page, picked, wait_after_ms=800)
    if not ok:
        print(f"[WARN] Falha ao selecionar '{label}': {text or value}")
        return False
    return True


def _click_search_if_present(page) -> bool:
    """Tenta clicar em um botão de busca/pesquisa (melhor esforço)."""
    texts = EAGENDAS_SELECTORS.get("search_button", []) or []
    for t in texts:
        try:
            btn = page.get_by_role("button", name=t)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_timeout(300)
                return True
        except Exception:
            pass
        try:
            loc = page.get_by_text(t, exact=False)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click()
                page.wait_for_timeout(300)
                return True
        except Exception:
            pass
    return False


def run_from_plan(plan_path: str | Path, headful: bool = False, slowmo: int = 0, max_combos: int | None = None) -> None:
    plan = _load_plan(plan_path)
    combos = plan.get("combos", [])
    if max_combos and max_combos > 0:
        combos = combos[:max_combos]

    print(f"[run-eagendas] Combos para executar: {len(combos)}")

    p, browser = launch_browser(headful=headful, slowmo=slowmo)
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_timeout(45_000)

        url = build_url("eagendas")
        print(f"[run-eagendas] Abrindo: {url}")
        goto(page, url)

        frame = page.main_frame

        for i, combo in enumerate(combos, 1):
            org_v = combo.get("orgao_value")
            org_t = combo.get("orgao_label")
            car_v = combo.get("cargo_value")
            car_t = combo.get("cargo_label")
            ag_v = combo.get("agente_value")
            ag_t = combo.get("agente_label")

            print(f"\n[combo {i}/{len(combos)}] Órgão='{org_t}' Cargo='{car_t}' Agente='{ag_t}'")

            # Selecionar N1: Órgão
            if not _select_by_value_or_text(page, frame, "Órgão ou entidade", org_v, org_t):
                print("[SKIP] Falha em Órgão; seguindo para próximo combo")
                continue

            # Aguardar AJAX do N2
            time.sleep(0.6)

            # Selecionar N2: Cargo
            if not _select_by_value_or_text(page, frame, "Cargo", car_v, car_t):
                print("[SKIP] Falha em Cargo; seguindo para próximo combo")
                continue

            # Aguardar AJAX do N3
            time.sleep(0.5)

            # Selecionar N3: Agente Público Obrigado
            if ag_t or ag_v:
                _select_by_value_or_text(page, frame, "Agente Público Obrigado", ag_v, ag_t)
                time.sleep(0.3)

            # Ação pós-seleção (opcional): tentar clicar em "Pesquisar"
            clicked = _click_search_if_present(page)
            print(f"[run-eagendas] Pesquisar clicado: {clicked}")

            # Ponto de extensão: coletar dados/gerar artefatos aqui
            # TODO: implementar coleta de resultados da página e salvar

            # Pequena pausa entre combos para estabilidade
            time.sleep(0.2)

        print("\n[run-eagendas] Execução concluída.")

    finally:
        import contextlib
        with contextlib.suppress(Exception):
            browser.close()
        with contextlib.suppress(Exception):
            p.stop()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Executa combos do e-agendas a partir de um plan JSON")
    ap.add_argument("--plan", required=True, help="Caminho para o plan JSON (ex.: planos/eagendas_plan_medium.json)")
    ap.add_argument("--headful", action="store_true", help="Mostrar navegador")
    ap.add_argument("--slowmo", type=int, default=0, help="Delay entre ações (ms)")
    ap.add_argument("--max-combos", type=int, default=0, help="Limitar número de combos (0 = todos)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(list(argv or sys.argv[1:]))
    try:
        run_from_plan(
            plan_path=ns.plan,
            headful=bool(ns.headful),
            slowmo=int(ns.slowmo or 0),
            max_combos=(ns.max_combos or None),
        )
        return 0
    except KeyboardInterrupt:
        print("\n[run-eagendas] Interrompido pelo usuário")
        return 1
    except Exception as e:
        print(f"[run-eagendas] Erro: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
