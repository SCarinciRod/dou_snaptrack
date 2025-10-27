# 🔒 Instalação Sem Permissões de Administrador

## Problema Resolvido

Anteriormente, a instalação do Python via PowerShell **solicitava permissões de administrador** (UAC), mesmo quando configurado para instalação de usuário. Isso causava problemas em máquinas corporativas ou compartilhadas.

## ✅ Solução Implementada

### 1. Instalação PER-USER do Python

O script agora usa **argumentos específicos** para garantir instalação sem admin:

```powershell
# ❌ ANTES (pedia admin):
Start-Process python-installer.exe -ArgumentList "/quiet InstallAllUsers=1"

# ✅ AGORA (sem admin):
Start-Process python-installer.exe -ArgumentList @(
    "/passive",              # Mostra progresso mas não pede interação
    "InstallAllUsers=0",     # 🔑 CRÍTICO: instalação de usuário
    "PrependPath=1",         # Adiciona ao PATH do usuário
    "Include_pip=1",
    "Include_launcher=1",
    "SimpleInstall=1",
    "TargetDir=`"$env:LocalAppData\Programs\Python\Python313`""
)
```

### 2. Sem `-Verb RunAs`

**REMOVIDO** o parâmetro `-Verb RunAs` que forçava elevação de privilégios:

```powershell
# ❌ ANTES:
Start-Process -FilePath $installer -Verb RunAs  # Pede UAC!

# ✅ AGORA:
Start-Process -FilePath $installer -Wait -PassThru -NoNewWindow
```

### 3. Diretório de Instalação do Usuário

Python é instalado em:
```
%LocalAppData%\Programs\Python\Python313\
```

Este diretório **não requer permissões de admin** para escrita.

### 4. Winget com `--scope user`

Se winget for usado como fallback:

```powershell
# ✅ Instalação de usuário via winget
winget install -e --id Python.Python.3.13 --scope user --silent
```

## 🎯 Benefícios

| Aspecto | Antes | Agora |
|---------|-------|-------|
| **Permissões** | ❌ Requer Admin (UAC) | ✅ Sem admin |
| **Instalação Corporativa** | ❌ Bloqueada | ✅ Funciona |
| **Múltiplos Usuários** | ⚠️ Global (conflitos) | ✅ Isolada por usuário |
| **Portabilidade** | ❌ Dificulta | ✅ Facilita |

## 🔍 Como Verificar

### Teste 1: Sem Admin
Execute em PowerShell **sem admin**:
```powershell
.\scripts\install.ps1
```

**Esperado:** Instalação completa sem pop-up de UAC.

### Teste 2: Verificar Localização
```powershell
python -c "import sys; print(sys.executable)"
```

**Esperado:**
```
C:\Users\<SeuUsuário>\AppData\Local\Programs\Python\Python313\python.exe
```

### Teste 3: Pip de Usuário
```powershell
python -m pip list --user
```

**Esperado:** Lista de pacotes instalados para o usuário.

## 🛠️ Resolução de Problemas

### Ainda Pede Admin?

**Causa:** Versão antiga do script ou política de execução.

**Solução:**
```powershell
# 1. Permitir execução de scripts locais
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 2. Forçar bypass no install
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

### Python Não Detectado Após Instalação?

**Causa:** PATH do usuário não atualizado.

**Solução 1 - Reabrir PowerShell:**
```powershell
# Feche e reabra o PowerShell
exit
# Abra novamente e teste
python --version
```

**Solução 2 - Atualizar PATH manualmente:**
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
python --version
```

**Solução 3 - Usar caminho completo:**
```powershell
$pyPath = "$env:LocalAppData\Programs\Python\Python313\python.exe"
& $pyPath --version
```

### Instalação Falha Silenciosamente?

**Debug:** Use `/passive` ao invés de `/quiet` para ver progresso:

```powershell
# Edite temporariamente o script para usar:
"/passive"  # Mostra barra de progresso
# ao invés de:
"/quiet"    # Totalmente silencioso
```

## 📋 Exit Codes do Instalador Python

| Código | Significado | Ação |
|--------|-------------|------|
| `0` | ✅ Sucesso | Continuar |
| `3010` | ✅ Sucesso (requer reinício) | OK, reiniciar depois |
| `1602` | ⚠️ Usuário cancelou | Reinstalar |
| `1638` | ⚠️ Já instalado | OK, usar existente |
| `5` | ❌ Acesso negado | **PROBLEMA: ainda pedindo admin!** |

## 🔐 Políticas Corporativas

Se sua empresa bloqueia instalações:

### Opção 1: Python Portável

1. Baixe Python "embeddable package" (zip):
   ```
   https://www.python.org/downloads/windows/
   ```

2. Extraia para:
   ```
   C:\Users\<SeuUsuário>\Python313\
   ```

3. Configure PATH manualmente:
   ```powershell
   $env:Path += ";C:\Users\$env:USERNAME\Python313"
   $env:Path += ";C:\Users\$env:USERNAME\Python313\Scripts"
   ```

### Opção 2: Solicitar Instalação Pré-configurada

Forneça ao TI estas instruções:

```
Produto: Python 3.13
Instalador: python-3.13.0-amd64.exe
Argumentos: /passive InstallAllUsers=0 PrependPath=1 Include_pip=1
Escopo: Usuário atual (sem admin)
Verificação: python --version
```

## 📊 Comparação de Métodos de Instalação

| Método | Admin? | PATH Auto | pip Incluído | Recomendado |
|--------|--------|-----------|--------------|-------------|
| **InstallAllUsers=0** | ❌ Não | ✅ Sim | ✅ Sim | ✅ **SIM** |
| **InstallAllUsers=1** | ⚠️ SIM | ✅ Sim | ✅ Sim | ❌ Não |
| **Embeddable ZIP** | ❌ Não | ❌ Manual | ⚠️ Opcional | ⚠️ Só se necessário |
| **Microsoft Store** | ❌ Não | ✅ Sim | ✅ Sim | ⚠️ Limitado |
| **winget (user)** | ❌ Não | ✅ Sim | ✅ Sim | ✅ **SIM** |

## 🎓 Entendendo os Argumentos

### `/passive` vs `/quiet`

- **`/passive`**: Mostra barra de progresso, sem interação
  - ✅ Bom para debug
  - ✅ Usuário vê o que está acontecendo
  
- **`/quiet`**: Totalmente silencioso
  - ✅ Automação completa
  - ❌ Dificulta debug

### `InstallAllUsers=0` - CRÍTICO!

- **`0` (False)**: Instala para usuário atual
  - ✅ Sem admin
  - ✅ Isolado
  - ✅ PATH do usuário
  
- **`1` (True)**: Instala para todos os usuários
  - ❌ **REQUER ADMIN**
  - ❌ PATH global
  - ❌ Conflitos entre usuários

### `PrependPath=1`

Adiciona Python ao PATH **antes** de outras entradas:
- ✅ `python` funciona no terminal
- ✅ `pip` funciona no terminal
- ⚠️ Substitui outras instalações Python

### `TargetDir`

Especifica diretório de instalação:
```
$env:LocalAppData\Programs\Python\Python313
```

Traduz para:
```
C:\Users\SeuUsuário\AppData\Local\Programs\Python\Python313\
```

## 🚀 Melhorias Futuras

- [ ] Detecção de políticas corporativas bloqueando instalação
- [ ] Fallback automático para Python embeddable
- [ ] Cache local de instaladores Python (evitar downloads repetidos)
- [ ] Verificação de integridade SHA256 do instalador baixado
- [ ] Suporte a proxy corporativo no download

## 📝 Changelog

### v2.0 (27/10/2025)
- ✅ Instalação 100% sem admin
- ✅ `/passive` ao invés de `/quiet` para debug
- ✅ `InstallAllUsers=0` garantido
- ✅ `TargetDir` explícito em `$env:LocalAppData`
- ✅ Removido `-Verb RunAs`
- ✅ winget com `--scope user`
- ✅ Mensagens detalhadas de progresso
- ✅ Verificação de exit codes do instalador
- ✅ Múltiplas versões Python suportadas (3.13, 3.12, 3.11)

### v1.0 (Anterior)
- ❌ Pedia admin (UAC)
- ⚠️ `/quiet` ocultava problemas
- ⚠️ `InstallAllUsers` não garantido
