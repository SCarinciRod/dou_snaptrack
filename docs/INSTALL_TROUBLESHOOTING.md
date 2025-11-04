# 🔧 Análise e Correção de Problemas de Instalação

## 📋 Problemas Identificados

### 1. **install.ps1 - Instalação Python Automática**

#### Problema 1.1: Versão Python 3.13 Não Recomendada
```powershell
[string]$PythonVersions = "3.13;3.12;3.11"  # ❌ 3.13 é muito novo
```

**Impacto**:
- Python 3.13 lançado recentemente (out/2024)
- Muitas bibliotecas ainda sem suporte (wheels)
- Playwright pode ter problemas de compatibilidade
- Streamlit pode falhar

**Solução**:
```powershell
[string]$PythonVersions = "3.12;3.11;3.10"  # ✅ Versões estáveis
```

---

#### Problema 1.2: Mapeamento de Versões Desatualizado
```powershell
$versionMap = @{
    '3.13' = '3.13.0'  # ❌ Versão inicial, pode ter bugs
    '3.12' = '3.12.7'  # ⚠️ Pode estar desatualizada
    '3.11' = '3.11.9'  # ⚠️ Pode estar desatualizada
}
```

**Impacto**:
- URLs de download podem estar quebradas (versão não existe mais)
- Patch versions antigas podem ter vulnerabilidades

**Solução**: Usar endpoint `/latest/` do python.org
```powershell
# Obter versão mais recente automaticamente
function Get-LatestPythonVersion([string]$major_minor) {
    $url = "https://www.python.org/downloads/release/"
    # Ou hardcode com versões verificadas em Nov/2024:
    $versionMap = @{
        '3.12' = '3.12.7'  # Última stable
        '3.11' = '3.11.10' # Última stable
        '3.10' = '3.10.15' # Última stable
    }
}
```

---

#### Problema 1.3: Instalação Silenciosa Pode Falhar Sem Feedback

```powershell
$proc = Start-Process -FilePath $tmp -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
```

**Impacto**:
- `/passive` mostra barra mas usuário não vê se travou
- Timeouts longos (1-2 min) sem progresso visível
- Erro silencioso se instalador não rodar

**Solução**: Adicionar timeout e feedback
```powershell
Write-Host "  [2/3] Instalando Python (timeout: 5 minutos)..."
$proc = Start-Process -FilePath $tmp -ArgumentList $installArgs -Wait -PassThru
$timeout = 300  # 5 minutos

$timer = [Diagnostics.Stopwatch]::StartNew()
while (-not $proc.HasExited -and $timer.Elapsed.TotalSeconds -lt $timeout) {
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 5
}

if (-not $proc.HasExited) {
    Write-Warning "  Timeout! Matando processo..."
    $proc.Kill()
    throw "Instalação Python excedeu $timeout segundos"
}
```

---

#### Problema 1.4: Verificação Python Após Instalação Frágil

```powershell
Start-Sleep -Seconds 3  # ❌ Tempo fixo pode ser insuficiente
$found = Find-PythonCandidate -versions $versions
```

**Impacto**:
- Instalação pode levar mais de 3s para registrar no PATH
- Falha intermitente "Python não detectado após instalação"
- Usuário precisa reiniciar terminal manualmente

**Solução**: Retry com crescimento exponencial
```powershell
Write-Host "  [3/3] Aguardando registro no sistema..."
$maxRetries = 10
$retryDelay = 2

for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds $retryDelay
    
    Write-Host "  Tentativa $i/$maxRetries..." -NoNewline
    $found = Find-PythonCandidate -versions $versions
    
    if ($found) {
        Write-Host " ✓"
        break
    }
    
    Write-Host " ✗"
    $retryDelay = [Math]::Min($retryDelay * 1.5, 10)
}
```

---

### 2. **install.ps1 - Instalação de Dependências**

#### Problema 2.1: pip Bootstrap Pode Falhar Silenciosamente

```powershell
$cmd = "& `"$py`" -m ensurepip --upgrade"
$ens = Run-GetResult $cmd 180
if ($ens.ExitCode -eq 0) {
    Write-Host "[pip] ✓ Instalado via ensurepip"
    $pipOk = $true
}
```

**Impacto**:
- Exit code 0 não garante que pip está funcional
- Pode instalar pip mas PATH não atualizado
- `pip --version` falha mas instalação continua

**Solução**: Verificar funcionalidade real
```powershell
# Após instalação, TESTAR pip funcional
$verifyCmd = "& `"$py`" -m pip list --format=json"
$verify = Run-GetResult $verifyCmd 30

if ($verify.ExitCode -eq 0 -and $verify.Stdout -match '^\[') {
    Write-Host "[pip] ✓ Verificado funcional"
    $pipOk = $true
} else {
    Write-Warning "[pip] Instalado mas não funcional"
    $pipOk = $false
}
```

---

#### Problema 2.2: Playwright Install Navegadores Pode Travar

```powershell
$cmd = "& `"$py`" -m playwright install chromium --with-deps"
$browserInstall = Run-GetResult $cmd 600  # 10 minutos!
```

**Impacto**:
- Download ~300MB pode levar >10min em conexões lentas
- Timeout 600s pode ser insuficiente
- Usuário não vê progresso (parece travado)
- `--with-deps` pode pedir `sudo` em alguns sistemas (falha silenciosa)

**Solução**: Feedback de progresso e timeout maior
```powershell
Write-Host "[Playwright] Instalando Chromium (~300MB)..."
Write-Host "  Isso pode levar 5-15 minutos dependendo da conexão..."
Write-Host "  Aguarde... (timeout: 20 minutos)"

# Background job com progresso
$job = Start-Job -ScriptBlock {
    param($python)
    & $python -m playwright install chromium 2>&1
} -ArgumentList $py

$timeout = 1200  # 20 minutos
$elapsed = 0

while ($job.State -eq 'Running' -and $elapsed -lt $timeout) {
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 5
    $elapsed += 5
    
    # A cada 30s mostrar progresso
    if ($elapsed % 30 -eq 0) {
        Write-Host " [$($elapsed)s]"
    }
}

if ($job.State -eq 'Running') {
    Stop-Job $job
    Remove-Job $job
    Write-Warning "[Playwright] Timeout após ${timeout}s"
} else {
    $output = Receive-Job $job
    Remove-Job $job
    
    if ($output -match 'success|downloaded') {
        Write-Host "`n[Playwright] ✓ Instalado"
    }
}
```

---

#### Problema 2.3: Smoke Test Falha Sem Detalhes

```powershell
if ($smokeTest.ExitCode -eq 0) {
    Write-Host "[Install] ✓ Smoke test passou!"
} else {
    Write-Warning "[Install] Smoke test falhou. Saída:"
    Write-Warning $smokeTest.Stderr  # ❌ Pode estar vazio!
}
```

**Impacto**:
- Stderr pode não conter o erro real
- Stdout ignorado (pode ter mensagem útil)
- Difícil debug para usuário

**Solução**: Mostrar AMBOS stdout e stderr
```powershell
if ($smokeTest.ExitCode -ne 0) {
    Write-Warning "[Install] ❌ Smoke test falhou (exit: $($smokeTest.ExitCode))"
    
    if ($smokeTest.Stdout) {
        Write-Warning "`nStdout:"
        Write-Warning $smokeTest.Stdout
    }
    
    if ($smokeTest.Stderr) {
        Write-Warning "`nStderr:"
        Write-Warning $smokeTest.Stderr
    }
    
    Write-Warning "`n💡 Dica: Tente executar manualmente:"
    Write-Warning "  $py scripts\playwright_smoke.py"
}
```

---

### 3. **bootstrap.ps1 - Download e Extração**

#### Problema 3.1: Download Pode Falhar em Redes Lentas

```powershell
Invoke-WebRequest -UseBasicParsing -Uri $zipUrl -OutFile $tmpZip  # ❌ Sem timeout!
```

**Impacto**:
- Redes lentas/instáveis podem travar infinitamente
- Sem progresso visível (~50MB download)
- Falha silenciosa se conexão cair

**Solução**: Timeout e retry
```powershell
Write-Host "[Bootstrap] Baixando (~50MB)..."

$maxAttempts = 3
$timeoutSec = 120

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
        Write-Host "  Tentativa $attempt/$maxAttempts..."
        
        $ProgressPreference = 'SilentlyContinue'  # Acelera download
        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri $zipUrl `
            -OutFile $tmpZip `
            -TimeoutSec $timeoutSec
        
        # Verificar se arquivo baixou completo
        $size = (Get-Item $tmpZip).Length / 1MB
        Write-Host "  ✓ Baixado: $([math]::Round($size, 2)) MB"
        break
        
    } catch {
        Write-Warning "  ✗ Falha: $($_.Exception.Message)"
        
        if ($attempt -lt $maxAttempts) {
            Write-Host "  Aguardando 5s antes de retry..."
            Start-Sleep -Seconds 5
        } else {
            throw "Download falhou após $maxAttempts tentativas"
        }
    }
}
```

---

#### Problema 3.2: Extração Pode Falhar por Arquivo Corrompido

```powershell
Expand-Archive -Path $tmpZip -DestinationPath $expandDir -Force  # ❌ Sem validação
```

**Impacto**:
- ZIP corrompido extrai parcialmente
- Instalação continua com arquivos faltando
- Erro genérico "arquivo não encontrado" depois

**Solução**: Validar ZIP antes de extrair
```powershell
Write-Host "[Bootstrap] Validando arquivo..."

# Verificar se é ZIP válido
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
    $entryCount = $zip.Entries.Count
    $zip.Dispose()
    
    Write-Host "  ✓ ZIP válido ($entryCount arquivos)"
} catch {
    throw "Arquivo baixado está corrompido: $($_.Exception.Message)"
}

Write-Host "[Bootstrap] Extraindo..."
Expand-Archive -Path $tmpZip -DestinationPath $expandDir -Force
```

---

#### Problema 3.3: Branch Incorreta Pode Causar Path Inválido

```powershell
$srcDir = Join-Path $expandDir "dou_snaptrack-$Branch"  # ❌ E se branch tiver caracteres especiais?
```

**Impacto**:
- Branch com `/` (ex: `feature/new`) quebra path
- GitHub transforma `eagendas-n1-fix` → `dou_snaptrack-eagendas-n1-fix`
- Path não encontrado, cópia falha

**Solução**: Detectar diretório automaticamente
```powershell
Write-Host "[Bootstrap] Localizando diretório extraído..."

# Encontrar diretório que começa com "dou_snaptrack"
$extractedDirs = Get-ChildItem -Path $expandDir -Directory | 
                 Where-Object { $_.Name -like "dou_snaptrack*" }

if ($extractedDirs.Count -eq 0) {
    throw "Nenhum diretório 'dou_snaptrack*' encontrado em $expandDir"
}

if ($extractedDirs.Count -gt 1) {
    Write-Warning "Múltiplos diretórios encontrados, usando primeiro"
}

$srcDir = $extractedDirs[0].FullName
Write-Host "  ✓ Encontrado: $($extractedDirs[0].Name)"
```

---

#### Problema 3.4: Chamada Recursiva de install.ps1 Sem Passar Parâmetros

```powershell
& powershell -ExecutionPolicy Bypass -File $installScript  # ❌ Sem parâmetros!
```

**Impacto**:
- Bootstrap não pode passar `$AllowWinget`, `$SkipSmoke`, etc
- Usuário não pode customizar instalação via bootstrap
- Sempre usa defaults (pode não ser desejado)

**Solução**: Propagar parâmetros
```powershell
param(
  [string]$InstallDir = "$env:USERPROFILE\dou_snaptrack",
  [string]$Branch = "main",
  [switch]$AllowWinget,  # ✅ Novo
  [switch]$SkipSmoke,    # ✅ Novo
  [switch]$SkipPlaywright  # ✅ Novo (opcional)
)

# ...

# Construir argumentos para passar ao install.ps1
$installArgs = @()
if ($AllowWinget) { $installArgs += '-AllowWinget' }
if ($SkipSmoke) { $installArgs += '-SkipSmoke' }
if ($SkipPlaywright) { $installArgs += '-SkipPlaywright' }

$installScriptArgs = $installArgs -join ' '

Write-Host "[Bootstrap] Executando install.ps1 $installScriptArgs"
& powershell -ExecutionPolicy Bypass -File $installScript @installArgs
```

---

## 🎯 Problemas Mais Críticos (Ordem de Prioridade)

### P0 - Crítico (Causa falha total)
1. ✅ **Python 3.13 incompatível** → Mudar para 3.12/3.11
2. ✅ **Playwright timeout** → Aumentar para 20min + progresso
3. ✅ **Branch path incorreto** → Auto-detectar diretório

### P1 - Alto (Causa falha frequente)
4. ✅ **Instalação Python sem feedback** → Adicionar timeout + progresso
5. ✅ **pip bootstrap sem validação** → Testar funcionalidade real
6. ✅ **Smoke test sem output** → Mostrar stdout+stderr

### P2 - Médio (UX ruim mas funciona)
7. ✅ **Download sem retry** → Retry com backoff
8. ✅ **ZIP sem validação** → Verificar integridade
9. ✅ **Verificação Python com delay fixo** → Retry incremental

### P3 - Baixo (Nice to have)
10. ⚠️ **Bootstrap sem passar parâmetros** → Propagar flags
11. ⚠️ **Versionamento Python hardcoded** → Auto-fetch latest

---

## 📝 Scripts Corrigidos

Vou criar versões corrigidas dos scripts com todas as melhorias aplicadas.

**Próximos passos**:
1. Criar `install_fixed.ps1` com todas correções
2. Criar `bootstrap_fixed.ps1` com todas correções  
3. Testar em máquina limpa (VM Windows)
4. Documentar comandos de teste
5. Substituir scripts originais após validação

---

**Criado**: 2025-11-04  
**Status**: Análise completa ✅ | Correções pendentes ⏳  
**Estimativa**: 2-3h para implementar todas correções
