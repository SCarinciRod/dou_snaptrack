# SnapTrack DOU — Execução Rápida (Windows)

Este projeto fornece uma UI Streamlit para montar planos (plan-live), executar a captação e gerar boletins a partir do DOU.

## Instalação em qualquer máquina (Windows)

1) Baixe e instale Python 3.11 (64 bits)
2) Abra o PowerShell e rode:

```
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

Isso irá:
- Baixar o repositório (branch main) para `%USERPROFILE%\dou_snaptrack`
- Criar um ambiente virtual
- Instalar dependências
- Testar o Playwright com o navegador do sistema (Chrome/Edge)

## Como rodar a UI

```
powershell -ExecutionPolicy Bypass -File %USERPROFILE%\dou_snaptrack\scripts\run-ui.ps1
```

A UI abre no navegador. O fluxo é:
- Explorar e montar plano (plan-live)
- Executar plano (resultados em `resultados/AAAA-MM-DD`)
- Gerar boletim (selecionando a pasta do dia e baixando o arquivo)

## Observações
- Em ambientes com firewall/SSL restrito, o Playwright usará Chrome/Edge do sistema (sem baixar binários).
- Resultados e relatórios ficam organizados em `resultados/<data>`.
- Planos são salvos em `planos/`.