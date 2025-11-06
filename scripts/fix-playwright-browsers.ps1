#!/usr/bin/env pwsh
# Corrige problema de navegadores Playwright não encontrados

param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
Set-Location $root

Write-Host "=== Correção de Navegadores Playwright ===" -ForegroundColor Cyan
Write-Host ""

$py = Join-Path $root "$VenvDir\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Error "Python não encontrado: $py. Execute scripts\install.ps1"
}

Write-Host "[1/3] Configurando variável de ambiente..." -ForegroundColor Cyan
$pwBrowsers = Join-Path $root "$VenvDir\pw-browsers"
$env:PLAYWRIGHT_BROWSERS_PATH = $pwBrowsers
Write-Host "PLAYWRIGHT_BROWSERS_PATH = $pwBrowsers" -ForegroundColor Gray

Write-Host ""
Write-Host "[2/3] Instalando navegadores Playwright..." -ForegroundColor Cyan
Write-Host "Isso pode levar alguns minutos..." -ForegroundColor Gray
Write-Host ""

# Criar diretório se não existir
if (-not (Test-Path $pwBrowsers)) {
  New-Item -ItemType Directory -Path $pwBrowsers -Force | Out-Null
  Write-Host "Pasta criada: $pwBrowsers" -ForegroundColor Gray
}

# Temporariamente desabilitar verificação TLS (corporate environments)
$prevTls = $env:NODE_TLS_REJECT_UNAUTHORIZED
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"

try {
  & $py -m playwright install chromium
} finally {
  # Restaurar configuração TLS
  if ($null -ne $prevTls -and $prevTls -ne "") {
    $env:NODE_TLS_REJECT_UNAUTHORIZED = $prevTls
  } else {
    $env:NODE_TLS_REJECT_UNAUTHORIZED = "1"
  }
}

Write-Host ""
Write-Host "[3/3] Verificando instalação..." -ForegroundColor Cyan

# Verificar se navegadores foram baixados
$chromiumDirs = Get-ChildItem -Path $pwBrowsers -Directory -Filter 'chromium-*' -ErrorAction SilentlyContinue

if ($chromiumDirs) {
  Write-Host "[OK] Navegadores instalados com sucesso:" -ForegroundColor Green
  foreach ($dir in $chromiumDirs) {
    Write-Host "  - $($dir.Name)" -ForegroundColor Gray
  }
  
  Write-Host ""
  Write-Host "=== Correção Concluída ===" -ForegroundColor Green
  Write-Host ""
  Write-Host "Os navegadores agora estão em: $pwBrowsers" -ForegroundColor Gray
  Write-Host "Você pode iniciar a aplicação normalmente." -ForegroundColor Gray
  Write-Host ""
  exit 0
} else {
  Write-Host "[ERRO] Navegadores não foram instalados!" -ForegroundColor Red
  Write-Host ""
  Write-Host "Possíveis causas:" -ForegroundColor Yellow
  Write-Host "1. Problema de conexão de rede" -ForegroundColor Gray
  Write-Host "2. Proxy ou firewall bloqueando download" -ForegroundColor Gray
  Write-Host "3. Falta de espaço em disco" -ForegroundColor Gray
  Write-Host ""
  Write-Host "Tente executar manualmente:" -ForegroundColor Yellow
  Write-Host "  `$env:PLAYWRIGHT_BROWSERS_PATH = '$pwBrowsers'" -ForegroundColor Gray
  Write-Host "  & '$py' -m playwright install chromium" -ForegroundColor Gray
  Write-Host ""
  exit 1
}
