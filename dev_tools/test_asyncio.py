import asyncio

try:
    loop = asyncio.get_running_loop()
    print(f'SIM - Loop ativo: {type(loop).__name__}')
except RuntimeError:
    print('NAO - Sem loop ativo')

# Testar Playwright
print('\nTestando Playwright...')
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        print('✅ Playwright funcionou!')
except Exception as e:
    print(f'❌ Erro: {e}')
