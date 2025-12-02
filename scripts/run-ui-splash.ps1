<#
.SYNOPSIS
    Launcher com splash screen para SnapTrack DOU.
    Abre uma tela de carregamento imediatamente enquanto Streamlit inicia em background.

.DESCRIPTION
    Este script:
    1. Inicia um servidor HTTP minimo para servir o splash screen
    2. Abre o navegador imediatamente mostrando o splash
    3. Inicia Streamlit em background
    4. O splash redireciona automaticamente quando Streamlit esta pronto
#>

param(
    [string]$VenvDir = ".venv",
    [int]$Port = 8501,
    [int]$SplashPort = 8500
)

$ErrorActionPreference = 'Stop'

# Paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
Set-Location $root

$logs = Join-Path $root 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$mgrLog = Join-Path $logs 'ui_manager.log'

function Write-Log($msg) {
    $ts = (Get-Date).ToString('s')
    "$ts [splash] $msg" | Out-File -FilePath $mgrLog -Encoding UTF8 -Append
}

# Verificar Python
$py = Join-Path (Join-Path $root $VenvDir) "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Python nao encontrado: $py"
    exit 1
}

# Encontrar porta livre para splash
function Test-PortFree($port) {
    $pattern = ":$port "
    $lines = netstat -ano 2>$null | Where-Object { $_ -match $pattern -and $_ -match 'LISTENING' }
    return ($null -eq $lines)
}

# Encontrar porta livre para Streamlit
$streamlitPort = $Port
for ($i = 0; $i -lt 10; $i++) {
    if (Test-PortFree ($Port + $i)) {
        $streamlitPort = $Port + $i
        break
    }
}

Write-Log "Streamlit port: $streamlitPort"

# Ler HTML do splash e substituir porta
$splashHtmlPath = Join-Path $scriptDir 'splash.html'
if (-not (Test-Path $splashHtmlPath)) {
    Write-Error "Splash HTML nao encontrado: $splashHtmlPath"
    exit 1
}

$splashHtml = Get-Content -Path $splashHtmlPath -Raw -Encoding UTF8
$splashHtml = $splashHtml -replace '\{\{STREAMLIT_PORT\}\}', $streamlitPort

# Salvar HTML temporario com porta substituida (evita servidor HTTP e problema de CORS)
$tempSplashPath = Join-Path $logs 'splash_temp.html'
[System.IO.File]::WriteAllText($tempSplashPath, $splashHtml, [System.Text.UTF8Encoding]::new($false))

# 1. Abrir navegador com splash (IMEDIATO - usuario ve algo na tela)
Write-Log "Abrindo navegador com splash..."

function Find-Chrome {
    $cands = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    return $null
}

function Find-Edge {
    $cands = @(
        "$env:ProgramFiles (x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    return $null
}

$chrome = Find-Chrome
$edge = $null
if (-not $chrome) { $edge = Find-Edge }
if (-not $chrome -and -not $edge) {
    Write-Log "Chrome/Edge nao encontrado."
    exit 3
}

$profileDir = Join-Path $logs 'ui_chrome_profile'
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir | Out-Null }

$browserExe = $chrome
if (-not $browserExe) { $browserExe = $edge }
$browserArgs = "--user-data-dir=`"$profileDir`" --new-window --app=file:///$($tempSplashPath -replace '\\', '/')"

$browserProc = Start-Process -FilePath $browserExe -ArgumentList $browserArgs -PassThru -WindowStyle Normal
Write-Log "Browser iniciado (PID=$($browserProc.Id))"

# 2. Iniciar Streamlit em background (enquanto usuario ve o splash)
Write-Log "Iniciando Streamlit em background..."

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $py
$psi.Arguments = "-m streamlit run src\dou_snaptrack\ui\app.py --server.port=$streamlitPort --server.headless=true --browser.gatherUsageStats=false"
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables["STREAMLIT_LOG_LEVEL"] = "error"
$psi.EnvironmentVariables["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# PYTHONPATH
$psi.EnvironmentVariables["PYTHONPATH"] = Join-Path $root 'src'

# Playwright browsers path
$pwBrowsers = Join-Path $root "$VenvDir\pw-browsers"
if (Test-Path $pwBrowsers) {
    $psi.EnvironmentVariables["PLAYWRIGHT_BROWSERS_PATH"] = $pwBrowsers
}

$streamlitProc = New-Object System.Diagnostics.Process
$streamlitProc.StartInfo = $psi
[void]$streamlitProc.Start()

Write-Log "Streamlit iniciado (PID=$($streamlitProc.Id))"

# 3. Aguardar browser fechar
Write-Log "Aguardando browser..."
try {
    Wait-Process -Id $browserProc.Id
} catch {}

# 4. Cleanup
Write-Log "Browser fechou. Encerrando Streamlit..."
try { Stop-Process -Id $streamlitProc.Id -Force } catch {}
try { Remove-Item -Path $tempSplashPath -Force } catch {}

Write-Log "Launcher finalizado."
exit 0
