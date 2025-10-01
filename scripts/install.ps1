param(
  [string]$Python = "python",
  [string]$VenvDir = ".venv"
)

function Run($cmd) {
  Write-Host "[RUN] $cmd"
  powershell -NoProfile -ExecutionPolicy Bypass -Command $cmd
  if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
}

Write-Host "[Install] Criando ambiente virtual ($VenvDir)"
Run "$Python -m venv $VenvDir"
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
