# cleanup_batch.ps1 - Script para limpar processos travados do batch
# Uso: .\scripts\cleanup_batch.ps1

Write-Host "=== DOU SnapTrack - Cleanup de Batch ===" -ForegroundColor Cyan

# 1. Remover locks
Write-Host "`n1. Removendo locks..." -ForegroundColor Yellow
$locks = @(
    "resultados\batch.lock",
    "resultados\ui.lock"
)
foreach ($lock in $locks) {
    if (Test-Path $lock) {
        Remove-Item -Force $lock -ErrorAction SilentlyContinue
        Write-Host "   Removido: $lock" -ForegroundColor Green
    }
}

# 2. Matar processos Python do worker_entry
Write-Host "`n2. Procurando processos worker_entry..." -ForegroundColor Yellow
$workers = Get-WmiObject Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -match "worker_entry" }

if ($workers) {
    foreach ($w in $workers) {
        Write-Host "   Matando PID $($w.ProcessId): $($w.CommandLine.Substring(0, [Math]::Min(80, $w.CommandLine.Length)))..." -ForegroundColor Red
        Stop-Process -Id $w.ProcessId -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "   Nenhum worker encontrado" -ForegroundColor Gray
}

# 3. Limpar arquivos de PIDs ativos
Write-Host "`n3. Limpando arquivos de PIDs..." -ForegroundColor Yellow
$pidFiles = Get-ChildItem -Path "resultados" -Filter "_active_pids.json" -Recurse -ErrorAction SilentlyContinue
foreach ($pf in $pidFiles) {
    try {
        $data = Get-Content $pf.FullName | ConvertFrom-Json
        foreach ($pid in $data.pids) {
            if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
                Write-Host "   Matando PID $pid..." -ForegroundColor Red
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $pf.FullName -Force
        Write-Host "   Removido: $($pf.FullName)" -ForegroundColor Green
    } catch {
        # Ignorar erros
    }
}

# 4. Executar cleanup via Python
Write-Host "`n4. Executando cleanup via Python..." -ForegroundColor Yellow
$venvPython = ".\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pyScript = @'
from dou_snaptrack.ui.batch_runner import cleanup_batch_processes
result = cleanup_batch_processes()
if result["killed_pids"]:
    print("   PIDs terminados:", result["killed_pids"])
if result["removed_locks"]:
    print("   Locks removidos:", result["removed_locks"])
if result["errors"]:
    print("   Erros:", result["errors"])
if not result["killed_pids"] and not result["removed_locks"] and not result["errors"]:
    print("   Nada a limpar")
'@
    $pyScript | & $venvPython -
}

Write-Host "`n=== Cleanup concluido ===" -ForegroundColor Cyan
Write-Host "Agora voce pode reiniciar a UI com: .\scripts\run-ui.ps1" -ForegroundColor White
