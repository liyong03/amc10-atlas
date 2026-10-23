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


# Start of an answer label inside math: \textbf{(A)…, \mathrm{(A)…, \text{(A) …, (\textbf{A}), (A)
CHOICE_LABEL = re.compile(r'\\(?:textbf|mathrm|text|textrm|mathbf)\s*\{\s*\{?\s*\(\s*([A-E])\s*\)'
                          r'|\(\s*\\(?:textbf|mathrm|text|mathbf)\s*\{\s*([A-E])\s*\}\s*\)'
                          r'|(?<![\w}])\(\s*([A-E])\s*\)')
INLINE_MATH = re.compile(r'(?<!\\)\$((?:\\.|[^$\\])+)\$|\\\[(.*?)\\\]|\\\((.*?)\\\)', re.S)
CHOICE_GAP = re.compile(r'(?:\s|~|\\[ ,:;!]|\\q?quad\b|\\hspace\*?\{[^{}]*\}|\\\\)+$')


def balanced(s):
    depth = 0
    for i, ch in enumerate(s):
        if ch in '{}' and (i == 0 or s[i - 1] != '\\'):
            depth += 1 if ch == '{' else -1
            if depth < 0:
                return False
    return depth == 0


TEXT_CMD = re.compile(r'\\(text|textrm|textbf|textit|mbox)\s*\{([^{}]*)\}')
SPACING = re.compile(r'^(?:\s|~|\\[ ,:;!]|\\q?quad\b|\\noindent\b)*$')


def demath(inner):
    """Math whose words are in \\text{...} can't wrap. If it holds a long sentence, rewrite
    '\\textbf{(C)}\\ \\text{If Lewis got ...}' as '<b>(C)</b> If Lewis got ...' with any real
    math left as small $...$ pieces. Returns None when not worth it or not safe."""
    texts = list(TEXT_CMD.finditer(inner))
    if not texts or max(len(t.group(2)) for t in texts) < 20:
        return None
    out, pos = [], 0
    for t in texts + [None]:
        chunk = inner[pos:t.start() if t else len(inner)]
        if chunk.strip():
            if not balanced(chunk):
                return None
            out.append(' ' if SPACING.match(chunk) else f'${chunk.strip()}$')
        elif chunk:
            out.append(' ')
        if t:
            kind, body = t.group(1), t.group(2)
            out.append(f'<b>{body}</b>' if kind == 'textbf' else f'<i>{body}</i>' if kind == 'textit' else body)
            pos = t.end()
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def demath_all(h):
    def repl(m):
        inner = next(g for g in m.groups() if g is not None)
        d = demath(inner)
        return f'<span class="prose">{d}</span>' if d else m.group(0)
    return INLINE_MATH.sub(repl, h)


def split_choices(h):
    """One long '(A) 4 \\qquad (B) 5 …' formula can't wrap on a phone; turn it into five
    separate formulas in a wrapping row. Leaves the problem untouched if anything looks odd."""
    for m in INLINE_MATH.finditer(h):
        inner = next(g for g in m.groups() if g is not None)
        if '\\begin' in inner:
            continue
        labels = list(CHOICE_LABEL.finditer(inner))
        letters = ''.join(next(g for g in l.groups() if g) for l in labels)
        # a run of 2+ consecutive choices: "ABCDE", or "ABCD" + "E" in the next formula, etc.
        if len(letters) < 2 or letters not in 'ABCDE':
            continue
        if not SPACING.match(CHOICE_GAP.sub('', inner[:labels[0].start()])):
            continue
        starts = [l.start() for l in labels] + [len(inner)]
        pieces = [CHOICE_GAP.sub('', inner[a:b]).strip() for a, b in zip(starts, starts[1:])]
        if not all(balanced(p) for p in pieces):
            continue
        row = ''.join(choice_span(p) for p in pieces)
        h = h[:m.start()] + f'<span class="choices">{row}</span>' + h[m.end():]
        return split_choices(h)  # the rest of the choices may be in a later formula
    return h


def choice_span(piece):
    d = demath(piece)
    return f'<span class="choice long">{d}</span>' if d else f'<span class="choice">${piece}$</span>'


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
    return demath_all(split_choices(ungroup_numbers(h)))


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
