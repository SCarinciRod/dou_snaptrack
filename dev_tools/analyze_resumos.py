import re

content = open('C:/Users/RSCARINC/Downloads/boletim_teste24-10-2025_24-10-2025 (3).md', encoding='utf-8').read()
matches = re.findall(r'## (.+?)\n\n- \[(.+?)\]\((.+?)\)\s+\n\s+_Resumo:_ (.+?)(?=\n\n|\n## |$)', content, re.DOTALL)

print(f'Total items: {len(matches)}\n')

for i, (cat, titulo, link, resumo) in enumerate(matches, 1):
    print(f'{i}. {titulo[:70]}')
    print(f'   Resumo length: {len(resumo)} chars')
    print(f'   First 100 chars: {resumo[:100].strip()}')
    if len(resumo) < 150:
        print(f'   ⚠️ RESUMO CURTO - Link: {link}')
    print()
