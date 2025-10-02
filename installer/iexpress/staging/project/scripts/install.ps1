param(
  [string]$Python = "python",
  [string]$VenvDir = ".venv"
)

function Run($cmd) {
  Write-Host "[RUN] $cmd"
  powershell -NoProfile -ExecutionPolicy Bypass -Command $cmd
  if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

function Resolve-Python311 {
  Write-Host "[Python] Verificando Python 3.11..."
  # 1) py -3.11 se disponível
  try {
    $out = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
  } catch {}
  # 2) python no PATH (verificar versão)
  try {
    $ver = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver -eq "3.11") {
      $exe = & $Python -c "import sys; print(sys.executable)"
      if ($exe) { return $exe.Trim() }
    }
  } catch {}
  # 3) winget
  try {
    Write-Host "[Python] Tentando instalar via winget Python.Python.3.11..."
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -eq 0) {
      $cand = Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"
      if (Test-Path $cand) { return $cand }
      $out = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    }
  } catch {}
  # 4) Download instalador oficial e instalação silenciosa (per-user)
  try {
    $ver = "3.11.9"
    $url = "https://www.python.org/ftp/python/$ver/python-$ver-amd64.exe"
    $tmp = Join-Path $env:TEMP "python-$ver-amd64.exe"
    Write-Host "[Python] Baixando instalador $ver..."
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tmp
    Write-Host "[Python] Instalando silenciosamente (per-user)..."
    & $tmp /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1 SimpleInstall=1
    # caminho padrão per-user
    $cand = Join-Path $env:LocalAppData "Programs\Python\Python311\python.exe"
    if (Test-Path $cand) { return $cand }
    $out = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
  } catch {
    Write-Warning "[Python] Falha ao instalar automaticamente: $_"
  }
  throw "Python 3.11 não encontrado nem instalado automaticamente. Instale manualmente e reexecute."
}

$pyExe = Resolve-Python311
Write-Host "[Python] Usando: $pyExe"

Write-Host "[Install] Criando ambiente virtual ($VenvDir)"
Run "$pyExe -m venv $VenvDir"
$pip = Join-Path $VenvDir "Scripts\pip.exe"
$py = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "[Install] Atualizando pip"
Run "$py -m pip install -U pip"

Write-Host "[Install] Instalando pacote do projeto (editable)"
Run "$py -m pip install -e ."

Write-Host "[Install] Verificando Playwright"
Run "$py -c 'import playwright; print("playwright", playwright.__version__)'"

Write-Host "[Install] Testando navegador do sistema (Chrome/Edge)"
Run "$py scripts\playwright_smoke.py"

Write-Host "[Install] OK. Para iniciar a UI: scripts\run-ui.ps1"
