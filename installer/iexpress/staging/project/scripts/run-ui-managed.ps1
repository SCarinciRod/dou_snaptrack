param(
  [string]$VenvDir = ".venv",
  [int]$Port = 8501
)

$ErrorActionPreference = 'Stop'

# Paths and logs
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$py = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Venv não encontrado em $VenvDir. Rode scripts\install.ps1"; exit 1 }

$logs = Join-Path $root 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$uiLog = Join-Path $logs 'ui_streamlit.log'
$mgrLog = Join-Path $logs 'ui_manager.log'

function Write-Log($msg) {
  $ts = (Get-Date).ToString('s')
  "$ts [mgr] $msg" | Out-File -FilePath $mgrLog -Encoding UTF8 -Append
}

Write-Log "Inicializando UI manager (Port=$Port)"
Write-Log "Python: $py"

# Start Streamlit as a child process with redirected output
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $py
$psi.Arguments = "-m streamlit run src\\dou_snaptrack\\ui\\app.py --server.port=$Port --server.headless=true --browser.gatherUsageStats=false"
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
[void]$p.Start()

# Async readers to file
$stdoutWriter = [System.IO.StreamWriter]::new($uiLog, $true, [System.Text.Encoding]::UTF8)
$stderrWriter = $stdoutWriter

Start-Job -ScriptBlock {
  param($proc, $writer)
  while (-not $proc.HasExited) {
    $line = $proc.StandardOutput.ReadLine()
    if ($null -ne $line) { $writer.WriteLine($line) }
  }
  $writer.Flush()
} -ArgumentList $p, $stdoutWriter | Out-Null

Start-Job -ScriptBlock {
  param($proc, $writer)
  while (-not $proc.HasExited) {
    $line = $proc.StandardError.ReadLine()
    if ($null -ne $line) { $writer.WriteLine($line) }
  }
  $writer.Flush()
} -ArgumentList $p, $stderrWriter | Out-Null

# Wait for server port
function Test-Port($port) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $ar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
    [void]$ar.AsyncWaitHandle.WaitOne(200)
    $ok = $c.Connected
    $c.Close()
    return $ok
  } catch { return $false }
}

$timeout = [DateTime]::UtcNow.AddMinutes(2)
while (-not (Test-Port $Port)) {
  if ([DateTime]::UtcNow -gt $timeout) { Write-Log "Timeout aguardando porta $Port"; Stop-Process -Id $p.Id -Force; exit 2 }
  Start-Sleep -Milliseconds 300
  if ($p.HasExited) { Write-Log "Streamlit terminou prematuramente (exit=$($p.ExitCode))"; exit $p.ExitCode }
}
Write-Log "Porta $Port disponível"

# Launch browser (Chrome preferred, fallback Edge) in app window tied to unique profile
$profileDir = Join-Path $logs 'ui_chrome_profile'
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir | Out-Null }
$url = "http://localhost:$Port"

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
  Write-Log "Chrome/Edge não encontrado. Encerrando Streamlit."
  Stop-Process -Id $p.Id -Force
  exit 3
}

$browserExe = $chrome; if (-not $browserExe) { $browserExe = $edge }
$browserArgs = "--user-data-dir=`"$profileDir`" --new-window --app=$url"

$bp = Start-Process -FilePath $browserExe -ArgumentList $browserArgs -PassThru -WindowStyle Hidden
Write-Log "Browser iniciado: $($bp.Path) (PID $($bp.Id))"

# Wait for browser window/process to exit, then terminate Streamlit
try {
  Wait-Process -Id $bp.Id
} catch {}
Write-Log "Browser encerrado. Terminando Streamlit (PID $($p.Id))"
try { Stop-Process -Id $p.Id -Force } catch {}
Write-Log "UI manager finalizado."
exit 0
