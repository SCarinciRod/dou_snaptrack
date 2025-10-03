param(
  [string]$VenvDir = ".venv",
  [switch]$Dev,
  [int]$Port = 8501
)

$ErrorActionPreference = 'Stop'

# Resolve repo root from this script location and work there
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
Set-Location $root

$py = Join-Path (Join-Path $root $VenvDir) "Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Venv não encontrado em $VenvDir. Rode scripts\install.ps1"; exit 1 }

# Ensure child can import from src/ regardless of how it's launched
$srcDir = Join-Path $root 'src'
if ($env:PYTHONPATH) {
  if (-not $env:PYTHONPATH.Split(';') -contains $srcDir) { $env:PYTHONPATH = "$srcDir;$($env:PYTHONPATH)" }
} else {
  $env:PYTHONPATH = $srcDir
}

# Streamlit run from repo root
$app = "src\dou_snaptrack\ui\app.py"
if ($Dev) {
  Write-Host "[Run] Streamlit (dev) em $root\$app (Port=$Port)"
} else {
  Write-Host "[Run] Streamlit em $root\$app (Port=$Port)"
}

& $py -m streamlit run $app --server.port=$Port --browser.gatherUsageStats=false
