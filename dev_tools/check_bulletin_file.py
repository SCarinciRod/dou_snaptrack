with open('C:/Projetos/src/dou_utils/bulletin_utils.py', encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines: {len(lines)}')

func_lines = [i for i, l in enumerate(lines) if 'def generate_bulletin' in l]
if func_lines:
    func_line = func_lines[0]
    print(f'\ngenerate_bulletin at line: {func_line+1}')
    print('\nNext 25 lines after function def:')
    for i in range(func_line, min(func_line+25, len(lines))):
        print(f'{i+1:4d}: {lines[i]}', end='')
