"""Split data/<contest>/problems.json into text batches for the LLM classification passes.
Usage: python3 scripts/make_batches.py [amc10|amc8] [number of batches, default 6]
Each problem is "### <id>" + its text. Diagrams saved locally are listed by absolute path so a
reviewer can open the picture; other diagrams (AoPS LaTeX renders) only show as [DIAGRAM]."""
import json, os, re, sys
from contest import D

n = next((int(a) for a in sys.argv[1:] if a.isdigit()), 6)
problems = json.load(open(D('problems.json')))
os.makedirs(D('batches'), exist_ok=True)
size = -(-len(problems) // n)
for i in range(n):
    with open(D(f'batches/batch_{i + 1}.txt'), 'w') as f:
        for p in problems[i * size:(i + 1) * size]:
            local = [os.path.abspath(D('raw/images', os.path.basename(s)))
                     for s in re.findall(r'<img [^>]*src="img/([^"]+)"', p['html'])]
            pics = ''.join(f'\n[DIAGRAM IMAGE: {x}]' for x in local)
            f.write(f"### {p['id']}\n{p['text']}{pics}\n\n")
    print('batch', i + 1, len(problems[i * size:(i + 1) * size]))
