#!/usr/bin/env pwsh
# Verifica configuração do Playwright e ajuda a diagnosticar problemas

param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
Set-Location $root

Write-Host "=== Verificação da Configuração do Playwright ===" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Python e venv
$py = Join-Path $root "$VenvDir\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "[ERRO] Python não encontrado em: $py" -ForegroundColor Red
  Write-Host "Execute: scripts\install.ps1" -ForegroundColor Yellow
  exit 1
}
Write-Host "[OK] Python encontrado: $py" -ForegroundColor Green

# 2. Verificar se Playwright está instalado
Write-Host ""
Write-Host "Verificando módulo Playwright..." -ForegroundColor Cyan
$null = & $py -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('playwright') else 1)" 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERRO] Playwright não instalado" -ForegroundColor Red
  Write-Host "Execute: $py -m pip install playwright" -ForegroundColor Yellow
  exit 1
}
Write-Host "[OK] Playwright instalado" -ForegroundColor Green

# 3. Verificar cache de navegadores
Write-Host ""
Write-Host "Verificando navegadores Playwright..." -ForegroundColor Cyan
$pwBrowsers = Join-Path $root "$VenvDir\pw-browsers"

if (Test-Path $pwBrowsers) {
  Write-Host "[OK] Pasta de navegadores encontrada: $pwBrowsers" -ForegroundColor Green
  
  $chromiumDirs = Get-ChildItem -Path $pwBrowsers -Directory -Filter 'chromium-*' -ErrorAction SilentlyContinue
  if ($chromiumDirs) {
    foreach ($dir in $chromiumDirs) {
      Write-Host "  - $($dir.Name)" -ForegroundColor Gray
    }
  } else {
    Write-Host "[AVISO] Nenhum navegador Chromium encontrado em $pwBrowsers" -ForegroundColor Yellow
  }
} else {
  Write-Host "[AVISO] Pasta de navegadores não encontrada: $pwBrowsers" -ForegroundColor Yellow
  Write-Host "Verificando localização padrão do sistema..." -ForegroundColor Cyan
  
  $defaultPath = Join-Path $env:LOCALAPPDATA 'ms-playwright'
  if (Test-Path $defaultPath) {
    Write-Host "[INFO] Navegadores encontrados em: $defaultPath" -ForegroundColor Gray
    $chromiumDirs = Get-ChildItem -Path $defaultPath -Directory -Filter 'chromium-*' -ErrorAction SilentlyContinue
    if ($chromiumDirs) {
      foreach ($dir in $chromiumDirs) {
        Write-Host "  - $($dir.Name)" -ForegroundColor Gray
      }
    }
  } else {
    Write-Host "[ERRO] Nenhum navegador Playwright encontrado!" -ForegroundColor Red
    Write-Host "Execute: $py -m playwright install chromium" -ForegroundColor Yellow
    exit 1
  }
}

# 4. Verificar variável de ambiente
Write-Host ""
Write-Host "Verificando configuração de ambiente..." -ForegroundColor Cyan
if ($env:PLAYWRIGHT_BROWSERS_PATH) {
  Write-Host "[INFO] PLAYWRIGHT_BROWSERS_PATH atual: $env:PLAYWRIGHT_BROWSERS_PATH" -ForegroundColor Gray
} else {
  Write-Host "[INFO] PLAYWRIGHT_BROWSERS_PATH não configurado (OK se usando localização padrão)" -ForegroundColor Gray
}

# 5. Teste de importação do Playwright
Write-Host ""
Write-Host "Testando importação do Playwright..." -ForegroundColor Cyan
$testScript = @"
import sys
from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        print('[OK] Playwright sync API disponível')
        sys.exit(0)
except Exception as e:
    print(f'[ERRO] Falha ao inicializar Playwright: {e}')
    sys.exit(1)
"@

$testFile = Join-Path $env:TEMP "test_playwright_import.py"
Set-Content -Path $testFile -Value $testScript -Encoding UTF8

$output = & $py $testFile 2>&1
$exitCode = $LASTEXITCODE
Remove-Item -Path $testFile -Force -ErrorAction SilentlyContinue

if ($exitCode -eq 0) {
  Write-Host $output -ForegroundColor Green
} else {
  Write-Host $output -ForegroundColor Red
  Write-Host ""
  Write-Host "Possíveis soluções:" -ForegroundColor Yellow
  Write-Host "1. Reinstalar navegadores: $py -m playwright install chromium" -ForegroundColor Gray
  Write-Host "2. Verificar se greenlet está instalado: $py -m pip install --force-reinstall --only-binary=:all: greenlet" -ForegroundColor Gray
  Write-Host "3. Verificar logs do sistema para bloqueios de segurança" -ForegroundColor Gray
  exit 1
}

# 6. Verificar scripts de launch
Write-Host ""
Write-Host "Verificando scripts de lançamento..." -ForegroundColor Cyan
$scripts = @(
  @{ path = "scripts\run-ui.ps1"; name = "run-ui.ps1" },
  @{ path = "scripts\run-ui-managed.ps1"; name = "run-ui-managed.ps1" },
  @{ path = "launch_ui.vbs"; name = "launch_ui.vbs" }
)

foreach ($script in $scripts) {
  $scriptPath = Join-Path $root $script.path
  if (Test-Path $scriptPath) {
    Write-Host "[OK] $($script.name) encontrado" -ForegroundColor Green
  } else {
    Write-Host "[AVISO] $($script.name) não encontrado: $scriptPath" -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "=== Verificação Concluída ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Green
Write-Host "1. Se tudo está OK, teste a UI: scripts\run-ui-managed.ps1" -ForegroundColor Gray
Write-Host "2. Se houver erros, siga as soluções sugeridas acima" -ForegroundColor Gray
Write-Host ""
