# Sistema de Atualização Automática - E-Agendas

## 📋 Visão Geral

Sistema de mapeamento incremental com atualização mensal automática do artefato de pares **Órgão → Cargo → Agente Público** do e-agendas.

### ✅ Vantagens

- ⚡ **Performance**: Usuário não espera 3-4 horas
- 🔄 **Automático**: Atualiza mensalmente sem intervenção
- 📊 **Histórico**: Mantém versões arquivadas
- 🎯 **Confiável**: Usa artefato pré-gerado validado

---

## 🗂️ Estrutura de Arquivos

### Scripts

```
scripts/
├── update_eagendas_artifact.py    # Atualização mensal (automática)
└── setup_monthly_update.ps1       # Configurar Task Scheduler
```

### Artefatos

```
artefatos/
├── pairs_eagendas_latest.json                  # Versão atual (sempre atualizada)
├── pairs_eagendas_YYYYMMDD_HHMMSS.json        # Versão timestamped
└── archive/
    ├── pairs_eagendas_YYYYMM.json             # Versão mensal
    └── pairs_eagendas_backup_YYYYMMDD_HHMMSS.json  # Backups automáticos
```

### Logs

```
logs/
└── artifact_updates/
    └── update_YYYYMMDD_HHMMSS.log  # Logs de cada atualização
```

### Utilitários

```
src/dou_snaptrack/utils/
└── artifact_checker.py  # Verificador de idade do artefato
```

---

## 🚀 Setup Inicial

### 1. Gerar Artefato Inicial

```powershell
# Primeira geração (manual)
python scripts/update_eagendas_artifact.py
```

**⏱️ Duração**: 3-4 horas (227 órgãos)

### 2. Configurar Atualização Mensal

```powershell
# Executar como Administrador
.\scripts\setup_monthly_update.ps1
```

**Configurações**:
- **Frequência**: Dia 1 de cada mês
- **Horário**: 02:00 (madrugada)
- **Usuário**: Atual
- **Timeout**: 6 horas máx

### 3. Verificar Status

```powershell
# Via PowerShell
Get-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate"

# Via Python
python src/dou_snaptrack/utils/artifact_checker.py
```

---

## 📊 Uso na Aplicação

### Verificar Idade do Artefato

```python
from dou_snaptrack.utils.artifact_checker import check_artifact_age

status = check_artifact_age()

if not status["exists"]:
    print("⚠️ Artefato não encontrado! Execute update_eagendas_artifact.py")
elif status["is_critical"]:
    print(f"🔴 CRÍTICO: {status['age_days']} dias sem atualizar!")
elif status["is_stale"]:
    print(f"⚠️ Desatualizado: {status['age_days']} dias")
else:
    print(f"✅ Atualizado: {status['age_days']} dias")
```

### Carregar Pares

```python
from dou_snaptrack.cli.plan_live_eagendas import load_eagendas_pairs

# Carregar artefato
pairs = load_eagendas_pairs()  # Usa 'latest' por padrão

# Acessar dados
hierarchy = pairs["hierarchy"]
stats = pairs["stats"]

print(f"Órgãos: {stats['total_orgaos']}")
print(f"Cargos: {stats['total_cargos']}")
print(f"Agentes: {stats['total_agentes']}")
```

### Gerar Plan

```python
from dou_snaptrack.cli.plan_live_eagendas import build_plan_eagendas

# Plan completo (rápido - sem scraping!)
plan = build_plan_eagendas(verbose=True)

# Plan filtrado
plan_filtered = build_plan_eagendas(
    limit_orgaos=10,
    verbose=True
)

# Plan específico
plan_specific = build_plan_eagendas(
    select_orgaos=["AGÊNCIA ESPACIAL BRASILEIRA"],
    verbose=True
)
```

---

## 🔄 Atualização Manual

Se precisar atualizar fora do agendamento:

```powershell
# Método 1: Executar script diretamente
python scripts/update_eagendas_artifact.py

# Método 2: Trigger via Task Scheduler
Start-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate"
```

---

## 📅 Ciclo de Vida do Artefato

### Estados

| Idade      | Status        | Ação                              |
|------------|---------------|-----------------------------------|
| 0-30 dias  | ✅ Atualizado  | Usar normalmente                  |
| 31-60 dias | ⚠️ Desatualizado | Recomenda-se atualizar          |
| 60+ dias   | 🔴 Crítico     | **Atualização urgente!**          |

### Metadata

Cada artefato contém:

```json
{
  "url": "https://eagendas.cgu.gov.br",
  "timestamp": "2025-11-03 10:31:28",
  "hierarchy": [...],
  "stats": {
    "total_orgaos": 227,
    "total_cargos": 1500,
    "total_agentes": 5000,
    "orgaos_sem_cargos": 50,
    "cargos_sem_agentes": 100
  },
  "update_info": {
    "update_date": "2025-11-03T10:31:28",
    "update_type": "monthly_automatic",
    "duration_seconds": 12345,
    "log_file": "C:/Projetos/logs/artifact_updates/update_20251103_103128.log"
  }
}
```

---

## 🛠️ Manutenção

### Ver Logs de Atualização

```powershell
# Último log
Get-Content logs/artifact_updates/*.log -Tail 50

# Todos os logs
Get-ChildItem logs/artifact_updates/ | Sort-Object LastWriteTime -Descending
```

### Limpar Arquivos Antigos

```powershell
# Remover backups com mais de 6 meses
Get-ChildItem artefatos/archive/pairs_eagendas_backup_*.json | 
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddMonths(-6)} | 
    Remove-Item

# Remover logs com mais de 3 meses
Get-ChildItem logs/artifact_updates/*.log | 
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddMonths(-3)} | 
    Remove-Item
```

### Desabilitar Atualização Automática

```powershell
# Desabilitar (temporário)
Disable-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate"

# Reabilitar
Enable-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate"

# Remover completamente
Unregister-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate" -Confirm:$false
```

---

## ⚡ Performance

### Comparação

| Abordagem          | Tempo         | Quando Usar                    |
|--------------------|---------------|--------------------------------|
| **Artefato** (atual) | < 1s          | Sempre (produção)              |
| Scraping em tempo real | 3-4 horas     | Nunca (só para gerar artefato) |
| Scraping seletivo  | 5-10 min      | Testes/desenvolvimento         |

### Estimativas

- **Artefato latest**: Carregamento instantâneo (< 1s)
- **Gerar plan**: 2-5s (227 órgãos completos)
- **Atualização mensal**: 3-4 horas (automática, madrugada)

---

## 🔍 Troubleshooting

### Artefato não encontrado

```powershell
# Verificar se existe
Test-Path C:\Projetos\artefatos\pairs_eagendas_latest.json

# Se não, gerar
python scripts/update_eagendas_artifact.py
```

### Task não executa

```powershell
# Verificar status
Get-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate" | Format-List *

# Ver histórico de execuções
Get-ScheduledTask -TaskName "DouSnapTrack_EAgendasUpdate" | Get-ScheduledTaskInfo

# Ver eventos
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" | 
    Where-Object {$_.Message -like "*DouSnapTrack*"} | 
    Select-Object -First 10
```

### Atualização falhou

```powershell
# Ver último log
$lastLog = Get-ChildItem logs/artifact_updates/*.log | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 1
    
Get-Content $lastLog.FullName
```

---

## 📚 Referências

- [EAGENDAS_INFRASTRUCTURE.md](../docs/EAGENDAS_INFRASTRUCTURE.md) - Arquitetura completa
- [Windows Task Scheduler](https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page)

---

**Última Atualização**: 2025-11-03  
**Status**: ✅ Sistema implementado e testado
