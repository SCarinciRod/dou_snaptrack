from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from ..utils.browser import launch_browser, new_context, goto, fmt_date
from ..utils.dom import find_best_frame, label_for_control, is_select, read_select_options
from ..constants import DROPDOWN_ROOT_SELECTORS, LEVEL_IDS
from ..utils.text import normalize_text

try:
    from dou_utils.selectors import LISTBOX_SELECTORS, OPTION_SELECTORS  # type: ignore
except Exception:
    LISTBOX_SELECTORS = (
        "[role=listbox]",
        "ul[role=listbox]",
        "div[role=listbox]",
        "ul[role=menu]",
        "div[role=menu]",
        ".ng-dropdown-panel",
        ".p-dropdown-items",
        ".select2-results__options",
        ".rc-virtual-list",
    )
    OPTION_SELECTORS = (
        "[role=option]",
        "li[role=option]",
        ".ng-option",
        ".p-dropdown-item",
        ".select2-results__option",
        "[data-value]",
        "[data-index]",
    )


def _collect_dropdown_roots(frame) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
    seen = set()

    def _push(kind: str, sel: str, loc):
        try:
            cnt = loc.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            h = loc.nth(i)
            try:
                box = h.bounding_box()
                if not box:
                    continue
                key = (sel, i, round(box["y"], 2), round(box["x"], 2))
                if key in seen:
                    continue
                seen.add(key)
                roots.append({
                    "selector": sel,
                    "kind": kind,
                    "index": i,
                    "handle": h,
                    "y": box["y"],
                    "x": box["x"],
                })
            except Exception:
                pass

    _push("combobox", "role=combobox", frame.get_by_role("combobox"))
    _push("select", "select", frame.locator("select"))
    for sel in DROPDOWN_ROOT_SELECTORS:
        _push("unknown", sel, frame.locator(sel))

    def _prio(k: str) -> int:
        return {"select": 3, "combobox": 2, "unknown": 1}.get(k, 0)

    by_key: Dict[Any, Dict[str, Any]] = {}
    for r in roots:
        h = r["handle"]
        try:
            elid = h.get_attribute("id")
        except Exception:
            elid = None
        k = ("id", elid) if elid else ("pos", round(r["y"], 1), round(r["x"], 1), r["selector"])
        best = by_key.get(k)
        if not best or _prio(r["kind"]) > _prio(best["kind"]):
            by_key[k] = r

    out = list(by_key.values())
    out.sort(key=lambda rr: (rr["y"], rr["x"]))
    return out


def _locate_root_by_id(frame, elem_id: str) -> Optional[Dict[str, Any]]:
    """Try to locate a dropdown root by a specific element id within the frame or page.

    Returns a root dict compatible with _collect_dropdown_roots entries or None if not found.
    """
    try:
        loc = frame.locator(f"#{elem_id}")
        if not loc or loc.count() == 0:
            loc = frame.page.locator(f"#{elem_id}")
        if not loc or loc.count() == 0:
            return None
        h = loc.first
        try:
            box = h.bounding_box() or {"y": 0, "x": 0}
        except Exception:
            box = {"y": 0, "x": 0}
        return {
            "selector": f"#{elem_id}",
            "kind": "id",
            "index": 0,
            "handle": h,
            "y": box.get("y") or 0,
            "x": box.get("x") or 0,
        }
    except Exception:
        return None


def _select_roots(frame) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Pick r1/r2 roots prioritizing known IDs from LEVEL_IDS; fallback to first two roots."""
    r1 = None
    r2 = None
    try:
        for eid in LEVEL_IDS.get(1, []) or []:
            r1 = _locate_root_by_id(frame, eid)
            if r1:
                break
    except Exception:
        r1 = None
    try:
        for eid in LEVEL_IDS.get(2, []) or []:
            r2 = _locate_root_by_id(frame, eid)
            if r2:
                break
    except Exception:
        r2 = None
    if not r1 or (not r2):
        roots = _collect_dropdown_roots(frame)
        if not r1:
            r1 = roots[0] if roots else None
        if not r2:
            r2 = roots[1] if roots and len(roots) > 1 else None
    return r1, r2


def _get_listbox_container(frame):
    for sel in LISTBOX_SELECTORS:
        try:
            loc = frame.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    page = frame.page
    for sel in LISTBOX_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    return None


def _read_open_list_options(frame) -> List[Dict[str, Any]]:
    def _is_placeholder_text(t: str) -> bool:
        nt = normalize_text(t or "")
        if not nt:
            return True
        placeholders = [
            "selecionar", "selecione", "escolha",
            "todos", "todas", "todas as", "todos os",
            "selecionar organizacao subordinada",
            "selecione uma opcao", "selecione a unidade", "selecione um orgao",
        ]
        return any(nt == p or nt.startswith(p + " ") for p in placeholders)
    container = _get_listbox_container(frame)
    if not container:
        return []
    opts: List[Dict[str, Any]] = []
    for sel in OPTION_SELECTORS:
        try:
            cands = container.locator(sel)
            cnt = cands.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            o = cands.nth(i)
            try:
                if not o.is_visible():
                    continue
                text = (o.text_content() or "").strip()
                # descartar placeholders genéricos (ex.: "Selecionar organização subordinada")
                if _is_placeholder_text(text):
                    continue
                val = o.get_attribute("value")
                dv = o.get_attribute("data-value")
                di = o.get_attribute("data-index") or o.get_attribute("data-option-index") or str(i)
                opts.append({"text": text, "value": val, "dataValue": dv, "dataIndex": di})
            except Exception:
                pass
    try:
        frame.page.keyboard.press("Escape")
    except Exception:
        pass
    # dedupe
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for o in opts:
        key = (o.get("text"), o.get("value"), o.get("dataValue"), o.get("dataIndex"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)
    return uniq


def _read_dropdown_options(frame, root: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not root:
        return []
    h = root.get("handle")
    if h is None:
        return []
    def _is_placeholder_text(t: str) -> bool:
        nt = normalize_text(t or "")
        if not nt:
            return True
        placeholders = [
            "selecionar", "selecione", "escolha",
            "todos", "todas", "todas as", "todos os",
            "selecionar organizacao subordinada",
            "selecione uma opcao", "selecione a unidade", "selecione um orgao",
        ]
        return any(nt == p or nt.startswith(p + " ") for p in placeholders)
    if is_select(h):
        opts = read_select_options(h)
        # Filtrar placeholders em listas nativas <select>
        out = []
        for o in opts or []:
            try:
                t = (o.get("text") or "").strip()
                if _is_placeholder_text(t):
                    continue
                out.append(o)
            except Exception:
                out.append(o)
        return out
    try:
        h.click(timeout=2000)
        frame.wait_for_timeout(120)
    except Exception:
        pass
    return _read_open_list_options(frame)


def _select_by_text(frame, root: Dict[str, Any], text: str) -> bool:
    h = root.get("handle")
    if h is None:
        return False
    # select native <select>
    if is_select(h):
        try:
            h.select_option(label=text)
            # Espera mais curta e específica
            try:
                frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            except Exception:
                pass
            try:
                frame.wait_for_timeout(200)
            except Exception:
                pass
            return True
        except Exception:
            pass
    # custom: open and click matching option
    try:
        h.click(timeout=2000)
        frame.wait_for_timeout(120)
    except Exception:
        pass
    container = _get_listbox_container(frame)
    if not container:
        return False
    try:
        # exact by role
        opt = container.get_by_role("option", name=re.compile(rf"^{re.escape(text)}$", re.I)).first
        if opt and opt.count() > 0 and opt.is_visible():
            opt.click(timeout=3000)
            try:
                frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
            except Exception:
                pass
            try:
                frame.wait_for_timeout(200)
            except Exception:
                pass
            return True
    except Exception:
        pass
    # fallback contains (normalized)
    nt = normalize_text(text)
    for sel in OPTION_SELECTORS:
        try:
            cands = container.locator(sel)
            cnt = cands.count()
        except Exception:
            cnt = 0
        for i in range(cnt):
            o = cands.nth(i)
            try:
                if not o.is_visible():
                    continue
                t = normalize_text((o.text_content() or "").strip())
                if nt and (t == nt or nt in t):
                    o.click(timeout=3000)
                    try:
                        frame.page.wait_for_load_state("domcontentloaded", timeout=30_000)
                    except Exception:
                        pass
                    try:
                        frame.wait_for_timeout(200)
                    except Exception:
                        pass
                    return True
            except Exception:
                pass
    try:
        frame.page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def _filter_opts(options: List[Dict[str, Any]], select_regex: Optional[str], pick_list: Optional[str], limit: Optional[int]) -> List[Dict[str, Any]]:
    opts = options or []
    out = opts
    if select_regex:
        try:
            pat = re.compile(select_regex, re.I)
            out = [o for o in opts if pat.search(o.get("text") or "")]
        except re.error:
            out = []
        if not out:
            tokens = [t.strip() for t in select_regex.splitlines() if t.strip()]
            tokens_norm = [normalize_text(t) for t in tokens]
            tmp = []
            for o in opts:
                nt = normalize_text(o.get("text") or "")
                if any(tok and tok in nt for tok in tokens_norm):
                    tmp.append(o)
            out = tmp
    if pick_list:
        picks = {s.strip() for s in pick_list.split(",") if s.strip()}
        out = [o for o in out if (o.get("text") or "") in picks]
    if limit and limit > 0:
        out = out[:limit]
    return out


def _build_keys(opts: List[Dict[str, Any]], key_type: str) -> List[str]:
    keys: List[str] = []
    for o in opts:
        if key_type == "text":
            t = (o.get("text") or "").strip()
            if t:
                keys.append(t)
        elif key_type == "value":
            v = o.get("value")
            if v not in (None, ""):
                keys.append(str(v))
        elif key_type == "dataValue":
            dv = o.get("dataValue")
            if dv not in (None, ""):
                keys.append(str(dv))
        elif key_type == "dataIndex":
            di = o.get("dataIndex")
            if di not in (None, ""):
                keys.append(str(di))
    seen = set(); out: List[str] = []
    for k in keys:
        if k in seen: continue
        seen.add(k); out.append(k)
    return out


def build_plan_live(p, args, browser=None) -> Dict[str, Any]:
    """Gera um plano dinâmico L1×L2 diretamente do site (sem N3).

    This implementation starts a local Playwright context so all browser
    operations happen in the same thread. The provided `p` argument is ignored
    here to avoid cross-thread usage.
    """
    v = bool(getattr(args, "plan_verbose", False))
    import os
    from pathlib import Path
    from playwright.sync_api import sync_playwright  # type: ignore

    headful = bool(getattr(args, "headful", False))
    slowmo = int(getattr(args, "slowmo", 0) or 0)

    combos: List[Dict[str, Any]] = []
    cfg: Dict[str, Any] = {}

    # Reuso: se um browser foi fornecido, evitamos abrir/fechar Playwright localmente
    pctx_mgr = None
    pctx = None
    must_close_browser = False
    try:
        if browser is None:
            from playwright.sync_api import sync_playwright  # type: ignore
            pctx_mgr = sync_playwright()
            pctx = pctx_mgr.__enter__()
            # Launch browser preferring system channels, then executable path, then fallback
            try:
                try:
                    browser = pctx.chromium.launch(channel="chrome", headless=not headful, slow_mo=slowmo)
                except Exception:
                    try:
                        browser = pctx.chromium.launch(channel="msedge", headless=not headful, slow_mo=slowmo)
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
                                    exe = c; break
                        if exe and Path(exe).exists():
                            try:
                                browser = pctx.chromium.launch(executable_path=exe, headless=not headful, slow_mo=slowmo)
                            except Exception:
                                browser = pctx.chromium.launch(headless=not headful, slow_mo=slowmo)
                        else:
                            browser = pctx.chromium.launch(headless=not headful, slow_mo=slowmo)
            except Exception:
                # Last resort
                browser = pctx.chromium.launch(headless=not headful, slow_mo=slowmo)
            must_close_browser = True

        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        # Main flow: collect dropdowns and build combos
        data = fmt_date(args.data)
        goto(page, f"https://www.in.gov.br/leiturajornal?data={data}&secao={args.secao}")
        frame = find_best_frame(context)

        r1, r2 = _select_roots(frame)
        if not r1 and not r2:
            raise RuntimeError("Nenhum dropdown detectado.")
        # aceitar fluxo somente N1 se r2 ausente

        # N1 candidates
        if not r1:
            roots_tmp = _collect_dropdown_roots(frame)
            r1 = roots_tmp[0] if roots_tmp else None
        if not r1:
            raise RuntimeError("Dropdown N1 não encontrado.")
        o1 = _read_dropdown_options(frame, r1)
        o1 = _filter_opts(o1, getattr(args, "select1", None), getattr(args, "pick1", None), getattr(args, "limit1", None))
        k1_list = _build_keys(o1, getattr(args, "key1_type_default", "text"))
        if not k1_list:
            raise RuntimeError("Após filtros, N1 ficou sem opções (ajuste --select1/--pick1/--limit1).")
        if v:
            print(f"[plan-live] N1 candidatos: {len(k1_list)}")

        maxc = getattr(args, "max_combos", None)
        if isinstance(maxc, int) and maxc <= 0:
            maxc = None

        for k1 in k1_list:
            if maxc and len(combos) >= maxc:
                break

            # Re-resolve roots (DOM may change). Prioritize IDs.
            r1, r2 = _select_roots(frame)
            if not r1:
                roots_tmp = _collect_dropdown_roots(frame)
                r1 = roots_tmp[0] if roots_tmp else None
            if not r1:
                if v: print("[plan-live][skip] N1 não encontrado após atualização do DOM.")
                continue

            if not _select_by_text(frame, r1, k1):
                if v: print(f"[plan-live][skip] N1 '{k1}' não pôde ser selecionado.")
                continue
            # Espera mais curta e específica após seleção
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30_000)
            except Exception:
                pass
            try:
                page.wait_for_timeout(200)
            except Exception:
                pass

            # Re-collect after selection in case the DOM updated
            _, r2 = _select_roots(frame)

            if r2:
                o2 = _read_dropdown_options(frame, r2)
                o2 = _filter_opts(o2, getattr(args, "select2", None), getattr(args, "pick2", None), getattr(args, "limit2", None))
                k2_list = _build_keys(o2, getattr(args, "key2_type_default", "text"))
                if v: print(f"[plan-live] N1='{k1}' => N2 válidos: {len(k2_list)}")
            else:
                k2_list = []

            if k2_list:
                for k2 in k2_list:
                    combos.append({
                        "key1_type": getattr(args, "key1_type_default", "text"), "key1": k1,
                        "key2_type": getattr(args, "key2_type_default", "text"), "key2": k2,
                        "key3_type": None, "key3": None,
                        "label1": label_for_control(frame, r1.get("handle")) or "",
                        "label2": (label_for_control(frame, r2.get("handle")) or "") if r2 else "",
                        "label3": "",
                    })
                    if maxc and len(combos) >= maxc:
                        break
            else:
                # N1-only combo
                combos.append({
                    "key1_type": getattr(args, "key1_type_default", "text"), "key1": k1,
                    "key2_type": None, "key2": None,
                    "key3_type": None, "key3": None,
                    "label1": label_for_control(frame, r1.get("handle")) or "",
                    "label2": "",
                    "label3": "",
                })
                if maxc and len(combos) >= maxc:
                    break

        if not combos:
            raise RuntimeError("Nenhum combo válido L1×L2 foi gerado.")

        cfg = {
            "data": data,
            "secaoDefault": args.secao or "DO1",
            "defaults": {
                "scrape_detail": bool(getattr(args, "scrape_detail", False)),
                "fallback_date_if_missing": bool(getattr(args, "fallback_date_if_missing", False)),
                "max_links": int(getattr(args, "max_links", 30)),
                "max_scrolls": int(getattr(args, "max_scrolls", 30)),
                "scroll_pause_ms": int(getattr(args, "scroll_pause_ms", 250)),
                "stable_rounds": int(getattr(args, "stable_rounds", 2)),
                "label1": getattr(args, "label1", None),
                "label2": getattr(args, "label2", None),
                "label3": None,
                "debug_dump": bool(getattr(args, "debug_dump", False)),
                "summary_lines": int(getattr(args, "summary_lines", 3)) if getattr(args, "summary_lines", None) else None,
                "summary_mode": getattr(args, "summary_mode", "center"),
            },
            "combos": combos,
            "output": {"pattern": "{secao}_{date}_{idx}.json", "report": "batch_report.json"},
        }

        # Se o usuário forneceu um nome de plano, preserve para nomear agregados/boletins
        plan_name = getattr(args, "plan_name", None) or getattr(args, "nome_plano", None)
        if plan_name:
            cfg["plan_name"] = str(plan_name)

        if getattr(args, "query", None):
            cfg["topics"] = [{"name": "Topic", "query": args.query}]
        if getattr(args, "state_file", None):
            cfg["state_file"] = args.state_file
        if getattr(args, "bulletin", None):
            ext = "docx" if args.bulletin == "docx" else args.bulletin
            out_b = args.bulletin_out or f"boletim_{{secao}}_{{date}}_{{idx}}.{ext}"
            cfg["output"]["bulletin"] = out_b
            cfg["defaults"]["bulletin"] = args.bulletin
            cfg["defaults"]["bulletin_out"] = out_b
        
        # Encerramento do contexto e, se aplicável, do browser local
        try:
            context.close()
        except Exception:
            pass
        if must_close_browser and browser is not None:
            try:
                browser.close()
            except Exception:
                pass
    finally:
        if pctx_mgr is not None:
            try:
                pctx_mgr.__exit__(None, None, None)
            except Exception:
                pass

    return cfg
