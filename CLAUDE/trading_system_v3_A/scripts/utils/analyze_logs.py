
import re
from collections import defaultdict

scanner_stats = defaultdict(lambda: {'zero': 0, 'non_zero': 0})

try:
    with open('logs/scanner.log', 'r') as f:
        for line in f:
            match = re.search(r'Scanner (\w+) returned (\d+) results', line)
            if match:
                name = match.group(1)
                count = int(match.group(2))
                if count == 0:
                    scanner_stats[name]['zero'] += 1
                else:
                    scanner_stats[name]['non_zero'] += 1
except FileNotFoundError:
    print('Log file not found')
    exit()

print(f"{'SCANNER NAME':<25} | {'ZEROS':<8} | {'HITS':<8} | {'RATE':<6}")
print('-'*55)
for name, stats in sorted(scanner_stats.items(), key=lambda x: x[1]['non_zero'], reverse=False):
    total = stats['zero'] + stats['non_zero']
    rate = (stats['non_zero'] / total * 100) if total > 0 else 0
    print(f"{name:<25} | {stats['zero']:<8} | {stats['non_zero']:<8} | {rate:<5.1f}%")
