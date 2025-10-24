# Dev Tools - Arquivos de Desenvolvimento e Teste

Este diretório contém scripts de teste, boletins de debug e relatórios gerados durante o desenvolvimento e correção de bugs.

## 📂 Estrutura

### Scripts de Teste Python
- `test_*.py` - Scripts de teste unitário e integração
- `check_*.py` - Scripts de verificação e validação
- `analyze_*.py` - Scripts de análise de dados
- `find_*.py` - Scripts de busca e investigação

### Boletins de Debug
- `*boletim*.md` - Boletins gerados durante testes e debug
- Exemplos: DEBUG_FULL_boletim.md, FINAL_PATCHED_boletim.md, etc.

### Relatórios
- `RELATORIO_*.md` - Relatórios de testes de execução e robustez

### Logs
- `*.log` - Logs de execução de testes
- `*.txt` - Outputs de debug e testes

## 🔧 Uso

Estes arquivos são para **desenvolvimento apenas** e não devem ser incluídos em builds de produção.

Para executar testes individuais:
```bash
python dev_tools/test_<nome>.py
```

## 📝 Histórico

Arquivos movidos para este diretório em 24/10/2025 durante limpeza pré-commit para organização do projeto.
