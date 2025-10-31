import re

# Ler arquivo
with open('C:/Projetos/src/dou_snaptrack/cli/plan_live_async.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remover linhas com DEBUG
lines = content.split('\n')
cleaned = []
for line in lines:
    if 'print(' in line and '[DEBUG' in line:
        continue
    if 'print(f' in line and 'DEBUG:' in line:
        continue
    cleaned.append(line)

result = '\n'.join(cleaned)

# Salvar
with open('C:/Projetos/src/dou_snaptrack/cli/plan_live_async.py', 'w', encoding='utf-8') as f:
    f.write(result)

print(f"Removed DEBUG lines. File has {len(cleaned)} lines now.")
