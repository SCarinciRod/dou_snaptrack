# 🚀 Guia de Instalação - DOU SnapTrack

## Instalação Rápida (Recomendado)

### Windows - Instalação Automática

1. **Abra o PowerShell** (não precisa ser Admin!)
   - Pressione `Win + X` → Escolha "Windows PowerShell"

2. **Navegue até a pasta do projeto:**
   ```powershell
   cd C:\caminho\para\dou_snaptrack
   ```

3. **Execute o instalador:**
   ```powershell
   .\scripts\install.ps1
   ```

**Pronto!** O instalador vai:
- ✅ Detectar ou instalar Python 3.13/3.12/3.11 automaticamente
- ✅ Instalar todas as dependências (sem necessidade de admin)
- ✅ Configurar o Playwright e navegadores
- ✅ Criar atalho na área de trabalho

---

## Como Usar Após Instalação

### Opção 1: Atalho na Área de Trabalho
Duplo clique no atalho **"DOU SnapTrack"** criado na área de trabalho.

### Opção 2: Via Script
```powershell
.\scripts\run-ui-managed.ps1
```

### Opção 3: Via VBS (Silencioso)
Duplo clique em `launch_ui.vbs` na raiz do projeto.

---

## Requisitos

- **Sistema Operacional:** Windows 10/11
- **Espaço em Disco:** ~500 MB (Python + dependências + navegador)
- **Internet:** Necessário apenas durante instalação
- **Permissões:** **NÃO** precisa de admin! Instalação modo usuário.

---

## Resolução de Problemas

### "Erro ao executar scripts do PowerShell"

Se você receber erro de política de execução:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Depois execute novamente:
```powershell
.\scripts\install.ps1
```

### "Python não encontrado"

O instalador tenta baixar Python automaticamente. Se falhar:

1. Baixe Python manualmente de [python.org](https://www.python.org/downloads/)
2. **IMPORTANTE:** Durante instalação, marque:
   - ☑️ "Add Python to PATH"
   - ☑️ "Install for current user only" (NÃO precisa de admin)
3. Execute `.\scripts\install.ps1` novamente

### "Navegador não funciona"

Se o smoke test falhar, instale navegadores manualmente:

```powershell
python -m playwright install chromium
```

---

## Instalação Avançada

### Forçar Limpeza e Reinstalação
```powershell
.\scripts\install.ps1 -ForceCleanVenv
```

### Pular Testes de Navegador
```powershell
.\scripts\install.ps1 -SkipSmoke
```

### Usar Winget (Se disponível)
```powershell
.\scripts\install.ps1 -AllowWinget
```

---

## Desinstalação

Para remover completamente:

```powershell
# Remover pacote Python
python -m pip uninstall dou-snaptrack -y

# Remover navegadores Playwright (opcional)
python -m playwright uninstall

# Deletar pasta do projeto
Remove-Item -Recurse -Force C:\caminho\para\dou_snaptrack
```

---

## Suporte

Se encontrar problemas:

1. Verifique os logs em `logs\ui_manager.log`
2. Execute com verbose: `.\scripts\install.ps1 -Verbose`
3. Abra uma issue no GitHub com:
   - Mensagem de erro completa
   - Versão do Windows
   - Saída do comando: `python --version`

---

## Changelog de Instalação

### v2.0 (27/10/2025)
- ✅ Instalação 100% sem admin
- ✅ Auto-detecção de Python 3.13/3.12/3.11
- ✅ Instalação automática de navegadores Playwright
- ✅ Mensagens amigáveis e progress indicators
- ✅ Criação automática de atalho na área de trabalho
- ✅ Suporte a múltiplos fallbacks (ensurepip → get-pip.py → virtualenv)

### v1.0 (Anterior)
- Instalação básica com venv
