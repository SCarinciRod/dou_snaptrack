param(
  [string]$VenvDir = ".venv",
  [int]$Port = 8501,
  [switch]$NoBootstrap
)

$ErrorActionPreference = 'Stop'

# Paths and logs (use project root = parent of scripts folder)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
Set-Location $root
$py = Join-Path (Join-Path $root $VenvDir) "Scripts\python.exe"

$logs = Join-Path $root 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$uiLog = Join-Path $logs 'ui_streamlit.log'
$mgrLog = Join-Path $logs 'ui_manager.log'

function Write-Log($msg) {
  $ts = (Get-Date).ToString('s')
  "$ts [mgr] $msg" | Out-File -FilePath $mgrLog -Encoding UTF8 -Append
}

function Resolve-SystemPython {
  Write-Log "Resolvendo Python do sistema..."
  $cands = @(
    @{ cmd = 'py'; args = '-3.11'; desc = 'py -3.11' },
    @{ cmd = 'py'; args = '-3.12'; desc = 'py -3.12' },
    @{ cmd = 'py'; args = '-3'; desc = 'py -3' },
    @{ cmd = 'python'; args = ''; desc = 'python' }
  )
  foreach($c in $cands){
    try {
      $exe = & $c.cmd $c.args -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $exe) {
        $v = & $c.cmd $c.args -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
        Write-Log "Encontrado $($c.desc): $exe (Python $v)"
        return @{ exe = $exe.Trim(); ver = $v.Trim() }
      }
    } catch {}
  }
  return $null
}

function Ensure-Venv {
  param([string]$VenvPath)
  if (Test-Path (Join-Path $VenvPath 'Scripts\python.exe')) { return }
  if ($NoBootstrap) { Write-Error "Venv não encontrado em $VenvPath e bootstrap desativado. Rode scripts\install.ps1 ou remova -NoBootstrap."; exit 1 }
  $sys = Resolve-SystemPython
  if (-not $sys) { Write-Error "Python não encontrado no sistema. Instale Python 3.11+ ou rode scripts\install.ps1."; exit 1 }
  Write-Log "Criando venv em $VenvPath com: $($sys.exe)"
  & $sys.exe -m venv $VenvPath
  if ($LASTEXITCODE -ne 0) { Write-Error "Falha ao criar venv."; exit 1 }
}

function Pip-Ensure {
  param([string]$PyExe)
  Write-Log "Atualizando pip..."
  & $PyExe -m pip install -U pip 2>&1 | Out-File -Append -FilePath $uiLog -Encoding UTF8
}

function Dep-Installed {
  param([string]$PyExe, [string]$module)
  & $PyExe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$module') else 1)" 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Ensure-Dependencies {
  param([string]$PyExe)
  $need = @()
  $deps = @(
    @{ pkg = 'streamlit';   mod = 'streamlit' },
    @{ pkg = 'playwright';  mod = 'playwright' },
    @{ pkg = 'python-docx'; mod = 'docx' }
  )
  foreach($d in $deps){ if (-not (Dep-Installed $PyExe $d.mod)) { $need += $d.pkg } }
  if ($need.Count -gt 0) {
    Write-Log ("Instalando dependências: " + ($need -join ', '))
    & $PyExe -m pip install -q $need 2>&1 | Out-File -Append -FilePath $uiLog -Encoding UTF8
    if ($LASTEXITCODE -ne 0) {
      Write-Log "Falha instalando dependências diretas; tentando instalar o pacote do projeto (-e .)"
      & $PyExe -m pip install -e . 2>&1 | Out-File -Append -FilePath $uiLog -Encoding UTF8
      if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha ao instalar dependências. Verifique conectividade e permissões. Consulte $uiLog"; exit 1
      }
    }
  } else {
    Write-Log "Dependências básicas já presentes."
  }
}

# Bootstrap se necessário
Ensure-Venv -VenvPath (Join-Path $root $VenvDir)
$py = Join-Path (Join-Path $root $VenvDir) "Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Python da venv não encontrado em $py"; exit 1 }

Pip-Ensure -PyExe $py
Ensure-Dependencies -PyExe $py

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
