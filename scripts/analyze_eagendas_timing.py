#!/usr/bin/env python
"""
Instrumentação de Performance - E-Agendas Fetch

Este script adiciona logging detalhado de timing ao eagendas_fetch.py
para diagnosticar onde o tempo está sendo gasto na UI.

Uso:
    1. Rode este script para ver o código atual
    2. Execute fetch via UI
    3. Verifique logs em logs/eagendas_timing.log
"""

import re
from pathlib import Path
from datetime import datetime

# Arquivo alvo
FETCH_FILE = Path(__file__).parent.parent / "src" / "dou_snaptrack" / "ui" / "eagendas_fetch.py"

def analyze_fetch_code():
    """Analisa o código atual do eagendas_fetch.py"""
    if not FETCH_FILE.exists():
        print(f"❌ Arquivo não encontrado: {FETCH_FILE}")
        return
    
    content = FETCH_FILE.read_text(encoding="utf-8")
    
    print("=" * 60)
    print("📊 ANÁLISE DO CÓDIGO - eagendas_fetch.py")
    print("=" * 60)
    
    # Buscar wait_for_timeout
    timeouts = re.findall(r'wait_for_timeout\((\d+)\)', content)
    print(f"\n🕐 wait_for_timeout encontrados: {len(timeouts)}")
    for t in timeouts:
        print(f"   - {t}ms")
    
    # Buscar wait_for_function
    functions = re.findall(r'wait_for_function\([^)]+\)', content)
    print(f"\n⚡ wait_for_function encontrados: {len(functions)}")
    
    # Buscar subprocess.run/Popen
    subprocess_calls = len(re.findall(r'subprocess\.(run|Popen)', content))
    print(f"\n🔄 Chamadas subprocess: {subprocess_calls}")
    
    # Verificar se usa _SCRIPT_TEMPLATE
    if "_SCRIPT_TEMPLATE" in content:
        print("\n📜 Usa _SCRIPT_TEMPLATE (script inline)")
        
        # Extrair template
        match = re.search(r'_SCRIPT_TEMPLATE\s*=\s*["\']+(.*?)["\']+ *$', content, re.MULTILINE | re.DOTALL)
        if match:
            template = match.group(0)[:500]
            print(f"   Preview: {template[:200]}...")
    
    print("\n" + "=" * 60)
    print("💡 RECOMENDAÇÃO")
    print("=" * 60)
    
    if timeouts:
        total_timeout = sum(int(t) for t in timeouts)
        print(f"\n⚠️  Total de esperas fixas: {total_timeout}ms ({total_timeout/1000:.1f}s)")
        print("   Isso pode ser otimizado com wait_for_function!")
    else:
        print("\n✅ Nenhum wait_for_timeout fixo encontrado.")
        print("   O código já está otimizado!")


def check_collect_subprocess():
    """Analisa o código atual do eagendas_collect_subprocess.py"""
    collect_file = Path(__file__).parent.parent / "src" / "dou_snaptrack" / "ui" / "eagendas_collect_subprocess.py"
    
    if not collect_file.exists():
        print(f"❌ Arquivo não encontrado: {collect_file}")
        return
    
    content = collect_file.read_text(encoding="utf-8")
    
    print("\n" + "=" * 60)
    print("📊 ANÁLISE DO CÓDIGO - eagendas_collect_subprocess.py")
    print("=" * 60)
    
    # Buscar wait_for_timeout
    timeouts = re.findall(r'wait_for_timeout\((\d+)\)', content)
    print(f"\n🕐 wait_for_timeout encontrados: {len(timeouts)}")
    for t in timeouts:
        print(f"   - {t}ms")
    
    # Buscar wait_for_function
    functions = re.findall(r'wait_for_function\(', content)
    print(f"\n⚡ wait_for_function encontrados: {len(functions)}")
    
    # Buscar angular_ready_js
    if "angular_ready_js" in content or "angular" in content.lower():
        print("\n✅ Usa condição AngularJS")
    
    if "selectize" in content.lower():
        print("✅ Usa condição Selectize")
    
    if "calendar" in content.lower():
        print("✅ Usa condição Calendar")


def show_timing_instructions():
    """Mostra instruções para adicionar timing manual"""
    print("\n" + "=" * 60)
    print("📋 COMO MEDIR TIMING NA UI")
    print("=" * 60)
    
    print("""
Para medir o tempo real de cada operação na UI:

1. Abra o arquivo de log durante execução:
   - logs/ui_debug.log
   - logs/eagendas_*.log (se existir)

2. Ou adicione print statements temporários:
   
   import time
   start = time.perf_counter()
   # ... operação ...
   print(f"[TIMING] Operação X: {time.perf_counter() - start:.2f}s")

3. Verifique o console do Streamlit (terminal onde rodou)

4. Use o DevTools do browser (F12 > Network) para ver requests
""")


if __name__ == "__main__":
    analyze_fetch_code()
    check_collect_subprocess()
    show_timing_instructions()
