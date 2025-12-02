"""
E-Agendas Fetch module for SnapTrack UI.

Modelo simplificado: Órgão → Agentes (direto, sem cargo intermediário).
O usuário seleciona o órgão e busca diretamente pelo nome do agente.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from dou_snaptrack.constants import (
    ALLOW_TLS_BYPASS_ENV,
    CACHE_TTL_MEDIUM,
    SAVE_DEBUG_SCRIPT_ENV,
)
from dou_snaptrack.ui.subprocess_utils import execute_script_and_read_result

# Module-level constants
SRC_ROOT = Path(__file__).resolve().parents[2]
CWD_ROOT = str(SRC_ROOT)

# E-Agendas Selectize element IDs
DD_ORGAO_ID = "filtro_orgao_entidade"
DD_CARGO_ID = "filtro_cargo"
DD_AGENTE_ID = "filtro_servidor"

# Logger
logger = logging.getLogger("dou_snaptrack.ui.eagendas_fetch")


def _prepare_subprocess_env(base_env: dict | None = None) -> dict:
    """Prepare and sanitize the env dict for subprocesses."""
    env = os.environ.copy()
    if base_env:
        env.update(base_env)

    # Prefer venv-local pw-browsers when available
    try:
        venv_browsers = Path(sys.executable).parent.parent / "pw-browsers"
        if venv_browsers.exists():
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(venv_browsers)
    except Exception:
        pass

    # TLS bypass only when explicitly enabled (opt-in)
    allow_tls = os.environ.get(ALLOW_TLS_BYPASS_ENV, "0").strip().lower() in ("1", "true", "yes")
    if not allow_tls and env.get("NODE_TLS_REJECT_UNAUTHORIZED") == "0":
        env.pop("NODE_TLS_REJECT_UNAUTHORIZED", None)
    elif allow_tls:
        env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"

    return env


def _make_error(msg: str) -> dict[str, Any]:
    """Return a standardized error payload for child-script results."""
    return {"success": False, "options": [], "error": str(msg)}


# Script template using $PLACEHOLDER$ style to avoid brace conflicts
_SCRIPT_TEMPLATE = r'''
import sys, json, os
from pathlib import Path

src_root = $SRC_ROOT$
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from playwright.sync_api import sync_playwright

DD_ORGAO_ID = '$DD_ORGAO_ID$'
DD_AGENTE_ID = '$DD_AGENTE_ID$'
LEVEL = $LEVEL$
N1V = $N1V$


def get_selectize_options(page, element_id: str):
    """Extract options from a Selectize dropdown."""
    return page.evaluate("""(id) => {
        const el = document.getElementById(id);
        if (!el || !el.selectize) return [];
        const s = el.selectize;
        const out = [];
        const opts = s.options || {};
        for (const [val, raw] of Object.entries(opts)) {
            const v = String(val ?? '');
            const t = (raw && (raw.text || raw.label || raw.nome || raw.name)) || v;
            if (!t) continue;
            out.push({ value: v, text: String(t) });
        }
        return out;
    }""", element_id)


def set_selectize_value(page, element_id: str, value: str):
    """Set a value in a Selectize dropdown."""
    return page.evaluate("""(args) => {
        const { id, value } = args;
        const el = document.getElementById(id);
        if (!el || !el.selectize) return false;
        el.selectize.setValue(String(value), false);
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }""", {'id': element_id, 'value': value})


def main():
    # E-Agendas detecta headless. Usamos headless=False + --start-minimized
    # Tambem negamos permissao de geolocalizacao para evitar popup bloqueante
    LAUNCH_ARGS = [
        '--start-minimized',
        '--disable-blink-features=AutomationControlled',
        '--ignore-certificate-errors',
    ]
    
    with sync_playwright() as p:
        browser = None
        
        # Tentar Chrome primeiro, depois Edge
        for channel in ['chrome', 'msedge']:
            try:
                print(f'[DEBUG] Tentando channel={channel}...', file=sys.stderr, flush=True)
                browser = p.chromium.launch(channel=channel, headless=False, args=LAUNCH_ARGS)
                print(f'[DEBUG] OK {channel}', file=sys.stderr, flush=True)
                break
            except Exception as e:
                print(f'[DEBUG] {channel} falhou: {e}', file=sys.stderr, flush=True)
        
        # Fallback: buscar executavel manualmente
        if not browser:
            exe_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            ]
            for exe in exe_paths:
                if Path(exe).exists():
                    try:
                        browser = p.chromium.launch(executable_path=exe, headless=False, args=LAUNCH_ARGS)
                        print(f'[DEBUG] executable_path OK', file=sys.stderr, flush=True)
                        break
                    except Exception:
                        pass
        
        if not browser:
            raise RuntimeError('Nenhum browser disponivel (Chrome/Edge)')
        
        # Criar contexto NEGANDO permissoes de geolocalizacao
        # Isso evita o popup "Este site quer saber sua localizacao"
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1280, 'height': 900},
            permissions=[],  # Negar todas as permissoes
            geolocation=None,
        )
        context.set_default_timeout(60000)
        
        page = context.new_page()
        
        print('[DEBUG] Navegando para eagendas.cgu.gov.br...', file=sys.stderr, flush=True)
        page.goto('https://eagendas.cgu.gov.br/', wait_until='commit', timeout=30000)
        page.wait_for_timeout(5000)  # Aguardar AngularJS carregar
        
        # Aguardar selectize de orgaos inicializar
        wait_orgao_js = "() => { const el = document.getElementById('" + DD_ORGAO_ID + "'); return el?.selectize && Object.keys(el.selectize.options||{}).length > 5; }"
        try:
            page.wait_for_function(wait_orgao_js, timeout=20000)
            print('[DEBUG] Selectize inicializado', file=sys.stderr, flush=True)
        except Exception as e:
            print(f'[DEBUG] Selectize nao inicializou: {e}', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return []
        
        if LEVEL == 1:
            # Buscar lista de orgaos
            orgs = get_selectize_options(page, DD_ORGAO_ID)
            out = [o for o in orgs if 'selecione' not in o['text'].lower()]
            print(f'[DEBUG] Retornando {len(out)} orgaos', file=sys.stderr, flush=True)
            context.close()
            browser.close()
            return out
        
        # LEVEL 2: Buscar agentes diretamente apos selecionar orgao
        print(f'[DEBUG] Selecionando orgao={N1V}...', file=sys.stderr, flush=True)
        set_selectize_value(page, DD_ORGAO_ID, N1V)
        page.wait_for_timeout(3000)  # Aguardar agentes carregarem
        
        # Aguardar selectize de agentes
        wait_agente_js = "() => { const el = document.getElementById('" + DD_AGENTE_ID + "'); return el?.selectize && Object.keys(el.selectize.options||{}).length > 0; }"
        try:
            page.wait_for_function(wait_agente_js, timeout=15000)
        except Exception:
            pass  # Pode nao ter agentes disponiveis
        
        # Buscar agentes diretamente (pula cargo)
        agentes = get_selectize_options(page, DD_AGENTE_ID)
        out = [
            o for o in agentes 
            if o.get('value') not in ['-1', ''] 
            and 'selecione' not in o['text'].lower()
            and 'todos os ocupantes' not in o['text'].lower()
        ]
        print(f'[DEBUG] Retornando {len(out)} agentes', file=sys.stderr, flush=True)
        
        context.close()
        browser.close()
        return out


# Execute
try:
    data = main()
    payload = {'success': True, 'options': data}
    out_path = os.environ.get('RESULT_JSON_PATH')
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
    else:
        print(json.dumps(payload, ensure_ascii=False))
except Exception as e:
    import traceback
    err_msg = str(type(e).__name__) + ': ' + str(e)
    payload = {
        'success': False,
        'error': err_msg,
        'traceback': traceback.format_exc()[:500]
    }
    out_path = os.environ.get('RESULT_JSON_PATH')
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
    else:
        print(json.dumps(payload, ensure_ascii=False))
'''


def _build_fetch_script(level: int, n1_value: str | None = None) -> str:
    """Build the Playwright script for fetching E-Agendas options.
    
    Args:
        level: 1=Órgãos, 2=Agentes (direto pelo órgão)
        n1_value: ID do órgão selecionado (obrigatório para level 2)
    """
    src_path = str(SRC_ROOT).replace("\\", "\\\\")

    script = _SCRIPT_TEMPLATE
    script = script.replace('$SRC_ROOT$', json.dumps(src_path, ensure_ascii=False))
    script = script.replace('$DD_ORGAO_ID$', DD_ORGAO_ID)
    script = script.replace('$DD_AGENTE_ID$', DD_AGENTE_ID)
    script = script.replace('$LEVEL$', str(level))
    script = script.replace('$N1V$', json.dumps(n1_value or '', ensure_ascii=False))

    return script


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_MEDIUM)
def fetch_orgaos() -> dict[str, Any]:
    """Fetch lista de órgãos do E-Agendas.
    
    Returns:
        dict: {"success": bool, "options": [{"label", "value"}], "error": str}
    """
    return _execute_fetch(level=1)


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_MEDIUM)
def fetch_agentes(orgao_id: str) -> dict[str, Any]:
    """Fetch lista de agentes de um órgão (direto, sem cargo intermediário).
    
    Args:
        orgao_id: ID do órgão selecionado
        
    Returns:
        dict: {"success": bool, "options": [{"label", "value"}], "error": str}
    """
    if not orgao_id:
        return _make_error("ID do órgão é obrigatório")
    return _execute_fetch(level=2, n1_value=orgao_id)


def _execute_fetch(level: int, n1_value: str | None = None) -> dict[str, Any]:
    """Execute fetch script and return normalized results."""
    script_content = _build_fetch_script(level=level, n1_value=n1_value)

    overrides = {
        'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1',
        'PYTHONUNBUFFERED': '1',
    }
    env = _prepare_subprocess_env(overrides)

    try:
        # Optionally save debug script
        save_debug = os.environ.get(SAVE_DEBUG_SCRIPT_ENV, '0').strip().lower() in ('1', 'true', 'yes')
        if save_debug:
            debug_script = Path(__file__).parent / f"_eagendas_debug_level{level}.py"
            try:
                debug_script.write_text(script_content, encoding='utf-8')
                logger.debug("Script salvo em: %s", debug_script)
            except Exception:
                logger.exception("Falha ao salvar debug script")

        # Timeout
        timeout = int(os.environ.get("DOU_UI_EAGENDAS_TIMEOUT", "90"))
        logger.debug("Executando eagendas subprocess (level=%s, timeout=%s)", level, timeout)

        data, stderr = execute_script_and_read_result(
            script_content=script_content,
            timeout=timeout,
            cwd=CWD_ROOT,
            extra_env=env,
        )
        logger.debug("fetch stderr_len=%s", len(stderr or ""))

        if not data:
            logger.debug("E-Agendas subprocess produced no JSON result")
            return _make_error("Sem resultado do subprocess")

        if not data.get('success'):
            return _make_error(data.get('error', 'Erro desconhecido'))

        # Normalize output
        raw_opts = data.get('options') or []
        norm = []
        for o in raw_opts:
            lbl = (o.get('text') or o.get('label') or '').strip()
            val = (o.get('value') or '').strip()
            if not lbl or not val:
                continue
            norm.append({'label': lbl, 'value': val})

        # Sort by label
        norm = sorted(norm, key=lambda x: x['label'].lower())
        return {"success": True, "options": norm, "error": ""}

    except subprocess.TimeoutExpired:
        logger.error("Timeout ao executar eagendas subprocess (level=%s)", level)
        return _make_error("Timeout (eagendas)")
    except Exception as e:
        logger.exception("Erro ao executar eagendas subprocess")
        return _make_error(f"{type(e).__name__}: {e}")


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

@st.cache_data(show_spinner=False, ttl=CACHE_TTL_MEDIUM)
def fetch_hierarchy(
    level: int = 1,
    n1_value: str | None = None,
    n2_value: str | None = None,
) -> dict[str, Any]:
    """Backward compatibility wrapper.
    
    DEPRECATED: Use fetch_orgaos() and fetch_agentes() instead.
    
    Args:
        level: 1=Órgãos, 2=Agentes (n2_value is ignored)
        n1_value: ID do órgão
        n2_value: Ignorado (modelo antigo com cargo foi removido)
    """
    if level == 1:
        return fetch_orgaos()
    elif level in (2, 3):
        # Ambos level 2 e 3 agora buscam agentes diretamente
        if not n1_value:
            return _make_error("ID do órgão é obrigatório")
        return fetch_agentes(n1_value)
    else:
        return _make_error(f"Level inválido: {level}")


# Alias for backward compatibility
_eagendas_fetch_hierarchy = fetch_hierarchy
