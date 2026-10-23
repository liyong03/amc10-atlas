"""Turn the raw browser dump (data/raw/amc10_data.json) into data/problems.json."""
import json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
WIKI = 'https://artofproblemsolving.com/wiki/index.php?title='

# Answer keys that hit a Cloudflare challenge in the bulk fetch, re-fetched separately.
ANSWER_FIX = {
    '2023_AMC_10B': 'CBDCAEBABCBCBCCEDEBAEBBEB',
    '2019_AMC_10A': 'CADBDCCCBCCEDDEADDBBDBCBD',
    '2016_AMC_10B': 'DBDBDBCACDBDDDCEDEDCBACDA',
    '2010_AMC_10A': 'DBDBECCDEEDCACDBABEDAAAAB',
    '2007_AMC_10B': 'EEBDDDEDDACDDCDCDBCCBBECA',
    '2002_AMC_10P': 'CBDCCDBEBCACBADDCCAABBBDD',
}

# Diagrams the bulk parser dropped because they shared a paragraph with the "Solution" link
# (fixed in scripts/fetch_in_browser.js for future fetches).
MISSING_DIAGRAMS = {
    '2014A-19': 'https://latex.artofproblemsolving.com/e/4/1/e41120e351bda42fada2fe2803e19a131bc30b96.png',
    '2013B-22': 'https://latex.artofproblemsolving.com/d/3/0/d305e9074b588800bd9056981b0e283a8488bc59.png',
}
# Images uploaded to the AoPS wiki can't be hotlinked (Cloudflare), so we serve copies
# from docs/img/; data/raw/images/<id>.<ext> holds the originals.
LOCAL_IMAGES = {f.split('.')[0]: f for f in os.listdir(os.path.join(ROOT, 'data/raw/images'))}


def fix_images(pid, html):
    if pid in LOCAL_IMAGES:
        html = re.sub(r'src="https://artofproblemsolving\.com/wiki/images/[^"]+"', f'src="img/{LOCAL_IMAGES[pid]}"', html)
    if pid in MISSING_DIAGRAMS:
        img = f'<img src="{MISSING_DIAGRAMS[pid]}" class="diagram" loading="lazy" alt="diagram">'
        html = html.replace('<p>$\\textbf{(A)}', f'<p>{img}\n</p><p>$\\textbf{{(A)}}', 1)
        assert img in html, pid
    return html


def test_meta(t):
    m = re.match(r'(\d{4})_(Fall_)?AMC_10([ABP]?)$', t)
    year, fall, ab = int(m.group(1)), bool(m.group(2)), m.group(3)
    label = f"{year}{' Fall' if fall else ''} AMC 10{ab}"
    # Sort key: newer first; within a year Fall > Spring, B > A (B is given later)
    order = year * 10 + (5 if fall else 0) + {'': 0, 'P': 0, 'A': 1, 'B': 2}[ab]
    short = f"{year}{'F' if fall else ''}{ab or ''}"
    return year, label, order, short

def main():
    raw = json.load(open(os.path.join(ROOT, 'data/raw/amc10_data.json')))
    problems = []
    for t, v in raw['tests'].items():
        year, label, order, short = test_meta(t)
        fix = ANSWER_FIX.get(t)
        for p in v['problems']:
            n = p['num']
            ans = fix[n - 1] if fix else p['answer']
            pid = f"{short}-{n:02d}"
            html = fix_images(pid, p['html'])
            problems.append({
                'id': pid,
                'test': t, 'label': label, 'year': year, 'order': order, 'num': n,
                'answer': ans,
                'url': WIKI + f"{t}_Problems/Problem_{n}",
                'text': p['text'] + (' [DIAGRAM]' if pid in MISSING_DIAGRAMS else ''),
                'html': html, 'diagrams': html.count('<img '),
            })
    problems.sort(key=lambda p: (-p['order'], p['num']))
    missing = [p['id'] for p in problems if not p['answer']]
    assert not missing, missing
    json.dump(problems, open(os.path.join(ROOT, 'data/problems.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(problems), 'problems from', len(raw['tests']), 'tests')

main()
