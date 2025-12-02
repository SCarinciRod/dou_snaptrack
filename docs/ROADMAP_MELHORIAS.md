# 🗺️ Roadmap de Melhorias - DOU SnapTrack

> **Documento criado:** 02/12/2024  
> **Última análise:** 10.144 linhas de código Python  
> **Objetivo:** Guia de melhorias técnicas para consulta futura

---

## 📊 Resumo da Análise

### Estado Atual (Dezembro 2024)

| Módulo    | Linhas | Funções | Classes | Status |
|-----------|--------|---------|---------|--------|
| `ui/`     | 4.578  | 91      | 6       | 🟡 Maior módulo, candidato a refatoração |
| `cli/`    | 3.592  | 32      | 1       | 🟡 Arquivos grandes |
| `utils/`  | 1.548  | 29      | 0       | 🟢 Tamanho adequado |
| `mappers/`| 265    | 8       | 0       | 🟢 OK |
| `adapters/`| 91    | 2       | 0       | 🟢 OK |

### Arquivos que Precisam de Atenção (>400 linhas)

| Arquivo | Linhas | Prioridade | Motivo |
|---------|--------|------------|--------|
| `cli/batch.py` | 861 | 🔴 Alta | Lógica complexa de processamento em lote |
| `ui/eagendas_ui.py` | 720 | 🔴 Alta | UI monolítica do E-Agendas |
| `cli/plan_live_eagendas_async.py` | 702 | 🟠 Média | Scraping assíncrono |
| `cli/plan_live_async.py` | 604 | 🟠 Média | Scraping assíncrono DOU |
| `ui/app.py` | 599 | 🔴 Alta | Entry point da UI |
| `cli/plan_live.py` | 583 | 🟠 Média | Versão sync (legado?) |
| `ui/batch_runner.py` | 550 | 🟠 Média | Execução de lotes |
| `ui/plan_editor.py` | 544 | 🟠 Média | Editor de planos |
| `utils/eagendas_calendar.py` | 517 | 🟡 Baixa | Lógica de calendário |
| `cli/reporting.py` | 448 | 🟡 Baixa | Geração de relatórios |

---

## 🎯 Melhorias por Categoria

### 1. 🚀 Performance (Prioridade Alta)

#### 1.1 Substituir `wait_for_timeout` por Esperas Condicionais
**Impacto:** Redução de 3-5 segundos em cada operação  
**Risco:** Médio (requer testes extensivos)  
**Esforço:** 4-6 horas

**Arquivos afetados:**
```
src/dou_snaptrack/cli/plan_live_async.py:273, 477
src/dou_snaptrack/cli/plan_live_eagendas_async.py:412, 509
src/dou_snaptrack/ui/dou_fetch.py:181
src/dou_snaptrack/ui/eagendas_collect_subprocess.py:176, 192, 206, 239
src/dou_snaptrack/ui/eagendas_fetch.py:170, 195
```

**Como fazer:**
```python
# ANTES (espera fixa)
page.wait_for_timeout(3000)
dropdown = page.query_selector('.selectize-dropdown')

# DEPOIS (espera condicional)
dropdown = page.wait_for_selector('.selectize-dropdown', state='visible', timeout=10000)
```

**Plano de implementação:**
1. Criar função helper `wait_for_dropdown_ready(page, selector)`
2. Testar com diferentes velocidades de conexão
3. Manter fallback para timeout fixo se seletor não encontrado
4. Documentar seletores específicos para cada site (DOU vs E-Agendas)

---

#### 1.2 Cache Inteligente com Invalidação
**Impacto:** Reduzir requests desnecessários  
**Risco:** Baixo  
**Esforço:** 2-3 horas

**Situação atual:**
- Cache TTL fixo de 15 minutos
- Não considera se dados mudaram

**Melhoria proposta:**
```python
# Criar cache com hash do conteúdo
@dataclass
class CachedData:
    data: Any
    fetched_at: datetime
    content_hash: str
    
def should_refresh(cached: CachedData, max_age: int = 900) -> bool:
    """Verifica se precisa atualizar baseado em tempo E mudança de conteúdo."""
    age = (datetime.now() - cached.fetched_at).total_seconds()
    return age > max_age
```

---

### 2. 🏗️ Arquitetura (Prioridade Média)

#### 2.1 Centralizar Lógica de Browser
**Impacto:** Código mais manutenível, menos bugs  
**Risco:** Baixo  
**Esforço:** 4-6 horas

**Problema:** Configuração de browser duplicada em 8+ arquivos

**Arquivos com código duplicado:**
- `cli/plan_live.py`
- `cli/plan_live_async.py`
- `ui/dou_fetch.py`
- `ui/eagendas_fetch.py`
- `ui/eagendas_collect_subprocess.py`
- `utils/eagendas_calendar.py`
- `utils/pairs_updater.py`

**Solução proposta:** Criar `utils/browser_factory.py`
```python
# utils/browser_factory.py
from dataclasses import dataclass
from typing import Literal, Optional
from playwright.sync_api import Browser, BrowserContext, Page

@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 30000
    viewport_width: int = 1366
    viewport_height: int = 900
    ignore_https_errors: bool = True
    block_resources: bool = True  # imagens, fontes, etc

class BrowserFactory:
    """Factory centralizada para criação de browsers Playwright."""
    
    @staticmethod
    def create_context(
        browser: Browser,
        config: BrowserConfig = BrowserConfig()
    ) -> BrowserContext:
        """Cria contexto com configurações padronizadas."""
        context = browser.new_context(
            ignore_https_errors=config.ignore_https_errors,
            viewport={"width": config.viewport_width, "height": config.viewport_height}
        )
        context.set_default_timeout(config.timeout)
        
        if config.block_resources:
            context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda r: r.abort())
        
        return context
    
    @staticmethod
    def get_browser_path() -> Optional[str]:
        """Retorna path do Chrome/Edge disponível."""
        # Centralizar lógica de utils/browser.py
        pass
```

---

#### 2.2 Unificar Padrão de Resposta JSON
**Impacto:** Consistência na API interna  
**Risco:** Baixo  
**Esforço:** 2-3 horas

**Problema:** 9 arquivos usam padrões diferentes de resposta JSON

**Solução:** Criar dataclasses padronizadas
```python
# utils/responses.py
from dataclasses import dataclass, asdict
from typing import Any, Optional
import json

@dataclass
class OperationResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def ok(cls, data: Any) -> "OperationResult":
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "OperationResult":
        return cls(success=False, error=error)
```

---

#### 2.3 Separar `ui/app.py` em Componentes
**Impacto:** Manutenibilidade, testabilidade  
**Risco:** Médio (muitas dependências)  
**Esforço:** 6-8 horas

**Situação atual:** `app.py` com 599 linhas misturando:
- Configuração do Streamlit
- Lógica de navegação
- Componentes de UI
- Handlers de eventos

**Estrutura proposta:**
```
ui/
├── app.py                 # Entry point enxuto (~100 linhas)
├── components/
│   ├── __init__.py
│   ├── header.py          # Cabeçalho e navegação
│   ├── sidebar.py         # Sidebar com opções
│   ├── status_bar.py      # Barra de status
│   └── notifications.py   # Sistema de notificações
├── pages/
│   ├── __init__.py
│   ├── dou_page.py        # Página DOU
│   ├── eagendas_page.py   # Página E-Agendas
│   ├── batch_page.py      # Página de lotes
│   └── settings_page.py   # Configurações
└── state/
    ├── __init__.py
    └── session.py         # Gerenciamento de session_state
```

---

### 3. 🧹 Qualidade de Código (Prioridade Baixa)

#### 3.1 Melhorar Tratamento de Exceções
**Impacto:** Debugging mais fácil, logs mais úteis  
**Risco:** Baixo  
**Esforço:** 4-6 horas

**Problema:** 221 ocorrências de `except Exception:` ou `except:`

**Ação:**
1. Criar exceções customizadas:
```python
# utils/exceptions.py
class DouSnapTrackError(Exception):
    """Base exception para o projeto."""
    pass

class BrowserNotFoundError(DouSnapTrackError):
    """Chrome/Edge não encontrado."""
    pass

class ScrapingError(DouSnapTrackError):
    """Erro durante scraping."""
    pass

class NetworkError(DouSnapTrackError):
    """Erro de rede/conexão."""
    pass
```

2. Substituir gradualmente:
```python
# ANTES
try:
    result = fetch_data()
except Exception:
    pass

# DEPOIS
try:
    result = fetch_data()
except NetworkError as e:
    logger.warning(f"Erro de rede: {e}, tentando novamente...")
    result = fetch_data_fallback()
except ScrapingError as e:
    logger.error(f"Erro de scraping: {e}")
    raise
```

---

#### 3.2 Extrair Magic Numbers para Constantes
**Impacto:** Código mais legível e configurável  
**Risco:** Baixo  
**Esforço:** 2 horas

**28 ocorrências** de timeouts hardcoded

**Solução:** Criar `constants/timeouts.py`
```python
# constants/timeouts.py
"""Constantes de timeout centralizadas."""

# Navegação
PAGE_LOAD_TIMEOUT = 30_000      # 30s para carregar página
ELEMENT_WAIT_TIMEOUT = 10_000   # 10s para elemento aparecer
DROPDOWN_LOAD_TIMEOUT = 5_000   # 5s para dropdown popular

# Operações longas
BATCH_OPERATION_TIMEOUT = 900   # 15min para operações em lote
SUBPROCESS_TIMEOUT = 120        # 2min para subprocessos

# Cache
CACHE_TTL_SHORT = 300           # 5min
CACHE_TTL_MEDIUM = 900          # 15min  
CACHE_TTL_LONG = 3600           # 1h
```

---

#### 3.3 Documentação de Funções Públicas
**Impacto:** Onboarding mais fácil  
**Risco:** Nenhum  
**Esforço:** Contínuo

**Situação:** Muitas funções sem docstrings

**Template sugerido:**
```python
def fetch_dou_options(date: str, secao: str) -> dict:
    """
    Busca opções de dropdown do DOU para uma data/seção.
    
    Args:
        date: Data no formato DD-MM-YYYY
        secao: Seção do DOU (DO1, DO2, DO3, etc.)
    
    Returns:
        dict com:
            - success (bool): Se a operação foi bem sucedida
            - n1_options (list): Lista de órgãos (nível 1)
            - n2_mapping (dict): Mapeamento N1 -> lista de N2
    
    Raises:
        NetworkError: Se não conseguir conectar ao site
        ScrapingError: Se estrutura da página mudou
    
    Example:
        >>> result = fetch_dou_options("02-12-2024", "DO1")
        >>> print(result['n1_options'][:3])
        ['Presidência da República', 'Ministério da Fazenda', ...]
    """
```

---

### 4. 🧪 Testes (Prioridade Média)

#### 4.1 Aumentar Cobertura de Testes
**Situação atual:** Testes básicos de imports e smoke tests

**Meta:** 60% de cobertura em `utils/` e `mappers/`

**Plano:**
```
tests/
├── unit/
│   ├── test_browser_factory.py
│   ├── test_responses.py
│   ├── test_exceptions.py
│   └── test_mappers.py
├── integration/
│   ├── test_dou_fetch.py
│   └── test_eagendas_fetch.py
└── e2e/
    └── test_full_workflow.py
```

---

## 📅 Cronograma Sugerido

### Sprint 1 (1-2 semanas) - Quick Wins
- [ ] Extrair magic numbers para constantes
- [ ] Criar `utils/responses.py` com padrão de resposta
- [ ] Adicionar docstrings nas funções principais

### Sprint 2 (2-3 semanas) - Performance
- [ ] Substituir `wait_for_timeout` por esperas condicionais
- [ ] Implementar cache inteligente com invalidação
- [ ] Centralizar configuração de browser

### Sprint 3 (3-4 semanas) - Arquitetura
- [ ] Refatorar `ui/app.py` em componentes
- [ ] Criar sistema de exceções customizadas
- [ ] Unificar padrão de resposta JSON

### Sprint 4 (2-3 semanas) - Testes
- [ ] Criar testes unitários para `utils/`
- [ ] Criar testes de integração para fetchers
- [ ] Configurar cobertura de código

---

## 📝 Notas para o Copilot

Quando for implementar estas melhorias:

1. **Sempre manter backward compatibility** - funções existentes devem continuar funcionando
2. **Testar em ambiente Windows** - o projeto é Windows-first
3. **Considerar redes corporativas** - timeouts conservadores são necessários
4. **Preferir Playwright channels** - não assumir browsers baixados
5. **Manter lazy loading** - imports pesados devem ser adiados
6. **Respeitar Ruff** - rodar linter antes de commitar

---

## 🔗 Referências

- Código fonte: `src/dou_snaptrack/`
- Testes: `tests/`
- Scripts: `scripts/`
- Instruções do projeto: `.github/copilot-instructions.md`

---

*Gerado automaticamente em 02/12/2024*
