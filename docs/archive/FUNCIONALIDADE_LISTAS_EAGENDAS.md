# Gerenciamento de Listas de Agentes - E-Agendas

## Nova Funcionalidade ✨

Implementado em: 2025-11-13

## Problema Resolvido

Antes, ao fazer consultas no E-Agendas, o usuário precisava:
1. Selecionar manualmente cada órgão → cargo → agente
2. Adicionar um por um à lista de consultas
3. Repetir todo o processo na próxima sessão (lista não era salva)

Isso tornava o acompanhamento constante de agentes específicos muito trabalhoso.

## Solução Implementada

### 💾 Salvar Listas de Agentes

**Localização na UI**: Seção "3️⃣ Consultas Salvas" → "💾 Gerenciar Listas de Agentes"

**Como usar**:
1. Monte sua lista de agentes (adicione consultas usando o botão "+ Adicionar Consulta Atual")
2. Digite um nome descritivo no campo "Nome da lista" (ex: "Ministros_CADE", "TCU_Auditores")
3. Clique em "💾 Salvar Lista"
4. A lista será salva em `planos/eagendas_listas/[nome].json`

**Estrutura do arquivo salvo**:
```json
{
  "nome": "Nome descritivo da lista",
  "criado_em": "2025-11-13",
  "total_agentes": 5,
  "queries": [
    {
      "n1_label": "Nome do Órgão",
      "n1_value": "514",
      "n2_label": "Nome do Cargo",
      "n2_value": "1001",
      "n3_label": "Nome do Agente Público",
      "n3_value": "5001",
      "person_label": "Nome do Agente (Cargo)"
    }
  ]
}
```

### 📂 Carregar Listas Salvas

**Como usar**:
1. No dropdown "Selecione uma lista", escolha uma lista salva
2. Visualize informações: nome, número de agentes, data de criação
3. Clique em "📂 Carregar" para restaurar a lista de consultas
4. Agora você pode:
   - Alterar o período de pesquisa (datas)
   - Executar a pesquisa com a lista carregada
   - Adicionar/remover agentes antes de executar

### 🗑️ Excluir Listas

**Como usar**:
1. Selecione a lista no dropdown
2. Clique em "🗑️ Excluir"
3. A lista será permanentemente removida do disco

## Casos de Uso

### Caso 1: Acompanhamento Mensal de Autoridades
```
1. Primeira vez:
   - Selecionar 10 ministros do CADE
   - Salvar como "Ministros_CADE"

2. Todo mês:
   - Carregar lista "Ministros_CADE"
   - Ajustar datas (ex: 01/11/2025 a 30/11/2025)
   - Executar pesquisa
   - Gerar relatório DOCX
```

### Caso 2: Múltiplas Listas Temáticas
```
- Lista "TCU_Auditores": 15 auditores do TCU
- Lista "AGU_Procuradores": 8 procuradores da AGU
- Lista "Educacao_Gestores": 12 gestores do MEC

Facilmente alternar entre listas dependendo do foco da pesquisa.
```

### Caso 3: Listas Colaborativas
```
Equipe pode compartilhar arquivos JSON via:
- Git (versionamento)
- E-mail
- Drive/OneDrive

Basta copiar o arquivo para planos/eagendas_listas/ e estará disponível.
```

## Estrutura de Arquivos

```
c:\Projetos\
├── planos/
│   ├── eagendas_listas/           ← NOVA PASTA
│   │   ├── Ministros_CADE.json
│   │   ├── TCU_Auditores.json
│   │   ├── AGU_Procuradores.json
│   │   └── Exemplo_CADE.json      ← Arquivo de exemplo criado
│   ├── dou2.json                   (planos DOU existentes)
│   └── ...
```

## Implementação Técnica

### Arquivos Modificados

**`src/dou_snaptrack/ui/app.py`** (linhas ~1587-1692):
- Adicionado bloco "💾 Gerenciar Listas de Agentes"
- Coluna esquerda: salvar lista atual
- Coluna direita: carregar/excluir listas salvas
- Sanitização de nomes de arquivo (remove caracteres especiais)
- Tratamento de erros em leitura/escrita de JSON

### Funções Principais

```python
# Salvar lista
listas_dir = Path("planos") / "eagendas_listas"
lista_data = {
    "nome": lista_name,
    "criado_em": date.today().strftime("%Y-%m-%d"),
    "total_agentes": len(queries),
    "queries": queries
}
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(lista_data, f, indent=2, ensure_ascii=False)

# Carregar lista
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
st.session_state.eagendas.saved_queries = data["queries"]
```

### Validações

- ✅ Nome da lista não pode estar vazio
- ✅ Só permite salvar se há pelo menos 1 agente na lista
- ✅ Sanitiza nome do arquivo (remove caracteres inválidos)
- ✅ Cria pasta automaticamente se não existir
- ✅ Ignora arquivos JSON corrompidos ao listar
- ✅ Tratamento de erros em todas operações de I/O

## Diferenças vs. DOU

| Recurso | DOU (Planos) | E-Agendas (Listas) |
|---------|--------------|-------------------|
| Salva período? | ✅ Sim (datas fixas) | ❌ Não (datas definidas na execução) |
| Salva consultas? | ✅ Sim (combos de seção/dia) | ✅ Sim (lista de agentes) |
| Formato | JSON com datas fixas | JSON com queries reutilizáveis |
| Caso de uso | Execução automática diária | Acompanhamento recorrente com período variável |

**Razão**: No E-Agendas, faz mais sentido salvar **quem** acompanhar (agentes) e permitir que o usuário defina **quando** acompanhar (período) a cada execução.

## Fluxo de Trabalho Recomendado

```
┌─────────────────────────────────────┐
│ 1. Montar lista de agentes          │
│    - Selecionar órgão/cargo/agente  │
│    - Clicar "+ Adicionar"           │
│    - Repetir para N agentes         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Salvar lista                     │
│    - Digite nome descritivo         │
│    - Clique "💾 Salvar Lista"       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Próxima sessão: Carregar lista   │
│    - Selecione lista no dropdown    │
│    - Clique "📂 Carregar"           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Definir período & Executar       │
│    - Ajuste datas (início/fim)      │
│    - Clique "🚀 Executar"           │
│    - Gere relatório DOCX            │
└─────────────────────────────────────┘
```

## Testes Realizados

### ✅ Teste 1: Salvar Lista
```
1. Adicionadas 2 consultas
2. Nome: "Exemplo_CADE"
3. Clicado "💾 Salvar Lista"
4. Resultado: Arquivo criado em planos/eagendas_listas/Exemplo_CADE.json
```

### ✅ Teste 2: Carregar Lista
```
1. Limpar todas consultas
2. Selecionar "Exemplo_CADE" no dropdown
3. Clicar "📂 Carregar"
4. Resultado: 2 consultas restauradas
```

### ✅ Teste 3: Excluir Lista
```
1. Selecionar lista no dropdown
2. Clicar "🗑️ Excluir"
3. Resultado: Arquivo removido do disco
```

### ✅ Teste 4: Validação de Sintaxe
```bash
python -m py_compile c:\Projetos\src\dou_snaptrack\ui\app.py
# Resultado: Sem erros
```

## Melhorias Futuras (Opcionais)

- [ ] **Editar lista**: Modificar nome ou queries sem recriar
- [ ] **Duplicar lista**: Criar cópia para variações
- [ ] **Exportar/Importar**: Compartilhar listas via arquivo único
- [ ] **Tags/Categorias**: Organizar listas por tema
- [ ] **Histórico de execuções**: Rastrear quando cada lista foi usada
- [ ] **Validação de agentes**: Verificar se agentes ainda existem no sistema
- [ ] **Auto-completar**: Sugerir nomes baseados em listas existentes

## Compatibilidade

- ✅ Windows (PowerShell 5.1)
- ✅ Python 3.10+
- ✅ Streamlit UI
- ✅ Formato JSON padrão (portável)

## Troubleshooting

### Problema: Não consigo salvar lista
**Causa**: Permissões de escrita na pasta `planos/eagendas_listas/`  
**Solução**: Verificar permissões ou executar como administrador

### Problema: Lista não aparece no dropdown
**Causa**: Arquivo JSON corrompido ou formato inválido  
**Solução**: Verificar estrutura do JSON (deve ter "nome", "queries", etc.)

### Problema: Erro ao carregar lista antiga
**Causa**: Formato de queries mudou (campos n1/n2/n3)  
**Solução**: Recriar lista manualmente ou editar JSON para novo formato

---

**Versão**: 1.0  
**Data**: 2025-11-13  
**Status**: ✅ Implementado e testado
