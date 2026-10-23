# AMC 10 Problem Atlas

Every AMC 10 problem from 2000 to 2025 (53 contests, 1,325 problems), grouped into small topics
like "Similar Triangles" or "Remainders & Modular Arithmetic". Each topic lists its problems from the
newest contest to the oldest, with a reveal-the-answer button, a one-line hint, and a link to the
AoPS solutions page.

The site is static and lives in `docs/`, so GitHub Pages can serve it directly.

## Publish on GitHub Pages

```bash
git init && git add . && git commit -m "AMC 10 Problem Atlas"
gh repo create amc10-atlas --public --source . --push
gh api -X POST repos/{owner}/amc10-atlas/pages -f "source[branch]=main" -f "source[path]=/docs"
```

Or set it up in the GitHub UI: **Settings → Pages → Deploy from a branch → `main` / `/docs`**.

To preview on your own computer: `python3 -m http.server 8000 --directory docs`, then open http://localhost:8000.

## How the data is built

| Step | File | What it is |
|---|---|---|
| 1 | `data/raw/amc10_data.json` | Raw dump of every `*_Problems` page and answer key from the AoPS wiki, fetched through a browser because AoPS blocks command-line downloads |
| 2 | `scripts/build_problems.py` → `data/problems.json` | One record per problem: text, HTML, answer, AoPS link |
| 3 | `data/taxonomy.json` | The topic list (areas → small categories). **Edit this to add, rename or split topics** |
| 4 | `data/labels/passA/` | Classification 1: an LLM reviewer labels each problem by *what it asks* |
| 5 | `data/labels/passB/` | Classification 2: an independent LLM reviewer labels each problem by *the technique that solves it*, and writes a one-line key idea |
| 6 | `scripts/keyword_classify.py` → `data/labels/passC.json` | Classification 3: deterministic keyword rules, used as a sanity check |
| 7 | `data/labels/adjudicated/` | A third LLM reviewer settles every problem where A and B disagree, plus any marked low confidence |
| 8 | `data/overrides.json` | **Your manual fixes.** These always win |
| 9 | `scripts/merge_labels.py` → `data/classification.json` | Combines everything; prints agreement stats |
| 10 | `scripts/build_site.py` → `docs/data.json` | What the website loads |

### Changing a problem's topic

Add it to `data/overrides.json`, keyed by problem id (the id is in the problem's link on the site, e.g. `2019A-12`):

```json
{
  "2019A-12": "alg-mean-median",
  "2008B-20": {"primary": "cp-probability-dice-coins", "secondary": ["cp-conditional-probability"]}
}
```

Then rebuild:

```bash
python3 scripts/merge_labels.py && python3 scripts/build_site.py
```

Progress (solved and starred problems) is saved in the browser's localStorage, so it stays on that device.

Problems © Mathematical Association of America. Problem text, diagrams and solutions are from the
[AoPS Wiki](https://artofproblemsolving.com/wiki/index.php?title=AMC_10_Problems_and_Solutions).
