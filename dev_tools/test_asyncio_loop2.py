import asyncio
import sys
sys.path.insert(0, 'C:/Projetos/src')

# Simular contexto com loop asyncio (como Streamlit faz)
async def test_with_asyncio_loop():
    print('Loop ativo?', end=' ')
    try:
        loop = asyncio.get_running_loop()
        print(f'SIM: {type(loop).__name__}')
    except RuntimeError:
        print('NÃO')
    
    print('\nTestando pairs_updater dentro de loop asyncio...')
    from dou_snaptrack.utils.pairs_updater import update_pairs_file
    result = update_pairs_file(limit1=2, limit2=2)
    print(f'\nResultado: {result.get("success")}')
    if not result.get("success"):
        print(f'Erro: {result.get("error")}')
    else:
        print(f'Pares encontrados: {result.get("pairs_count")}')

if __name__ == '__main__':
    # Executar dentro de loop asyncio
    asyncio.run(test_with_asyncio_loop())
