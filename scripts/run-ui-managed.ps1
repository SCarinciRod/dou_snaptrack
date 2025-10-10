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
$depsFlag = Join-Path $logs 'ui_deps_ok.flag'

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

function Dep-Installed {
  param([string]$PyExe, [string]$module)
  & $PyExe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$module') else 1)" 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Ensure-Dependencies-Light {
  param([string]$PyExe, [string]$FlagPath)
  if (Test-Path $FlagPath) { Write-Log "Pulando checagem de dependências (cache)."; return }
  # Startup rápido: só instala o mínimo se estiver faltando; não faz upgrade de pip ou editable install
  $need = @()
  if (-not (Dep-Installed $PyExe 'streamlit')) { $need += 'streamlit' }
  if (-not (Dep-Installed $PyExe 'playwright')) { $need += 'playwright' }
  if (-not (Dep-Installed $PyExe 'docx')) { $need += 'python-docx' }
  if ($need.Count -gt 0) {
    Write-Log ("Instalando rapidamente dependências ausentes: " + ($need -join ', '))
    & $PyExe -m pip install -q $need 2>&1 | Out-File -Append -FilePath $uiLog -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { Write-Error "Falha ao instalar dependências mínimas. Consulte $uiLog"; exit 1 }
  } else {
    Write-Log "Dependências básicas já presentes."
  }
  try { Set-Content -Path $FlagPath -Value ((Get-Date).ToString('s')) -Encoding UTF8 } catch {}
}

# Bootstrap se necessário
Ensure-Venv -VenvPath (Join-Path $root $VenvDir)
$py = Join-Path (Join-Path $root $VenvDir) "Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Python da venv não encontrado em $py"; exit 1 }

# Startup rápido: não atualizar pip a cada execução, só instalar módulos ausentes (com cache)
Ensure-Dependencies-Light -PyExe $py -FlagPath $depsFlag

Write-Log "Inicializando UI manager (Port=$Port)"
Write-Log "Python: $py"

# Não encerrar UI anterior nem remover ui.lock: a decisão fica dentro do app
$uiLock = Join-Path $root 'resultados/ui.lock'
if (Test-Path $uiLock) { Write-Log "ui.lock presente; deixado intocado para aviso no app." }

# Selecionar porta: tenta $Port e, se ocupada, tenta as próximas sem matar nada
function Get-PortOwnerPid {
  param([int]$port)
  try {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -First 1
    if ($conn -and $conn.OwningProcess) { return [int]$conn.OwningProcess }
  } catch {}
  try {
    $lines = netstat -ano | Select-String -Pattern (":" + $port + "\s") | Select-Object -First 1
    if ($lines) {
      $t = $lines.ToString().Trim() -split "\s+"
      $pidStr = $t[-1]
      if ($pidStr -match '^[0-9]+$') { return [int]$pidStr }
    }
  } catch {}
  return $null
}

$basePort = [int]$Port
$chosenPort = $null
for ($try=0; $try -lt 10; $try++) {
  $cand = $basePort + $try
  $owner = Get-PortOwnerPid -port $cand
  if ($null -eq $owner) { $chosenPort = $cand; break }
  Write-Log ("Porta $cand ocupada (PID=$owner); tentando próxima…")
}
if ($null -eq $chosenPort) { Write-Log "Nenhuma porta livre encontrada no range."; exit 5 }
$Port = $chosenPort
Write-Log ("Usando porta $Port")

# Start Streamlit as a child process with redirected output (config tuned for startup)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $py
$psi.Arguments = "-m streamlit run src\\dou_snaptrack\\ui\\app.py --server.port=$Port --server.headless=true --browser.gatherUsageStats=false"
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
# Reduce Streamlit verbosity
$psi.EnvironmentVariables["STREAMLIT_LOG_LEVEL"] = "warning"
$psi.EnvironmentVariables["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# Ensure Python can import project packages from src/ even when launched via shortcut
$currentPyPath = $env:PYTHONPATH
$desiredPyPath = Join-Path $root 'src'
if ([string]::IsNullOrEmpty($currentPyPath)) {
  $psi.EnvironmentVariables["PYTHONPATH"] = $desiredPyPath
} else {
  # Avoid duplicates
  if ($currentPyPath.Split(';') -notcontains $desiredPyPath) {
    $psi.EnvironmentVariables["PYTHONPATH"] = "$desiredPyPath;$currentPyPath"
  } else {
    $psi.EnvironmentVariables["PYTHONPATH"] = $currentPyPath
  }
}
Write-Log ("PYTHONPATH set for child: " + $psi.EnvironmentVariables["PYTHONPATH"]) 

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

# Esperar porta ficar disponível para abrir o navegador
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
  if ([DateTime]::UtcNow -gt $timeout) { Write-Log "Timeout aguardando porta $Port"; try { Stop-Process -Id $p.Id -Force } catch {}; exit 2 }
  Start-Sleep -Milliseconds 300
  if ($p.HasExited) { Write-Log "Streamlit terminou prematuramente (exit=$($p.ExitCode))"; exit $p.ExitCode }
}
Write-Log "Porta $Port disponível"

# Launch browser (Chrome preferred, fallback Edge) in app window tied to unique profile
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
  try { Stop-Process -Id $p.Id -Force } catch {}
  exit 3
}

$profileDir = Join-Path $logs 'ui_chrome_profile'
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir | Out-Null }
$url = "http://localhost:$Port"

$browserExe = $chrome; if (-not $browserExe) { $browserExe = $edge }
$browserArgs = "--user-data-dir=`"$profileDir`" --new-window --app=$url"

$bp = Start-Process -FilePath $browserExe -ArgumentList $browserArgs -PassThru -WindowStyle Normal
Write-Log "Browser iniciado: $($bp.Path) (PID $($bp.Id))"

# Wait for browser window/process to exit, then terminate Streamlit
try {
  Wait-Process -Id $bp.Id
} catch {}
Write-Log "Browser encerrado. Terminando Streamlit (PID $($p.Id))"
try { Stop-Process -Id $p.Id -Force } catch {}
Write-Log "UI manager finalizado."
exit 0
