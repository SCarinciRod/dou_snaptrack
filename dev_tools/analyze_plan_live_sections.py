"""Diagnóstico comparativo dos dropdowns (N1/N2) nas seções DO1/DO2/DO3.

Objetivo: verificar se há diferenças em IDs, estruturas e rótulos que possam
impactar o plan_live (async ou sync) na coleta dos pares.

Saída: imprime um relatório Markdown com:
- Raízes detectadas (ordem por posição Y,X)
- ID, kind, tagName
- Label (quando aplicável)
- Contagem total de opções e amostra de até 10 textos.
- Heurística rápida de quais raízes parecem ser N1 / N2 (pelas quantidades e IDs conhecidos)

Uso:
  python dev_tools/analyze_plan_live_sections.py --date 10-11-2025 --sections DO1,DO2,DO3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from dou_snaptrack.utils.browser import build_dou_url, goto
from dou_snaptrack.utils.dom import find_best_frame
from dou_utils.dropdowns import collect_open_list_options, open_dropdown_robust

# IDs conhecidos (import leve para evitar dependência circular grande)
try:
    from dou_snaptrack.cli.plan_live import LEVEL_IDS
except Exception:
    LEVEL_IDS = {1: ["slcOrgs", "slcOrgsPrincipal"], 2: ["slcSuborgs", "slcSubOrgs"]}


def _read_options(frame, root_handle) -> list[dict[str, Any]]:
    """Ler opções de um root <select> ou combobox custom.
    Retorna lista com text/value/dataIndex etc. Pode retornar vazia em falhas.
    """
    out: list[dict[str, Any]] = []
    try:
        tag = root_handle.evaluate("el => el.tagName && el.tagName.toLowerCase()")
    except Exception:
        tag = None
    if tag == "select":
        try:
            opts = root_handle.evaluate(
                """
                (sel) => Array.from(sel.options).map(o => ({text: o.text.trim(), value: o.value, index: o.index}))
                """
            )
            for o in opts or []:
                t = (o.get("text") or "").strip()
                if not t:
                    continue
                out.append(o)
            return out
        except Exception:
            return []
    # Combobox custom - tentar abrir e coletar
    opened = open_dropdown_robust(frame.page, root_handle)
    if not opened:
        return []
    try:
    # Alguns dropdowns podem paginar - coletar após scroll leve
        options = collect_open_list_options(frame.page)
        for o in options or []:
            t = (o.get("text") or "").strip()
            if not t:
                continue
            out.append(o)
    except Exception:
        pass
    finally:
        # tenta fechar
        import contextlib
        with contextlib.suppress(Exception):
            frame.page.keyboard.press("Escape")
    return out


def _label_for(frame, h) -> str:
    try:
        elid = h.get_attribute("id")
        if elid:
            lab = frame.locator(f'label[for="{elid}"]').first
            if lab and lab.count() > 0:
                txt = (lab.text_content() or "").strip()
                if txt:
                    return txt
        # aria-label fallback
        aria = h.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    return ""


def _map_roots(frame, max_per_type: int = 120) -> list[dict[str, Any]]:
    roots = []
    seen = set()

    def push(kind: str, sel: str, loc):
        try:
            cnt = loc.count()
        except Exception:
            cnt = 0
        for i in range(min(cnt, max_per_type)):
            h = loc.nth(i)
            try:
                box = h.bounding_box() or {}
                if not box:
                    continue
                key = (sel, i, round(box.get("y", 0), 2), round(box.get("x", 0), 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({
                    "kind": kind,
                    "sel": sel,
                    "index": i,
                    "handle": h,
                    "y": box.get("y", 0),
                    "x": box.get("x", 0),
                })
            except Exception:
                pass

    push("combobox", "role=combobox", frame.get_by_role("combobox"))
    push("select", "select", frame.locator("select"))
    # heurísticas adicionais - reutilizar constantes se existirem
    try:
        from dou_snaptrack.cli.plan_live import DROPDOWN_ROOT_SELECTORS as EXTRA_SELECTORS
    except Exception:
        EXTRA_SELECTORS = [".ng-select", "select[formcontrolname]", "[role=combobox]"]
    for selroot in EXTRA_SELECTORS:
        push("unknown", selroot, frame.locator(selroot))

    # Dedupe por id ou posição priorizando select > combobox > unknown
    def _priority(kind: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(kind, 0)

    by_key: dict[Any, dict[str, Any]] = {}
    for r in roots:
        h = r["handle"]
        try:
            elid = h.get_attribute("id")
        except Exception:
            elid = None
        k = ("id", elid) if elid else ("pos", round(r["y"], 1), round(r["x"], 1), r["sel"])
        best = by_key.get(k)
        if not best or _priority(r["kind"]) > _priority(best["kind"]):
            by_key[k] = {**r, "id_attr": elid}

    out = list(by_key.values())
    out.sort(key=lambda rr: (rr["y"], rr["x"]))
    return out


def analyze_section(secao: str, data: str, headful: bool = False) -> dict[str, Any]:
    url = build_dou_url(data, secao)
    with sync_playwright() as p:
        # Preferir canais instalados
        browser = None
        for channel in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=channel, headless=not headful)
                break
            except Exception:
                browser = None
        if not browser:
            # fallback executável ou sem canal
            try:
                browser = p.chromium.launch(headless=not headful)
            except Exception as e:
                raise RuntimeError(f"Falha ao lançar browser: {e}") from e
        context = browser.new_context(ignore_https_errors=True)
        context.set_default_timeout(60_000)
        page = context.new_page()
        goto(page, url)

        # tentativa de 'Visualizar em Lista' (ajusta layout)
        try:
            from dou_snaptrack.utils.browser import try_visualizar_em_lista
            try_visualizar_em_lista(page)
        except Exception:
            pass

        frame = find_best_frame(context) or page

        # aguardar carregamento base e primeira população de N1 (#slcOrgs frequente)
        try:
            page.wait_for_timeout(4000)
            page.wait_for_function(
                "() => document.querySelector('#slcOrgs')?.options?.length > 2",
                timeout=8000,
            )
        except Exception:
            pass

        roots = _map_roots(frame)
        enriched = []
        for r in roots:
            h = r["handle"]
            try:
                tag = h.evaluate("el => el.tagName && el.tagName.toLowerCase()") or ""
            except Exception:
                tag = ""
            lab = _label_for(frame, h)
            opts = _read_options(frame, h)
            sample = [o.get("text") for o in opts[:10]]
            enriched.append({
                "kind": r["kind"],
                "id": r.get("id_attr"),
                "tag": tag,
                "label": lab,
                "y": r["y"],
                "x": r["x"],
                "total_options": len(opts),
                "sample_options": sample,
                "maybe_n1": r.get("id_attr") in set(LEVEL_IDS.get(1, [])),
                "maybe_n2": r.get("id_attr") in set(LEVEL_IDS.get(2, [])),
            })
        browser.close()
    return {
        "secao": secao,
        "url": url,
        "roots": enriched,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="10-11-2025")
    ap.add_argument("--sections", default="DO1,DO2,DO3")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    report = []
    for sec in sections:
        try:
            rep = analyze_section(sec, args.date, headful=args.headful)
            report.append(rep)
        except Exception as e:
            report.append({"secao": sec, "error": str(e)})

    # Saída JSON opcional
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Imprimir relatório Markdown
    print("\n# Diagnóstico Dropdowns DOU")
    print(f"Data: {args.date}")
    for rep in report:
        print(f"\n## Seção {rep.get('secao')}")
        if rep.get("error"):
            print(f"Falha: {rep['error']}")
            continue
        roots = rep.get("roots") or []
        print(f"Total raízes deduped: {len(roots)}")
        for i, r in enumerate(roots, 1):
            flags = []
            if r.get("maybe_n1"):
                flags.append("N1?")
            if r.get("maybe_n2"):
                flags.append("N2?")
            fstr = f" ({', '.join(flags)})" if flags else ""
            print(f"- [{i}] kind={r['kind']} tag={r['tag']} id={r.get('id') or '-'} label='{r.get('label') or ''}' y={round(r['y'],1)} x={round(r['x'],1)} total_opts={r['total_options']}{fstr}")
            if r.get("sample_options"):
                sample = ", ".join(r["sample_options"])[:300]
                print(f"    amostra: {sample}")

    # Resumo diferenças potenciais
    print("\n## Resumo potenciais diferenças")
    # comparar ids candidatos N1/N2 por seção
    n1_ids = {rep.get("secao"): [r.get("id") for r in rep.get("roots", []) if r.get("maybe_n1")] for rep in report}
    n2_ids = {rep.get("secao"): [r.get("id") for r in rep.get("roots", []) if r.get("maybe_n2")] for rep in report}
    print("IDs candidatos N1 por seção:")
    for s, ids in n1_ids.items():
        print(f"- {s}: {ids}")
    print("IDs candidatos N2 por seção:")
    for s, ids in n2_ids.items():
        print(f"- {s}: {ids}")
    print("\nSe notar variação grande de total_options ou ausência de N2 em alguma seção, considerar aumentar timeout de repopulação ou adicionar novos IDs em LEVEL_IDS.")


if __name__ == "__main__":  # guard para evitar multiprocessing interferir
    main()
