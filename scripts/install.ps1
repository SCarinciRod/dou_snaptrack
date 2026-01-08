param(
  [string]$Python = "python",
  [string]$VenvDir = ".venv",
  # Preferir versões com melhor suporte de pacotes/binários (Playwright é mais estável em 3.12 hoje)
  [string]$PythonVersions = "3.12;3.11",
  [switch]$AllowWinget,
  [switch]$SkipSmoke,
  [switch]$ForceCleanVenv,
  [switch]$NoVenv,
  [switch]$Quiet
)

# Normalize console encoding to UTF-8 for consistent output (best effort)
try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
} catch {}

# Detectar SO de forma compativel com Windows PowerShell 5.1
$onWindows = $false
try {
  if ($env:OS -and $env:OS -match 'Windows_NT') { $onWindows = $true } else { $onWindows = $false }
} catch { $onWindows = $false }

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
  Write-Host "[Venv] Limpando diretorio existente: $path"
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
  function TryVenv([string]$venvArgs) {
    try { Run "$BasePython $venvArgs" 120; return $true }
    catch { $script:lastErr = $_; return $false }
  }
  function CheckVenvCreated([string]$dir) {
    $pyPath = Join-Path $dir "Scripts\python.exe"
    return (Test-Path $pyPath)
  }

  if (-not $created) {
    if (TryVenv "-m venv `"$targetDir`"") { $created = $true }
    elseif (CheckVenvCreated $targetDir) { $created = $true; Write-Host "[Venv] venv criada (exit code ignorado)" }
    else { Write-Warning ("[Venv] venv padrao falhou: {0}" -f $script:lastErr.Exception.Message) }
    if (-not $created -and ($script:lastErr.Exception.Message -match 'Permission denied')) { $permDenied = $true }
  }
  if (-not $created) {
    if (TryVenv "-m venv --without-pip `"$targetDir`"") { $created = $true }
    elseif (CheckVenvCreated $targetDir) { $created = $true; Write-Host "[Venv] venv criada (exit code ignorado)" }
    else { Write-Warning ("[Venv] venv --without-pip falhou: {0}" -f $script:lastErr.Exception.Message) }
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
    # virtualenv fallback (mais robusto em ambientes com restricoes de symlink/permissao)
    $basePipOk = $false
    # 1) ensurepip
    $ensRes = Run-GetResult "& `"$BasePython`" -m ensurepip --upgrade" 120
    if ($ensRes.ExitCode -eq 0) {
      $basePipOk = $true
    } else {
      Write-Warning "[Venv] ensurepip no Python base falhou, tentando get-pip.py"
      # 2) get-pip.py
      $getPip = Join-Path $env:TEMP "get-pip.py"
      try {
        Invoke-FileDownloadWithRetry -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -MaxAttempts 4 -TimeoutSec 15
        $gpRes = Run-GetResult "& `"$BasePython`" `"$getPip`"" 300
        # Considerar sucesso se pip responder apos execucao, mesmo que exit code inesperado
        $pipVer = Run-GetResult "& `"$BasePython`" -m pip --version" 30
        if ($pipVer.ExitCode -eq 0 -or ($pipVer.Stdout -match '^(?i)pip\s+\d')) { $basePipOk = $true }
        elseif (($gpRes.Stdout -match '(?i)Successfully installed pip')) { $basePipOk = $true }
      } catch {
        Write-Warning ("[Venv] get-pip tambem falhou: {0}" -f $_.Exception.Message)
      } finally {
        try { Remove-Item -LiteralPath $getPip -Force -ErrorAction SilentlyContinue } catch {}
      }
    }
    if ($basePipOk) {
      # 3) instalar virtualenv e criar venv com --copies (evitar symlinks bloqueados)
      try { Run "$BasePython -m pip install --user virtualenv" 240 } catch { Write-Warning ("[Venv] instalacao do virtualenv falhou: {0}" -f $_.Exception.Message) }
      if (TryVenv "-m virtualenv `"$targetDir`" --copies") { $created = $true }
      elseif (CheckVenvCreated $targetDir) { $created = $true; Write-Host "[Venv] virtualenv criada (exit code ignorado)" }
      else { Write-Warning ("[Venv] criacao via virtualenv falhou: {0}" -f $script:lastErr.Exception.Message) }
      if (-not $created -and $permDenied -and $ForceClean) {
        if (Remove-DirectoryRobust $targetDir) {
          if (TryVenv "-m virtualenv `"$targetDir`" --copies") { $created = $true }
          elseif (CheckVenvCreated $targetDir) { $created = $true; Write-Host "[Venv] virtualenv criada apos limpeza (exit code ignorado)" }
        }
      }
    }
  }

  if (-not $created -and $AltVenvDirs -and $AltVenvDirs.Count -gt 0) {
    foreach ($alt in $AltVenvDirs) {
      if ($created) { break }
  Write-Warning "[Venv] Alternando para diretorio alternativo de venv: $alt"
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

  # Alguns ambientes retornam exit code diferente de 0 mesmo com venv criada.
  # Se detectarmos o interpretador na pasta alvo, considerar sucesso.
  $maybePyPath = Join-Path $targetDir "Scripts\python.exe"
  if (-not $created -and (Test-Path $maybePyPath)) { $created = $true }

  if (-not $created) { throw "Falha ao criar venv em $targetDir por todos os metodos." }

  $venvPy = Join-Path $targetDir "Scripts\python.exe"
  if (-not (Test-Path $venvPy)) { throw "Venv criada, mas python.exe nao encontrado: $venvPy" }
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
    $handler = $null
    $client = $null
    try {
      try { Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue } catch {}
      $handler = New-Object System.Net.Http.HttpClientHandler
      $client = New-Object System.Net.Http.HttpClient($handler)
      $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
      $bytes = $client.GetByteArrayAsync($Url).GetAwaiter().GetResult()
      [IO.File]::WriteAllBytes($OutFile, $bytes)
      Write-Host "[Download] Sucesso na tentativa $attempt"
      return
    } catch {
      Write-Warning ("[Download] Falha na tentativa {0}: {1}" -f $attempt, $_.Exception.Message)
      if ($attempt -lt $MaxAttempts) {
        Start-Sleep -Seconds $delay
        $delay = [Math]::Min($delay * 2, 8)
      }
    } finally {
      if ($client) { $client.Dispose() }
      if ($handler) { $handler.Dispose() }
    }
  }
  throw "Falha no download após $MaxAttempts tentativas: $Url"
}

function Get-PyVer([string]$exe) {
  try { return (& $exe -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null) } catch { return $null }
}

function Find-PythonCandidate([string[]]$versions) {
  $minVersion = [version]'3.10'
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
    try {
      $exePath = & $wa -c "import sys; print(sys.executable)" 2>$null
      if ($exePath -and -not ($exePath -like '*\\WindowsApps\\*') -and (Test-Path $exePath)) {
        $ver = Get-PyVer $wa
        if ($ver) {
          try { if ([version]$ver -ge $minVersion) { return $exePath.Trim() } } catch {}
        } else { return $exePath.Trim() }
      }
    } catch {}
  }
  # 4) python no PATH
  try {
    $ver = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
    if ($LASTEXITCODE -eq 0) {
      if ($ver) { try { if ([version]$ver -lt $minVersion) { return $null } } catch {} }
      $exe = & $Python -c "import sys; print(sys.executable)" 2>$null
      if ($exe -and -not ($exe -like '*\\WindowsApps\\*') -and (Test-Path $exe)) { return $exe.Trim() }
    }
  } catch {}
  return $null
}

function Resolve-Python {
  param([string]$Versions = "3.12;3.11", [switch]$AllowWinget)
  # Normalizar lista de versoes em array de strings (suporta ; , e espaco)
  $versions = @()
  if ($Versions) {
    $versions = ($Versions -split '[,; ]+') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }
  $versions = @([string[]]$versions)
  # Garantir que seja um array mesmo se vier como string unica
  if ($versions -is [string]) { $versions = ($versions -split '[,; ]+') | ForEach-Object { $_.Trim() } | Where-Object { $_ } }
  if (-not $versions -or $versions.Count -eq 0) { $versions = @('3.12','3.11') }
  Write-Host "`n=== Procurando Python ==="
  Write-Host "[Python] Versoes aceitas: $($versions -join ', ')"
  
  $found = Find-PythonCandidate -versions $versions
  if ($found) {
    Write-Host "[Python] Encontrado: $found"
    $ver = Get-PyVer $found
    if ($ver) { Write-Host "[Python] Versao: $ver" }
    # Se encontrou uma versao fora da lista aceita, continuar com instalacao das aceitas
    if ($ver -and $versions -and -not ($versions -contains $ver)) {
      Write-Host "[Python] Versao encontrada ($ver) fora da lista aceita. Prosseguindo para instalar: $($versions -join ', ')"
    } else {
      return $found
    }
  }

  Write-Host "`n[Python] Nao encontrado no sistema. Iniciando instalacao automatica..."
  Write-Host "[Python] Modo: PER-USER (sem necessidade de admin)"
  Write-Host ""

  # Mapear versões full
  $versionMap = @{

    '3.12' = '3.12.7'
    '3.11' = '3.11.9'
  }

  # Tentar instalar cada versão até conseguir
  $versionsToInstall = @($versions | ForEach-Object { $_.Trim() }) | Where-Object { $_ }
  if ($versionsToInstall -is [string]) { $versionsToInstall = ($versionsToInstall -split '[,; ]+') | ForEach-Object { $_.Trim() } | Where-Object { $_ } }
  foreach ($v in $versionsToInstall) {
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
  Write-Host "  [1/3] Download concluido"
    } catch {
      Write-Warning "  [1/3] Download falhou: $($_.Exception.Message)"
      continue
    }

    # Verificar se arquivo foi baixado
    if (-not (Test-Path $tmp)) {
      Write-Warning "  Arquivo nao encontrado apos download: $tmp"
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
  Write-Host "  Diretorio: $installDir"
  Write-Host "  IMPORTANTE: Instalacao PER-USER (sem necessidade de admin)"
    
    try {
      # Usar Start-Process com -Verb RunAs REMOVIDO (não pedir admin)
      # -Wait garante que esperamos a instalação terminar
      # -WindowStyle Hidden oculta janela (ou use Normal para debug)
      $proc = Start-Process -FilePath $tmp -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
      
      $exitCode = $proc.ExitCode
  Write-Host "  [2/3] Instalacao finalizada (Exit Code: $exitCode)"
      
      # Exit codes do instalador Python:
      # 0 = Sucesso
      # 1602 = Usuário cancelou (não deve acontecer em /passive)
      # 1638 = Outra versão já instalada
      # 3010 = Sucesso mas requer reinicialização
      
      if ($exitCode -eq 0 -or $exitCode -eq 3010) {
  Write-Host "  [2/3] Instalacao bem-sucedida"
      } elseif ($exitCode -eq 1638) {
  Write-Host "  [2/3] Python ja esta instalado"
      } else {
  Write-Warning "  [2/3] Exit code nao esperado: $exitCode"
      }
      
    } catch {
  Write-Warning "  [2/3] Erro ao executar instalador: $($_.Exception.Message)"
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
      $foundVer = Get-PyVer $found
      if ($foundVer -and -not ($versions -contains $foundVer)) { $found = $null }
    }
    if ($found) {
      Write-Host "  [3/3] Python detectado com sucesso!"
      Write-Host "  Localizacao: $found"
      return $found
    } else {
      Write-Warning "  [3/3] Python nao detectado apos instalacao"
      Write-Host "  Tentando buscar diretamente em: $installDir"
      $directPy = Join-Path $installDir "python.exe"
      if (Test-Path $directPy) {
        Write-Host "  [3/3] Encontrado diretamente: $directPy"
        return $directPy
      }
    }
  }

  # Fallback: winget (se permitido e disponível)
  if ($AllowWinget) {
  Write-Host "`n[Python] Tentando instalacao via winget..."
    foreach ($v in $versions) {
      $wingetId = "Python.Python.$v"
      Write-Host "[winget] Instalando $wingetId..."
      
      try {
        # winget install com argumentos para instalação silenciosa de usuário
        $wingetArgs = "install -e --id $wingetId --scope user --accept-source-agreements --accept-package-agreements --silent"
        Run "winget $wingetArgs" 300
        
  Write-Host "[winget] Comando executado"
        Start-Sleep -Seconds 5
        
        $found = Find-PythonCandidate -versions $versions
        if ($found) {
          Write-Host "[winget] Python detectado apos instalacao via winget!"
          return $found
        }
      } catch {
        Write-Warning "[winget] Falha: $($_.Exception.Message)"
      }
    }
  }

  # Se chegou aqui, falhou
  Write-Host ""
  Write-Host "[Python] Instalacao automatica de Python falhou"
  Write-Host ""
  Write-Host ""
  Write-Host "Por favor, instale Python manualmente:"
  Write-Host ""
  Write-Host "1. Acesse: https://www.python.org/downloads/"
  Write-Host "2. Baixe Python 3.12 ou 3.11"
  Write-Host "3. Durante instalação:"
  Write-Host "   - Marque 'Add Python to PATH'"
  Write-Host "   - Escolha 'Install for current user only' (NAO precisa de admin)"
  Write-Host "4. Após instalação, execute novamente: .\scripts\install.ps1"
  Write-Host ""
  
  throw "Python nao encontrado. Instalacao manual necessaria."
}


$pyExe = Resolve-Python -Versions $PythonVersions -AllowWinget:$AllowWinget

Write-Host ""
Write-Host "=== DOU SnapTrack - Instalacao Automatica ==="
Write-Host ""
Write-Host "Python base encontrado: $pyExe"
Write-Host "Modo: Instalacao de usuario (sem necessidade de admin)"
Write-Host "Tipo: Desenvolvimento (modo editavel)"
Write-Host ""

# --- Preparar ambiente do programa ---
$usingVenv = $true
if ($NoVenv) { $usingVenv = $false }

if ($usingVenv) {
  Write-Host "[Env] Criando/atualizando ambiente virtual em '$VenvDir'"
  try {
    $venv = New-VenvRobust -BasePython $pyExe -VenvDir $VenvDir -ForceClean:$ForceCleanVenv
    $py = $venv.Python
    Write-Host "[Env] Venv pronta: $($venv.VenvDir)"
    Write-Host "[Env] Python da venv: $py"
  } catch {
    Write-Warning "[Env] Falha ao criar venv. Continuando sem venv. Detalhe: $($_.Exception.Message)"
    $usingVenv = $false
    $py = $pyExe
  }
} else {
  Write-Host "[Env] Opcao -NoVenv ativa: usando Python base"
  $py = $pyExe
}
Write-Host "=== Verificando dependencias ==="
Write-Host "[pip] Verificando gerenciador de pacotes..."
$pipOk = $false
$cmd = "& `"$py`" -m pip --version"
$chk = Run-GetResult $cmd 30

if ($chk.ExitCode -eq 0 -or ($chk.Stdout -match '^(?i)pip\s+\d')) {
  $pipOk = $true
  # Extrair versão do pip
  if ($chk.Stdout -match 'pip\s+([\d.]+)') {
  Write-Host "[pip] Versao $($matches[1]) encontrada"
  } else {
  Write-Host "[pip] Instalado e funcional"
  }
}

if (-not $pipOk) {
  Write-Warning "[pip] Nao encontrado. Inicializando pip..."
  
  # Tentar ensurepip primeiro
  Write-Host "[pip] Tentando ensurepip..."
  $cmd = "& `"$py`" -m ensurepip --upgrade"
  $ens = Run-GetResult $cmd 180
  if ($ens.ExitCode -eq 0) {
  Write-Host "[pip] Instalado via ensurepip"
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
  Write-Host "[pip] Instalado via get-pip.py"
    } catch {
  Write-Warning "[pip] Falha no download/instalacao de get-pip.py"
    } finally {
      try { Remove-Item -LiteralPath $getPip -Force -ErrorAction SilentlyContinue } catch {}
    }
  }
  
  # Verificar novamente
  $cmd = "& `"$py`" -m pip --version"
  $chk2 = Run-GetResult $cmd 30
  if ($chk2.ExitCode -eq 0 -or ($chk2.Stdout -match '^(?i)pip\s+\d')) {
    $pipOk = $true
  Write-Host "[pip] Verificacao final OK"
  } else {
    $pipOk = $false
  }
}
if (-not $pipOk) { throw "[Install] pip indisponivel apos tentativa de bootstrap (ensurepip/get-pip)." }

Write-Host "`n=== Instalando DOU SnapTrack ==="
Write-Host "[Install] Instalando pacote em modo editavel (desenvolvimento)..."
if ($usingVenv) { Write-Host "  Modo: venv local ($VenvDir)" } else { Write-Host "  Modo: --user (sem necessidade de admin)" }

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
    Write-Host "[Install] Pacote ja instalado em modo editavel neste repositorio."
      Write-Host "  Localizacao: $editableLoc"
      $succ = $true
    }
  }
}

if (-not $succ) {
  Write-Host "[Install] Instalando pacote..."
  if ($usingVenv) {
    $cmd = "& `"$py`" -m pip install -e ."
  } else {
    $cmd = "& `"$py`" -m pip install --user --no-warn-script-location -e ."
  }
  $r = Run-GetResult $cmd 900
  
  if ($r.ExitCode -eq 0 -or ($r.Stdout -match '(?i)Successfully installed')) {
  Write-Host "[Install] Pacote instalado com sucesso!"
    $succ = $true
  } else {
    # Alguns ambientes retornam exit code não-zero por warnings/interceptação, mesmo com o pacote instalável.
    # Antes de abortar, validar import do pacote.
    Write-Warning "[Install] pip retornou exit code nao-zero. Validando import do pacote antes de abortar..."
    $imp = Run-GetResult "& `"$py`" -c `"import dou_snaptrack, dou_utils; print('IMPORT_OK')`"" 30
    if ($imp.ExitCode -eq 0 -and ($imp.Stdout -match 'IMPORT_OK')) {
      Write-Host "[Install] Import OK. Prosseguindo apesar do exit code do pip."
      $succ = $true
    } else {
      $msg = "[Install] Falha ao instalar o pacote em modo usuario.`n" +
             "Exit Code: {0}`n`nSTDOUT:`n{1}`n`nSTDERR:`n{2}" -f $r.ExitCode, $r.Stdout, $r.Stderr
      throw $msg
    }
  }
}

if (-not $SkipSmoke) {
  Write-Host "`n=== Configurando Playwright ==="
  
  # Verificar se Playwright esta instalado (por import direto, mais confiavel que 'pip show')
  Write-Host "[Playwright] Verificando modulo (import)..."
  $cmd = "& `"$py`" -c `"import importlib.util,sys; sys.exit(0 if importlib.util.find_spec(''playwright'') else 2)`""
  $pwImport = Run-GetResult $cmd 30

  if ($pwImport.ExitCode -ne 0) {
    Write-Warning "[Playwright] Modulo nao encontrado. Instalando..."
    # 1) Atualizar ferramentas de empacotamento
    if ($usingVenv) { $cmd = "& `"$py`" -m pip install -U pip setuptools wheel" }
    else { $cmd = "& `"$py`" -m pip install -U pip setuptools wheel --user" }
    $null = Run-GetResult $cmd 240

    # 2) Tentativa padrao
    if ($usingVenv) { $cmd = "& `"$py`" -m pip install playwright" }
    else { $cmd = "& `"$py`" -m pip install --user playwright" }
    $pwInstall1 = Run-GetResult $cmd 420
    if ($pwInstall1.ExitCode -ne 0 -and ($pwInstall1.Stdout -notmatch '(?i)Requirement already satisfied: playwright')) {
      Write-Warning "[Playwright] Falha na instalacao (tentativa 1). Resumo:"
      if ($pwInstall1.Stdout) { Write-Warning ($pwInstall1.Stdout | Select-Object -First 20) }
      if ($pwInstall1.Stderr) { Write-Warning ($pwInstall1.Stderr | Select-Object -First 20) }
      
      # 3) Tentativa com flags de robustez
      if ($usingVenv) { $cmd = "& `"$py`" -m pip install --no-cache-dir --prefer-binary playwright" }
      else { $cmd = "& `"$py`" -m pip install --user --no-cache-dir --prefer-binary playwright" }
      $pwInstall2 = Run-GetResult $cmd 420
      if ($pwInstall2.ExitCode -ne 0) {
        Write-Warning "[Playwright] Falha na instalacao (tentativa 2). Tentando versao especifica..."
        # 4) Pinar para uma versao recente conhecida
        $versionsTry = @('1.49.*','1.48.*','1.47.*')
        $installed = $false
        foreach ($pv in $versionsTry) {
          if ($usingVenv) { $cmd = "& `"$py`" -m pip install --no-cache-dir --prefer-binary playwright==$pv" }
          else { $cmd = "& `"$py`" -m pip install --user --no-cache-dir --prefer-binary playwright==$pv" }
          $pwPin = Run-GetResult $cmd 420
          if ($pwPin.ExitCode -eq 0) { $installed = $true; break }
        }
        if (-not $installed) {
          Write-Warning "[Playwright] Nao foi possivel instalar o pacote playwright via pip."
          Write-Warning "  Dicas: configurar PROXY (HTTPS_PROXY/HTTP_PROXY), CA corporativa (SSL_CERT_FILE/REQUESTS_CA_BUNDLE)"
          Write-Warning "  ou tentar novamente com: $py -m pip install --no-cache-dir --prefer-binary playwright"
        }
      }
    }

    # Revalidar import
    $cmd = "& `"$py`" -c `"import importlib.util,sys; sys.exit(0 if importlib.util.find_spec(''playwright'') else 2)`""
    $pwImport = Run-GetResult $cmd 30
    # Considerar instalado se pip disse 'Requirement already satisfied'
    if ($pwImport.ExitCode -ne 0 -and ($pwInstall1.Stdout -match '(?i)Requirement already satisfied: playwright')) {
      $pwImport = [pscustomobject]@{ ExitCode = 0; Stdout = 'import-ok-by-pip-satisfied'; Stderr = ''; TimedOut = $false }
      Write-Host "[Playwright] Detectado via pip: Requirement already satisfied"
    }
    if ($pwImport.ExitCode -eq 0) { Write-Host "[Playwright] Modulo instalado com sucesso" }
    else { Write-Warning "[Playwright] Modulo ainda ausente apos tentativas. Navegadores nao serao provisionados automaticamente." }
  } else {
    Write-Host "[Playwright] Modulo encontrado"
  }

  # Provisionar navegadores Playwright (Chrome/Edge) automaticamente (somente se modulo presente)
  if ($pwImport.ExitCode -eq 0) {
    # Garantir greenlet funcional (necessario para API sincronica do Playwright)
    $grChk = Run-GetResult "& `"$py`" -c `"import importlib,sys; spec=importlib.util.find_spec(''greenlet._greenlet''); sys.exit(0 if spec else 2)`"" 20
    if ($grChk.ExitCode -ne 0) {
      Write-Warning "[Deps] greenlet._greenlet ausente. Reinstalando greenlet (wheel somente)…"
      $grOk = $false
      $grVers = @('3.2.4','3.2.3','3.2.2','3.0.3')
      foreach ($gv in $grVers) {
        $cmd = "& `"$py`" -m pip install --no-cache-dir --only-binary=:all: -U greenlet==$gv"
        $null = Run-GetResult $cmd 240
        $grChk2 = Run-GetResult "& `"$py`" -c `"import importlib,sys; spec=importlib.util.find_spec(''greenlet._greenlet''); sys.exit(0 if spec else 2)`"" 20
        if ($grChk2.ExitCode -eq 0) {
          $grOk = $true
          Write-Host "[Deps] greenlet $gv instalado com sucesso"
          break
        }
      }
      if (-not $grOk) {
        Write-Warning "[Deps] Falha ao garantir greenlet. A API sync do Playwright pode falhar (use a async ou ajuste politicas)."
      }
    }

    # Tentar remover marca de zona/Smartscreen que pode causar Access denied em binarios baixados
    try {
      $drvPathRes = Run-GetResult "& `"$py`" -c `"import pathlib,playwright; print(str(pathlib.Path(playwright.__file__).with_name('driver')))`"" 20
      if ($drvPathRes.ExitCode -eq 0 -and $drvPathRes.Stdout) {
        $drvDir = $drvPathRes.Stdout.Trim()
        if (Test-Path $drvDir) {
          Write-Host "[Playwright] Desbloqueando arquivos do driver (se aplicavel): $drvDir"
          try { Get-ChildItem -LiteralPath $drvDir -Recurse -Force -File | ForEach-Object { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } } catch {}
        }
      }
    } catch {}

    # Verificar se o driver/CLI do Playwright consegue rodar (diagnostico de permissao)
    $cmd = "& `"$py`" -m playwright --version"
    $cliTest = Run-GetResult $cmd 30
    if ($cliTest.ExitCode -ne 0 -and (($cliTest.Stderr -match '(?i)Access is denied') -or ($cliTest.Stdout -match '(?i)Access is denied'))) {
      Write-Warning "[Playwright] Falha ao iniciar o driver (Access is denied)."
      Write-Warning "  Possivel bloqueio por antivirus/politicas ao executar binarios em: %APPDATA%\\Python\\<versao>\\site-packages\\playwright\\driver"
      Write-Warning "  Solucoes:"
      Write-Warning "   - Adicione excecao/allowlist para a pasta acima"
      Write-Warning "   - OU use venv local (C:\\Projetos\\.venv) e reinstale"
      if (-not $usingVenv) {
        Write-Host "[Playwright] Tentando migrar automaticamente para venv local para contornar bloqueio..."
        try {
          $venvAuto = New-VenvRobust -BasePython $pyExe -VenvDir $VenvDir -ForceClean:$ForceCleanVenv
          if ($venvAuto) {
            $py = $venvAuto.Python
            $usingVenv = $true
            Write-Host "[Playwright] Venv criada em $($venvAuto.VenvDir). Reinstalando pacote e Playwright dentro da venv..."
            # Reinstalar pacote em modo editavel dentro da venv
            $null = Run-GetResult "& `"$py`" -m pip install -U pip setuptools wheel" 240
            $null = Run-GetResult "& `"$py`" -m pip install -e ." 600
            $null = Run-GetResult "& `"$py`" -m pip install playwright" 420
            # Retestar driver
            $cliTest = Run-GetResult "& `"$py`" -m playwright --version" 30
            if ($cliTest.ExitCode -eq 0) {
              Write-Host "[Playwright] Driver operacional na venv. Prosseguindo com instalacao de navegadores."
            } else {
              Write-Warning "[Playwright] Ainda com falha ao iniciar driver apos migracao para venv."
            }
          }
        } catch {
          Write-Warning ("[Playwright] Migracao automatica para venv falhou: {0}" -f $_.Exception.Message)
        }
      }
    }
  # TLS bypass (NODE_TLS_REJECT_UNAUTHORIZED=0) é útil em ambientes com proxy/CA corporativa,
  # mas deve ser opt-in e temporário.
  $prevNodeTls = $env:NODE_TLS_REJECT_UNAUTHORIZED
  $prevPwBrowsers = $env:PLAYWRIGHT_BROWSERS_PATH
  $tlsBypassApplied = $false
  $allowTlsBypass = $false
  try {
    $v = ($env:DOU_UI_ALLOW_TLS_BYPASS)
    if ($v) {
      $vv = $v.Trim().ToLower()
      if ($vv -in @('1','true','yes')) { $allowTlsBypass = $true }
    }
  } catch { $allowTlsBypass = $false }

  function Enable-TlsBypassIfNeeded {
    if (-not $tlsBypassApplied) {
      $env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
      $script:tlsBypassApplied = $true
      Write-Host "[Playwright] NODE_TLS_REJECT_UNAUTHORIZED=0 (temporario para download)"
    }
  }

  # Direcionar cache de navegadores para dentro do projeto/venv quando possivel (evita pastas do Roaming)
  if ($usingVenv) {
    try {
      $pwCache = Join-Path $VenvDir 'pw-browsers'
      $env:PLAYWRIGHT_BROWSERS_PATH = $pwCache
      Write-Host "[Playwright] PLAYWRIGHT_BROWSERS_PATH=$pwCache"
    } catch {}
  }

  Write-Host "[Playwright] Instalando navegadores (Chrome/Edge)..."
  Write-Host "  (Isso pode levar alguns minutos na primeira vez...)"

  # --with-deps é aplicável a Linux; em Windows pode causar falha.
  $installArgs = "install chromium"
  if (-not $onWindows) { $installArgs += " --with-deps" }

  if ($allowTlsBypass) { Enable-TlsBypassIfNeeded }

  $cmd = "& `"$py`" -m playwright $installArgs"
  $browserInstall = Run-GetResult $cmd 600

  # Verificar se navegadores foram realmente baixados (exit code pode ser não-zero por warnings do Node)
  $browserSuccess = $false
  
  # Verificar se o stdout menciona "downloaded to" (sinal de sucesso)
  if ($browserInstall.Stdout -match 'downloaded to') {
    $browserSuccess = $true
  }
  
  # Fallback: verificar se pasta chromium existe no cache
  if (-not $browserSuccess) {
    $possiblePaths = @()
    if ($usingVenv) {
      $possiblePaths += (Join-Path $VenvDir 'pw-browsers')
    }
    $possiblePaths += (Join-Path $env:USERPROFILE 'AppData\Local\ms-playwright')
    $possiblePaths += (Join-Path $env:LOCALAPPDATA 'ms-playwright')
    
    foreach ($testPath in $possiblePaths) {
      if (Test-Path $testPath) {
        $chromiumDirs = Get-ChildItem -Path $testPath -Directory -Filter 'chromium-*' -ErrorAction SilentlyContinue
        if ($chromiumDirs) {
          $browserSuccess = $true
          break
        }
      }
    }
  }

  if ($browserSuccess) {
    Write-Host "[Playwright] Navegadores instalados com sucesso"
  } else {
    Write-Warning "[Playwright] Falha ao instalar navegadores. Saída (resumo):"
    if ($browserInstall.Stdout) { Write-Warning ($browserInstall.Stdout | Select-Object -First 20) }
    if ($browserInstall.Stderr) { Write-Warning ($browserInstall.Stderr | Select-Object -First 20) }

    # Se não foi opt-in, mas parece erro de TLS/certificado, tentar UMA vez com bypass
    if (-not $allowTlsBypass) {
      $tlsHints = ($browserInstall.Stdout + "`n" + $browserInstall.Stderr)
      if ($tlsHints -match '(?i)certificate|self signed|unable to get local issuer|CERT_|SSL|TLS') {
        Write-Warning "[Playwright] Sinais de erro TLS/certificado detectados. Retentando com TLS bypass (temporario)…"
        Enable-TlsBypassIfNeeded
      }
    }

    # Segunda tentativa sem flags adicionais (fallback)
    $cmd = "& `"$py`" -m playwright install chromium"
    $browserInstall2 = Run-GetResult $cmd 600
    
    # Re-verificar após segunda tentativa
    if ($browserInstall2.Stdout -match 'downloaded to') {
      Write-Host "[Playwright] Navegador Chromium instalado (fallback)"
    } else {
      Write-Warning "[Playwright] Nao foi possivel instalar navegadores automaticamente."
      Write-Warning "  Execute manualmente: $py -m playwright install chromium"
      Write-Warning '  (Opcional para logs: defina $env:DEBUG=''pw:install'' e tente novamente)'
    }
  }

  # Restaurar configuracao TLS (seguranca) somente se alteramos
  if ($tlsBypassApplied) {
    if ($null -ne $prevNodeTls -and $prevNodeTls -ne "") {
      $env:NODE_TLS_REJECT_UNAUTHORIZED = $prevNodeTls
    } else {
      $env:NODE_TLS_REJECT_UNAUTHORIZED = "1"
    }
    Write-Host "[Playwright] NODE_TLS_REJECT_UNAUTHORIZED restaurado para $($env:NODE_TLS_REJECT_UNAUTHORIZED)"
  }
  if ($prevPwBrowsers) { $env:PLAYWRIGHT_BROWSERS_PATH = $prevPwBrowsers } else { try { $env:PLAYWRIGHT_BROWSERS_PATH = $null } catch {} }
  } else {
    Write-Warning "[Playwright] Modulo ausente. Pulei instalacao de navegadores."
  }

  # Smoke test
  Write-Host "`n[Install] Executando smoke test..."
  $cmd = "& `"$py`" scripts\playwright_smoke.py"
  $smokeTest = Run-GetResult $cmd 60
  
  if ($smokeTest.ExitCode -eq 0 -or ($smokeTest.Stdout -match 'RESULT\s+SUCCESS')) {
  Write-Host "[Install] Smoke test passou! Navegador funcionando corretamente."
  } else {
    Write-Warning "[Install] Smoke test falhou. Saída:"
    if ($smokeTest.Stdout) { Write-Warning $smokeTest.Stdout }
    if ($smokeTest.Stderr) { Write-Warning $smokeTest.Stderr }
    Write-Warning "`nVoce pode precisar configurar o navegador manualmente."
  }
}

Write-Host "`n=== Instalacao Concluida ==="
Write-Host "Python: $pyExe"
Write-Host "Pacote: dou-snaptrack (modo editavel)"
Write-Host "Playwright: Configurado"
Write-Host "`nPara iniciar a aplicacao:"
Write-Host "  1. Via atalho na Area de Trabalho (se criado)"
Write-Host "  2. Executar: scripts\run-ui-managed.ps1"
Write-Host "  3. Duplo clique em: launch_ui.vbs"

# Criar atalho na área de trabalho ao final
try {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $shortcutScript = Join-Path $scriptDir 'create-desktop-shortcut.ps1'
  if (Test-Path $shortcutScript) {
    Write-Host "[Install] Criando atalho na Area de Trabalho"
    $r = Run-GetResult "& `"$shortcutScript`"" 30
    $lnkPath = Join-Path $env:USERPROFILE "Desktop\Dou SnapTrack.lnk"
    $createdPath = $null
    if (Test-Path $lnkPath) { $createdPath = $lnkPath }
    elseif ($r.Stdout -match 'Atalho criado:\s*(.+\.lnk)') { $createdPath = $matches[1].Trim() }

    if ($createdPath) {
      Write-Host "[Install] Atalho criado: $createdPath"
    } else {
      Write-Warning ("[Install] Falha ao criar atalho (exit={0}).\nSTDOUT:\n{1}\n\nSTDERR:\n{2}" -f $r.ExitCode, $r.Stdout, $r.Stderr)
    }
  } else {
    Write-Warning "[Install] Script para criar atalho nao encontrado: $shortcutScript"
  }
} catch {
  Write-Warning "[Install] Falha ao criar atalho: $_"
}
