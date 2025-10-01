param(
  [string]$InstallDir = "$env:USERPROFILE\dou_snaptrack",
  [string]$Branch = "main"
)

Write-Host "[Bootstrap] Instalando em: $InstallDir (branch=$Branch)"
$zipUrl = "https://codeload.github.com/SCarinciRod/dou_snaptrack/zip/refs/heads/$Branch"
$tmpZip = Join-Path $env:TEMP "dou_snaptrack_$Branch.zip"
$expandDir = Join-Path $env:TEMP "dou_snaptrack_$Branch"

try {
  if (Test-Path $tmpZip) { Remove-Item -Force $tmpZip -ErrorAction SilentlyContinue }
  if (Test-Path $expandDir) { Remove-Item -Recurse -Force $expandDir -ErrorAction SilentlyContinue }

  Write-Host "[Bootstrap] Baixando pacote do repositório..."
  Invoke-WebRequest -UseBasicParsing -Uri $zipUrl -OutFile $tmpZip

  Write-Host "[Bootstrap] Extraindo..."
  Expand-Archive -Path $tmpZip -DestinationPath $expandDir -Force
  $srcDir = Join-Path $expandDir "dou_snaptrack-$Branch"

  Write-Host "[Bootstrap] Copiando para $InstallDir"
  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
  Copy-Item -Path (Join-Path $srcDir '*') -Destination $InstallDir -Recurse -Force

  Write-Host "[Bootstrap] Limpando temporários"
  Remove-Item -Force $tmpZip -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force $expandDir -ErrorAction SilentlyContinue

  $installScript = Join-Path $InstallDir "scripts\install.ps1"
  Write-Host "[Bootstrap] Rodando instalação: $installScript"
  & powershell -ExecutionPolicy Bypass -File $installScript
} catch {
  Write-Error "[Bootstrap] Falhou: $_"
  exit 1
}

Write-Host "[Bootstrap] Concluído. Para abrir a UI:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$InstallDir\scripts\run-ui.ps1`""
