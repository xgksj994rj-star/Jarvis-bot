from pathlib import Path
import re
root = Path('.')
command_names = []
for p in root.rglob('*.py'):
    text = p.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'@[^\n]*\.tree\.command\(\s*name\s*=\s*"([^"]+)"', text):
        command_names.append((p.as_posix(), m.group(1)))
print('total count:', len(command_names))
from collections import Counter
counts = Counter(path for path, _ in command_names)
for path, count in sorted(counts.items(), key=lambda x:(-x[1], x[0])):
    print(count, path)
print('\nCOMMANDS:')
for path, name in sorted(command_names):
    print(f'{path}: {name}')
