"""Combine the classification passes into data/classification.json.

Pass A  (LLM, "what is the problem about")      data/labels/passA/*.json
Pass B  (LLM, "what technique solves it")        data/labels/passB/*.json
Pass C  (keyword rules, scripts/keyword_classify) data/labels/passC.json
Adjudication of A/B disagreements (LLM judge)    data/labels/adjudicated/*.json
Manual overrides (edit this to iterate!)         data/overrides.json

Final primary = override > adjudicated > A (when A == B).
Usage:  python3 scripts/merge_labels.py            -> writes classification.json + report
        python3 scripts/merge_labels.py --disputes -> also writes data/labels/disputes_*.txt for adjudication
"""
import glob, json, os, sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(ROOT, *a)


def load_dir(d):
    out = {}
    for f in sorted(glob.glob(P(d, '*.json'))):
        for r in json.load(open(f)):
            out[r['id']] = r
    return out


def main():
    tax = json.load(open(P('data/taxonomy.json')))
    valid = {c['id'] for c in tax['categories']}
    problems = json.load(open(P('data/problems.json')))
    A, B = load_dir('data/labels/passA'), load_dir('data/labels/passB')
    C = {r['id']: r for r in json.load(open(P('data/labels/passC.json')))}
    J = load_dir('data/labels/adjudicated')
    overrides = json.load(open(P('data/overrides.json'))) if os.path.exists(P('data/overrides.json')) else {}

    result, disputes, stats = {}, [], Counter()
    for p in problems:
        pid = p['id']
        a, b, c = A.get(pid), B.get(pid), C.get(pid, {'top': []})
        if not a or not b:
            stats['missing_pass'] += 1
            continue
        pa, pb = a['primary'], b['primary']
        votes = {'A': pa, 'B': pb, 'C': c['top'][:3]}
        if pid in overrides:
            o = overrides[pid]
            primary, method = (o if isinstance(o, str) else o['primary']), 'override'
        elif pid in J:
            primary, method = J[pid]['primary'], 'adjudicated'
        elif pa == pb:
            primary, method = pa, 'consensus'
        else:
            primary, method = None, 'disputed'
            disputes.append(p)
        # Secondary topics: anything either LLM pass named (including the losing primary).
        sec = []
        for x in [pa, pb] + a.get('secondary', []) + b.get('secondary', []) + (J.get(pid, {}).get('secondary', [])):
            if x in valid and x != primary and x not in sec:
                sec.append(x)
        if isinstance(overrides.get(pid), dict) and 'secondary' in overrides[pid]:
            sec = overrides[pid]['secondary']
        kw_agrees = primary in c['top']
        stats[method] += 1
        if method == 'consensus':
            stats['consensus_kw_agrees' if kw_agrees else 'consensus_kw_differs'] += 1
        result[pid] = {
            'primary': primary, 'secondary': sec[:3], 'method': method, 'votes': votes,
            'kw_agrees': kw_agrees, 'key_idea': b.get('key_idea', ''),
            'confidence': [a.get('confidence'), b.get('confidence')],
        }
        for x in [primary] + sec:
            assert x is None or x in valid, (pid, x)

    json.dump(result, open(P('data/classification.json'), 'w'), indent=1)
    print(dict(stats))
    counts = Counter(r['primary'] for r in result.values())
    print('categories used:', len([k for k in counts if k]), '/', len(valid))
    print('per category:', sorted(counts.items(), key=lambda kv: -kv[1]))

    if '--disputes' in sys.argv:
        # Review set: A/B disagreements, plus anything either pass flagged as low confidence
        # or as not fitting the taxonomy (taxonomy may have grown since the passes ran).
        def flagged(pid):
            r = result.get(pid)
            if not r or r['method'] in ('override', 'adjudicated'):
                return False
            return (r['method'] == 'disputed' or 'low' in r['confidence']
                    or 'suggest' in A[pid] or 'suggest' in B[pid])
        ds = [p for p in problems if flagged(p['id'])]
        print('review set:', len(ds))
        n = 4
        for i in range(n):
            chunk = ds[i::n]
            with open(P(f'data/labels/disputes_{i + 1}.txt'), 'w') as f:
                for p in chunk:
                    r = result[p['id']]
                    notes = '; '.join(x for x in [A[p['id']].get('suggest'), B[p['id']].get('suggest')] if x)
                    f.write(f"### {p['id']}\nPassA: {r['votes']['A']} | PassB: {r['votes']['B']} | keywords: {', '.join(r['votes']['C'])}"
                            f" | confidence A/B: {'/'.join(map(str, r['confidence']))}{' | suggested new category: ' + notes if notes else ''}\n"
                            f"PassB key idea: {r['key_idea']}\n{p['text']}\n\n")
            print('disputes file', i + 1, len(chunk))


if __name__ == '__main__':
    main()
