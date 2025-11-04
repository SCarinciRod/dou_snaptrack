"""
Quick start para sistema de atualização automática e-agendas.

Execute este script para:
1. Verificar status do artefato
2. Opcionalmente gerar artefato inicial
3. Configurar atualização mensal
"""
from pathlib import Path
import subprocess
import sys

print("=" * 80)
print("SETUP: SISTEMA DE ATUALIZAÇÃO AUTOMÁTICA E-AGENDAS")
print("=" * 80)
print()

# [1] Verificar artefato
print("[1/3] Verificando artefato existente...")
print()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dou_snaptrack.utils.artifact_checker import check_artifact_age, print_artifact_status

status = check_artifact_age()
print_artifact_status(status)
print()

# [2] Gerar artefato se necessário
if not status["exists"] or status["is_critical"]:
    print("[2/3] Artefato precisa ser gerado/atualizado")
    print()
    print("⚠️  ATENÇÃO: A geração inicial pode levar 3-4 horas!")
    print()
    
    response = input("Deseja gerar o artefato AGORA? (S/N): ").strip().upper()
    
    if response == 'S':
        print()
        print("Iniciando geração do artefato...")
        print("Logs em: logs/artifact_updates/")
        print()
        
        update_script = Path(__file__).parent / "update_eagendas_artifact.py"
        result = subprocess.run(
            [sys.executable, str(update_script)],
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            print()
            print("✅ Artefato gerado com sucesso!")
        else:
            print()
            print("❌ Erro ao gerar artefato. Verifique os logs.")
            sys.exit(1)
    else:
        print()
        print("⚠️  Geração cancelada.")
        print()
        print("Você pode gerar manualmente depois:")
        print("  python scripts/update_eagendas_artifact.py")
        print()
else:
    print("[2/3] Artefato OK, não precisa atualizar agora")
    print()

# [3] Configurar Task Scheduler
print("[3/3] Configurar atualização mensal automática")
print()
print("Para configurar a task mensal (dia 1 às 02:00):")
print("  1. Abra PowerShell como ADMINISTRADOR")
print("  2. Execute: .\\scripts\\setup_monthly_update.ps1")
print()
print("Ou execute agora:")

response = input("Abrir PowerShell Admin para configurar task? (S/N): ").strip().upper()

if response == 'S':
    ps_script = Path(__file__).parent / "setup_monthly_update.ps1"
    
    # Abrir PowerShell como admin
    import os
    if os.name == 'nt':  # Windows
        subprocess.run([
            "powershell",
            "-Command",
            f"Start-Process powershell -Verb RunAs -ArgumentList '-NoExit', '-File', '{ps_script.absolute()}'"
        ])
        print()
        print("✅ PowerShell Admin aberto. Siga as instruções na janela.")
    else:
        print("❌ Só funciona no Windows")
else:
    print()
    print("OK. Configure manualmente quando quiser:")
    print("  .\\scripts\\setup_monthly_update.ps1 (como Admin)")

print()
print("=" * 80)
print("SETUP CONCLUÍDO!")
print("=" * 80)
print()
print("PRÓXIMOS PASSOS:")
print("  1. ✅ Artefato disponível em: artefatos/pairs_eagendas_latest.json")
print("  2. 📅 Configure task mensal (se ainda não fez)")
print("  3. 🚀 Use na aplicação via plan_live_eagendas.py")
print()
print("Ver documentação completa: docs/EAGENDAS_AUTO_UPDATE.md")
print()
