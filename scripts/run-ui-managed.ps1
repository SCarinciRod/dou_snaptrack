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

# Ensure we always use the same port by terminating any existing owner of the port
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

function Kill-ProcessTree {
  param([int]$TargetPid)
  try {
    # Prefer taskkill to ensure child tree termination
    & taskkill /PID $TargetPid /T /F | Out-Null
  } catch {}
  try { Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue } catch {}
}

function Get-ProcessInfo {
  param([int]$Pid)
  try {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$Pid"
    if (-not $p) { return $null }
    $owner = $p.GetOwner()
    return [PSCustomObject]@{
      ExecutablePath = $p.ExecutablePath
      CommandLine    = $p.CommandLine
      User           = if ($owner) { "$($owner.Domain)\$($owner.User)" } else { $null }
    }
  } catch { return $null }
}

function Is-OurUiProcess {
  param([int]$Pid)
  $info = Get-ProcessInfo -Pid $Pid
  if (-not $info) { return $false }
  $venvPy = Join-Path (Join-Path $root $VenvDir) 'Scripts\python.exe'
  $app = (Join-Path $root 'src\dou_snaptrack\ui\app.py')
  $exe = ("" + $info.ExecutablePath).ToLower()
  $cmd = ("" + $info.CommandLine).ToLower()
  $venvPyL = $venvPy.ToLower()
  $appL = $app.ToLower()
  if (($exe -like "*$venvPyL*") -or ($cmd -like "*$venvPyL*")) {
    if ($cmd -like "*streamlit*" -and $cmd -like "*$appL*") { return $true }
  }
  return $false
}

# Try to terminate previously running UI via lock file (if present)
$uiLock = Join-Path $root 'resultados/ui.lock'
if (Test-Path $uiLock) {
  try {
    $lockData = Get-Content -Raw -Path $uiLock | ConvertFrom-Json
    if ($lockData -and $lockData.pid) {
      $pidToKill = [int]$lockData.pid
      if (Is-OurUiProcess -Pid $pidToKill) {
        Write-Log ("Encerrando UI anterior via lock (PID=" + $pidToKill + ")")
        Kill-ProcessTree -TargetPid $pidToKill
      } else {
        Write-Log ("Ignorando ui.lock: PID " + $pidToKill + " não parece ser nossa UI.")
      }
    }
  } catch { Write-Log "Não foi possível ler ui.lock; seguindo." }
}

# Ensure port is free; if not, kill its owner
for ($i=0; $i -lt 10; $i++) {
  $owner = Get-PortOwnerPid -port $Port
  if ($null -eq $owner) { break }
  if (Is-OurUiProcess -Pid $owner) {
    Write-Log ("Porta $Port ocupada por nossa UI (PID=$owner); encerrando processo…")
    Kill-ProcessTree -TargetPid $owner
  } else {
    Write-Log ("Porta $Port ocupada por processo não reconhecido (PID=$owner); não será encerrado.")
    break
  }
  Start-Sleep -Milliseconds 400
}
if (Get-PortOwnerPid -port $Port) {
  Write-Log "Falha ao liberar a porta após tentativas; encerrando."
  exit 5
}

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

# Create loader page immediately and open browser to it; it will auto-redirect when the app is ready
$profileDir = Join-Path $logs 'ui_chrome_profile'
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir | Out-Null }
$url = "http://localhost:$Port"
$loaderPath = Join-Path $logs 'ui_loading.html'
$loaderHtml = @"
<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8"/>
<title>Carregando SnapTrack DOU…</title>
<style>body{font-family:system-ui,Segoe UI,Arial;margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0} .box{max-width:520px;text-align:center} h1{font-size:20px;margin:0 0 8px} p{opacity:.8;margin:0 0 16px} .dot{display:inline-block;width:8px;height:8px;margin:0 3px;border-radius:4px;background:#38bdf8;animation:b .9s infinite;} .dot:nth-child(2){animation-delay:.15s} .dot:nth-child(3){animation-delay:.3s}@keyframes b{0%{opacity:.2}50%{opacity:1}100%{opacity:.2}}</style>
<script>
const target = "$url";
async function ping(){
  try{ await fetch(target, {cache:'no-store', mode:'no-cors'}); window.location.href = target; }catch(e){}
}
setInterval(ping, 500);
setTimeout(ping, 100);
</script>
</head><body><div class="box">
<h1>Iniciando a Interface…</h1>
<p>Preparando o servidor local na porta $Port</p>
<div><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
</div></body></html>
"@
Set-Content -Path $loaderPath -Value $loaderHtml -Encoding UTF8

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
  Stop-Process -Id $p.Id -Force
  exit 3
}

$browserExe = $chrome; if (-not $browserExe) { $browserExe = $edge }
$browserArgs = "--user-data-dir=`"$profileDir`" --new-window --app=file:///$($loaderPath.Replace('\\', '/'))"

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
