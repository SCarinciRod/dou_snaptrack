import re

content = open('C:/Users/RSCARINC/Downloads/boletim_teste24-10-2025_24-10-2025 (3).md', encoding='utf-8').read()

# Procurar padrões de resumo que sejam apenas título
matches = re.findall(r'- \[(.+?)\]\((.+?)\)\s+\n\s+_Resumo:_ (.+?)(?=\n\n|\n## |\n- \[|$)', content, re.DOTALL)

print(f'Total de itens analisados: {len(matches)}\n')

problemas = []
for i, (titulo, link, resumo) in enumerate(matches, 1):
    resumo_clean = resumo.strip()
    titulo_clean = titulo.strip().upper()
    
    # Verificar se o resumo é muito similar ao título
    resumo_upper = resumo_clean.upper()
    similarity = sum(1 for a, b in zip(titulo_clean, resumo_upper) if a == b) / max(len(titulo_clean), 1)
    
    if similarity > 0.8:
        problemas.append((i, titulo, link, resumo_clean, similarity))
    elif len(resumo_clean) < 50:
        problemas.append((i, titulo, link, resumo_clean, 0))

if problemas:
    print(f'⚠️ PROBLEMAS ENCONTRADOS: {len(problemas)}\n')
    for i, titulo, link, resumo, sim in problemas:
        print(f'{i}. {titulo[:70]}')
        print(f'   Link: {link}')
        print(f'   Resumo: {resumo[:150]}')
        if sim > 0:
            print(f'   Similaridade com título: {sim:.1%}')
        print()
else:
    print('✅ TODOS OS RESUMOS ESTÃO COMPLETOS!')
    print('\nExemplos de resumos bem-sucedidos:')
    for i in [0, len(matches)//2, -1]:
        titulo, link, resumo = matches[i]
        print(f'\n{i+1 if i >= 0 else len(matches)}. {titulo[:70]}')
        print(f'   Resumo ({len(resumo.strip())} chars): {resumo.strip()[:150]}...')
