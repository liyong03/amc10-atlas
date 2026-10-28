"""Build the site's data.json (what the GitHub Pages site loads) from problems + classification.
Usage: python3 scripts/build_site.py [amc10|amc8]   -> docs/data.json or docs/amc8/data.json"""
import json, os, re, shutil
from contest import KEY, C, CONTESTS, ROOT, D, DOCS


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
LEAD_SPACING = re.compile(r'^(?:\s|~|\\[ ,:;!]|\\q?quad\b)+')
TRAIL_SPACING = re.compile(r'(?:\s|~|(?<!\\)\\[ ,:;!]|\\q?quad\b)+$')


def math_piece(chunk):
    """'\\mathrm{(B)}\\ ' -> '$\\mathrm{(B)}$ ': TeX spacing at the ends becomes one plain space
    (plain spaces, which math ignores, are just dropped). A plain strip() would leave
    '\\mathrm{(B)}\\', whose backslash escapes the closing $."""
    lead, trail = LEAD_SPACING.search(chunk), TRAIL_SPACING.search(chunk)
    core = chunk[lead.end() if lead else 0:trail.start() if trail else len(chunk)]
    space = lambda m: ' ' if m and m.group(0).strip() else ''
    return space(lead) + f'${core}$' + space(trail)


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
            out.append(' ' if SPACING.match(chunk) else math_piece(chunk))
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
    raw = json.load(open(D(f'raw/{KEY}_data.json')))
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


# A command with its {arguments}, inline math, or an HTML entity (&amp;): left alone when converting a table
TEX_TOKEN = re.compile(r'(\\[a-zA-Z]+\*?(?:\[\w\]|\{[^{}]*\})*|\$[^$]*\$|&#?\w+;)')
WORDS = re.compile(r"[ ]*[A-Za-z][A-Za-z']+(?:[ ]+[A-Za-z0-9][A-Za-z0-9']*)*[ ]*")


def tabular_to_array(t):
    """MathJax has no tabular. array draws the same table but in math mode, so words in the
    cells ("Average height", "11 meters") are wrapped in \\text{} to keep their spacing."""
    t = t.replace('\\multicolumn{4}{c}{}\\\\', '')
    parts = TEX_TOKEN.split(t)
    for i in range(0, len(parts), 2):  # the text between commands
        parts[i] = WORDS.sub(lambda m: f'\\text{{{m.group(0)}}}', parts[i])
    for i in range(1, len(parts), 2):  # $x$ inside a cell is already math
        if parts[i].startswith('$') and len(parts[i]) > 1:
            parts[i] = parts[i][1:-1]
    t = ''.join(parts)
    return re.sub(r'\\begin\{tabular\}(\[\w\])?', r'\\begin{array}', t).replace('\\end{tabular}', '\\end{array}')


def clean_html(h):
    h = re.sub(r'<(script|iframe|style)\b.*?</\1>', '', h, flags=re.S | re.I)
    h = re.sub(r'\son\w+="[^"]*"', '', h)
    h = re.sub(r'<img ', '<img referrerpolicy="no-referrer" ', h)
    # Wiki lines that start with a space become <pre>, which can't wrap on a phone; make them plain lines.
    h = re.sub(r'<pre>(.*?)</pre>', lambda m: '<p>' + '<br>'.join(x.strip() for x in m.group(1).strip().split('\n') if x.strip()) + '</p>', h, flags=re.S)
    h = re.sub(r'\\begin\{tabular\}.*?\\end\{tabular\}', lambda m: tabular_to_array(m.group(0)), h, flags=re.S)
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
    tax = json.load(open(D('taxonomy.json')))
    problems = json.load(open(D('problems.json')))
    # Only latex.artofproblemsolving.com (asy/LaTeX renders) allows hotlinking; anything else must be local.
    for p in problems:
        for src in re.findall(r'<img [^>]*src="([^"]+)"', p['html']):
            if not (src.startswith('img/') or src.startswith('https://latex.artofproblemsolving.com/')):
                raise SystemExit(f"{p['id']}: image {src} can't be hotlinked; save it to data/{KEY}/raw/images/{p['id']}.<ext>")
    os.makedirs(DOCS('img'), exist_ok=True)
    for f in os.listdir(D('raw/images')):
        shutil.copyfile(D('raw/images', f), DOCS('img', f))
    cls = json.load(open(D('classification.json')))
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
    # Links to every contest's atlas, relative to this one
    here = os.path.join(ROOT, C['docs'])
    contests = [{'name': c['name'], 'href': os.path.relpath(os.path.join(ROOT, c['docs']), here) + '/', 'current': c is C}
                for c in CONTESTS.values()]
    os.makedirs(DOCS(), exist_ok=True)
    json.dump({'contest': C['name'], 'contests': contests, 'taxonomy': tax, 'tests': tests, 'problems': out},
              open(DOCS('data.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f"wrote {C['docs']}/data.json:", len(out), 'problems,', os.path.getsize(DOCS('data.json')) // 1024, 'KB')
    if KEY != 'amc10':
        write_index()


def write_index():
    """Every contest's page is docs/index.html with its own name, pointing at the shared app.js/style.css."""
    h = open(os.path.join(ROOT, 'docs/index.html')).read()
    up = os.path.relpath(os.path.join(ROOT, 'docs'), DOCS()) + '/'
    for old, new in [('<html lang="en">', f'<html lang="en" data-contest="{KEY}">'),
                     ('href="style.css"', f'href="{up}style.css"'), ('src="app.js"', f'src="{up}app.js"'),
                     ('AMC_10_Problems_and_Solutions', f"{C['wiki']}_Problems_and_Solutions"),
                     ('AMC&nbsp;10', C['name'].replace(' ', '&nbsp;')), ('AMC 10', C['name']),
                     ('since 2000', f"since {C['first_year']}")]:
        assert old in h, old
        h = h.replace(old, new)
    h = h.replace('<!doctype html>\n', '<!doctype html>\n<!-- generated by scripts/build_site.py from docs/index.html -->\n', 1)
    open(DOCS('index.html'), 'w').write(h)


if __name__ == '__main__':
    main()
