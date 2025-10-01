from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

from ..utils.browser import launch_browser, new_context, goto, fmt_date
from ..utils.dom import find_best_frame, label_for_control, is_select, read_select_options
from ..constants import DROPDOWN_ROOT_SELECTORS
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
    if is_select(h):
        return read_select_options(h)
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
            frame.page.wait_for_load_state("networkidle", timeout=60_000)
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
            frame.page.wait_for_load_state("networkidle", timeout=60_000)
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
                    frame.page.wait_for_load_state("networkidle", timeout=60_000)
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


def build_plan_live(p, args) -> Dict[str, Any]:
    """Gera um plano dinâmico L1×L2 diretamente do site (sem N3)."""
    v = bool(getattr(args, "plan_verbose", False))
    # Preferir usar Chrome instalado no sistema (evita download de browsers em ambientes com SSL restrito)
    import os
    from pathlib import Path
    browser = None
    try:
        browser = p.chromium.launch(channel="chrome", headless=not args.headful, slow_mo=args.slowmo)
    except Exception:
        try:
            browser = p.chromium.launch(channel="msedge", headless=not args.headful, slow_mo=args.slowmo)
        except Exception:
            # tentar via caminho explícito
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
                    browser = p.chromium.launch(executable_path=exe, headless=not args.headful, slow_mo=args.slowmo)
                except Exception:
                    browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)
            else:
                browser = p.chromium.launch(headless=not args.headful, slow_mo=args.slowmo)

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1366, "height": 900})
    page = context.new_page()
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)

    combos: List[Dict[str, Any]] = []
    try:
        data = fmt_date(args.data)
        goto(page, f"https://www.in.gov.br/leiturajornal?data={data}&secao={args.secao}")
        frame = find_best_frame(context)

        roots = _collect_dropdown_roots(frame)
        if not roots:
            raise RuntimeError("Nenhum dropdown detectado.")
        r1 = roots[0]
        r2 = roots[1] if len(roots) > 1 else None
        if not r2:
            raise RuntimeError("Dropdown de nível 2 não encontrado.")

        # N1 candidates
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

            # Re-resolve roots (DOM may change)
            roots = _collect_dropdown_roots(frame)
            r1 = roots[0]
            r2 = roots[1] if len(roots) > 1 else None
            if not r2:
                if v: print("[plan-live][skip] N2 não encontrado após refresh de roots.")
                continue

            if not _select_by_text(frame, r1, k1):
                if v: print(f"[plan-live][skip] N1 '{k1}' não pôde ser selecionado.")
                continue
            page.wait_for_load_state("networkidle", timeout=90_000)

            roots = _collect_dropdown_roots(frame)
            r2 = roots[1] if len(roots) > 1 else None
            if not r2:
                if v: print(f"[plan-live][skip] N2 não encontrado após N1='{k1}'.")
                continue

            o2 = _read_dropdown_options(frame, r2)
            o2 = _filter_opts(o2, getattr(args, "select2", None), getattr(args, "pick2", None), getattr(args, "limit2", None))
            k2_list = _build_keys(o2, getattr(args, "key2_type_default", "text"))
            if v: print(f"[plan-live] N1='{k1}' => N2 válidos: {len(k2_list)}")
            if not k2_list:
                continue

            for k2 in k2_list:
                combos.append({
                    "key1_type": getattr(args, "key1_type_default", "text"), "key1": k1,
                    "key2_type": getattr(args, "key2_type_default", "text"), "key2": k2,
                    "key3_type": None, "key3": None,
                    "label1": label_for_control(frame, r1.get("handle")) or "",
                    "label2": label_for_control(frame, r2.get("handle")) or "",
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
                "max_scrolls": int(getattr(args, "max_scrolls", 40)),
                "scroll_pause_ms": int(getattr(args, "scroll_pause_ms", 350)),
                "stable_rounds": int(getattr(args, "stable_rounds", 3)),
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

        return cfg
    finally:
        try:
            browser.close()
        except Exception:
            pass
