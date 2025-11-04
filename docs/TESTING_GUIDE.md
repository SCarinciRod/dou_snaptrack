# 🧪 Guia de Teste - DOU SnapTrack

## 📋 Pré-requisitos para Testers

- ✅ Windows 10/11
- ✅ Conexão com internet
- ✅ **NÃO precisa** de privilégios de administrador
- ✅ **NÃO precisa** ter Python pré-instalado

---

## 🚀 Instalação Rápida (Método Recomendado)

### Opção 1: Instalação Automática Completa

```powershell
# 1. Abra PowerShell (não precisa ser Admin)
# Tecla Windows + R → digite "powershell" → Enter

# 2. Execute o bootstrap (copia repositório + instala tudo)
irm https://raw.githubusercontent.com/SCarinciRod/dou_snaptrack/main/scripts/bootstrap.ps1 | iex
```

**O que acontece**:
- ✅ Baixa código do GitHub (~50MB)
- ✅ Instala Python 3.12 automaticamente (sem pedir admin!)
- ✅ Configura Playwright (navegador automatizado)
- ✅ Cria atalho na Área de Trabalho
- ⏱️ **Tempo estimado**: 5-15 minutos

---

### Opção 2: Instalação Manual (Mais Controle)

Se preferir ter controle sobre o processo:

```powershell
# 1. Baixar repositório
git clone https://github.com/SCarinciRod/dou_snaptrack.git
cd dou_snaptrack

# 2. Executar instalação
.\scripts\install.ps1

# Opções úteis:
# -SkipSmoke     : Pula teste de navegador (mais rápido)
# -AllowWinget   : Usa winget se Python não encontrado
```

---

## ✅ Validação Pós-Instalação

### Teste 1: Verificar Instalação

```powershell
# Executar script de validação
.\scripts\test_install.ps1

# Teste completo (inclui download real)
.\scripts\test_install.ps1 -FullTest
```

**Resultado esperado**:
```
================================================================================
RESUMO DOS TESTES
================================================================================

Testes Passados: 11
Testes Falhados: 0

✅ TODOS OS TESTES PASSARAM!
```

---

### Teste 2: Abrir UI

```powershell
# Método 1: Duplo clique no atalho da Área de Trabalho
"DOU SnapTrack"

# Método 2: Via PowerShell
.\launch_ui.vbs

# Método 3: Script gerenciado
.\scripts\run-ui-managed.ps1
```

**Resultado esperado**:
- ✅ Navegador abre com UI Streamlit
- ✅ URL: http://localhost:8501
- ✅ Interface carrega sem erros

---

## 🧪 Casos de Teste Essenciais

### TC01: Instalação em Máquina Limpa

**Pré-condição**: Windows sem Python instalado

**Passos**:
1. Executar `bootstrap.ps1`
2. Aguardar instalação completa (5-15min)
3. Verificar atalho criado na Área de Trabalho

**Resultado Esperado**:
- ✅ Python 3.12 instalado automaticamente
- ✅ Chromium instalado
- ✅ Smoke test passa
- ✅ Atalho funciona

---

### TC02: Geração de Plano DO1

**Pré-condição**: UI aberta

**Passos**:
1. Selecionar data (ex: hoje)
2. Escolher seção: DO1
3. Escolher Modo: "Plan Live"
4. Selecionar 2-3 órgãos
5. Clicar "Gerar Plano"

**Resultado Esperado**:
- ✅ Plano gerado em < 30 segundos
- ✅ Arquivo salvo em `planos/`
- ✅ Mensagem de sucesso exibida

---

### TC03: Execução de Batch

**Pré-condição**: Plano gerado (TC02)

**Passos**:
1. Ir para aba "Execução de Plano"
2. Selecionar plano gerado
3. Marcar "Gerar Boletim"
4. Clicar "Executar Batch"
5. Aguardar conclusão (~5-15min dependendo do plano)

**Resultado Esperado**:
- ✅ Progresso exibido em tempo real
- ✅ Boletim gerado em `resultados/<data>/`
- ✅ Formato: DOCX (padrão)
- ✅ Relatório JSON criado

---

### TC04: Geração de Plano E-Agendas

**Pré-condição**: UI aberta

**Passos**:
1. Ir para aba "E-Agendas"
2. Selecionar 2-3 órgãos
3. Clicar "Gerar Plano"

**Resultado Esperado**:
- ✅ Plan carrega em < 5 segundos (usa artefato pré-gerado)
- ✅ Combos gerados corretamente
- ✅ Arquivo salvo

---

### TC05: Atualização Mensal E-Agendas (Opcional)

**Pré-condição**: Sistema instalado

**Passos**:
1. Executar manualmente: `python scripts/update_eagendas_artifact.py`
2. Aguardar conclusão (5-15min com mapper otimizado)
3. Verificar artefato em `artefatos/pairs_eagendas_latest.json`

**Resultado Esperado**:
- ✅ Completa em < 20 minutos
- ✅ Artefato atualizado
- ✅ Backup criado
- ✅ Logs em `logs/artifact_updates/`

---

## 🐛 Problemas Comuns e Soluções

### P1: "Python não encontrado"

**Sintoma**: Erro ao executar install.ps1

**Solução**:
```powershell
# Permitir instalação via winget
.\scripts\install.ps1 -AllowWinget

# OU instalar manualmente
# Baixar: https://www.python.org/downloads/
# Versões suportadas: 3.12, 3.11 ou 3.10
# IMPORTANTE: Marcar "Add to PATH" durante instalação
```

---

### P2: "Playwright timeout"

**Sintoma**: Instalação trava em "Instalando navegadores"

**Solução**:
```powershell
# Pular instalação de navegador
.\scripts\install.ps1 -SkipSmoke

# Instalar Chromium manualmente depois
python -m playwright install chromium

# OU usar navegador do sistema (Chrome/Edge)
# Configurar em constants.py: BROWSER_CHANNEL = "chrome"
```

---

### P3: "Smoke test falhou"

**Sintoma**: Teste de navegador não passa

**Diagnóstico**:
```powershell
# Executar smoke test manualmente para ver erro detalhado
python scripts\playwright_smoke.py

# Verificar se Chromium está instalado
python -m playwright install --help
```

**Soluções**:
1. Instalar Chromium: `python -m playwright install chromium`
2. Usar Chrome do sistema: Editar `constants.py`
3. Pular smoke test: `-SkipSmoke` (não recomendado)

---

### P4: "UI não abre"

**Sintoma**: Atalho/script não abre interface

**Diagnóstico**:
```powershell
# Verificar se Streamlit está instalado
python -c "import streamlit; print(streamlit.__version__)"

# Tentar abrir manualmente
python -m streamlit run src/dou_snaptrack/ui/app.py
```

**Solução**:
```powershell
# Reinstalar dependências
pip install -e .
pip install streamlit playwright
```

---

### P5: "Erro de módulo não encontrado"

**Sintoma**: `ModuleNotFoundError: No module named 'dou_snaptrack'`

**Solução**:
```powershell
# Reinstalar em modo editável
cd C:\Users\<SEU_USUARIO>\dou_snaptrack
pip install -e .

# Verificar instalação
pip show dou-snaptrack
```

---

## 📊 Critérios de Aceitação

### Instalação (Crítico)
- [ ] Instala em máquina limpa sem Python
- [ ] Não pede privilégios de administrador
- [ ] Completa em < 20 minutos
- [ ] Cria atalho na Área de Trabalho

### Funcionalidade Core (Crítico)
- [ ] Gera plano DO1 em < 1 minuto
- [ ] Executa batch sem erros
- [ ] Gera boletim DOCX corretamente
- [ ] E-Agendas carrega em < 5 segundos

### Performance (Importante)
- [ ] Plan Live DO1: < 2 minutos (227 órgãos)
- [ ] Batch 10 combos: < 15 minutos
- [ ] E-Agendas atualização: < 20 minutos
- [ ] UI responsiva (sem travamentos)

### UX (Desejável)
- [ ] Mensagens de erro claras
- [ ] Progresso visível em operações longas
- [ ] Documentação acessível
- [ ] Logs úteis para debug

---

## 📝 Checklist de Reporte de Bugs

Ao encontrar um problema, incluir:

- [ ] **OS**: Windows 10/11 (qual?)
- [ ] **Python**: Versão (se instalado antes)
- [ ] **Comando**: Exato comando executado
- [ ] **Erro**: Mensagem de erro completa
- [ ] **Logs**: Conteúdo de `logs/` relevante
- [ ] **Screenshots**: Se UI, incluir prints
- [ ] **Reprodução**: Passos para reproduzir

**Template de Issue**:
```markdown
## Descrição
[O que aconteceu]

## Passos para Reproduzir
1. [Passo 1]
2. [Passo 2]
3. [Erro ocorreu]

## Comportamento Esperado
[O que deveria acontecer]

## Comportamento Atual
[O que realmente aconteceu]

## Ambiente
- OS: Windows 11 Pro 23H2
- Python: 3.12.7 (instalado automaticamente)
- Comando: `.\scripts\bootstrap.ps1`

## Logs
```
[Cole logs relevantes aqui]
```

## Screenshots
[Anexe prints se aplicável]
```

---

## 🎯 Foco de Teste por Perfil

### Tester Básico (30min)
1. ✅ TC01: Instalação limpa
2. ✅ TC02: Gerar plano DO1
3. ✅ Reportar se algo falhou

### Tester Intermediário (1-2h)
1. ✅ TC01-TC04: Todos casos essenciais
2. ✅ Testar em 2 máquinas diferentes
3. ✅ Reportar problemas de UX

### Tester Avançado (3-4h)
1. ✅ TC01-TC05: Cobertura completa
2. ✅ Testar edge cases (rede lenta, Python pré-instalado, etc)
3. ✅ Validar performance (timings)
4. ✅ Revisar código para melhorias

---

## 📞 Suporte

**Problemas durante teste?**

1. Verificar [INSTALL_TROUBLESHOOTING.md](./INSTALL_TROUBLESHOOTING.md)
2. Executar `.\scripts\test_install.ps1` para diagnóstico
3. Abrir issue com template acima
4. Anexar logs de `logs/` se possível

---

**Versão do Guia**: 1.0  
**Última Atualização**: 2025-11-04  
**Scripts Corrigidos**: ✅ install.ps1 + bootstrap.ps1  
**Status**: Pronto para testes! 🚀
