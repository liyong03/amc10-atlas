# AMC 10 & AMC 8 Problem Atlas

Every AMC 10 problem from 2000 to 2025 (53 contests, 1,325 problems) and every AMC 8 problem from
1999 to 2026 (`docs/amc8/`), grouped into small topics
like "Similar Triangles" or "Remainders & Modular Arithmetic". Each topic lists its problems from the
newest contest to the oldest, with a reveal-the-answer button, a one-line hint, and a link to the
AoPS solutions page.

The site is static and lives in `docs/` (AMC 10) and `docs/amc8/` (AMC 8), so GitHub Pages can serve
it directly. Both pages share `docs/app.js` and `docs/style.css`; `docs/amc8/index.html` is generated
from `docs/index.html` by `build_site.py`.

## Publish on GitHub Pages

```bash
git init && git add . && git commit -m "AMC 10 Problem Atlas"
gh repo create amc10-atlas --public --source . --push
gh api -X POST repos/{owner}/amc10-atlas/pages -f "source[branch]=main" -f "source[path]=/docs"
```

Or set it up in the GitHub UI: **Settings → Pages → Deploy from a branch → `main` / `/docs`**.

To preview on your own computer: `python3 -m http.server 8000 --directory docs`, then open http://localhost:8000.

## How the data is built

Each contest has its own folder, `data/amc10/` or `data/amc8/`, and every script takes the contest
as its first argument (default `amc10`), e.g. `python3 scripts/merge_labels.py amc8`. Paths below
are inside the contest's folder.

| Step | File | What it is |
|---|---|---|
| 1 | `raw/<contest>_data.json` | Raw dump of every `*_Problems` page, answer key and uploaded diagram from the AoPS wiki, fetched through a browser (`scripts/fetch_in_browser.js`) because AoPS blocks command-line downloads |
| 2 | `scripts/build_problems.py` → `problems.json` | One record per problem: text, HTML, answer, AoPS link |
| 3 | `taxonomy.json` | The topic list (areas → small categories). **Edit this to add, rename or split topics** |
| 4 | `labels/passA/` (input: `scripts/make_batches.py` → `batches/`) | Classification 1: an LLM reviewer labels each problem by *what it asks* |
| 5 | `labels/passB/` | Classification 2: an independent LLM reviewer labels each problem by *the technique that solves it*, and writes a one-line key idea |
| 6 | `scripts/keyword_classify.py` → `labels/passC.json` | Classification 3: deterministic keyword rules, used as a sanity check |
| 7 | `labels/adjudicated/` | A third LLM reviewer settles every problem where A and B disagree, plus any marked low confidence |
| 8 | `overrides.json` | **Your manual fixes.** These always win |
| 9 | `scripts/merge_labels.py` → `classification.json` | Combines everything; prints agreement stats |
| 10 | `scripts/build_site.py` → `docs/data.json` or `docs/amc8/data.json` | What the website loads |

### Changing a problem's topic

Add it to `data/amc10/overrides.json` (or `data/amc8/overrides.json`), keyed by problem id (the id is in the problem's link on the site, e.g. `2019A-12` for AMC 10 or `2019-12` for AMC 8):

```json
{
  "2019A-12": "alg-mean-median",
  "2008B-20": {"primary": "cp-probability-dice-coins", "secondary": ["cp-conditional-probability"]}
}
```

Then rebuild:

```bash
python3 scripts/merge_labels.py amc10 && python3 scripts/build_site.py amc10
python3 scripts/merge_labels.py amc8 && python3 scripts/build_site.py amc8
```

Progress (solved and starred problems) is saved in the browser's localStorage, separately for each contest, so it stays on that device.

Problems © Mathematical Association of America. Problem text, diagrams and solutions are from the
AoPS Wiki ([AMC 10](https://artofproblemsolving.com/wiki/index.php?title=AMC_10_Problems_and_Solutions),
[AMC 8](https://artofproblemsolving.com/wiki/index.php?title=AMC_8_Problems_and_Solutions)).
