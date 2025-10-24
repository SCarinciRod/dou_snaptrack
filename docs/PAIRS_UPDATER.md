# Sistema de Atualização do Artefato de Pares

## 📋 Visão Geral

O artefato `artefatos/pairs_DO1_full.json` contém o mapeamento de órgãos (N1) e subórgãos (N2) do Diário Oficial da União. Este arquivo é usado pela UI para preencher dropdowns e acelerar a criação de planos.

**Problema:** O DOU adiciona/remove órgãos e subórgãos frequentemente. Um artefato desatualizado pode causar:
- ❌ Órgãos novos não aparecerem na UI
- ❌ Subórgãos removidos gerarem erros
- ❌ Mapeamentos incorretos

**Solução:** Sistema de atualização automática com detecção de obsolescência.

---

## 📁 Formato do Arquivo

### Novo Formato (v2)
```json
{
  "_metadata": {
    "secao": "DO1",
    "data_scrape": "24-10-2025",
    "timestamp": "2025-10-24T14:30:00",
    "total_n1": 32,
    "total_pairs": 83,
    "auto_generated": true,
    "max_age_days": 7
  },
  "pairs": {
    "Presidência da República": [
      "Advocacia-Geral da União",
      "Casa Civil",
      "Secretaria-Geral"
    ],
    "Ministério da Educação": [
      "Gabinete do Ministro",
      "INEP"
    ]
  }
}
```

### Formato Antigo (v1) - OBSOLETO
```json
{
  "date": "12-09-2025",
  "secao": "DO1",
  "controls": {...},
  "n1_options": [...]
}
```

**Migração:** Use `scripts/migrate_pairs_format.py` para converter formato antigo → novo.

---

## 🔄 Atualização Automática

### Via UI (Recomendado)

1. Abra a UI: `streamlit run src/dou_snaptrack/ui/app.py`
2. Na barra lateral, expanda **"🔧 Manutenção do Artefato"**
3. Veja status atual:
   - ✅ **Existe** - Arquivo OK
   - ⚠️ **Obsoleto** - Arquivo > 7 dias
   - **Idade** - Dias desde última atualização
   - **Órgãos (N1)** - Total de órgãos mapeados
   - **Pares (N1→N2)** - Total de mapeamentos

4. Clique **"🔄 Atualizar Agora"** para forçar atualização
   - Scraping do DOU (2-5 minutos)
   - Progresso em tempo real
   - Cache limpo automaticamente

5. Clique **"ℹ️ Ver Info"** para detalhes JSON completos

### Via CLI

#### Atualização Manual
```bash
# Atualizar se obsoleto (> 7 dias)
python -m dou_snaptrack.utils.pairs_updater

# Forçar atualização mesmo se recente
python -m dou_snaptrack.utils.pairs_updater --force

# Ver apenas informações (sem atualizar)
python -m dou_snaptrack.utils.pairs_updater --info

# Atualizar com limite (mais rápido para testes)
python -m dou_snaptrack.utils.pairs_updater --limit1 10 --limit2 5

# Mostrar browser durante scraping
python -m dou_snaptrack.utils.pairs_updater --headful
```

#### Integração em Scripts Python
```python
from dou_snaptrack.utils.pairs_updater import (
    update_pairs_file_if_stale,
    get_pairs_file_info,
    is_pairs_file_stale
)

# Atualizar apenas se obsoleto
result = update_pairs_file_if_stale()
if result:
    print(f"Atualizado: {result['n1_count']} órgãos")
else:
    print("Arquivo ainda está válido")

# Verificar status
info = get_pairs_file_info()
print(f"Idade: {info['age_days']:.1f} dias")
print(f"Obsoleto: {info['is_stale']}")

# Verificação manual
if is_pairs_file_stale():
    print("Precisa atualizar!")
```

---

## ⚙️ Configuração

### Parâmetros de Obsolescência

Arquivo considerado obsoleto se:
- Não existe
- Idade > `MAX_AGE_DAYS` (padrão: 7 dias)

**Alterar limite:**
```python
from dou_snaptrack.utils.pairs_updater import update_pairs_file_if_stale

# Atualizar se > 3 dias
update_pairs_file_if_stale(max_age_days=3)
```

### Cache na UI

O arquivo é carregado com cache de **1 hora** (`ttl=3600`):
```python
@st.cache_data(show_spinner=False, ttl=3600)
def _load_pairs_file_cached(path_str: str) -> dict[str, list[str]]:
    ...
```

**Limpar cache manualmente:**
```python
st.cache_data.clear()  # Na UI
```

---

## 🛠️ Troubleshooting

### Problema: UI não mostra órgãos novos após atualização

**Causa:** Cache do Streamlit ainda tem dados antigos.

**Solução:**
1. Recarregue a página (F5)
2. Ou use botão "🔄 Atualizar Agora" (limpa cache automaticamente)

---

### Problema: Erro "Nenhum combo encontrado no scraping"

**Causa:** DOU pode estar fora do ar ou mudou estrutura HTML.

**Soluções:**
1. Tente novamente mais tarde
2. Verifique conexão com internet
3. Use `--headful` para ver o que está acontecendo:
   ```bash
   python -m dou_snaptrack.utils.pairs_updater --headful
   ```

---

### Problema: Arquivo muito antigo mas não atualiza

**Causa:** Parâmetro `max_age_days` muito alto.

**Solução:**
```bash
# Forçar atualização independente da idade
python -m dou_snaptrack.utils.pairs_updater --force
```

---

## 📊 Monitoramento

### Logs de Atualização

Quando executado via CLI:
```
🔄 Atualizando artefatos/pairs_DO1_full.json...
  [ 10%] Iniciando atualização para DO1 - 24-10-2025...
  [ 30%] Scraping site do DOU...
  [ 70%] Encontrados 32 órgãos...
  [100%] Atualização concluída!
✅ Sucesso!
   - 32 órgãos (N1)
   - 83 pares (N1→N2)
   - Salvo em: artefatos/pairs_DO1_full.json
   - Timestamp: 2025-10-24T14:30:45
```

### Metadata no Arquivo

Cada atualização registra:
```json
"_metadata": {
  "secao": "DO1",
  "data_scrape": "24-10-2025",      // Data do scraping
  "timestamp": "2025-10-24T14:30:00", // Quando foi gerado
  "total_n1": 32,                    // Órgãos encontrados
  "total_pairs": 83,                 // Mapeamentos totais
  "auto_generated": true,            // Gerado automaticamente
  "max_age_days": 7                  // Política de obsolescência
}
```

---

## 🚀 Melhores Práticas

### 1. Atualização Semanal Automática

**Opção A - Cron Job (Linux/Mac):**
```bash
# Editar crontab
crontab -e

# Adicionar linha (executa todo domingo às 2h)
0 2 * * 0 cd /path/to/Projetos && python -m dou_snaptrack.utils.pairs_updater
```

**Opção B - Task Scheduler (Windows):**
```powershell
# Criar tarefa agendada
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m dou_snaptrack.utils.pairs_updater" -WorkingDirectory "C:\Projetos"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "DOU_UpdatePairs"
```

### 2. Validação Pós-Atualização

```python
from dou_snaptrack.utils.pairs_updater import update_pairs_file, get_pairs_file_info

# Atualizar
result = update_pairs_file()

# Validar
if result["success"]:
    info = get_pairs_file_info()
    
    # Verificar sanidade
    assert info["n1_count"] > 0, "Nenhum órgão encontrado!"
    assert info["pairs_count"] > 0, "Nenhum par encontrado!"
    assert info["age_days"] < 1, "Arquivo não foi atualizado!"
    
    print(f"✅ Validação OK: {info['n1_count']} órgãos")
else:
    print(f"❌ Erro: {result['error']}")
```

### 3. Backup Antes de Atualizar

```python
from pathlib import Path
from datetime import datetime

# Criar backup com timestamp
pairs_file = Path("artefatos/pairs_DO1_full.json")
backup_file = pairs_file.with_name(
    f"pairs_DO1_full.backup.{datetime.now():%Y%m%d_%H%M%S}.json"
)
backup_file.write_text(pairs_file.read_text(encoding="utf-8"), encoding="utf-8")

# Atualizar
from dou_snaptrack.utils.pairs_updater import update_pairs_file
update_pairs_file()
```

---

## 📝 Changelog

### v2.0 (24/10/2025)
- ✨ Novo formato com metadata completa
- ✨ Sistema de atualização automática via UI e CLI
- ✨ Detecção de obsolescência (7 dias)
- ✨ Cache com TTL de 1 hora
- ✨ Script de migração de formato antigo
- 🔧 Browser launch com timeout (10s)
- 🔧 LRU cache aumentado (1 → 4 entradas)

### v1.0 (12/09/2025)
- 📋 Formato inicial baseado em scraping manual
- 📋 Estrutura com n1_options e n2_options

---

## 🤝 Contribuindo

Para adicionar novas features ao sistema de atualização:

1. **Novos parâmetros de scraping:** Edite `utils/pairs_updater.py::update_pairs_file()`
2. **Novos checks de sanidade:** Adicione em `utils/pairs_updater.py::get_pairs_file_info()`
3. **Nova UI na sidebar:** Edite `ui/app.py` seção "Manutenção do Artefato"

---

## 📞 Suporte

**Problemas ou dúvidas?**
- Verifique logs em `resultados/*/batch_run.log`
- Use `--headful` para debug visual
- Execute `python -m dou_snaptrack.utils.pairs_updater --info` para diagnosticar
