# Plano de Testes - Batch Runner e Editor de Planos DOU

## Objetivo
Validar o funcionamento do batch runner para execucao de planos e o editor de planos do DOU.

---

## Pre-requisitos

1. Ambiente Python configurado com `.venv` ativo
2. Streamlit UI funcionando
3. Conexao com internet estavel
4. Arquivo de plano de teste: `planos/teste_batch_dou.json`

---

## Teste 1: Iniciar a UI

```powershell
cd C:\Projetos
.venv\Scripts\python.exe -m streamlit run src/dou_snaptrack/ui/app.py --server.port 8501
```

**Resultado esperado:** UI abre no navegador em http://localhost:8501

---

## Teste 2: Navegar para Editor de Planos DOU

1. Na barra lateral, selecionar "DOU" como fonte
2. Clicar em "Editor de Planos" ou aba equivalente
3. Verificar se a interface carrega corretamente

**Resultado esperado:** Editor de planos exibe campos para criar/editar jobs

---

## Teste 3: Carregar Plano Existente

1. No editor, clicar em "Carregar Plano"
2. Selecionar arquivo `planos/teste_batch_dou.json`
3. Verificar se os 3 jobs aparecem na lista

**Resultado esperado:**
- Job 001: DO1, Presidencia da Republica
- Job 002: DO1, Ministerio da Fazenda  
- Job 003: DO2, Todos

---

## Teste 4: Editar Job no Plano

1. Selecionar Job 001
2. Alterar N2 de "Todos" para orgao especifico (se disponivel)
3. Salvar alteracao
4. Verificar se mudanca persiste

**Resultado esperado:** Job atualizado corretamente

---

## Teste 5: Adicionar Novo Job

1. Clicar em "Adicionar Job"
2. Preencher:
   - Secao: DO3
   - Data: 03-12-2025
   - N1: Todos
   - N2: Todos
3. Salvar

**Resultado esperado:** Novo job aparece na lista (total 4 jobs)

---

## Teste 6: Remover Job

1. Selecionar Job 003 (DO2)
2. Clicar em "Remover"
3. Confirmar remocao

**Resultado esperado:** Job removido, lista com 3 jobs restantes

---

## Teste 7: Salvar Plano

1. Clicar em "Salvar Plano"
2. Escolher nome: `planos/teste_batch_editado.json`
3. Confirmar

**Resultado esperado:** Arquivo salvo com sucesso

---

## Teste 8: Executar Batch Runner

1. Navegar para "Execucao em Lote" ou "Batch Runner"
2. Carregar plano `planos/teste_batch_dou.json`
3. Clicar em "Executar"
4. Observar progresso

**Resultado esperado:**
- Barra de progresso mostra avanço
- Cada job executa sequencialmente
- Resultados salvos em `resultados/03-12-2025/`

---

## Teste 9: Verificar Resultados

1. Navegar para pasta `resultados/03-12-2025/`
2. Verificar arquivos gerados
3. Abrir um resultado e validar conteudo

**Resultado esperado:**
- Arquivos JSON ou MD com conteudo extraido
- Dados correspondem aos jobs do plano

---

## Teste 10: Verificar Relatorio de Batch

1. Abrir `resultados/batch_report.json`
2. Verificar metricas:
   - Total de jobs
   - Jobs com sucesso
   - Jobs com falha
   - Tempo de execucao

**Resultado esperado:** Relatorio com estatisticas precisas

---

## Teste 11: Diagnostico de Performance

```powershell
cd C:\Projetos
.venv\Scripts\python.exe -m dou_snaptrack.tools.fetch_diagnostics --target dou --iterations 3
```

**Resultado esperado:**
- 3 iteracoes com sucesso
- Tempo medio < 15s
- wait_content < 0.5s

---

## Checklist Final

| Teste | Status | Observacoes |
|-------|--------|-------------|
| 1. Iniciar UI | [ ] | |
| 2. Navegar Editor | [ ] | |
| 3. Carregar Plano | [ ] | |
| 4. Editar Job | [ ] | |
| 5. Adicionar Job | [ ] | |
| 6. Remover Job | [ ] | |
| 7. Salvar Plano | [ ] | |
| 8. Executar Batch | [ ] | |
| 9. Verificar Resultados | [ ] | |
| 10. Verificar Relatorio | [ ] | |
| 11. Diagnostico Performance | [ ] | |

---

## Comandos Uteis

```powershell
# Verificar testes unitarios
.venv\Scripts\python.exe -m pytest tests/ -q --tb=no

# Diagnostico rapido DOU
.venv\Scripts\python.exe -m dou_snaptrack.tools.fetch_diagnostics --target dou

# Ver estrutura de planos
Get-ChildItem planos/*.json | Select-Object Name, Length, LastWriteTime

# Ver resultados
Get-ChildItem resultados/ -Recurse | Select-Object FullName, Length
```

---

## Problemas Conhecidos

1. **Timeout em conexoes lentas**: Aumentar timeout se necessario
2. **Dropdowns nao carregam**: Verificar se site DOU esta online
3. **Erros de permissao**: Executar como administrador se necessario

---

## Contato

Para reportar problemas, incluir:
- Log de erro completo
- Versao Python (`python --version`)
- Sistema operacional
- Captura de tela se aplicavel
