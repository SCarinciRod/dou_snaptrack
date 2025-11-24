import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

src_root = 'C:\\Projetos\\src'
if src_root not in sys.path:
    sys.path.insert(0, src_root)
# DEBUG: Verificar ambiente
print(f'[ENV] PLAYWRIGHT_BROWSERS_PATH={os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "NOT_SET")}', file=sys.stderr, flush=True)
print(f'[ENV] src_root={src_root}', file=sys.stderr, flush=True)

DD_ORGAO_ID = 'filtro_orgao_entidade'
DD_CARGO_ID = 'filtro_cargo'
DD_AGENTE_ID = 'filtro_servidor'
LEVEL = 1
N1V = ""
N2V = ""
def get_selectize_options(page, element_id: str):
    return page.evaluate("(id) => {\n        const el = document.getElementById(id);\n        if (!el || !el.selectize) return [];\n        const s = el.selectize;\n        const out = [];\n        const opts = s.options || {};\n        for (const [val, raw] of Object.entries(opts)) {\n            const v = String(val ?? '');\n            const t = (raw && (raw.text || raw.label || raw.nome || raw.name)) || v;\n            if (!t) continue;\n            out.push({ value: v, text: String(t) });\n        }\n        return out;\n    }", element_id)
def set_selectize_value(page, element_id: str, value: str):
    return page.evaluate("(args) => {\n        const { id, value } = args;\n        const el = document.getElementById(id);\n        if (!el || !el.selectize) return false;\n        el.selectize.setValue(String(value), false);\n        el.dispatchEvent(new Event('change', { bubbles: true }));\n        el.dispatchEvent(new Event('input', { bubbles: true }));\n        return true;\n    }", { 'id': element_id, 'value': value })
def main():
    import os
    import sys
    diagnostics = {'console_errors': [], 'network_errors': [], 'dom_checks': {}}
    with sync_playwright() as p:
        browser = None
        # Usar mesma estratégia do plan_live_async.py: tentar channels primeiro, depois fallback para executável
        try:
            print('[DEBUG] Tentando channel=chrome...', file=sys.stderr, flush=True)
            browser = p.chromium.launch(channel='chrome', headless=True)
            print('[DEBUG] ✓ channel=chrome OK', file=sys.stderr, flush=True)
        except Exception as e1:
            print(f'[DEBUG] ✗ channel=chrome falhou: {e1}', file=sys.stderr, flush=True)
            try:
                print('[DEBUG] Tentando channel=msedge...', file=sys.stderr, flush=True)
                browser = p.chromium.launch(channel='msedge', headless=True)
                print('[DEBUG] ✓ channel=msedge OK', file=sys.stderr, flush=True)
            except Exception as e2:
                print(f'[DEBUG] ✗ channel=msedge falhou: {e2}', file=sys.stderr, flush=True)
                # Fallback: buscar executável explícito (evita PermissionError em ambientes restritos)
                exe = os.environ.get('PLAYWRIGHT_CHROME_PATH') or os.environ.get('CHROME_PATH')
                if not exe:
                    for c in (
                        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                    ):
                        if Path(c).exists():
                            exe = c
                            break
                if exe and Path(exe).exists():
                    print(f'[DEBUG] Tentando executable_path={exe}...', file=sys.stderr, flush=True)
                    browser = p.chromium.launch(executable_path=exe, headless=True)
                    print('[DEBUG] ✓ executable_path OK', file=sys.stderr, flush=True)
        # Se ainda não conseguiu, tentar download padrão (último recurso)
        if not browser:
            print('[DEBUG] Tentando launch padrão...', file=sys.stderr, flush=True)
            browser = p.chromium.launch(headless=True)
            print('[DEBUG] ✓ launch padrão OK', file=sys.stderr, flush=True)
        context = browser.new_context(ignore_https_errors=True, viewport={'width':1280,'height':900})
        context.set_default_timeout(60000)
        page = context.new_page()
        page.on('console', lambda msg: diagnostics['console_errors'].append(msg.text) if msg.type in ['error','warning'] else None)
        page.on('requestfailed', lambda req: diagnostics['network_errors'].append(req.url))
        print('[DEBUG] Navegando para eagendas.cgu.gov.br...', file=sys.stderr, flush=True)
        page.goto('https://eagendas.cgu.gov.br/', wait_until='domcontentloaded')
        print('[DEBUG] Página carregada, verificando DOM...', file=sys.stderr, flush=True)
        diagnostics['dom_checks']['element_exists'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')")
        diagnostics['dom_checks']['has_selectize_class'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')?.classList.contains('selectized')")
        diagnostics['dom_checks']['selectize_obj'] = page.evaluate(f"!!document.getElementById('{DD_ORGAO_ID}')?.selectize")
        try:
            print('[DEBUG] Aguardando selectize inicializar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return !!(el && el.selectize); }}", timeout=20000)
            print('[DEBUG] ✓ Selectize inicializado', file=sys.stderr, flush=True)
        except Exception as e:
            diagnostics['wait_error'] = str(e)
            print(f'[DEBUG] ✗ Selectize não inicializou: {e}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return []
        if LEVEL == 1:
            print('[DEBUG] Esperando selectize com >5 opções...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_ORGAO_ID}'); return el?.selectize && Object.keys(el.selectize.options||{{}}).length > 5; }}", timeout=15000)
            print('[DEBUG] Wait concluído, lendo options_count...', file=sys.stderr, flush=True)
            options_count = page.evaluate(f"Object.keys(document.getElementById('{DD_ORGAO_ID}')?.selectize?.options || {{}}).length")
            diagnostics['dom_checks']['options_count'] = options_count
            print(f'[DEBUG] options_count={options_count}, chamando get_selectize_options...', file=sys.stderr, flush=True)
            orgs = get_selectize_options(page, DD_ORGAO_ID)
            print(f'[DEBUG] get_selectize_options retornou {len(orgs)} items', file=sys.stderr, flush=True)
            out = [o for o in orgs if 'selecione' not in o['text'].lower()]
            diagnostics['result_count'] = len(out)
            diagnostics['raw_orgs_sample'] = orgs[:3] if orgs else []
            if len(out) == 0:
                diagnostics['screenshot'] = page.screenshot(type='png', full_page=False)
            print(f'[DIAG] {json.dumps(diagnostics, default=str, ensure_ascii=False)}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return out
        print(f'[DEBUG] Selecionando N1={N1V}...', file=sys.stderr, flush=True)
        set_selectize_value(page, DD_ORGAO_ID, N1V)
        page.wait_for_timeout(1000)
        try:
            print('[DEBUG] Aguardando N2 carregar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_CARGO_ID}'); return !!(el && el.selectize); }}", timeout=10000)
        except Exception:
            pass
        if LEVEL == 2:
            cargos = get_selectize_options(page, DD_CARGO_ID)
            out = [o for o in cargos if 'selecione' not in o['text'].lower()]
            print(f'[DEBUG] N2 retornou {len(out)} cargos', file=sys.stderr, flush=True)
            # Se N2 vazio, tentar N3 como fallback
            if len(out) == 0:
                print('[DEBUG] N2 vazio, tentando N3 (agentes) como fallback...', file=sys.stderr, flush=True)
                try:
                    page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return !!(el && el.selectize); }}", timeout=10000)
                    agentes = get_selectize_options(page, DD_AGENTE_ID)
                    out = [o for o in agentes if o.get('value') != '-1' and 'selecione' not in o['text'].lower() and 'todos os ocupantes' not in o['text'].lower()]
                    print(f'[DEBUG] N3 fallback retornou {len(out)} agentes', file=sys.stderr, flush=True)
                except Exception as e:
                    print(f'[DEBUG] N3 fallback falhou: {e}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return out
        print(f'[DEBUG] Selecionando N2={N2V}...', file=sys.stderr, flush=True)
        set_selectize_value(page, DD_CARGO_ID, N2V)
        page.wait_for_timeout(1000)
        try:
            print('[DEBUG] Aguardando N3 carregar...', file=sys.stderr, flush=True)
            page.wait_for_function(f"() => {{ const el = document.getElementById('{DD_AGENTE_ID}'); return !!(el && el.selectize); }}", timeout=10000)
        except Exception:
            pass
        agentes = get_selectize_options(page, DD_AGENTE_ID)
        out = [o for o in agentes if o.get('value') != '-1' and 'selecione' not in o['text'].lower() and 'todos os ocupantes' not in o['text'].lower()]
        print(f'[DEBUG] N3 retornou {len(out)} agentes', file=sys.stderr, flush=True)
        context.close()
        browser.close()
        return out
try:
    data = main()
    print(json.dumps({'success': True, 'options': data}))
except Exception as e:
    import traceback
    print(json.dumps({'success': False, 'error': str(type(e).__name__) + ': ' + str(e), 'traceback': traceback.format_exc()[:400]}))
