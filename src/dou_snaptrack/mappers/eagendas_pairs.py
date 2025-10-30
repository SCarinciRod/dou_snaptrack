from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import time

from ..utils.text import normalize_text
from ..utils.dom import find_best_frame
import re
from ..utils.dom import is_select, read_select_options
try:
    # reuse robust dropdown helpers from the DOU pairs mapper
    from ..mappers.pairs_mapper import (
        remove_placeholders, filter_opts, select_by_text_or_attrs,
        wait_n2_repopulated, _scroll_listbox_to_end
    )
    from dou_utils.dropdown_strategies import open_dropdown_robust, collect_open_list_options
except Exception:
    # fallbacks if pairs_mapper helpers are not available
    def remove_placeholders(options):
        return options or []
    def filter_opts(options, *args, **kwargs):
        return options or []
    def select_by_text_or_attrs(page, root, option):
        try:
            if is_select(root['handle']):
                try:
                    root['handle'].select_option(value=option.get('value'))
                    page.wait_for_load_state('networkidle', timeout=30000)
                    return True
                except Exception:
                    pass
            try:
                root['handle'].click()
            except Exception:
                pass
            txt = option.get('text') or ''
            try:
                opt = page.get_by_role('option', name=txt).first
                if opt and opt.count() > 0 and opt.is_visible():
                    opt.click(); page.wait_for_load_state('networkidle', timeout=30000); return True
            except Exception:
                pass
        except Exception:
            pass
        return False
    def wait_n2_repopulated(page, n2_root, prev_count, timeout_ms=15000):
        page.wait_for_timeout(300)
    def _scroll_listbox_to_end(page):
        try: page.keyboard.press('End')
        except Exception: pass
    def open_dropdown_robust(page, handle):
        try:
            handle.click(); page.wait_for_timeout(200); return True
        except Exception:
            return False
    def collect_open_list_options(page):
        out = []
        try:
            opts = page.locator('[role=option]')
            for i in range(opts.count()):
                o = opts.nth(i)
                out.append({
                    'text': (o.text_content() or '').strip(),
                    'value': o.get_attribute('data-value') or o.get_attribute('value')
                })
        except Exception:
            pass
        return out
except Exception:
    # fallbacks if pairs_mapper helpers are not available
    def remove_placeholders(options):
        return options or []
    def filter_opts(options, *args, **kwargs):
        return options or []
    def select_by_text_or_attrs(page, root, option):
        # best-effort: try click by visible option text
        try:
            if is_select(root['handle']):
                try:
                    root['handle'].select_option(value=option.get('value'))
                    page.wait_for_load_state('networkidle', timeout=30000)
                    return True
                except Exception:
                    pass
            # try opening and clicking an option that matches text
            try:
                root['handle'].click()
            except Exception:
                pass
            txt = option.get('text') or ''
            try:
                opt = page.get_by_role('option', name=txt).first
                if opt and opt.count() > 0 and opt.is_visible():
                    opt.click(); page.wait_for_load_state('networkidle', timeout=30000); return True
            except Exception:
                pass
        except Exception:
            pass
        return False
    def wait_n2_repopulated(page, n2_root, prev_count, timeout_ms=15000):
        page.wait_for_timeout(300)
    def _scroll_listbox_to_end(page):
        try: page.keyboard.press('End')
        except Exception: pass


def _best_match_key(keys: List[str], desired: str) -> Optional[str]:
    if not desired:
        return None
    dnorm = normalize_text(desired)
    tokens = [t for t in dnorm.split() if t]
    # prefer exact contains
    for k in keys:
        kn = normalize_text(k)
        if all(tok in kn for tok in tokens):
            return k
    # fallback: any key containing one token
    for k in keys:
        kn = normalize_text(k)
        if any(tok in kn for tok in tokens):
            return k
    return None


def _click_visible(locator) -> bool:
    try:
        if locator.count() > 0:
            el = locator.first
            if el.is_visible():
                el.scroll_into_view_if_needed()
                el.click(timeout=5000)
                return True
    except Exception:
        pass
    return False


def _select_from_wrapped_input(frame, input_id: str, prefer_token: Optional[str] = None) -> bool:
    """Click input wrapper and choose an option containing prefer_token if possible."""
    try:
        sel = f"#{input_id}"
        inp = frame.locator(sel)
        if inp.count() == 0:
            return False
        # click to open — try multiple wrapper id variations
        wrapper_ids = [input_id, f"{input_id}-selectized", f"{input_id}-select2", f"{input_id}-wrapper"]
        clicked = False
        for wid in wrapper_ids:
            try:
                wloc = frame.locator(f"#{wid}")
                if wloc.count() > 0:
                    try:
                        wloc.first.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        wloc.first.click(timeout=3000)
                        clicked = True
                        break
                    except Exception:
                        pass
            except Exception:
                pass
        if not clicked:
            # last resort: click the original input element
            try:
                inp.first.scroll_into_view_if_needed()
                inp.first.click(timeout=3000)
                clicked = True
            except Exception:
                pass
        if not clicked:
            return False
        # wait briefly for options to render
        frame.wait_for_timeout(500)
        # try common option locators
        option_selectors = ["[role=option]", ".selectize-dropdown .option", ".select2-results__option", "li[role=option]", "ul[role=listbox] li"]
        for osel in option_selectors:
            try:
                opts = frame.locator(osel)
                if opts.count() == 0:
                    continue
                # find prefer_token first
                if prefer_token:
                    for i in range(opts.count()):
                        o = opts.nth(i)
                        try:
                            txt = (o.text_content() or "").strip()
                            if prefer_token.lower() in txt.lower():
                                o.click()
                                frame.wait_for_load_state('networkidle', timeout=30_000)
                                return True
                        except Exception:
                            pass
                # otherwise click first visible
                for i in range(opts.count()):
                    o = opts.nth(i)
                    try:
                        if not o.is_visible():
                            continue
                        o.click()
                        frame.wait_for_load_state('networkidle', timeout=30_000)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass
        return False
    except Exception:
        return False


def _select_native_select(frame, select_id: str, prefer_token: Optional[str] = None) -> bool:
    try:
        sel = f"select#{select_id}"
        s = frame.locator(sel)
        if s.count() == 0:
            return False
        # try to set via JS: iterate options and pick one matching prefer_token or first non-empty
        try:
            opts = s.first.locator('option')
            for i in range(opts.count()):
                o = opts.nth(i)
                txt = (o.text_content() or "").strip()
                val = o.get_attribute('value') or txt
                if not txt or txt.lower().startswith('selecion'):
                    continue
                if prefer_token and prefer_token.lower() in txt.lower():
                    s.first.select_option(value=val)
                    frame.wait_for_load_state('networkidle', timeout=30000)
                    return True
            # otherwise pick first usable
            for i in range(opts.count()):
                o = opts.nth(i)
                txt = (o.text_content() or "").strip()
                val = o.get_attribute('value') or txt
                if not txt or txt.lower().startswith('selecion'):
                    continue
                s.first.select_option(value=val)
                frame.wait_for_load_state('networkidle', timeout=30000)
                return True
        except Exception:
            # fallback: click the select and choose
            try:
                s.first.click()
            except Exception:
                pass
        return False
    except Exception:
        return False


def _click_input_or_label(frame, eid: str) -> bool:
    """Try clicking an input by id, its label or set checked via JS as fallback."""
    try:
        loc = frame.locator(f"input#{eid}")
        if loc.count() > 0:
            try:
                loc.first.scroll_into_view_if_needed()
                loc.first.click(timeout=3000)
                return True
            except Exception:
                pass
    except Exception:
        pass
    try:
        lab = frame.locator(f"label[for=\"{eid}\"]")
        if lab.count() > 0:
            try:
                lab.first.scroll_into_view_if_needed()
                lab.first.click(timeout=3000)
                return True
            except Exception:
                pass
    except Exception:
        pass
    # JS fallback: set checked and dispatch event
    try:
        js = r"(id)=>{const el=document.getElementById(id); if(!el) return false; el.checked=true; el.dispatchEvent(new Event('change',{bubbles:true})); return true;}"
        ok = frame.evaluate(js, eid)
        return bool(ok)
    except Exception:
        return False


def map_pairs_eagendas(page, page_map_path: str, n1_label: str, n2_label: str, n3_label: Optional[str] = None, limit1: Optional[int] = None, limit2_per_n1: Optional[int] = None, verbose: bool = False, strict_selection: bool = False) -> Dict[str, Any]:
    """Interact with the page using selectors from page_map JSON to select filters in order n1 -> n2 -> n3.

    Returns a dict similar to other mappers with 'n1_options' mapping to selected N2/N3 options.
    """
    # load mapping
    pm = None
    try:
        pm = json.loads(open(page_map_path, encoding='utf-8').read())
    except Exception as e:
        raise RuntimeError(f"Failed to load page_map: {e}")

    elements_by_name = pm.get('elements', {}).get('by_name', {})
    keys = list(elements_by_name.keys())

    # find matching keys
    k1 = _best_match_key(keys, n1_label) if n1_label else None
    k2 = _best_match_key(keys, n2_label) if n2_label else None
    k3 = _best_match_key(keys, n3_label) if n3_label else None

    if verbose:
        print('map_pairs_eagendas: resolved keys:', k1, k2, k3)

    frame = find_best_frame(page.context) or page.main_frame

    result = {'date': pm.get('scannedUrl'), 'secao': pm.get('scannedUrl'), 'controls': {}, 'n1_options': []}

    # resolve control roots using IDs present in page_map entries
    def _find_control_by_ids(ids: List[str]):
        # try exact ids and common widget suffixes
        for base in ids or []:
            if not base:
                continue
            candidates = [base, f"{base}-selectized", f"{base}-select2", f"{base}-wrapper"]
            for cid in candidates:
                try:
                    loc = frame.locator(f"#{cid}")
                    if loc.count() > 0 and loc.first.is_visible():
                        root = {'handle': loc.first, 'id': cid}
                        return root
                except Exception:
                    pass
        return None

    # gather candidate ids for n1/n2 from page_map entries
    def _ids_for_key(key: Optional[str]):
        if not key:
            return []
        entries = elements_by_name.get(key, [])
        ids = []
        for e in entries:
            eid = e.get('id')
            if eid:
                ids.append(eid)
        # If strict selection and we found no ids (label-only entry), try to resolve from the live DOM
        if strict_selection and not ids:
            try:
                # try label[for=...] matching the label text
                lab_text = key
                # exact label match first
                labs = frame.locator(f'label:has-text("{lab_text}")')
                if labs.count() > 0:
                    lab = labs.first
                    try:
                        fid = lab.get_attribute('for')
                        if fid:
                            ids.append(fid)
                    except Exception:
                        pass
                    # if the fid looks like a label id, also try a stripped candidate
                    try:
                        if fid and (fid.endswith('_label') or fid.endswith('-label') or fid.endswith('_lbl') or fid.endswith('-lbl')):
                            stripped = fid.rsplit('_',1)[0] if '_' in fid else fid.rsplit('-',1)[0]
                            if stripped:
                                ids.append(stripped)
                    except Exception:
                        pass
                    if not ids:
                        # try inputs/selects within same container
                        try:
                            parent = lab.locator('xpath=..').first
                            cand = parent.locator('input,select,div[class*=select],div[class*=selectize]').first
                            if cand and cand.count() > 0:
                                try:
                                    cid = cand.get_attribute('id')
                                    if cid:
                                        ids.append(cid)
                                except Exception:
                                    pass
                                # if the found id looks like a label wrapper, also try a stripped control id
                                try:
                                    if cid and (cid.endswith('_label') or cid.endswith('-label') or cid.endswith('_lbl') or cid.endswith('-lbl')):
                                        stripped = cid.rsplit('_',1)[0] if '_' in cid else cid.rsplit('-',1)[0]
                                        if stripped:
                                            ids.append(stripped)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                # fallback: find inputs/selects by aria-label/placeholder equal to label
                if not ids:
                    try:
                        cand = frame.locator(f'input[placeholder="{lab_text}"], input[aria-label="{lab_text}"], select[aria-label="{lab_text}"]')
                        if cand.count() > 0:
                            try:
                                cid = cand.first.get_attribute('id')
                                if cid:
                                    ids.append(cid)
                                # if the found id looks like a label wrapper, try stripping common suffixes to reach control id
                                if cid and (cid.endswith('_label') or cid.endswith('-label') or cid.endswith('_lbl') or cid.endswith('-lbl')):
                                    stripped = cid.rsplit('_',1)[0] if '_' in cid else cid.rsplit('-',1)[0]
                                    if stripped:
                                        ids.append(stripped)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        return ids
        

    # find other keys that may contain a real combobox for the same concept
    def _expanded_keys_for_label(label: Optional[str]):
        if not label:
            return []
        tnorm = normalize_text(label)
        # split on non-word to get tokens (handles underscores)
        toks = [t for t in re.findall(r"\w{3,}", tnorm) if t]
        res = []
        for k in elements_by_name.keys():
            kn = normalize_text(k)
            if any(tok in kn for tok in toks):
                res.append(k)
        # prefer keys that look like combobox/select
        def score_key(k):
            kn = normalize_text(k)
            s = 0
            if 'select' in kn or 'digite' in kn or 'lista' in kn:
                s += 2
            # presence of a selectized id in entries
            entries = elements_by_name.get(k, [])
            for e in entries:
                eid = (e.get('id') or '')
                if '-selectized' in eid or '-select2' in eid:
                    s += 1
            return s
        res_sorted = sorted(res, key=score_key, reverse=True)
        return res_sorted

    # prefer expanded set of keys for n1 (e.g., an orgao combobox instead of a single active/inactive checkbox)
    if strict_selection:
        n1_candidate_keys = [k1] if k1 else []
    else:
        n1_candidate_keys = [k1] + _expanded_keys_for_label(n1_label)
    n1_ids = []
    for kk in n1_candidate_keys:
        n1_ids.extend(_ids_for_key(kk))
    # dedupe while preserving order
    seen = set(); n1_ids = [x for x in n1_ids if not (x in seen or seen.add(x))]

    if strict_selection:
        n2_candidate_keys = [k2] if k2 else []
    else:
        n2_candidate_keys = [k2] + _expanded_keys_for_label(n2_label) if k2 else []
    n2_ids = []
    for kk in n2_candidate_keys:
        n2_ids.extend(_ids_for_key(kk))
    seen = set(); n2_ids = [x for x in n2_ids if not (x in seen or seen.add(x))]

    n1_root = _find_control_by_ids(n1_ids)
    n2_root = _find_control_by_ids(n2_ids) if n2_ids else None

    if not n1_root:
        raise RuntimeError(f"N1 control not found on page for '{n1_label}' (keys: {n1_ids})")

    result['controls']['n1_id'] = n1_root.get('id')
    result['controls']['n2_id'] = n2_root.get('id') if n2_root else None

    # obtain N1 options
    def _collect_options_for_root(root):
        if not root:
            return []
        try:
            if is_select(root['handle']):
                return read_select_options(root['handle']) or []
        except Exception:
            pass
        # try robust open + collect
        try:
            opened = open_dropdown_robust(frame, root['handle'])
            if opened:
                opts = collect_open_list_options(frame)
                return opts or []
        except Exception:
            pass
        # fallback: collect role=option visible list
        out = []
        try:
            opts = frame.locator('[role=option]')
            for i in range(opts.count()):
                o = opts.nth(i)
                out.append({'text': (o.text_content() or '').strip(), 'value': o.get_attribute('data-value') or o.get_attribute('value')})
        except Exception:
            pass
    # If still empty, try typeahead probing: focus an input near the root and type a short token to trigger suggestions
        if not out:
            try:
                probe_inputs = []
                rid = root.get('id')
                if rid:
                    probe_inputs.extend([
                        f"input#{rid}",
                        f"#{rid} input",
                        f"#{rid}-selectized",
                        f"input#{rid}-selectized",
                        f"input[aria-controls*='{rid}']",
                    ])
                probe_inputs.extend(["input[role='combobox']", "input[type='search']", "input[placeholder]", "input"])
                seen_probe = set()
                for psel in probe_inputs:
                    if psel in seen_probe: continue
                    seen_probe.add(psel)
                    try:
                        pl = frame.locator(psel)
                        if pl.count() == 0:
                            continue
                        el = pl.first
                        try:
                            el.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        try:
                            el.click()
                        except Exception:
                            pass
                        try:
                            el.fill("")
                        except Exception:
                            pass
                        # try a few small probes to trigger typeahead suggestions
                        probes = ["a", "ab", "da", "o"]
                        for token in probes:
                            try:
                                # try typing the token
                                try:
                                    el.fill("")
                                except Exception:
                                    pass
                                try:
                                    el.type(token, delay=60)
                                except Exception:
                                    try:
                                        el.press(token)
                                    except Exception:
                                        pass
                                # allow debounce and rendering
                                frame.wait_for_timeout(900)
                                # try to open with arrow down
                                try:
                                    el.press("ArrowDown")
                                    frame.wait_for_timeout(300)
                                except Exception:
                                    pass
                                opts = collect_open_list_options(frame)
                                if opts:
                                    out = opts
                                    break
                            except Exception:
                                continue
                        # try to clear the probe
                        try:
                            el.fill("")
                        except Exception:
                            pass
                    except Exception:
                        continue
            except Exception:
                pass
        # If still empty, try to read a native <select> that may be the source for a selectized control
        if not out:
            try:
                rid = root.get('id')
                if rid:
                    # common wrappers: '-selectized', '-select2', '-wrapper', '_label', '-label'
                    for suffix in ('-selectized', '-select2', '-wrapper', '_label', '-label'):
                        if rid.endswith(suffix):
                            base = rid[:-len(suffix)]
                            try:
                                sel = frame.locator(f'select#{base}')
                                if sel.count() > 0:
                                    out = read_select_options(sel.first) or []
                                    if out:
                                        break
                            except Exception:
                                pass
                    # try also base equal to rid
                    try:
                        sel = frame.locator(f'select#{rid}')
                        if sel.count() > 0:
                            out = read_select_options(sel.first) or []
                    except Exception:
                        pass
            except Exception:
                pass

        return out

    def _verify_selection(page, frame, root, option, prev_n2_count) -> bool:
        """Return True if selecting `option` on `root` appears to have taken effect.

        Heuristics:
        - If there is a n2_root provided, consider N2 repopulation as confirmation.
        - For native <select> check selected option value/text.
        - For wrapped widgets search for a visible selected token/text inside the wrapper.
        """
        # 1) If n2 exists, wait briefly and check count change
        try:
            if n2_root:
                try:
                    wait_n2_repopulated(page, n2_root, prev_n2_count, timeout_ms=2500)
                    # after wait, check if count changed
                    if is_select(n2_root['handle']):
                        new = len(read_select_options(n2_root['handle']))
                    else:
                        try:
                            opened = open_dropdown_robust(frame, n2_root['handle'])
                            new = len(collect_open_list_options(frame)) if opened else 0
                        except Exception:
                            new = 0
                    if new != prev_n2_count and new > 0:
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # 2) native select check for this root
        try:
            if is_select(root['handle']):
                try:
                    sel_info = root['handle'].evaluate("el => { const s = el.options[el.selectedIndex]; return {value: s ? s.value : null, text: s ? (s.textContent||'').trim() : null}; }")
                    sval = sel_info.get('value') if isinstance(sel_info, dict) else None
                    stxt = sel_info.get('text') if isinstance(sel_info, dict) else None
                    want_val = option.get('value')
                    want_txt = (option.get('text') or '').strip()
                    if want_val and sval and str(want_val) == str(sval):
                        return True
                    if want_txt and stxt and normalize_text(want_txt) == normalize_text(stxt):
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # 3) wrapped control: look for a selected token/text inside the wrapper
        try:
            rid = root.get('id')
            if rid:
                sel_candidates = [
                    f"#{rid} .item", f"#{rid} .selected", f"#{rid} .selectize-input .item",
                    f"#{rid} .select2-selection__rendered", f"#{rid} .token", f"#{rid} .p-highlight",
                    f"div.selectize-control[data-for='{rid}'] .item",
                ]
                want_txt = (option.get('text') or '').strip()
                for sc in sel_candidates:
                    try:
                        loc = frame.locator(sc)
                        if loc.count() == 0:
                            continue
                        for i in range(loc.count()):
                            t = (loc.nth(i).text_content() or '').strip()
                            if not t:
                                continue
                            if want_txt and want_txt.lower() in t.lower():
                                return True
                    except Exception:
                        continue
        except Exception:
            pass

        return False

    try:
        n1_all = _collect_options_for_root(n1_root)
    except Exception:
        n1_all = []

    n1_all = remove_placeholders(n1_all)
    # If no options were collected, try building a two-state options list from *_ativos/_inativos controls
    if not n1_all:
        # look for id patterns like filtro_orgaos_ativos -> paired with filtro_orgaos_inativos
        built = []
        for eid in n1_ids:
            if eid.endswith('_ativos'):
                base = eid[:-7]
                other = base + '_inativos'
                if other in n1_ids:
                    built.append({'text': 'ativos', 'value': 'ativos', 'id': eid})
                    built.append({'text': 'inativos', 'value': 'inativos', 'id': other})
                    break
        if built:
            n1_all = built

    n1_filtered = n1_all[:limit1] if limit1 and limit1 > 0 else n1_all

    if verbose:
        print(f"[N1] total={len(n1_all)} filtrado={len(n1_filtered)}")

    for idx, o1 in enumerate(n1_filtered, 1):
        prev_n2_count = 0
        if n2_root:
            try:
                if is_select(n2_root['handle']):
                    prev_n2_count = len(read_select_options(n2_root['handle']))
                else:
                    # attempt to open and count
                    try:
                        n2_root['handle'].click()
                        opts = frame.locator('[role=option]')
                        prev_n2_count = opts.count()
                    except Exception:
                        prev_n2_count = 0
            except Exception:
                prev_n2_count = 0

        # Try multiple selection strategies and verify the selection actually took effect.
        ok = False
        # limit how many strategies we will try per N1 option to avoid excessive clicking
        MAX_STRATEGY_ATTEMPTS = 3
        attempt_count = 0

        def _attempt_and_verify_named(name, fn_callable):
            nonlocal ok, attempt_count
            if attempt_count >= MAX_STRATEGY_ATTEMPTS:
                return False
            attempt_count += 1
            if verbose:
                print(f"[attempt:{attempt_count}] strategy={name} for N1='{o1.get('text')}'")
            try:
                res = fn_callable()
            except Exception:
                res = False
            # small delay to allow UI to update
            try:
                frame.wait_for_timeout(300)
            except Exception:
                pass
            if res:
                # verify effect (check n2 repopulation or visible selection)
                try:
                    if _verify_selection(page, frame, n1_root, o1, prev_n2_count):
                        ok = True
                        if verbose:
                            print(f"[ok] strategy={name} verified for N1='{o1.get('text')}'")
                        return True
                    else:
                        if verbose:
                            print(f"[verify-failed] strategy={name} for N1='{o1.get('text')}'")
                except Exception:
                    if verbose:
                        print(f"[verify-exc] strategy={name} for N1='{o1.get('text')}'")
            return False

        # prepare named strategy list in order
        strategies = []
        oid = o1.get('id')
        if oid:
            strategies.append(('click_input_label', lambda: _click_input_or_label(frame, oid)))
        strategies.append(('select_by_text_or_attrs', lambda: select_by_text_or_attrs(page, n1_root, o1)))
        try:
            rid = n1_root.get('id')
            strategies.append(('select_from_wrapped_input', lambda: _select_from_wrapped_input(frame, rid, prefer_token=(o1.get('text') or None))))
        except Exception:
            pass
        try:
            if oid:
                base = oid
                for suf in ('-selectized', '-select2', '-wrapper', '_label', '-label'):
                    if base.endswith(suf):
                        base = base[:-len(suf)]; break
                strategies.append(('select_native', lambda: _select_native_select(frame, base, prefer_token=(o1.get('text') or None))))
        except Exception:
            pass

        # execute named strategies until verified or we exhaust the per-option budget
        for name, fn in strategies:
            if _attempt_and_verify_named(name, fn):
                break

        if not ok:
            if verbose:
                print(f"[skip] N1 not selected after {attempt_count} attempts: {o1.get('text')}")
            continue

        # re-resolve n2 root and collect options
        if n2_ids:
            n2_root = _find_control_by_ids(n2_ids) or n2_root
        if n2_root:
            # wait and collect
            try:
                wait_n2_repopulated(page, n2_root, prev_n2_count, timeout_ms=15_000)
            except Exception:
                pass
            try:
                if is_select(n2_root['handle']):
                    o2_all = read_select_options(n2_root['handle']) or []
                else:
                    try:
                        n2_root['handle'].click()
                    except Exception:
                        pass
                    _scroll_listbox_to_end(page)
                    opts = frame.locator('[role=option]')
                    o2_all = []
                    for i in range(opts.count()):
                        el = opts.nth(i)
                        o2_all.append({'text': (el.text_content() or '').strip(), 'value': el.get_attribute('data-value') or el.get_attribute('value')})
                    try:
                        page.keyboard.press('Escape')
                    except Exception:
                        pass
            except Exception:
                o2_all = []

            o2_all = remove_placeholders(o2_all)
            o2_filtered = o2_all[:limit2_per_n1] if limit2_per_n1 and limit2_per_n1 > 0 else o2_all

            if verbose:
                print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> N2 total={len(o2_all)} filtrado={len(o2_filtered)}")

            result['n1_options'].append({'n1': o1, 'n2_options': o2_filtered})
        else:
            if verbose:
                print(f"[N1:{idx}/{len(n1_filtered)}] '{o1.get('text')}' -> no N2 control")
            result['n1_options'].append({'n1': o1, 'n2_options': []})

    return result
