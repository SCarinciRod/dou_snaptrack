"""
Versão ASYNC do plan_live_eagendas para geração interativa via Streamlit.

Diferente da versão sync (que carrega de JSON pré-gerado), esta versão:
- Navega no site e-agendas usando Playwright async
- Detecta e interage com dropdowns Selectize.js (N1: Órgão → N2: Cargo → N3: Agente)
- Gera combos N1→N2→N3 sob demanda
- Suporta filtros e limites para controle de escopo

ARQUITETURA:
- 3 níveis hierárquicos: Órgão (N1) → Cargo (N2) → Agente Público (N3)
- Cada nível depende da seleção do anterior
- Selectize.js requer estratégias específicas de abertura/leitura/seleção
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

# ============================================================================
# HELPERS ASYNC PARA SELECTIZE.JS
# ============================================================================


async def _find_selectize_by_label_async(frame, label_text: str) -> dict[str, Any] | None:
    """Versão async de find_selectize_by_label."""
    try:
        label_loc = frame.locator(f'label:has-text("{label_text}")').first
        if await label_loc.count() == 0:
            return None

        # Buscar div.selectize-control associado
        selectize = frame.locator(f'label:has-text("{label_text}")').first.locator(
            'xpath=following::div[contains(@class, "selectize-control")][1]'
        )

        if await selectize.count() == 0:
            parent = label_loc.locator("xpath=ancestor::div[1]")
            selectize = parent.locator(".selectize-control").first

        if await selectize.count() > 0:
            bbox = None
            try:
                bbox = await selectize.bounding_box()
            except Exception:
                bbox = None

            return {
                "label": label_text,
                "selector": selectize,
                "input": selectize.locator(".selectize-input").first,
                "bbox": bbox,
            }
        return None
    except Exception:
        return None


async def _is_selectize_disabled_async(selectize_control: dict) -> bool:
    """Verifica se controle Selectize está desabilitado (async)."""
    try:
        selector = selectize_control["selector"]
        class_attr = await selector.get_attribute("class") or ""
        if "disabled" in class_attr or "locked" in class_attr:
            return True

        with contextlib.suppress(Exception):
            aria_dis = await selector.get_attribute("aria-disabled")
            if aria_dis and aria_dis.lower() in {"true", "1"}:
                return True

        inp = selectize_control.get("input")
        if inp and await inp.count() > 0:
            with contextlib.suppress(Exception):
                icls = await inp.get_attribute("class") or ""
                if "disabled" in icls:
                    return True

        return False
    except Exception:
        return False


async def _open_selectize_dropdown_async(page, selectize_control: dict, wait_ms: int = 1500) -> bool:
    """Abre dropdown Selectize usando focus + ArrowDown (async)."""
    try:
        inp = selectize_control.get("input")
        if not inp or await inp.count() == 0:
            return False

        # ESTRATÉGIA CORRETA: Focus + ArrowDown (funciona melhor que click)
        await inp.focus()
        await page.keyboard.press("ArrowDown")
        
        # Espera condicional: aguardar dropdown ficar visível
        try:
            await page.wait_for_function(
                "() => { const dd = document.querySelector('.selectize-dropdown'); return dd && dd.offsetParent !== null; }",
                timeout=wait_ms
            )
            return True
        except Exception:
            pass

        # Verificar se dropdown apareceu
        dropdown = page.locator(".selectize-dropdown").first
        if await dropdown.count() > 0 and await dropdown.is_visible():
            return True

        # Fallback: tentar click simples
        with contextlib.suppress(Exception):
            await inp.click(timeout=3000, force=True)
            try:
                await page.wait_for_function(
                    "() => { const dd = document.querySelector('.selectize-dropdown'); return dd && dd.offsetParent !== null; }",
                    timeout=wait_ms
                )
                return True
            except Exception:
                pass

        # Fallback 2: JavaScript API
        with contextlib.suppress(Exception):
            await inp.evaluate("""
                (element) => {
                    if (element.selectize) {
                        element.selectize.open();
                    }
                }
            """)
            try:
                await page.wait_for_function(
                    "() => { const dd = document.querySelector('.selectize-dropdown'); return dd && dd.offsetParent !== null; }",
                    timeout=wait_ms
                )
                return True
            except Exception:
                pass

        return False

    except Exception:
        return False


async def _get_selectize_options_async(frame, include_empty: bool = False) -> list[dict[str, Any]]:
    """Lê opções do dropdown Selectize aberto (async)."""
    DEFAULT_EXCLUDE = [
        "selecione",
        "selecione uma opção",
        "selecione um item",
        "selecione o órgão",
        "selecione o cargo",
        "selecione o agente",
        "todos os ocupantes",
    ]

    opts: list[dict[str, Any]] = []
    try:
        # Buscar dropdown (remover .single para aceitar qualquer tipo)
        dropdown = frame.page.locator(".selectize-dropdown").first
        if await dropdown.count() == 0 or not await dropdown.is_visible():
            return []

        # Scroll para carregar todas as opções (caso virtualizado)
        for _ in range(30):
            with contextlib.suppress(Exception):
                await dropdown.evaluate("(el)=>{el.scrollTop=el.scrollHeight}")
            await frame.page.wait_for_timeout(50)

        # Ler opções - tentar múltiplos seletores
        items_found = False
        items = None

        for selector in [".selectize-dropdown-content .option", ".option", "div[data-value]"]:
            items = dropdown.locator(selector)
            cnt = await items.count()
            if cnt > 0:
                items_found = True
                break

        if not items_found or items is None:
            return []

        cnt = await items.count()

        for i in range(cnt):
            item = items.nth(i)
            try:
                if not await item.is_visible():
                    continue

                text = (await item.text_content() or "").strip()
                value = await item.get_attribute("data-value") or text

                # Filtrar placeholders genéricos
                tnorm = text.lower()
                if not include_empty and any(tnorm == p or tnorm.startswith(p + " ") for p in DEFAULT_EXCLUDE):
                    continue

                opts.append(
                    {
                        "text": text,
                        "value": value,
                        "index": i,
                        "handle": item,
                    }
                )
            except Exception:
                pass

        return opts

    except Exception:
        return []


async def _select_selectize_option_async(page, option: dict[str, Any], wait_after_ms: int = 800) -> bool:
    """Seleciona opção no dropdown Selectize (async)."""
    try:
        h = option.get("handle")
        if not h:
            return False

        await h.click(timeout=3000)
        
        # Espera condicional: aguardar dropdown fechar (indica seleção completa)
        try:
            await page.wait_for_function(
                "() => { const dd = document.querySelector('.selectize-dropdown'); return !dd || dd.offsetParent === null; }",
                timeout=wait_after_ms
            )
        except Exception:
            pass  # Timeout ok, prosseguir

        # Aguardar AJAX
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)

        return True
    except Exception:
        return False


async def _read_selectize_options_for_label_async(frame, label: str) -> list[dict[str, Any]]:
    """Wrapper: encontra controle, abre dropdown, lê opções (async)."""
    ctrl = await _find_selectize_by_label_async(frame, label)
    if not ctrl:
        return []

    if await _is_selectize_disabled_async(ctrl):
        return []

    if not await _open_selectize_dropdown_async(frame.page, ctrl, wait_ms=1500):
        return []

    opts = await _get_selectize_options_async(frame, include_empty=False)

    # Fechar dropdown
    with contextlib.suppress(Exception):
        await frame.page.keyboard.press("Escape")
        await frame.page.wait_for_timeout(200)

    return opts


async def _select_by_label_and_text_async(frame, label: str, text: str) -> bool:
    """Seleciona opção específica em dropdown Selectize (async)."""
    ctrl = await _find_selectize_by_label_async(frame, label)
    if not ctrl:
        return False

    if await _is_selectize_disabled_async(ctrl):
        return False

    if not await _open_selectize_dropdown_async(frame.page, ctrl, wait_ms=1500):
        return False

    opts = await _get_selectize_options_async(frame, include_empty=False)
    picked = None
    tnorm = text.lower().strip()

    # Match exato
    for o in opts:
        if o["text"].lower().strip() == tnorm:
            picked = o
            break

    # Match por prefixo (fallback)
    if not picked and len(tnorm) >= 5:
        for o in opts:
            if o["text"].lower().strip().startswith(tnorm[:5]):
                picked = o
                break

    if not picked:
        # Fechar dropdown
        with contextlib.suppress(Exception):
            await frame.page.keyboard.press("Escape")
        return False

    return await _select_selectize_option_async(frame.page, picked, wait_after_ms=800)


# ============================================================================
# FILTRO DE OPÇÕES (reutilizar lógica do plan_live)
# ============================================================================


def _filter_opts(
    opts: list[dict[str, Any]], select_pattern: str | None, pick_values: list[str] | None, limit: int | None
) -> list[dict[str, Any]]:
    """Filtra opções por padrão regex, lista de valores ou limite."""
    import re

    if not opts:
        return []

    # Filtro por regex (select_pattern)
    if select_pattern:
        try:
            pat = re.compile(select_pattern, re.IGNORECASE)
            opts = [o for o in opts if pat.search(o.get("text", ""))]
        except Exception:
            pass

    # Filtro por valores específicos (pick_values)
    if pick_values:
        pick_set = {v.strip().lower() for v in pick_values}
        opts = [o for o in opts if o.get("text", "").strip().lower() in pick_set]

    # Limite
    if limit and limit > 0:
        opts = opts[:limit]

    return opts


# ============================================================================
# BUILD_PLAN_EAGENDAS_ASYNC
# ============================================================================


async def build_plan_eagendas_async(p, args) -> dict[str, Any]:
    """
    Gera plan de combos para e-agendas navegando no site (async).

    NOVA VERSÃO: Usa JavaScript API do Selectize ao invés de interação DOM.
    Isso é muito mais confiável e rápido.

    Args:
        p: playwright async instance
        args: Namespace com:
            - headful: bool (mostrar navegador)
            - slowmo: int (delay entre ações em ms)
            - select1/pick1/limit1: filtros para N1 (Órgão)
            - select2/pick2/limit2: filtros para N2 (Cargo)
            - select3/pick3/limit3: filtros para N3 (Agente)
            - plan_out: str (caminho para salvar JSON)
            - plan_verbose: bool (logs detalhados)

    Returns:
        Dict com:
        {
            "source": "e-agendas",
            "url": "https://eagendas.cgu.gov.br/",
            "combos": [...],
            "stats": {...}
        }
    """
    v = bool(getattr(args, "plan_verbose", False))
    headful = bool(getattr(args, "headful", False))
    slowmo = int(getattr(args, "slowmo", 0) or 0)

    combos: list[dict[str, Any]] = []
    stats = {"total_orgaos": 0, "total_cargos": 0, "total_agentes": 0}

    # IDs FIXOS dos dropdowns e-agendas
    DD_ORGAO_ID = "filtro_orgao_entidade"
    DD_CARGO_ID = "filtro_cargo"
    DD_AGENTE_ID = "filtro_servidor"

    # NOTA: E-Agendas detecta headless e bloqueia. Sempre usar headless=False + --start-minimized
    LAUNCH_ARGS = ['--start-minimized', '--disable-blink-features=AutomationControlled', '--ignore-certificate-errors']
    # Se headful explícito, não minimizar
    if headful:
        LAUNCH_ARGS = ['--disable-blink-features=AutomationControlled', '--ignore-certificate-errors']

    # Launch browser
    browser = None
    try:
        browser = await p.chromium.launch(channel="chrome", headless=False, slow_mo=slowmo, args=LAUNCH_ARGS)
    except Exception:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=False, slow_mo=slowmo, args=LAUNCH_ARGS)
        except Exception:
            exe = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME_PATH")
            if not exe:
                for c in (
                    r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                    r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                    r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                ):
                    if Path(c).exists():
                        exe = c
                        break
            if exe and Path(exe).exists():
                browser = await p.chromium.launch(executable_path=exe, headless=False, slow_mo=slowmo, args=LAUNCH_ARGS)

    if not browser:
        msg = (
            "Nenhum browser disponível. Tentativas:\n"
            "  1. channel='chrome' falhou\n"
            "  2. channel='msedge' falhou\n"
            "  3. Não encontrou Chrome/Edge em caminhos padrão\n"
            "Certifique-se de ter Chrome ou Edge instalado."
        )
        raise RuntimeError(msg)

    context = await browser.new_context(ignore_https_errors=True)
    context.set_default_timeout(90_000)
    page = await context.new_page()

    from dou_snaptrack.constants import EAGENDAS_URL

    url = EAGENDAS_URL
    await page.goto(url, wait_until="commit", timeout=60_000)

    # Aguardar AngularJS e Selectize inicializar via espera condicional
    angular_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => document.querySelector('[ng-app]') !== null",
            timeout=10_000
        )
        angular_ready = True

    # Aguardar Selectize do órgão estar populado
    selectize_ready = False
    with contextlib.suppress(Exception):
        await page.wait_for_function(
            "() => { const el = document.getElementById('filtro_orgao_entidade'); return el?.selectize && Object.keys(el.selectize.options || {}).length > 5; }",
            timeout=15_000
        )
        selectize_ready = True

    # Fallback se esperas condicionais falharem (reduzido: condicionais já tentaram)
    if not angular_ready or not selectize_ready:
        await page.wait_for_timeout(1000)

    frame = page.main_frame

    if v:
        print(f"[plan-eagendas-async] URL: {url}")
        print("[plan-eagendas-async] Detectando dropdowns...")

    # Helper async para obter opções via JavaScript API
    async def get_selectize_options_js(element_id: str) -> list[dict[str, Any]]:
        """Obter opções do Selectize via JavaScript API."""
        try:
            opts = await frame.evaluate(
                """
                (id) => {
                    const el = document.getElementById(id);
                    if (!el || !el.selectize) return [];

                    const s = el.selectize;
                    const out = [];

                    if (s.options) {
                        for (const [val, raw] of Object.entries(s.options)) {
                            const v = String(val ?? '');
                            const t = raw?.text || raw?.label || raw?.nome || raw?.name || v;
                            out.push({ value: v, text: String(t) });
                        }
                    }

                    return out;
                }
                """,
                element_id,
            )
            return opts or []
        except Exception:
            return []

    # Helper async para setar valor via JavaScript API
    async def set_selectize_value_js(element_id: str, value: str) -> bool:
        """Setar valor no Selectize via JavaScript API."""
        try:
            success = await frame.evaluate(
                """
                (args) => {
                    const { id, value } = args;
                    const el = document.getElementById(id);
                    if (!el || !el.selectize) return false;

                    el.selectize.setValue(String(value), false);

                    // Disparar eventos
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('input', { bubbles: true }));

                    return true;
                }
                """,
                {"id": element_id, "value": value},
            )
            return bool(success)
        except Exception:
            return False

    # ========================================================================
    # NÍVEL 1: ÓRGÃOS
    # ========================================================================
    opts_orgao = await get_selectize_options_js(DD_ORGAO_ID)

    # Filtrar placeholders
    opts_orgao = [o for o in opts_orgao if o.get("text") and "selecione" not in o["text"].lower()]

    opts_orgao = _filter_opts(
        opts_orgao, getattr(args, "select1", None), getattr(args, "pick1", None), getattr(args, "limit1", None)
    )

    if v:
        print(f"[plan-eagendas-async] Órgãos válidos: {len(opts_orgao)}")

    stats["total_orgaos"] = len(opts_orgao)

    # Iterar N1 (Órgãos)
    for org in opts_orgao:
        org_text = org["text"]
        org_value = org.get("value", org_text)

        if v:
            print(f"\n[plan-eagendas-async] Processando: {org_text}")

        # Selecionar N1 via JavaScript API
        success = await set_selectize_value_js(DD_ORGAO_ID, org_value)
        if not success:
            if v:
                print("[plan-eagendas-async]   ⚠️  Falha ao selecionar órgão")
            continue

        # Aguardar N2 (Cargo) repopular via espera condicional
        cargo_ready = False
        with contextlib.suppress(Exception):
            await page.wait_for_function(
                f"() => {{ const el = document.getElementById('{DD_CARGO_ID}'); return el?.selectize && Object.keys(el.selectize.options || {{}}).length > 0; }}",
                timeout=10_000
            )
            cargo_ready = True

        # Fallback se espera condicional falhar (reduzido: condicional já tentou 10s)
        if not cargo_ready:
            await page.wait_for_timeout(500)

        # ====================================================================
        # NÍVEL 2: CARGOS
        # ====================================================================
        opts_cargo = await get_selectize_options_js(DD_CARGO_ID)

        # Filtrar placeholders
        opts_cargo = [o for o in opts_cargo if o.get("text") and "selecione" not in o["text"].lower()]

        opts_cargo = _filter_opts(
            opts_cargo, getattr(args, "select2", None), getattr(args, "pick2", None), getattr(args, "limit2", None)
        )

        if v:
            print(f"[plan-eagendas-async]   Cargos: {len(opts_cargo)}")

        stats["total_cargos"] += len(opts_cargo)

        if not opts_cargo:
            # Sem cargos: criar combo só com órgão
            combos.append(
                {
                    "orgao_label": org_text,
                    "orgao_value": org_value,
                    "cargo_label": "Todos",
                    "cargo_value": "Todos",
                    "agente_label": "Todos",
                    "agente_value": "Todos",
                }
            )
            continue

        # Iterar N2 (Cargos)
        for cargo in opts_cargo:
            cargo_text = cargo["text"]
            cargo_value = cargo.get("value", cargo_text)

            # Selecionar N2 via JavaScript API
            success = await set_selectize_value_js(DD_CARGO_ID, cargo_value)
            if not success:
                if v:
                    print(f"[plan-eagendas-async]     ⚠️  Falha ao selecionar cargo: {cargo_text}")
                continue

            # Aguardar N3 (Agente) repopular via espera condicional
            agente_ready = False
            with contextlib.suppress(Exception):
                await page.wait_for_function(
                    f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return el?.selectize && Object.keys(el.selectize.options || {{}}).length > 0; }}",
                    timeout=8_000
                )
                agente_ready = True

            # Fallback se espera condicional falhar (reduzido: condicional já tentou 8s)
            if not agente_ready:
                await page.wait_for_timeout(300)

            # ================================================================
            # NÍVEL 3: AGENTES
            # ================================================================
            opts_agente = await get_selectize_options_js(DD_AGENTE_ID)

            # Filtrar placeholders E "Todos os ocupantes"
            opts_agente = [
                o
                for o in opts_agente
                if o.get("text")
                and "selecione" not in o["text"].lower()
                and "todos os ocupantes" not in o["text"].lower()
            ]

            opts_agente = _filter_opts(
                opts_agente, getattr(args, "select3", None), getattr(args, "pick3", None), getattr(args, "limit3", None)
            )

            if v:
                print(f"[plan-eagendas-async]     Agentes: {len(opts_agente)}")

            stats["total_agentes"] += len(opts_agente)

            if not opts_agente:
                # Sem agentes: criar combo só com órgão+cargo
                combos.append(
                    {
                        "orgao_label": org_text,
                        "orgao_value": org_value,
                        "cargo_label": cargo_text,
                        "cargo_value": cargo_value,
                        "agente_label": "Todos",
                        "agente_value": "Todos",
                    }
                )
                continue

            # Criar combo para cada agente
            for agente in opts_agente:
                agente_text = agente["text"]
                agente_value = agente.get("value", agente_text)

                combos.append(
                    {
                        "orgao_label": org_text,
                        "orgao_value": org_value,
                        "cargo_label": cargo_text,
                        "cargo_value": cargo_value,
                        "agente_label": agente_text,
                        "agente_value": agente_value,
                    }
                )

            # Reset N2 para próximo cargo (selecionar órgão novamente)
            await set_selectize_value_js(DD_ORGAO_ID, org_value)
            # Pequena pausa para estabilizar antes do próximo cargo
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=2_000)

    await browser.close()

    # ========================================================================
    # MONTAR CONFIG
    # ========================================================================
    cfg = {
        "source": "e-agendas",
        "url": url,
        "filters": {
            "select1": getattr(args, "select1", None),
            "pick1": getattr(args, "pick1", None),
            "limit1": getattr(args, "limit1", None),
            "select2": getattr(args, "select2", None),
            "pick2": getattr(args, "pick2", None),
            "limit2": getattr(args, "limit2", None),
            "select3": getattr(args, "select3", None),
            "pick3": getattr(args, "pick3", None),
            "limit3": getattr(args, "limit3", None),
        },
        "combos": combos,
        "stats": {
            "total_orgaos": stats["total_orgaos"],
            "total_cargos": stats["total_cargos"],
            "total_agentes": stats["total_agentes"],
            "total_combos": len(combos),
        },
    }

    # Salvar plan se especificado
    plan_out = getattr(args, "plan_out", None)
    if plan_out:
        import json

        Path(plan_out).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_out).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if v:
            print(f"\n[plan-eagendas-async] ✅ Plan salvo: {plan_out}")

    if v:
        print(f"\n[plan-eagendas-async] ✅ Gerados {len(combos)} combos")
        print("[plan-eagendas-async] Estatísticas:")
        print(f"  Órgãos: {stats['total_orgaos']}")
        print(f"  Cargos: {stats['total_cargos']}")
        print(f"  Agentes: {stats['total_agentes']}")

    return cfg


# ============================================================================
# WRAPPER SÍNCRONO
# ============================================================================


def build_plan_eagendas_sync_wrapper(args) -> dict[str, Any]:
    """Wrapper síncrono que roda async via asyncio.run()."""

    async def run():
        async with async_playwright() as p_async:
            return await build_plan_eagendas_async(p_async, args)

    return asyncio.run(run())


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera plan de combos e-agendas (async)")
    parser.add_argument("--headful", action="store_true", help="Mostrar navegador")
    parser.add_argument("--slowmo", type=int, default=0, help="Slow motion (ms)")
    parser.add_argument("--limit1", type=int, help="Limite de órgãos (N1)")
    parser.add_argument("--limit2", type=int, help="Limite de cargos por órgão (N2)")
    parser.add_argument("--limit3", type=int, help="Limite de agentes por cargo (N3)")
    parser.add_argument("--plan-out", help="Caminho para salvar plan JSON")
    parser.add_argument("--plan-verbose", action="store_true", help="Logs detalhados")

    args = parser.parse_args()

    print("=" * 80)
    print("PLAN LIVE E-AGENDAS (ASYNC)")
    print("=" * 80)

    plan = build_plan_eagendas_sync_wrapper(args)

    print("\n✅ Plan gerado com sucesso!")
    print(f"Total de combos: {len(plan['combos'])}")
