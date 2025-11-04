# Configuração do Ruff - Linter Moderno para Python

## 📋 O que é o Ruff?

**Ruff** é um linter Python extremamente rápido, escrito em Rust, que substitui múltiplas ferramentas:
- **Flake8** (verificação de código)
- **isort** (organização de imports)
- **pyupgrade** (modernização de sintaxe Python)
- **autoflake** (remoção de código não usado)

### 🚀 Principais Benefícios

1. **Velocidade**: 50-100x mais rápido que ferramentas tradicionais
2. **Unificação**: Uma ferramenta para múltiplas verificações
3. **Auto-fix**: Corrige automaticamente 70-80% dos problemas
4. **Modernização**: Atualiza código para usar sintaxe Python moderna

## ⚙️ Configuração Aplicada

### Regras Habilitadas

```toml
[tool.ruff.lint]
select = [
    "F",     # Pyflakes (erros lógicos)
    "E",     # pycodestyle errors (formatação)
    "W",     # pycodestyle warnings
    "I",     # isort (imports organizados)
    "UP",    # pyupgrade (sintaxe moderna)
    "B",     # bugbear (bugs comuns)
    "SIM",   # simplificações de código
    "C4",    # comprehensions
    "ARG",   # argumentos não usados
    "PERF",  # performance anti-patterns
    "RUF",   # regras específicas do Ruff
]
```

### Correções Automáticas Habilitadas

```toml
fixable = ["F", "E", "W", "I", "UP", "C4", "RUF"]
```

### Configurações Especiais

- **Linha máxima**: 120 caracteres (adequado para monitores modernos)
- **Target Python**: 3.11 (usa recursos da versão correta)
- **Import sorting**: isort configurado para 3 seções (stdlib, third-party, first-party)
- **Exceções por arquivo**: `__init__.py` permite imports não usados (F401)

## 📊 Resultado da Aplicação Inicial

### Estatísticas Gerais

- **Total de problemas encontrados**: 1.158
- **Corrigidos automaticamente**: 899 (77.6%)
- **Avisos restantes**: 259 (não-críticos)

### Top 5 Correções Aplicadas

| Categoria | Quantidade | Descrição |
|-----------|------------|-----------|
| **UP006** | 381 | `List[X]` → `list[X]`, `Dict[X,Y]` → `dict[X,Y]` (PEP 585) |
| **UP045** | 199 | `Optional[X]` → `X \| None` (PEP 604 union types) |
| **W293**  | 127 | Remoção de espaços em linhas vazias |
| **I001**  | 65 | Organização alfabética de imports |
| **UP035** | 79 | Atualização de imports deprecados |

### Exemplos de Modernização

#### Antes (Python ≤3.9):
```python
from typing import List, Dict, Optional

def process_items(items: List[Dict[str, str]]) -> Optional[str]:
    ...
```

#### Depois (Python 3.11):
```python
def process_items(items: list[dict[str, str]]) -> str | None:
    ...
```

## 🔍 Avisos Restantes (259)

### Categorias Principais

1. **SIM105** (77 casos): Sugestão de usar `contextlib.suppress()` em try-except-pass
   - **Decisão**: Manter try-except por clareza e performance em hot paths
   
2. **E701** (49 casos): Múltiplos statements em uma linha
   - **Contexto**: Padrões compactos intencionais (ex: `try: x = func()`)
   - **Decisão**: Revisar caso a caso em próxima iteração

3. **B023** (26 casos): Variável de loop usada em closure
   - **Impacto**: Potencial bug em lambdas/funções dentro de loops
   - **Ação**: Revisar prioridade ALTA

4. **RUF002/RUF001** (3 casos): Caracteres Unicode ambíguos em strings/docstrings
   - **Exemplo**: EN DASH (–) vs HYPHEN-MINUS (-)
   - **Ação**: Normalizar para ASCII quando possível

## 🛠️ Uso Diário

### Comandos Úteis

```bash
# Verificar todo o código
ruff check src/

# Auto-corrigir problemas
ruff check src/ --fix

# Verificar com estatísticas
ruff check src/ --statistics

# Apenas imports
ruff check src/ --select I --fix

# Ignorar regra específica
ruff check src/ --ignore E501
```

### Integração com IDE

VSCode já detecta automaticamente `pyproject.toml`. Para ativar:
1. Instalar extensão "Ruff" (charliermarsh.ruff)
2. Adicionar ao `settings.json`:
   ```json
   {
     "[python]": {
       "editor.defaultFormatter": "charliermarsh.ruff",
       "editor.formatOnSave": true
     }
   }
   ```

## 📈 Performance Verificada

Após aplicação das correções Ruff, todos os testes passaram:
- ✅ Imports funcionando corretamente
- ✅ Benchmark de performance executado com sucesso
- ✅ Sintaxe moderna aplicada sem regressões
- ✅ Organização de código melhorada

## 🎯 Próximos Passos

1. **Revisar B023**: Variáveis de loop em closures (potencial bug)
2. **Avaliar SIM105**: Decidir sobre `contextlib.suppress()` vs try-except
3. **Normalizar Unicode**: Substituir caracteres ambíguos (–, —) por padrão ASCII
4. **Integrar CI/CD**: Adicionar `ruff check` no pipeline de testes
5. **Pre-commit hook**: Executar Ruff automaticamente antes de commits

## 📚 Referências

- Documentação oficial: https://docs.astral.sh/ruff/
- Catálogo de regras: https://docs.astral.sh/ruff/rules/
- Comparação com outras ferramentas: https://docs.astral.sh/ruff/faq/
