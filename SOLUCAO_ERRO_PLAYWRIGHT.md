# Solução para Erro: "Executable doesn't exist at C:\Users\...\ms-playwright\..."

## O Problema

Você está vendo este erro:
```
Error: BrowserType.launch: Executable doesn't exist at C:\Users\LEBERLEI\AppData\Local\ms-playwright\chromium_headless_shell-1187\chrome-win\headless_shell.exe
```

**Causa**: O Playwright está procurando os navegadores na pasta errada. Na instalação, os navegadores foram baixados para `.venv\pw-browsers`, mas quando você executa a aplicação, o Playwright está procurando em `C:\Users\LEBERLEI\AppData\Local\ms-playwright`.

## Solução Rápida (Automática)

Execute este comando no PowerShell **na pasta do projeto**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\fix-playwright-browsers.ps1"
```

Este script vai:
1. Configurar a variável de ambiente correta
2. Baixar os navegadores para `.venv\pw-browsers`
3. Verificar se tudo funcionou

Depois, tente iniciar a aplicação novamente pelo atalho ou executando `launch_ui.vbs`.

## Solução Manual (se a automática não funcionar)

### Passo 1: Abrir PowerShell no diretório do projeto

```powershell
cd C:\Projetos
```

### Passo 2: Configurar a variável de ambiente

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "C:\Projetos\.venv\pw-browsers"
```

### Passo 3: Instalar os navegadores

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Isso vai baixar aproximadamente 250 MB de arquivos. Aguarde a conclusão.

### Passo 4: Verificar se funcionou

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\verify-playwright-setup.ps1"
```

Se tudo estiver OK, você verá mensagens verdes confirmando que:
- Python foi encontrado ✓
- Playwright está instalado ✓
- Navegadores estão presentes ✓

## Solução Permanente

**Para garantir que isso não aconteça novamente**, execute o instalador completo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install.ps1"
```

O instalador atualizado agora:
- ✅ Baixa navegadores para `.venv\pw-browsers`
- ✅ Configura `PLAYWRIGHT_BROWSERS_PATH` automaticamente
- ✅ Detecta sucesso do download corretamente (não apenas pelo exit code)

## Verificação

Após aplicar a solução, teste executando:

```powershell
# Via script gerenciado (recomendado)
scripts\run-ui-managed.ps1

# OU via atalho na área de trabalho
# Duplo clique em "Dou SnapTrack"

# OU via VBS
launch_ui.vbs
```

A UI deve abrir normalmente no navegador.

## Ainda com Problemas?

### Erro: "Access is denied" ou "WinError 5"

Se você vir erros sobre acesso negado, pode ser um problema de segurança do Windows bloqueando o driver do Playwright. Execute:

```powershell
# Desbloquear driver
$driverPath = ".venv\Lib\site-packages\playwright\driver"
Get-ChildItem -Path $driverPath -Recurse | Unblock-File
```

### Erro: "No module named 'greenlet._greenlet'"

Se a UI abrir mas falhar ao tentar usar o Playwright, execute:

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall --only-binary=:all: greenlet==3.2.4
```

### Espaço em Disco

O Playwright precisa de aproximadamente **250 MB** livres para os navegadores. Verifique se há espaço disponível.

### Firewall/Proxy

Se você está em uma rede corporativa com proxy ou firewall, o download pode falhar. Nesse caso:

1. Contate o administrador de TI para liberar acesso a `cdn.playwright.dev`
2. OU use Chrome/Edge já instalado no sistema (a aplicação tem fallback automático)

## Arquivos de Diagnóstico

Se nada funcionar, envie os seguintes arquivos para análise:

- `logs\ui_manager.log` - Log do gerenciador da UI
- `logs\ui_streamlit_*.log` - Logs mais recentes do Streamlit
- Saída do comando: `powershell -File scripts\verify-playwright-setup.ps1 > diagnostico.txt 2>&1`

---

**Última atualização**: 2025-11-06  
**Versão do instalador**: Com detecção de sucesso aprimorada e PLAYWRIGHT_BROWSERS_PATH automático
