"""Build docs/data.json (what the GitHub Pages site loads) from problems + classification."""
import json, os, re, shutil

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(ROOT, *a)


# A comma-grouped number such as 9,901 or 16{,}384. Not when it follows [ ( \{ a comma, a digit
# or a capital letter, or is followed by another comma: that's an interval, a set/list, or a
# digit puzzle like 121,6T5,100 rather than one number.
GROUPED_NUMBER = re.compile(r'(?<![\d.,\[(A-Z])(?<!\\\{)\d{1,3}(?:(?:\{,\}|,)\d{3})+(?![\d,A-Z])')
MATH = re.compile(r'\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\)|\\begin\{(\w+\*?)\}.*?\\end\{\1\}', re.S)


def ungroup_numbers(h):
    """Write numbers in math as 9901 rather than 9,901, so expressions read like equations."""
    return MATH.sub(lambda m: GROUPED_NUMBER.sub(lambda n: re.sub(r'\{,\}|,', '', n.group(0)), m.group(0)), h)


def text_dollar_problems():
    """(test, num) of problems whose wiki source has a plain-text "$" (e.g. "worth &#36;300")
    outside math tags. In the HTML those look like math delimiters, so they must be escaped."""
    raw = json.load(open(P('data/raw/amc10_data.json')))
    found = set()
    for t, v in raw['tests'].items():
        secs = re.split(r'^==\s*Problem\s*(\d+)\s*==', v['wikitext'], flags=re.M)
        for i in range(1, len(secs), 2):
            body = re.sub(r'<(i?math)>.*?</\1>|<asy>.*?</asy>', '', secs[i + 1], flags=re.S)
            if re.search(r'(?<!\\)\$|&#36;', body):
                found.add((t, int(secs[i])))
    return found


def escape_text_dollars(h):
    """'$300 and' -> '\\$300 and' (only used on problems from text_dollar_problems)."""
    return re.sub(r'(?<![\\$])\$(\d[\d,.]*)(?![\d$])', r'\\$\1', h)


def clean_html(h):
    h = re.sub(r'<(script|iframe|style)\b.*?</\1>', '', h, flags=re.S | re.I)
    h = re.sub(r'\son\w+="[^"]*"', '', h)
    h = re.sub(r'<img ', '<img referrerpolicy="no-referrer" ', h)
    # MathJax has no tabular; the AMC tables only hold numbers, so array renders them the same.
    h = re.sub(r'\\begin\{tabular\}(\[\w\])?', r'\\begin{array}', h)
    h = h.replace('\\end{tabular}', '\\end{array}').replace('\\multicolumn{4}{c}{}\\\\', '')
    # Some old AoPS pages split "\$7" across two math tags, leaving "\$$7" / "\$ $14"
    # (2003 10B #2, #4, #12); join them back into one "\$7".
    h = re.sub(r'\\\$\s*\$', r'\\$', h)
    # No problem uses $$...$$ display math, so any "$$" is one of two accidents MathJax would
    # read as display math:
    #  - two touching formulas "$\triangle$$EBD$" -> join them: "$\triangle EBD$"
    h = re.sub(r'(?<=[^\s\\$])\$\$(?=[^\s$])', ' ', h)
    #  - a plain-text "$" before a formula, "five for $$2$" -> "five for $\$2$"
    h = re.sub(r'(?<=\s)\$\$([^$]+?)\$(?!\$)', r'$\\$\1$', h)
    return ungroup_numbers(h)


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
    text_dollars = text_dollar_problems()
    out = []
    for p in problems:
        if (p['test'], p['num']) in text_dollars:
            p['html'] = escape_text_dollars(p['html'])
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
