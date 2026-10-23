"""Build docs/data.json (what the GitHub Pages site loads) from problems + classification."""
import json, os, re, shutil

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(ROOT, *a)


def clean_html(h):
    h = re.sub(r'<(script|iframe|style)\b.*?</\1>', '', h, flags=re.S | re.I)
    h = re.sub(r'\son\w+="[^"]*"', '', h)
    h = re.sub(r'<img ', '<img referrerpolicy="no-referrer" ', h)
    # MathJax has no tabular; the AMC tables only hold numbers, so array renders them the same.
    h = re.sub(r'\\begin\{tabular\}(\[\w\])?', r'\\begin{array}', h)
    h = h.replace('\\end{tabular}', '\\end{array}').replace('\\multicolumn{4}{c}{}\\\\', '')
    return h


def main():
    tax = json.load(open(P('data/taxonomy.json')))
    problems = json.load(open(P('data/problems.json')))
    # Only latex.artofproblemsolving.com (asy/LaTeX renders) allows hotlinking; anything else must be local.
    for p in problems:
        for src in re.findall(r'<img [^>]*src="([^"]+)"', p['html']):
            if not (src.startswith('img/') or src.startswith('https://latex.artofproblemsolving.com/')):
                raise SystemExit(f"{p['id']}: image {src} can't be hotlinked; save it to data/raw/images/{p['id']}.<ext>")
    os.makedirs(P('docs/img'), exist_ok=True)
    for f in os.listdir(P('data/raw/images')):
        shutil.copyfile(P('data/raw/images', f), P('docs/img', f))
    cls = json.load(open(P('data/classification.json')))
    out = []
    for p in problems:
        c = cls.get(p['id'])
        if not c or not c['primary']:
            raise SystemExit(f"unclassified problem {p['id']} - run merge_labels.py / adjudication first")
        out.append({
            'id': p['id'], 'label': p['label'], 'year': p['year'], 'order': p['order'], 'num': p['num'],
            'answer': p['answer'], 'url': p['url'], 'html': clean_html(p['html']),
            'cat': c['primary'], 'sec': c['secondary'], 'idea': c.get('key_idea', ''),
            'how': c['method'],
        })
    # Newest test first, then by problem number.
    out.sort(key=lambda r: (-r['order'], r['num']))
    tests = []
    for r in out:
        if r['label'] not in tests:
            tests.append(r['label'])
    os.makedirs(P('docs'), exist_ok=True)
    json.dump({'taxonomy': tax, 'tests': tests, 'problems': out},
              open(P('docs/data.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print('wrote docs/data.json:', len(out), 'problems,', os.path.getsize(P('docs/data.json')) // 1024, 'KB')


if __name__ == '__main__':
    main()
