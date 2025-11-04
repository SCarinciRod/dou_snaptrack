# Script para configurar atualização mensal automática do artefato e-agendas
# Cria uma Task no Windows Task Scheduler que roda no dia 1 de cada mês às 02:00

$ErrorActionPreference = "Stop"

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 78) -ForegroundColor Cyan
Write-Host "CONFIGURAÇÃO DE ATUALIZAÇÃO MENSAL - E-AGENDAS" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 78) -ForegroundColor Cyan
Write-Host ""

# Verificar se está rodando como administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "AVISO: Este script requer privilégios de administrador." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Deseja continuar com elevação de privilégios? (S/N)" -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -eq 'S' -or $response -eq 's') {
        # Reiniciar como administrador
        Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        exit
    } else {
        Write-Host "Operação cancelada." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[OK] Rodando como administrador" -ForegroundColor Green
Write-Host ""

# Configurações
$projectPath = "C:\Projetos"
$pythonExe = "$projectPath\.venv\Scripts\python.exe"
$scriptPath = "$projectPath\scripts\update_eagendas_artifact.py"
$logPath = "$projectPath\logs\artifact_updates"

# Verificar se os arquivos existem
Write-Host "Verificando arquivos necessários..." -ForegroundColor Cyan

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERRO: Python não encontrado em: $pythonExe" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Python: $pythonExe" -ForegroundColor Green

if (-not (Test-Path $scriptPath)) {
    Write-Host "ERRO: Script não encontrado em: $scriptPath" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Script: $scriptPath" -ForegroundColor Green

# Criar diretório de logs se não existir
if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
}
Write-Host "  [OK] Diretório de logs: $logPath" -ForegroundColor Green
Write-Host ""

# Configurações da Task
$taskName = "DouSnapTrack_EAgendasUpdate"
$taskDescription = "Atualização mensal automática do artefato de pares Órgão→Cargo→Agente do e-agendas"

# Remover task existente (se houver)
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removendo task existente..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "  [OK] Task removida" -ForegroundColor Green
    Write-Host ""
}

# Criar ação
Write-Host "Criando nova task agendada..." -ForegroundColor Cyan

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $projectPath

Write-Host "  [OK] Ação configurada" -ForegroundColor Green

# Criar trigger (dia 1 de cada mês às 02:00)
$trigger = New-ScheduledTaskTrigger `
    -Monthly `
    -DaysOfMonth 1 `
    -At "02:00AM"

Write-Host "  [OK] Agendamento: Dia 1 de cada mês às 02:00" -ForegroundColor Green

# Configurações adicionais
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Write-Host "  [OK] Configurações aplicadas" -ForegroundColor Green

# Criar principal (usuário atual)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

Write-Host "  [OK] Usuário: $env:USERNAME" -ForegroundColor Green

# Registrar task
Register-ScheduledTask `
    -TaskName $taskName `
    -Description $taskDescription `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "  [OK] Task registrada com sucesso!" -ForegroundColor Green
Write-Host ""

# Verificar task criada
$task = Get-ScheduledTask -TaskName $taskName

Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 78) -ForegroundColor Green
Write-Host "TASK AGENDADA COM SUCESSO!" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 78) -ForegroundColor Green
Write-Host ""
Write-Host "Nome: $taskName" -ForegroundColor White
Write-Host "Status: $($task.State)" -ForegroundColor White
Write-Host "Próxima execução: " -NoNewline -ForegroundColor White

# Calcular próxima execução
$nextRun = $task.Triggers[0].StartBoundary
if ($nextRun) {
    Write-Host $nextRun -ForegroundColor Cyan
} else {
    # Calcular manualmente
    $now = Get-Date
    $nextMonth = $now.AddMonths(1)
    $nextFirst = Get-Date -Year $nextMonth.Year -Month $nextMonth.Month -Day 1 -Hour 2 -Minute 0 -Second 0
    Write-Host $nextFirst.ToString("dd/MM/yyyy HH:mm:ss") -ForegroundColor Cyan
}

Write-Host ""
Write-Host "COMANDOS ÚTEIS:" -ForegroundColor Yellow
Write-Host "  Ver detalhes:  Get-ScheduledTask -TaskName '$taskName' | Format-List *" -ForegroundColor White
Write-Host "  Executar agora: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
Write-Host "  Desabilitar:   Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
Write-Host "  Remover:       Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor White
Write-Host ""

# Perguntar se quer testar agora
Write-Host "Deseja executar a atualização AGORA para testar? (S/N)" -ForegroundColor Yellow
Write-Host "  (A atualização completa pode levar 3-4 horas)" -ForegroundColor Gray
$testNow = Read-Host

if ($testNow -eq 'S' -or $testNow -eq 's') {
    Write-Host ""
    Write-Host "Iniciando atualização de teste..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $taskName
    Write-Host "  [OK] Task iniciada!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Acompanhe o progresso em: $logPath" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Task configurada! Primeira execução será no próximo dia 1 às 02:00" -ForegroundColor Green
}

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 78) -ForegroundColor Cyan
Write-Host "Pressione qualquer tecla para sair..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
