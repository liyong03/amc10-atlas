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
            problems.append({
                'id': f"{short}-{n:02d}",
                'test': t, 'label': label, 'year': year, 'order': order, 'num': n,
                'answer': ans,
                'url': WIKI + f"{t}_Problems/Problem_{n}",
                'text': p['text'], 'html': p['html'], 'diagrams': p['diagrams'],
            })
    problems.sort(key=lambda p: (-p['order'], p['num']))
    missing = [p['id'] for p in problems if not p['answer']]
    assert not missing, missing
    json.dump(problems, open(os.path.join(ROOT, 'data/problems.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(problems), 'problems from', len(raw['tests']), 'tests')

main()
