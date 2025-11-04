# Changelog consolidado

Este documento consolida as principais mudanças, otimizações e correções recentes do projeto, substituindo diversos resumos e relatórios espalhados.

## 2025-10-27 — Migração completa para Playwright Async API
- Eliminado conflito "Sync API inside asyncio loop" no Streamlit/Python 3.13
- Implementação async nas rotas críticas (utils/browser async, plan_live_async, wrappers sync)
- Remoção de workarounds com threading/subprocess; código mais simples e robusto
- Compatível com UI (Streamlit) e CLI

Referências: MIGRACAO_ASYNC_COMPLETA_27-10-2025.md (arquivado)

## 2025-10-27 — Otimizações de startup da UI (<500ms)
- Lazy import do batch_runner (Playwright) e utilitários pesados
- Criação de diretórios on-demand
- Importes de reporting já eram lazy e foram mantidos

Referências: OTIMIZACAO_UI_STARTUP.md (arquivado)

## 2025-10-27 — Dead code e performance
- Remoção de funções não utilizadas e duplicações
- Verificação de lock 4x mais rápida (tasklist CSV + timeout menores)
- Cache de validação do browser (redução ~90% de RPC)
- Otimizações de subprocess e PYTHONPATH

Referências: ANALISE_DEAD_CODE_PERFORMANCE.md e RESUMO_OTIMIZACOES_DEADCODE_27-10-2025.md (arquivados)

## 2025-10-24 — Otimizações gerais e sistema de atualização de artefatos
- Cache com TTL em carregamento de pares
- Redução de timeouts de browser launch
- Novo sistema de atualização do artefato pairs (CLI + UI + metadata)

Referências: RESUMO_OTIMIZACOES_24-10-2025.md e docs/PAIRS_UPDATER.md

## 2025-10-27 — Otimizações opcionais adicionais
- Waits condicionais (polling) para dropdowns (50–150ms por operação)
- ThreadPoolExecutor para cleanup de arquivos (3–5x mais rápido)
- UI lazy imports (consolidado acima)

Referências: RESUMO_OTIMIZACOES_OPCIONAIS_27-10-2025.md (arquivado)

## 2025-11-04 — Instalador (sem admin) e logs legíveis
- Mensagens 100% ASCII, sem acentos/emoji (evita mojibake)
- Detecção robusta de Python (>=3.10), pip bootstrap (ensurepip/get-pip)
- Instalação do pacote em modo usuário (editable) + Playwright opcional
- Criação de atalho detectada corretamente (sem falsos negativos)

Arquivos: scripts/install.ps1, INSTALACAO.md, docs/INSTALL_TROUBLESHOOTING.md

## 2025-11-04 — Testes unificados e limpeza de scripts
- Runner único: tests/run_tests.py (+ wrapper scripts/run-tests.ps1)
- Suítes: imports, smoke (Playwright), mapping (opcional)
- Remoção/arquivamento de scripts ad hoc de teste

Como executar:
- Imports: `./scripts/run-tests.ps1 -Suite imports`
- Smoke: `./scripts/run-tests.ps1 -Suite smoke`
- Mapping (longo): `python ./tests/run_tests.py --suite mapping --allow-long --timeout 600`

---

Para histórico detalhado, consulte os arquivos arquivados em `docs/archive/` ou o histórico de commits no Git.
