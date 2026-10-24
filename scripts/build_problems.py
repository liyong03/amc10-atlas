"""Turn the raw browser dump (data/<contest>/raw/<contest>_data.json) into data/<contest>/problems.json.
Usage: python3 scripts/build_problems.py [amc10|amc8]"""
import base64, json, os, re
from contest import KEY, D

WIKI = 'https://artofproblemsolving.com/wiki/index.php?title='

# Answer keys that hit a Cloudflare challenge in the bulk fetch, re-fetched separately.
ANSWER_FIX = {} if KEY != 'amc10' else {
    '2023_AMC_10B': 'CBDCAEBABCBCBCCEDEBAEBBEB',
    '2019_AMC_10A': 'CADBDCCCBCCEDDEADDBBDBCBD',
    '2016_AMC_10B': 'DBDBDBCACDBDDDCEDEDCBACDA',
    '2010_AMC_10A': 'DBDBECCDEEDCACDBABEDAAAAB',
    '2007_AMC_10B': 'EEBDDDEDDACDDCDCDBCCBBECA',
    '2002_AMC_10P': 'CBDCCDBEBCACBADDCCAABBBDD',
}

# Diagrams the bulk parser dropped because they shared a paragraph with the "Solution" link
# (fixed in scripts/fetch_in_browser.js for future fetches).
MISSING_DIAGRAMS = {} if KEY != 'amc10' else {
    '2014A-19': 'https://latex.artofproblemsolving.com/e/4/1/e41120e351bda42fada2fe2803e19a131bc30b96.png',
    '2013B-22': 'https://latex.artofproblemsolving.com/d/3/0/d305e9074b588800bd9056981b0e283a8488bc59.png',
}
# Images uploaded to the AoPS wiki can't be hotlinked (Cloudflare), so we serve copies
# from <site>/img/. data/<contest>/raw/images/ holds them: either <problem id>.<ext> (saved by
# hand, AMC 10) or the wiki file name (from the "images" part of the browser dump).
os.makedirs(D('raw/images'), exist_ok=True)
LOCAL_IMAGES = {f.split('.')[0]: f for f in os.listdir(D('raw/images'))}


def save_dump_images(images):
    """Write the dump's {wiki url: data: URL} images to raw/images/; returns {wiki url: file name}."""
    names = {}
    for url, data in images.items():
        if not data:
            raise SystemExit(f'image {url} failed to download in the browser; fetch it again')
        name = re.sub(r'[^\w.-]', '_', url.split('/')[-1].split('?')[0])
        assert name not in names.values(), f'two wiki images named {name}'
        with open(D('raw/images', name), 'wb') as f:
            f.write(base64.b64decode(data.split(',', 1)[1]))
        names[url] = name
    return names


def fix_images(pid, html, dump_images):
    for url, name in dump_images.items():
        html = html.replace(f'src="{url}"', f'src="img/{name}"')
    if pid in LOCAL_IMAGES:
        html = re.sub(r'src="https://artofproblemsolving\.com/wiki/images/[^"]+"', f'src="img/{LOCAL_IMAGES[pid]}"', html)
    if pid in MISSING_DIAGRAMS:
        img = f'<img src="{MISSING_DIAGRAMS[pid]}" class="diagram" loading="lazy" alt="diagram">'
        html = html.replace('<p>$\\textbf{(A)}', f'<p>{img}\n</p><p>$\\textbf{{(A)}}', 1)
        assert img in html, pid
    return html


# AMC 8 groups of problems that share one setup (a story, table or figure). The wiki puts the
# setup in only one place, so the browser parser left it out of the other problems or, where the
# group sits under its own heading, merged or dropped the problems. Rebuild each group so every
# problem carries the setup.
def html_text(html):
    t = re.sub(r'<[^>]+>', ' ', html).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', t).strip() + (' [DIAGRAM]' if '<img ' in html else '')


def wiki_problem(wikitext, n):
    """Problem n as HTML, from the wiki source (only for problems without pictures)."""
    body = re.search(rf'^==+\s*Problem {n}\s*==+\s*$(.*?)(?=^==)', wikitext, re.M | re.S).group(1)
    body = re.sub(r'\[\[[^]]*\|\s*Solution\s*\]\]', '', body)
    assert '<asy>' not in body and '[[' not in body, n
    body = re.sub(r'<math>(.*?)</math>', r'$\1$', body, flags=re.S)
    return ''.join(f'<p>{x.strip()}\n</p>' for x in re.split(r'\n\s*\n', body) if x.strip())


def fix_shared_setups(tests):
    if KEY != 'amc8':
        return
    by_num = lambda t: {p['num']: p for p in tests[t]['problems']}

    def put(t, n, html):
        ps = by_num(t)
        if n not in ps:
            ps[n] = {'num': n, 'answer': re.findall(r'^#\s*([A-E])', tests[t]['answerKeyRaw'], re.M)[n - 1]}
            tests[t]['problems'].append(ps[n])
        ps[n].update(html=html, text=html_text(html), diagrams=html.count('<img '))

    # 2001 #7-9 sit under sub-headings inside #6, after the kite setup.
    p6 = by_num('2001_AMC_8')[6]['html']
    cut = p6.index('<p><br>\n<i>Problems 7, 8 and 9')
    parts = re.split(r'<h3>.*?Problem (\d+)</span>.*?</h3>', p6[cut:], flags=re.S)
    setup = parts[0]
    put('2001_AMC_8', 6, p6[:cut])
    for n, h in zip(parts[1::2], parts[2::2]):
        put('2001_AMC_8', int(n), setup + h.strip())
    # 2002 #8-10 are under their own heading ("Juan's Old Stamping Grounds"), which the parser skipped.
    w = tests['2002_AMC_8']['wikitext']
    juan = re.search(r'Problems 8,9 and 10 use.*?<center>(.*?)</center>', w, re.S)
    setup = (f'<p><i>Problems 8, 9 and 10 use the data found in the accompanying paragraph and table:</i>\n</p>'
             f'<p>{juan.group(1).strip()}\n</p><p><img src="https://latex.artofproblemsolving.com/f/6/7/'
             f'f679bb00d960506089f9cd632a80bd218347de4e.png" class="diagram" alt="diagram" loading="lazy">\n</p>')
    for n in (8, 9, 10):
        put('2002_AMC_8', n, setup + wiki_problem(w, n))
    # 2003 #8-10: the "Bake Sale" setup is at the top of #8.
    p8 = by_num('2003_AMC_8')[8]['html']
    setup = p8[:p8.index('<p>Each friend uses the same amount of dough, and Art makes exactly 12 cookies. Who')]
    for n in (9, 10):
        put('2003_AMC_8', n, setup + by_num('2003_AMC_8')[n]['html'])
    # 2006 #14-16: the setup is under a heading of its own.
    setup = ('<p><i>Problems 14, 15 and 16 involve Mrs. Reed\'s English assignment.</i>\n</p><p>A Novel Assignment\n</p>'
             '<p>The students in Mrs. Reed\'s English class are reading the same 760-page novel. Three friends, Alice, Bob '
             'and Chandra, are in the class. Alice reads a page in 20 seconds, Bob reads a page in 45 seconds and Chandra '
             'reads a page in 30 seconds.\n</p>')
    for n in (14, 15, 16):
        put('2006_AMC_8', n, setup + by_num('2006_AMC_8')[n]['html'])


def test_meta(t):
    m = re.match(r'(\d{4})_(Fall_)?AMC_(10|8)([ABP]?)$', t)
    year, fall, level, ab = int(m.group(1)), bool(m.group(2)), m.group(3), m.group(4)
    label = f"{year}{' Fall' if fall else ''} AMC {level}{ab}"
    # Sort key: newer first; within a year Fall > Spring, B > A (B is given later)
    order = year * 10 + (5 if fall else 0) + {'': 0, 'P': 0, 'A': 1, 'B': 2}[ab]
    short = f"{year}{'F' if fall else ''}{ab or ''}"
    return year, label, order, short

def main():
    raw = json.load(open(D(f'raw/{KEY}_data.json')))
    dump_images = save_dump_images(raw.get('images', {}))
    fix_shared_setups(raw['tests'])
    problems = []
    for t, v in raw['tests'].items():
        year, label, order, short = test_meta(t)
        fix = ANSWER_FIX.get(t)
        for p in v['problems']:
            n = p['num']
            ans = fix[n - 1] if fix else p['answer']
            pid = f"{short}-{n:02d}"
            html = fix_images(pid, p['html'], dump_images)
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
    json.dump(problems, open(D('problems.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(problems), 'problems from', len(raw['tests']), 'tests')

main()
