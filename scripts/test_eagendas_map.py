from __future__ import annotations
import re, json, time
from pathlib import Path

from dou_snaptrack.utils.browser import launch_browser, new_context, goto, build_url
from dou_snaptrack.utils.dom import find_best_frame
from dou_snaptrack.mappers.page_mapper import map_dropdowns, map_elements_by_category

OUT = Path("test_eagendas_map.json")

def is_placeholder_text(t: str) -> bool:
    if not t:
        return True
    nt = t.strip().lower()
    placeholders = ["selecionar", "selecione", "escolha", "todos", "todas", "selecionar organizacao subordinada", "selecione uma opcao"]
    return any(nt == p or nt.startswith(p + " ") for p in placeholders)


def main():
    p, browser = launch_browser(headful=False, slowmo=0)
    try:
        context = new_context(browser)
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(60_000)

        url = build_url('eagendas', path=None)
        print(f"Opening {url}")
        goto(page, url)
        time.sleep(1)

        frame = find_best_frame(context) or page.main_frame

        # Try to find a combobox or select
        try:
            comboboxes = frame.get_by_role('combobox')
            cnt = comboboxes.count()
        except Exception:
            cnt = 0
        print(f"Combobox count: {cnt}")

        selected = None
        if cnt > 0:
            try:
                cb = comboboxes.first
                cb.click(timeout=3000)
                page.wait_for_timeout(500)
                # try to find options in the opened list
                try:
                    opts = frame.get_by_role('option')
                    ocnt = opts.count()
                except Exception:
                    ocnt = 0
                print(f"Options found by role option: {ocnt}")
                for i in range(ocnt):
                    try:
                        o = opts.nth(i)
                        txt = (o.text_content() or "").strip()
                        if is_placeholder_text(txt):
                            continue
                        print(f"Selecting option: {txt}")
                        o.click(timeout=2000)
                        page.wait_for_load_state('networkidle', timeout=60_000)
                        selected = txt
                        break
                    except Exception as e:
                        print("option click failed:", e)
                if not selected:
                    print("No selectable option found in role options")
            except Exception as e:
                print("combobox open failed:", e)

        # Fallback: try native <select>
        if not selected:
            try:
                selects = frame.locator('select')
                scnt = selects.count()
            except Exception:
                scnt = 0
            print(f"Select elements count: {scnt}")
            if scnt > 0:
                s = selects.first
                try:
                    # pick first non-placeholder option
                    options = s.locator('option')
                    for i in range(options.count()):
                        o = options.nth(i)
                        txt = (o.text_content() or "").strip()
                        if is_placeholder_text(txt):
                            continue
                        val = o.get_attribute('value') or txt
                        print(f"Selecting native option: {txt}")
                        s.select_option(value=val)
                        page.wait_for_load_state('networkidle', timeout=60_000)
                        selected = txt
                        break
                except Exception as e:
                    print("native select failed:", e)

        # Try to click a search button if present
        if selected:
            try:
                btn = page.get_by_role('button', name=re.compile(r"Pesquisar|Buscar|Procurar|Search", re.I)).first
                if btn and btn.count() > 0:
                    try:
                        btn.click()
                        page.wait_for_load_state('networkidle', timeout=60_000)
                        print("Clicked search button")
                    except Exception as e:
                        print("search button click failed:", e)
            except Exception:
                pass

        # Finally, map dropdowns and elements
        try:
            dd = map_dropdowns(frame, open_combos=False)
            elements = map_elements_by_category(frame)
            result = {"url": page.url, "selected": selected, "dropdowns": dd, "elements": elements}
            OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Mapping saved to {OUT}")
        except Exception as e:
            print("Mapping failed:", e)

    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass

if __name__ == '__main__':
    main()
