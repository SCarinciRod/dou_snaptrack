param(
  [string]$Python = "python",
  [string]$VenvDir = ".venv",
  [string]$PythonVersions = "3.13;3.12;3.11",
  [switch]$AllowWinget,
  [switch]$SkipSmoke,
  [switch]$ForceCleanVenv,
  [switch]$NoVenv,
  [switch]$Quiet
)

function Run($cmd, [int]$TimeoutSeconds = 30) {
  # Execute a PowerShell command in a child process with a timeout (seconds).
  Write-Host "[RUN] $cmd (timeout=${TimeoutSeconds}s)"
  $stdout = [System.IO.Path]::GetTempFileName()
  $stderr = [System.IO.Path]::GetTempFileName()
  $psArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-Command',$cmd)
  $argJoined = ($psArgs -join ' ')
  $p = Start-Process -FilePath powershell -ArgumentList $argJoined -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  if ($null -eq $p) { throw "Failed to start PowerShell for: $cmd" }
  $timeoutMs = [int]($TimeoutSeconds * 1000)
  try {
    $finished = $p.WaitForExit($timeoutMs)
  } catch {
    $finished = $false
  }
  if (-not $finished) {
    Write-Warning "[TIMEOUT] Command exceeded ${TimeoutSeconds}s: $cmd"
    try { $p.Kill() } catch {}
    $outTxt = (Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue -Raw)
    $errTxt = (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue -Raw)
    throw ("Timeout: command exceeded {0}s: {1}`nSTDOUT:`n{2}`nSTDERR:`n{3}" -f $TimeoutSeconds, $cmd, $outTxt, $errTxt)
  }
  $exit = $p.ExitCode
  $outTxt = (Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue -Raw)
  $errTxt = (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue -Raw)
  if ($exit -ne 0) { throw ("Command failed (exit={0}): {1}`nSTDOUT:`n{2}`nSTDERR:`n{3}" -f $exit, $cmd, $outTxt, $errTxt) }
  try { Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue } catch {}
  try { Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue } catch {}
}

# Variante que retorna ExitCode/STDOUT/STDERR sem lançar exceção
function Run-GetResult($cmd, [int]$TimeoutSeconds = 30) {
  Write-Host "[RUN] $cmd (timeout=${TimeoutSeconds}s)"
  $stdout = [System.IO.Path]::GetTempFileName()
  $stderr = [System.IO.Path]::GetTempFileName()
  $tmpPs1 = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "runwrap_" + [System.Guid]::NewGuid().ToString() + ".ps1")
  $content = @(
    $cmd,
    'if ($LASTEXITCODE) { exit $LASTEXITCODE } elseif (-not $?) { exit 1 }'
  ) -join "`n"
  Set-Content -LiteralPath $tmpPs1 -Value $content -Encoding UTF8 -Force
  $psArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-File', $tmpPs1)
  $argJoined = ($psArgs -join ' ')
  $p = Start-Process -FilePath powershell -ArgumentList $argJoined -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  if ($null -eq $p) { return [pscustomobject]@{ ExitCode = 901; Stdout = ''; Stderr = 'Failed to start PowerShell'; TimedOut = $false } }
  $timeoutMs = [int]($TimeoutSeconds * 1000)
  $timedOut = $false
  try { $finished = $p.WaitForExit($timeoutMs) } catch { $finished = $false }
  if (-not $finished) {
    $timedOut = $true
    try { $p.Kill() } catch {}
  }
  $exit = $p.ExitCode
  $outTxt = (Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue -Raw)
  $errTxt = (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue -Raw)
  try { Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue } catch {}
  try { Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue } catch {}
  try { Remove-Item -LiteralPath $tmpPs1 -Force -ErrorAction SilentlyContinue } catch {}
  return [pscustomobject]@{ ExitCode = $exit; Stdout = $outTxt; Stderr = $errTxt; TimedOut = $timedOut }
}

# Cria venv de maneira robusta (venv -> venv --without-pip -> virtualenv) e retorna objeto com Python e VenvDir
function New-VenvRobust {
  param(
    [Parameter(Mandatory=$true)][string]$BasePython,
    [Parameter(Mandatory=$true)][string]$VenvDir,
    [switch]$ForceClean,
    [string[]]$AltVenvDirs
  )
  function Remove-DirectoryRobust([string]$path) {
    if (-not (Test-Path $path)) { return $true }
    Write-Host "[Venv] Limpando diretório existente: $path"
    $ok = $false
    try { Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop; $ok = $true } catch {}
    if (-not $ok) {
      $bak = "$path-old-$(Get-Date -Format yyyyMMddHHmmss)"
      try { Rename-Item -LiteralPath $path -NewName (Split-Path -Leaf $bak) -ErrorAction Stop; $ok = $true; Write-Host "[Venv] Renomeado para: $bak" } catch {}
    }
    return $ok
  }

  $targetDir = $VenvDir
  if ($ForceClean) { Remove-DirectoryRobust $targetDir | Out-Null }

  Write-Host "[Venv] Criando venv em $targetDir usando $BasePython"
  $created = $false
  $permDenied = $false
  function TryVenv([string]$venvArgs) { try { Run "$BasePython $venvArgs" 120; return $true } catch { $script:lastErr = $_; return $false } }

  if (-not $created) {
    if (TryVenv "-m venv `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] venv padrão falhou: {0}" -f $script:lastErr.Exception.Message) }
    if (-not $created -and ($script:lastErr.Exception.Message -match 'Permission denied')) { $permDenied = $true }
  }
  if (-not $created) {
    if (TryVenv "-m venv --without-pip `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] venv --without-pip falhou: {0}" -f $script:lastErr.Exception.Message) }
    if (-not $created -and ($script:lastErr.Exception.Message -match 'Permission denied')) { $permDenied = $true }
  }
  if (-not $created -and $permDenied) {
    # mesmo sem ForceClean, tentar limpar quando houver Permission denied
    if (Remove-DirectoryRobust $targetDir) {
      if (TryVenv "-m venv `"$targetDir`"") { $created = $true }
      if (-not $created) { if (TryVenv "-m venv --without-pip `"$targetDir`"") { $created = $true } }
    }
  }

  if (-not $created) {
    # virtualenv fallback
    $basePipOk = $false
    try { Run "$BasePython -m ensurepip --upgrade" 90; $basePipOk = $true } catch {
      Write-Warning "[Venv] ensurepip no Python base falhou, tentando get-pip.py"
      $getPip = Join-Path $env:TEMP "get-pip.py"
      try { Invoke-FileDownloadWithRetry -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -MaxAttempts 4 -TimeoutSec 15; Run "$BasePython `"$getPip`"" 180; $basePipOk = $true } catch { Write-Warning ("[Venv] get-pip também falhou: {0}" -f $_.Exception.Message) } finally { try { Remove-Item -LiteralPath $getPip -Force -ErrorAction SilentlyContinue } catch {} }
    }
    if ($basePipOk) {
      try { Run "$BasePython -m pip install --user virtualenv" 180 } catch { Write-Warning ("[Venv] instalação do virtualenv falhou: {0}" -f $_.Exception.Message) }
      if (TryVenv "-m virtualenv `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] criação via virtualenv falhou: {0}" -f $script:lastErr.Exception.Message) }
      if (-not $created -and $permDenied -and $ForceClean) {
        if (Remove-DirectoryRobust $targetDir) { if (TryVenv "-m virtualenv `"$targetDir`"") { $created = $true } }
      }
    }
  }

  if (-not $created -and $AltVenvDirs -and $AltVenvDirs.Count -gt 0) {
    foreach ($alt in $AltVenvDirs) {
      if ($created) { break }
      Write-Warning "[Venv] Alternando para diretório alternativo de venv: $alt"
      $targetDir = $alt
      if (Test-Path $targetDir) { Remove-DirectoryRobust $targetDir | Out-Null }
      if (TryVenv "-m venv `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] venv padrão (alt) falhou: {0}" -f $script:lastErr.Exception.Message) }
      if (-not $created) { if (TryVenv "-m venv --without-pip `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] venv --without-pip (alt) falhou: {0}" -f $script:lastErr.Exception.Message) } }
      if (-not $created) {
        $basePipOk = $false
        try { Run "$BasePython -m ensurepip --upgrade" 90; $basePipOk = $true } catch {}
        if (-not $basePipOk) {
          $getPip = Join-Path $env:TEMP "get-pip.py"
          try { Invoke-FileDownloadWithRetry -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -MaxAttempts 4 -TimeoutSec 15; Run "$BasePython `"$getPip`"" 180; $basePipOk = $true } catch {} finally { try { Remove-Item -LiteralPath $getPip -Force -ErrorAction SilentlyContinue } catch {} }
        }
        if ($basePipOk) {
          try { Run "$BasePython -m pip install --user virtualenv" 180 } catch {}
          if (TryVenv "-m virtualenv `"$targetDir`"") { $created = $true } else { Write-Warning ("[Venv] virtualenv (alt) falhou: {0}" -f $script:lastErr.Exception.Message) }
        }
      }
    }
  }

  if (-not $created) { throw "Falha ao criar venv em $targetDir por todos os métodos." }

  $venvPy = Join-Path $targetDir "Scripts\python.exe"
  if (-not (Test-Path $venvPy)) { throw "Venv criada, mas python.exe não encontrado: $venvPy" }
  try { Run "$venvPy -m ensurepip --upgrade" 90 } catch { Write-Warning ("[Venv] ensurepip na venv falhou: {0}" -f $_.Exception.Message) }
  try { Run "$venvPy -m pip install -U pip" 180 } catch { Write-Warning ("[Venv] upgrade do pip na venv falhou: {0}" -f $_.Exception.Message) }
  return [pscustomobject]@{ Python = $venvPy; VenvDir = $targetDir }
}

# Download com retry/backoff (TTL por tentativa = 15s)
function Invoke-FileDownloadWithRetry {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile,
    [int]$MaxAttempts = 4,
    [int]$TimeoutSec = 15
  )
  Write-Host ("[Download] {0} -> {1} (timeout={2}s; attempts={3})" -f $Url, $OutFile, $TimeoutSec, $MaxAttempts)
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
  $attempt = 0
  $delay = 1
  while ($attempt -lt $MaxAttempts) {
    $attempt++
    try {
  try { Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue } catch {}
  $handler = New-Object System.Net.Http.HttpClientHandler
      $client = New-Object System.Net.Http.HttpClient($handler)
      $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
      try {
        $bytes = $client.GetByteArrayAsync($Url).GetAwaiter().GetResult()
        [IO.File]::WriteAllBytes($OutFile, $bytes)
        Write-Host "[Download] Sucesso na tentativa $attempt"
        return
      } finally {
        $client.Dispose()
        $handler.Dispose()
      }
    } catch {
      Write-Warning ("[Download] Falha na tentativa {0}: {1}" -f $attempt, $_.Exception.Message)
      if ($attempt -lt $MaxAttempts) {
        Start-Sleep -Seconds $delay
        $delay = [Math]::Min($delay * 2, 8)
      }
    }
  }
  throw "Falha no download após $MaxAttempts tentativas: $Url"
}

function Get-PyVer([string]$exe) {
  try { return (& $exe -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null) } catch { return $null }
}

function Find-PythonCandidate([string[]]$versions) {
  # 1) Caminhos conhecidos por usuário (oficial installer per-user)
  foreach ($v in $versions) {
    $verDigits = $v.Replace('.', '')
    $cand = Join-Path $env:LocalAppData ("Programs\Python\Python{0}\python.exe" -f $verDigits)
    if (Test-Path $cand) { return $cand }
  }
  # 2) Registro HKCU do instalador oficial
  foreach ($v in $versions) {
    try {
      $key = "HKCU:\\Software\\Python\\PythonCore\\$v\\InstallPath"
      $p = (Get-Item -Path $key -ErrorAction SilentlyContinue).GetValue('')
      if ($p) {
        $exe = Join-Path $p 'python.exe'
        if (Test-Path $exe) { return $exe }
      }
    } catch {}
  }
  # 3) Microsoft Store App Execution Alias
  $wa = Join-Path $env:LocalAppData 'Microsoft\WindowsApps\python.exe'
  if (Test-Path $wa) {
    $ver = Get-PyVer $wa
    if ($ver -and ($versions -contains $ver)) { return $wa }
  }
  # 4) python no PATH
  try {
    $ver = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
    if ($LASTEXITCODE -eq 0 -and ($versions -contains $ver)) {
      $exe = & $Python -c "import sys; print(sys.executable)" 2>$null
      if ($exe) { return $exe.Trim() }
    }
  } catch {}
  return $null
}

function Resolve-Python {
  param([string]$Versions = "3.13;3.12;3.11", [switch]$AllowWinget)
  $versions = $Versions -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  Write-Host "`n=== Procurando Python ==="
  Write-Host "[Python] Versões aceitas: $($versions -join ', ')"
  
  $found = Find-PythonCandidate -versions $versions
  if ($found) {
    Write-Host "[Python] ✓ Encontrado: $found"
    $ver = Get-PyVer $found
    if ($ver) { Write-Host "[Python] ✓ Versão: $ver" }
    return $found
  }

  Write-Host "`n[Python] Não encontrado no sistema. Iniciando instalação automática..."
  Write-Host "[Python] Modo: PER-USER (sem necessidade de admin)"
  Write-Host ""

  # Mapear versões full
  $versionMap = @{
    '3.13' = '3.13.0'
    '3.12' = '3.12.7'
    '3.11' = '3.11.9'
  }

  # Tentar instalar cada versão até conseguir
  foreach ($v in $versions) {
    $full = $versionMap[$v]
    if (-not $full) {
      Write-Warning "[Python] Versão $v não mapeada. Pulando..."
      continue
    }

    $url = "https://www.python.org/ftp/python/$full/python-$full-amd64.exe"
    $tmp = Join-Path $env:TEMP ("python-installer-{0}.exe" -f $full)
    
    Write-Host "[Python] Tentando instalar Python $full..."
    Write-Host "  URL: $url"
    
    # Download com retry
    try {
      Write-Host "  [1/3] Baixando instalador..."
      Invoke-FileDownloadWithRetry -Url $url -OutFile $tmp -MaxAttempts 4 -TimeoutSec 30
      Write-Host "  [1/3] ✓ Download concluído"
    } catch {
      Write-Warning "  [1/3] ✗ Download falhou: $($_.Exception.Message)"
      continue
    }

    # Verificar se arquivo foi baixado
    if (-not (Test-Path $tmp)) {
      Write-Warning "  Arquivo não encontrado após download: $tmp"
      continue
    }

    $fileSize = (Get-Item $tmp).Length / 1MB
    Write-Host "  Tamanho: $([math]::Round($fileSize, 2)) MB"

    # Instalação silenciosa SEM admin
    # Argumentos críticos:
    # - /passive ou /quiet: instalação silenciosa
    # - InstallAllUsers=0: instalação PER-USER (não requer admin)
    # - PrependPath=1: adiciona ao PATH do usuário
    # - Include_pip=1: inclui pip
    # - Include_launcher=1: inclui py.exe launcher
    # - SimpleInstall=1: instalação simplificada
    # - TargetDir: diretório específico do usuário (opcional, mas ajuda)
    
    $installDir = Join-Path $env:LocalAppData "Programs\Python\Python$($v.Replace('.', ''))"
    
    $installArgs = @(
      "/passive",  # Mostra barra de progresso mas não requer interação
      "InstallAllUsers=0",  # CRÍTICO: instala só para usuário atual
      "PrependPath=1",
      "Include_pip=1",
      "Include_launcher=1",
      "SimpleInstall=1",
      "TargetDir=`"$installDir`""
    )
    
    Write-Host "  [2/3] Instalando Python $v (aguarde 1-2 minutos)..."
    Write-Host "  Diretório: $installDir"
    Write-Host "  IMPORTANTE: Instalação PER-USER (sem necessidade de admin)"
    
    try {
      # Usar Start-Process com -Verb RunAs REMOVIDO (não pedir admin)
      # -Wait garante que esperamos a instalação terminar
      # -WindowStyle Hidden oculta janela (ou use Normal para debug)
      $proc = Start-Process -FilePath $tmp -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
      
      $exitCode = $proc.ExitCode
      Write-Host "  [2/3] Instalação finalizada (Exit Code: $exitCode)"
      
      # Exit codes do instalador Python:
      # 0 = Sucesso
      # 1602 = Usuário cancelou (não deve acontecer em /passive)
      # 1638 = Outra versão já instalada
      # 3010 = Sucesso mas requer reinicialização
      
      if ($exitCode -eq 0 -or $exitCode -eq 3010) {
        Write-Host "  [2/3] ✓ Instalação bem-sucedida"
      } elseif ($exitCode -eq 1638) {
        Write-Host "  [2/3] ⚠ Python já está instalado"
      } else {
        Write-Warning "  [2/3] ✗ Exit code não esperado: $exitCode"
      }
      
    } catch {
      Write-Warning "  [2/3] ✗ Erro ao executar instalador: $($_.Exception.Message)"
      continue
    } finally {
      # Limpar instalador temporário
      try {
        Start-Sleep -Seconds 2  # Aguardar liberação do arquivo
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      } catch {}
    }

    # Aguardar Python ficar disponível
    Write-Host "  [3/3] Verificando instalação..."
    Start-Sleep -Seconds 3
    
    # Revarrer após instalação
    $found = Find-PythonCandidate -versions $versions
    if ($found) {
      Write-Host "  [3/3] ✓ Python $v detectado com sucesso!"
      Write-Host "  Localização: $found"
      return $found
    } else {
      Write-Warning "  [3/3] ✗ Python não detectado após instalação"
      Write-Host "  Tentando buscar diretamente em: $installDir"
      
      $directPy = Join-Path $installDir "python.exe"
      if (Test-Path $directPy) {
        Write-Host "  [3/3] ✓ Encontrado diretamente: $directPy"
        return $directPy
      }
    }
  }

  # Fallback: winget (se permitido e disponível)
  if ($AllowWinget) {
    Write-Host "`n[Python] Tentando instalação via winget..."
    foreach ($v in $versions) {
      $wingetId = "Python.Python.$v"
      Write-Host "[winget] Instalando $wingetId..."
      
      try {
        # winget install com argumentos para instalação silenciosa de usuário
        $wingetArgs = "install -e --id $wingetId --scope user --accept-source-agreements --accept-package-agreements --silent"
        Run "winget $wingetArgs" 300
        
        Write-Host "[winget] ✓ Comando executado"
        Start-Sleep -Seconds 5
        
        $found = Find-PythonCandidate -versions $versions
        if ($found) {
          Write-Host "[winget] ✓ Python detectado após instalação via winget!"
          return $found
        }
      } catch {
        Write-Warning "[winget] Falha: $($_.Exception.Message)"
      }
    }
  }

  # Se chegou aqui, falhou
  Write-Host "`n╔════════════════════════════════════════════════════════════════════╗"
  Write-Host "║  ❌ INSTALAÇÃO AUTOMÁTICA DE PYTHON FALHOU                        ║"
  Write-Host "╚════════════════════════════════════════════════════════════════════╝"
  Write-Host ""
  Write-Host "Por favor, instale Python manualmente:"
  Write-Host ""
  Write-Host "1. Acesse: https://www.python.org/downloads/"
  Write-Host "2. Baixe Python 3.13, 3.12 ou 3.11"
  Write-Host "3. Durante instalação:"
  Write-Host "   ☑️  Marque 'Add Python to PATH'"
  Write-Host "   ☑️  Escolha 'Install for current user only' (NÃO precisa de admin)"
  Write-Host "4. Após instalação, execute novamente: .\scripts\install.ps1"
  Write-Host ""
  
  throw "Python não encontrado. Instalação manual necessária."
}

$pyExe = Resolve-Python -Versions $PythonVersions -AllowWinget:$AllowWinget

Write-Host "`n╔════════════════════════════════════════════════════════════════════╗"
Write-Host "║           DOU SnapTrack - Instalação Automática                   ║"
Write-Host "╚════════════════════════════════════════════════════════════════════╝"
Write-Host "`n[✓] Python encontrado: $pyExe"
Write-Host "[✓] Modo: Instalação de usuário (sem necessidade de admin)"
Write-Host "[✓] Tipo: Desenvolvimento (modo editável)"
Write-Host ""

# --- User-mode streamlined install ---
$py = $pyExe
Write-Host "=== Verificando dependências ==="
Write-Host "[pip] Verificando gerenciador de pacotes..."
$pipOk = $false
$cmd = "& `"$py`" -m pip --version"
$chk = Run-GetResult $cmd 30

if ($chk.ExitCode -eq 0 -or ($chk.Stdout -match '^(?i)pip\s+\d')) {
  $pipOk = $true
  # Extrair versão do pip
  if ($chk.Stdout -match 'pip\s+([\d.]+)') {
    Write-Host "[pip] ✓ Versão $($matches[1]) encontrada"
  } else {
    Write-Host "[pip] ✓ Instalado e funcional"
  }
}

if (-not $pipOk) {
  Write-Warning "[pip] Não encontrado. Inicializando pip..."
  
  # Tentar ensurepip primeiro
  Write-Host "[pip] Tentando ensurepip..."
  $cmd = "& `"$py`" -m ensurepip --upgrade"
  $ens = Run-GetResult $cmd 180
  if ($ens.ExitCode -eq 0) {
    Write-Host "[pip] ✓ Instalado via ensurepip"
    $pipOk = $true
  }
  
  # Fallback para get-pip.py
  if (-not $pipOk) {
    Write-Host "[pip] ensurepip falhou. Tentando get-pip.py..."
    $getPip = Join-Path $env:TEMP "get-pip.py"
    try {
      Invoke-FileDownloadWithRetry -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -MaxAttempts 4 -TimeoutSec 15
  $cmd = "& `"$py`" `"$getPip`""
  $null = Run-GetResult $cmd 300
      Write-Host "[pip] ✓ Instalado via get-pip.py"
    } catch {
      Write-Warning "[pip] Falha no download/instalação de get-pip.py"
    } finally {
      try { Remove-Item -LiteralPath $getPip -Force -ErrorAction SilentlyContinue } catch {}
    }
  }
  
  # Verificar novamente
  $cmd = "& `"$py`" -m pip --version"
  $chk2 = Run-GetResult $cmd 30
  if ($chk2.ExitCode -eq 0 -or ($chk2.Stdout -match '^(?i)pip\s+\d')) {
    $pipOk = $true
    Write-Host "[pip] ✓ Verificação final OK"
  } else {
    $pipOk = $false
  }
}
if (-not $pipOk) { throw "[Install] pip indisponível após tentativa de bootstrap (ensurepip/get-pip)." }

Write-Host "`n=== Instalando DOU SnapTrack ==="
Write-Host "[Install] Instalando pacote em modo editável (desenvolvimento)..."
Write-Host "  Modo: --user (sem necessidade de admin)"

$succ = $false
try { $repoPath = (Resolve-Path ".").Path } catch { $repoPath = (Get-Location).Path }

# Verificar se já está instalado em modo editável neste local
$cmd = "& `"$py`" -m pip show dou-snaptrack"
$rshow = Run-GetResult $cmd 20
if ($rshow.ExitCode -eq 0 -and ($rshow.Stdout)) {
  $editableLoc = $null
  foreach ($line in ($rshow.Stdout -split "`r?`n")) {
    if ($line -match '^Editable project location:\s*(.+)$') { $editableLoc = $matches[1].Trim(); break }
  }
  if ($editableLoc) {
    $a = ($editableLoc -replace '/', '\\').TrimEnd('\\')
    $b = ($repoPath -replace '/', '\\').TrimEnd('\\')
    if ($a.ToLowerInvariant() -eq $b.ToLowerInvariant()) {
      Write-Host "[Install] ✓ Pacote já instalado em modo editável neste repositório."
      Write-Host "  Localização: $editableLoc"
      $succ = $true
    }
  }
}

if (-not $succ) {
  Write-Host "[Install] Instalando pacote..."
  $cmd = "& `"$py`" -m pip install --user --no-warn-script-location -e ."
  $r = Run-GetResult $cmd 900
  
  if ($r.ExitCode -eq 0 -or ($r.Stdout -match '(?i)Successfully installed')) {
    Write-Host "[Install] ✓ Pacote instalado com sucesso!"
    $succ = $true
  } else {
    $msg = "[Install] ❌ Falha ao instalar o pacote em modo usuário.`n" +
           "Exit Code: {0}`n`nSTDOUT:`n{1}`n`nSTDERR:`n{2}" -f $r.ExitCode, $r.Stdout, $r.Stderr
    throw $msg
  }
}

if (-not $SkipSmoke) {
  Write-Host "`n=== Configurando Playwright ==="
  
  # Verificar se Playwright está instalado
  Write-Host "[Playwright] Verificando instalação..."
  $cmd = "& `"$py`" -c `"import importlib; m=importlib.util.find_spec('playwright'); print('installed' if m else 'missing')`""
  $pwCheck = Run-GetResult $cmd 30
  
  if ($pwCheck.Stdout -notmatch 'installed') {
    Write-Warning "[Playwright] Não encontrado. Instalando..."
  $cmd = "& `"$py`" -m pip install --user playwright"
  $pwInstall = Run-GetResult $cmd 300
    if ($pwInstall.ExitCode -ne 0) {
      Write-Warning "[Playwright] Falha na instalação. Testes de browser podem falhar."
    }
  } else {
    Write-Host "[Playwright] ✓ Já instalado"
  }

  # Instalar navegadores Playwright (Chrome/Edge) automaticamente
  Write-Host "[Playwright] Instalando navegadores (Chrome/Edge)..."
  Write-Host "  (Isso pode levar alguns minutos na primeira vez...)"
  
  $cmd = "& `"$py`" -m playwright install chromium --with-deps"
  $browserInstall = Run-GetResult $cmd 600
  
  if ($browserInstall.ExitCode -eq 0) {
    Write-Host "[Playwright] ✓ Navegadores instalados com sucesso"
  } else {
    Write-Warning "[Playwright] Instalação de navegadores falhou. Tentando sem dependências do sistema..."
  $cmd = "& `"$py`" -m playwright install chromium"
  $browserInstall2 = Run-GetResult $cmd 600
    
    if ($browserInstall2.ExitCode -eq 0) {
      Write-Host "[Playwright] ✓ Navegador Chromium instalado (sem deps do sistema)"
    } else {
      Write-Warning "[Playwright] Não foi possível instalar navegadores automaticamente."
      Write-Warning "  Execute manualmente: $py -m playwright install chromium"
    }
  }

  # Smoke test
  Write-Host "`n[Install] Executando smoke test..."
  $cmd = "& `"$py`" scripts\playwright_smoke.py"
  $smokeTest = Run-GetResult $cmd 60
  
  if ($smokeTest.ExitCode -eq 0) {
    Write-Host "[Install] ✓ Smoke test passou! Navegador funcionando corretamente."
  } else {
    Write-Warning "[Install] Smoke test falhou. Saída:"
    Write-Warning $smokeTest.Stderr
    Write-Warning "`nVocê pode precisar configurar o navegador manualmente."
  }
}

Write-Host "`n=== Instalação Concluída ==="
Write-Host "✓ Python: $pyExe"
Write-Host "✓ Pacote: dou-snaptrack (modo editável)"
Write-Host "✓ Playwright: Configurado"
Write-Host "`nPara iniciar a aplicação:"
Write-Host "  1. Via atalho na Área de Trabalho (se criado)"
Write-Host "  2. Executar: scripts\run-ui-managed.ps1"
Write-Host "  3. Duplo clique em: launch_ui.vbs"

# Criar atalho na área de trabalho ao final
try {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $shortcutScript = Join-Path $scriptDir 'create-desktop-shortcut.ps1'
  if (Test-Path $shortcutScript) {
    Write-Host "[Install] Criando atalho na Área de Trabalho"
    Run "& `"$shortcutScript`""
  } else {
    Write-Warning "[Install] Script para criar atalho não encontrado: $shortcutScript"
  }
} catch {
  Write-Warning "[Install] Falha ao criar atalho: $_"
}
