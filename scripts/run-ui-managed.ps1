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
$tsLog = (Get-Date).ToString('yyyyMMdd_HHmmss')
$uiLog = Join-Path $logs ("ui_streamlit_{0}.log" -f $tsLog)
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

function Initialize-Venv {
  param([string]$VenvPath)
  $venvPy = Join-Path $VenvPath 'Scripts\python.exe'
  if (Test-Path $venvPy) { return @{ exe = $venvPy; isVenv = $true } }
  if ($NoBootstrap) { Write-Error "Venv não encontrado em $VenvPath e bootstrap desativado. Rode scripts\install.ps1 ou remova -NoBootstrap."; exit 1 }
  $sys = Resolve-SystemPython
  if (-not $sys) { Write-Error "Python não encontrado no sistema. Instale Python 3.11+ ou rode scripts\install.ps1."; exit 1 }
  Write-Log "Criando venv em $VenvPath com: $($sys.exe)"
  & $sys.exe -m venv $VenvPath
  if ($LASTEXITCODE -ne 0) {
    Write-Log "Falha ao criar venv. Fallback para Python do sistema."
    return @{ exe = $sys.exe; isVenv = $false }
  }
  return @{ exe = (Join-Path $VenvPath 'Scripts\python.exe'); isVenv = $true }
}

function Test-ModuleInstalled {
  param([string]$PyExe, [string]$module)
  & $PyExe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$module') else 1)" 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Initialize-DependenciesLight {
  param([string]$PyExe, [string]$FlagPath, [bool]$IsVenv)
  $fingerprint = $PyExe
  $useCache = $false
  if (Test-Path $FlagPath) {
    try {
      $content = Get-Content -LiteralPath $FlagPath -Raw -ErrorAction Stop
      if ($content -match [regex]::Escape($fingerprint)) { $useCache = $true }
    } catch {}
  }
  # Always verify core modules even when cache suggests OK (stale cache guard)
  $need = @()
  if (-not (Test-ModuleInstalled $PyExe 'streamlit')) { $need += 'streamlit' }
  if (-not (Test-ModuleInstalled $PyExe 'playwright')) { $need += 'playwright' }
  if (-not (Test-ModuleInstalled $PyExe 'docx')) { $need += 'python-docx' }
  if ($useCache -and $need.Count -eq 0) {
    Write-Log "Pulando instalação: dependências básicas já presentes (cache válida)."
    return
  }
  if ($need.Count -gt 0) {
    Write-Log ("Instalando rapidamente dependências ausentes: " + ($need -join ', '))
    $pipArgs = @('-m','pip','install','-q') + $need
    if (-not $IsVenv) { $pipArgs = @('-m','pip','install','--user','-q') + $need }
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $PyExe $pipArgs 2>&1 | Out-File -Append -FilePath $uiLog -Encoding UTF8
    } finally {
      $ErrorActionPreference = $prevEAP
    }
    if ($LASTEXITCODE -ne 0) {
      try { Remove-Item -LiteralPath $FlagPath -Force -ErrorAction SilentlyContinue } catch {}
      Write-Error "Falha ao instalar dependências mínimas. Consulte $uiLog"; exit 1
    }
  } else {
    Write-Log "Dependências básicas já presentes."
  }
  try { Set-Content -Path $FlagPath -Value ($fingerprint + "|" + (Get-Date).ToString('s')) -Encoding UTF8 } catch {}
}

# Bootstrap se necessário
$venvInfo = Initialize-Venv -VenvPath (Join-Path $root $VenvDir)
$py = $venvInfo.exe
$isVenv = $venvInfo.isVenv
if (-not (Test-Path $py)) { Write-Error "Python não encontrado: $py"; exit 1 }

# Detect Python version and avoid known incompatibilities (e.g., Streamlit on 3.13+)
function Get-PythonVersion([string]$exe) {
  try {
    $v = & $exe -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
    return [version]$v.Trim()
  } catch { return $null }
}

$pyVer = Get-PythonVersion $py
if ($null -ne $pyVer -and $pyVer.Major -ge 3 -and $pyVer.Minor -ge 13) {
  Write-Log ("Python $($pyVer.ToString()) detectado na venv; tentando Python do sistema 3.11/3.12 por compatibilidade do Streamlit.")
  $sys = Resolve-SystemPython
  if ($sys -and (Test-Path $sys.exe)) {
    $py = $sys.exe
    $isVenv = $false
    Write-Log ("Usando Python do sistema: $py")
  } else {
    Write-Log "Python alternativo não encontrado; prosseguindo com a venv atual."
  }
}

# Startup rápido: não atualizar pip a cada execução, só instalar módulos ausentes (com cache)
if (-not $isVenv) { $depsFlag = (Join-Path $logs 'ui_deps_ok_system.flag') }
Initialize-DependenciesLight -PyExe $py -FlagPath $depsFlag -IsVenv:$isVenv

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

# Configure Playwright to use local browser cache (same path as installer)
if ($isVenv) {
  $pwBrowsers = Join-Path $root "$VenvDir\pw-browsers"
  if (Test-Path $pwBrowsers) {
    $psi.EnvironmentVariables["PLAYWRIGHT_BROWSERS_PATH"] = $pwBrowsers
    Write-Log "PLAYWRIGHT_BROWSERS_PATH configurado: $pwBrowsers"
  }
}

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

# OTIMIZAÇÃO: Não gravar logs automaticamente - só capturar em caso de erro
# Mantém stdout/stderr redirecionados mas não escreve em disco até erro ocorrer
$stdoutBuffer = New-Object System.Collections.Generic.List[string]
$stderrBuffer = New-Object System.Collections.Generic.List[string]

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
  if ($p.HasExited) {
    Write-Log "Streamlit terminou prematuramente (exit=$($p.ExitCode))"
    # ERRO: Gravar logs agora
    try {
      $fs = [System.IO.File]::Open($uiLog, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
      $writer = New-Object System.IO.StreamWriter($fs, [System.Text.Encoding]::UTF8)
      $writer.WriteLine("=== ERRO: Streamlit terminou prematuramente (exit=$($p.ExitCode)) ===")
      $outAll = $p.StandardOutput.ReadToEnd()
      $errAll = $p.StandardError.ReadToEnd()
      if ($outAll) { $writer.WriteLine("STDOUT:"); $writer.WriteLine($outAll) }
      if ($errAll) { $writer.WriteLine("STDERR:"); $writer.WriteLine($errAll) }
      $writer.Flush()
      $writer.Close()
      $fs.Close()
      Write-Log "Logs de erro salvos em: $uiLog"
    } catch {
      Write-Log "Falha ao salvar logs de erro: $_"
    }
    exit $p.ExitCode
  }
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
# OTIMIZAÇÃO: Não gravar logs de saída normal - só em caso de erro (já tratado acima)
try {
  $null = $p.WaitForExit(2000)
} catch {}
Write-Log "UI manager finalizado."
exit 0
