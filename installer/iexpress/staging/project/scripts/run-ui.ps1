param(
  [string]$VenvDir = ".venv",
  [switch]$Dev
)

$py = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Venv não encontrado em $VenvDir. Rode scripts\install.ps1"; exit 1 }

# Streamlit run
$app = "src\dou_snaptrack\ui\app.py"
if ($Dev) {
  Write-Host "[Run] Streamlit (dev) em $app"
} else {
  Write-Host "[Run] Streamlit em $app"
}

& $py -m streamlit run $app
