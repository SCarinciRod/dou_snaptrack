# Ajustes na Funcionalidade de Edição de Planos DOU

**Data**: 13 de novembro de 2025  
**Versão**: 2.0 (Ajustes baseados no feedback do usuário)

---

## 🔄 Mudanças Implementadas

### 1. **Problema: Células Vazias na Tabela** ✅ RESOLVIDO

**Causa**: Função `_build_combos()` criava combos com `label1=""` e `label2=""`

**Solução**:
```python
# ANTES
def _build_combos(n1: str, n2_list: list[str], key_type: str = "text") -> list[dict[str, Any]]:
    return [{
        ...
        "label1": "",  # ❌ Vazio
        "label2": "",  # ❌ Vazio
    } for n2 in n2_list]

# DEPOIS
def _build_combos(n1: str, n2_list: list[str], key_type: str = "text") -> list[dict[str, Any]]:
    return [{
        ...
        "label1": n1,  # ✅ Usa o valor da key como label inicial
        "label2": n2,  # ✅ Usa o valor da key como label inicial
    } for n2 in n2_list]
```

**Resultado**: Agora os nomes dos órgãos aparecem corretamente na tabela

---

### 2. **Remoção por Checkbox** ✅ IMPLEMENTADO

**Antes**: Campo de texto onde usuário digitava IDs (ex: `0,3,7`)  
**Depois**: Coluna "Remover?" com checkbox ✓

#### Interface Nova

```
📋 Plano Atual
┌─────────┬────┬──────────────────────┬─────────────────┐
│Remover? │ ID │ Órgão                │ Sub-órgão       │
├─────────┼────┼──────────────────────┼─────────────────┤
│   ☐     │ 0  │ Ministério da Saúde  │ Secretaria Exec │
│   ✓     │ 1  │ Ministério da Educ.  │ Gabinete        │ ← Marcado
│   ☐     │ 2  │ Ministério da Fazenda│ Todos           │
└─────────┴────┴──────────────────────┴─────────────────┘

[💾 Salvar Edições] [🗑️ Remover Marcados (1)] [🗑️ Limpar Tudo]
```

#### Como Usar

1. **Marcar combos para remover**: Clique no checkbox da coluna "Remover?"
2. **Clicar botão**: "🗑️ Remover Marcados (N)"
3. **Resultado**: Apenas os marcados são removidos

**Código**:
```python
# Checkbox column no data_editor
"Remover?": st.column_config.CheckboxColumn(
    "Remover?",
    help="Marque para remover este combo",
    default=False,
    width="small"
)

# Botão conta quantos estão marcados
selected_count = int(edited_df["Remover?"].sum())
btn_label = f"🗑️ Remover Marcados ({selected_count})"

# Remove apenas os NÃO marcados
new_combos = []
for i, combo in enumerate(st.session_state.plan.combos):
    if i < len(edited_df) and not edited_df.iloc[i]["Remover?"]:
        new_combos.append(combo)
st.session_state.plan.combos = new_combos
```

---

### 3. **Botão Duplicar Removido** ✅ REMOVIDO

**Motivo**: Não há necessidade de duplicar combos em consultas DOU

**Antes**: 3 botões (Salvar, Remover, Duplicar, Limpar + caixa de texto)  
**Depois**: 3 botões simplificados (Salvar, Remover Marcados, Limpar Tudo)

---

### 4. **Tabela Simplificada** ✅ AJUSTADO

**Colunas Removidas**:
- ❌ `key1`, `key2`, `key3` (dados internos)
- ❌ `key1_type`, `key2_type`, `key3_type` (metadados)
- ❌ `label3` (não usado no DOU)

**Colunas Mantidas**:
- ✅ **Remover?** (checkbox)
- ✅ **ID** (referência, não editável)
- ✅ **Órgão** (label1, editável)
- ✅ **Sub-órgão** (label2, editável)

**Configuração**:
```python
column_config={
    "Remover?": st.column_config.CheckboxColumn(...),
    "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
    "Órgão": st.column_config.TextColumn("Órgão", width="large"),
    "Sub-órgão": st.column_config.TextColumn("Sub-órgão", width="large"),
},
disabled=["ID"]  # Apenas ID não pode ser editado
```

---

## 📊 Comparação Antes x Depois

### Antes (Complexo)

```
📋 Plano Atual
[Tabela com key1, key2, label1, label2, keytype, etc.]

**Ações:**
[💾 Aplicar Mudanças] [🗑️ Limpar Tudo] [📋 Duplicar ID: __]

**Remover Combos Específicos:**
Digite IDs: [0,3,7,12___________] [🗑️ Remover]
```

**Problemas**:
- ❌ Células vazias (labels não preenchidos)
- ❌ Precisa digitar IDs manualmente
- ❌ Fácil errar ao digitar (ex: `0,3,7,a`)
- ❌ Botão duplicar desnecessário
- ❌ Muitas colunas confusas

---

### Depois (Simplificado)

```
📋 Plano Atual
┌─────────┬────┬──────────────────┬─────────────┐
│Remover? │ ID │ Órgão            │ Sub-órgão   │
├─────────┼────┼──────────────────┼─────────────┤
│   ☐     │ 0  │ Min. da Saúde    │ Secretaria  │
│   ✓     │ 1  │ Min. da Educação │ Gabinete    │
│   ☐     │ 2  │ Min. da Fazenda  │ Todos       │
└─────────┴────┴──────────────────┴─────────────┘

**Ações:**
[💾 Salvar Edições] [🗑️ Remover Marcados (1)] [🗑️ Limpar Tudo]
```

**Melhorias**:
- ✅ Células preenchidas com nomes dos órgãos
- ✅ Checkbox visual (sem digitar IDs)
- ✅ Impossível errar (só marca/desmarca)
- ✅ Botão mostra quantos serão removidos
- ✅ Apenas 4 colunas essenciais

---

## 🎯 Fluxo de Uso

### Caso 1: Remover 3 Combos Específicos

**Antes**:
1. Olhar IDs na tabela: 2, 5, 8
2. Digitar na caixa: `2,5,8`
3. Clicar "Remover"
4. Verificar se não errou ao digitar

**Depois**:
1. Marcar checkbox nos IDs 2, 5, 8
2. Clicar "Remover Marcados (3)"
3. ✅ Pronto

---

### Caso 2: Editar Nome de Órgão

**Antes**:
1. Ver célula vazia
2. Não saber o que editar (key1? label1?)
3. Editar e aplicar mudanças

**Depois**:
1. Ver nome completo do órgão
2. Clicar na célula e editar diretamente
3. Clicar "Salvar Edições"
4. ✅ Pronto

---

### Caso 3: Remover 20 de 50 Combos

**Antes**:
1. Identificar todos os 20 IDs
2. Digitar: `0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38`
3. Rezar para não ter errado nenhum número
4. Clicar "Remover"

**Depois**:
1. Scrollar pela tabela marcando checkboxes
2. Ver contador em tempo real: "Remover Marcados (20)"
3. Clicar botão
4. ✅ Pronto

---

## 🧪 Testes Realizados

### Teste 1: Labels Preenchidos ✅

**Passos**:
1. Adicionar combo: Ministério da Saúde → Secretaria Executiva
2. Verificar tabela

**Resultado**:
- ✅ Coluna "Órgão": "Ministério da Saúde"
- ✅ Coluna "Sub-órgão": "Secretaria Executiva"

---

### Teste 2: Remoção por Checkbox ✅

**Passos**:
1. Criar plano com 10 combos
2. Marcar IDs 2, 5, 7
3. Clicar "Remover Marcados (3)"

**Resultado**:
- ✅ Restam 7 combos
- ✅ IDs corretos foram removidos

---

### Teste 3: Edição de Labels ✅

**Passos**:
1. Criar combo com label1="Ministério da Saúde"
2. Editar na tabela para "Min. Saúde"
3. Clicar "Salvar Edições"
4. Salvar plano e recarregar

**Resultado**:
- ✅ Label editado persiste no JSON
- ✅ Keys também atualizados para consistência

---

## 📁 Arquivos Modificados

### `src/dou_snaptrack/ui/app.py`

**Função `_build_combos()`** (linha ~237):
- Alterado: `label1` e `label2` agora recebem valores das keys

**Seção "Plano Atual"** (linhas ~1165-1242):
- Adicionado: Coluna "Remover?" com checkbox
- Removido: Caixa de texto para IDs
- Removido: Botão "Duplicar"
- Simplificado: Apenas 3 botões de ação

**Linhas alteradas**: ~80 linhas modificadas

---

## 🚀 Próximos Passos (Futuro)

### 1. Seleção Múltipla com Shift
```python
# Permitir selecionar range de checkboxes com Shift+Click
# Exemplo: Shift+Click ID 5 → ID 15 marca todos entre 5-15
```

### 2. Filtro de Busca
```python
# Campo de busca acima da tabela
search = st.text_input("Buscar órgão:", "")
filtered = [c for c in combos if search.lower() in c["label1"].lower()]
```

### 3. Ordenação de Colunas
```python
# Clicar no header da coluna para ordenar
sort_col = st.selectbox("Ordenar por:", ["ID", "Órgão", "Sub-órgão"])
sorted_combos = sorted(combos, key=lambda x: x.get(sort_col, ""))
```

---

## 📚 Documentação para Usuário

### Como Remover Combos

1. Vá até "📋 Plano Atual"
2. Marque os checkboxes na coluna "Remover?"
3. Clique em "🗑️ Remover Marcados (N)"
4. ✅ Combos removidos

### Como Editar Órgãos

1. Clique na célula da coluna "Órgão" ou "Sub-órgão"
2. Digite o novo valor
3. Clique em "💾 Salvar Edições"
4. ✅ Mudanças aplicadas

### Como Limpar Tudo

1. Clique em "🗑️ Limpar Tudo"
2. ✅ Todos os combos removidos

---

## 🎯 Conclusão

**Antes**: Interface complexa com 5 botões, caixa de texto, e células vazias  
**Depois**: Interface simples com 3 botões, checkbox visual, e dados preenchidos

**Impacto**: 
- ⚡ Mais rápido (não precisa digitar IDs)
- 🎯 Mais preciso (impossível errar checkbox)
- 👁️ Mais visual (vê os nomes dos órgãos)
- 🧹 Mais limpo (menos botões e campos)

**Feedback incorporado**: 100% ✅

---

**Testado e validado**: 13/11/2025  
**Status**: ✅ Pronto para uso
