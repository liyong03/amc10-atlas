/* Fetch every AMC 10 (or AMC 8) test from the AoPS wiki and download <contest>_data.json.
   AoPS sits behind Cloudflare, so this runs in a normal browser tab: open
   https://artofproblemsolving.com/wiki/index.php?title=AMC_10_Problems_and_Solutions
   (or AMC_8_Problems_and_Solutions), paste this into the DevTools console, wait a few minutes,
   then move the downloaded file into data/<contest>/raw/ and run scripts/build_problems.py <contest>.
   Images uploaded to the wiki (/wiki/images/...) can't be hotlinked, so they are downloaded
   here too and saved inside the JSON as data: URLs ("images", keyed by their wiki URL). */
(async () => {
  const CONTEST = location.href.includes('AMC_8_') ? 'AMC_8' : 'AMC_10';
  const MIN_YEAR = CONTEST === 'AMC_8' ? 1999 : 2000;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // Cloudflare answers bursts with a challenge page, so retry slowly.
  async function get(url) {
    for (let i = 0; i < 6; i++) {
      const r = await fetch(url); const t = await r.text();
      if (r.ok && !t.startsWith('<!DOCTYPE')) return t;
      await sleep(5000 * (i + 1));
    }
    throw new Error('failed ' + url);
  }
  async function dataUrl(url) {
    for (let i = 0; i < 4; i++) {
      const r = await fetch(url);
      const type = r.headers.get('content-type') || '';
      if (r.ok && type.startsWith('image/')) {
        const b = await r.blob();
        return await new Promise(res => { const f = new FileReader(); f.onload = () => res(f.result); f.readAsDataURL(b); });
      }
      await sleep(4000 * (i + 1));
    }
    return null;
  }

  function parse(html, ak) {
    const answers = (ak.match(/^#\s*([A-E])/gm) || []).map(s => s.replace(/[#\s]/g, ''));
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const root = doc.querySelector('.mw-parser-output') || doc.body;
    const out = []; let cur = null;
    for (const node of [...root.childNodes]) {
      if (node.nodeType === 1 && node.tagName === 'H2') {
        const m = node.textContent.match(/Problem\s*(\d+)/i);
        cur = m ? { num: +m[1], nodes: [] } : null; if (cur) out.push(cur); continue;
      }
      if (cur && node.nodeType === 1 && node.matches('div.toc, table')) continue;
      if (cur) cur.nodes.push(node);
    }
    return out.map(p => {
      const box = doc.createElement('div');
      p.nodes.forEach(n => box.appendChild(n.cloneNode(true)));
      // Drop the "Solution" link, but never a paragraph that also holds a diagram.
      box.querySelectorAll('a').forEach(a => { if (/^\s*Solutions?\s*$/i.test(a.textContent)) a.remove(); });
      box.querySelectorAll('p, div').forEach(el => { if (!el.textContent.trim() && !el.querySelector('img')) el.remove(); });
      const imgs = [];
      box.querySelectorAll('img').forEach(img => {
        const alt = img.getAttribute('alt') || ''; const src = img.getAttribute('src') || '';
        const isDiagram = /^\s*\[asy\]/i.test(alt) || img.classList.contains('mw-file-element') || !/latex\.artofproblemsolving\.com/.test(src);
        if (isDiagram) {
          const abs = src.startsWith('//') ? 'https:' + src : (src.startsWith('/') ? 'https://artofproblemsolving.com' + src : src);
          img.setAttribute('src', abs); imgs.push(abs);
          img.removeAttribute('srcset'); img.setAttribute('loading', 'lazy'); img.className = 'diagram'; img.setAttribute('alt', 'diagram');
        } else {
          img.replaceWith(doc.createTextNode(alt)); // LaTeX image -> its source, rendered by MathJax
        }
      });
      box.querySelectorAll('a').forEach(a => a.replaceWith(...a.childNodes));
      box.querySelectorAll('[style]').forEach(e => e.removeAttribute('style'));
      const text = box.textContent.replace(/\s+/g, ' ').trim() + (imgs.length ? ' [DIAGRAM]' : '');
      return { num: p.num, answer: answers[p.num - 1] || null, html: box.innerHTML.trim(), text, diagrams: imgs.length, imgs };
    });
  }

  const re = new RegExp(`title=(\\d{4}).*${CONTEST}$`);
  const tests = [...new Set([...document.querySelectorAll('#mw-content-text a')]
    .map(a => decodeURIComponent((a.getAttribute('href') || '').split('title=')[1] || ''))
    .filter(t => re.test('title=' + t) && +t.slice(0, 4) >= MIN_YEAR))];
  const all = {}, images = {};
  for (const t of tests) {
    const html = JSON.parse(await get(`/wiki/api.php?action=parse&page=${t}_Problems&format=json&prop=text&redirects=1`)).parse.text['*'];
    await sleep(1500);
    const wikitext = await get(`/wiki/index.php?title=${t}_Problems&action=raw`); await sleep(1500);
    const ak = await get(`/wiki/index.php?title=${t}_Answer_Key&action=raw`); await sleep(1500);
    const problems = parse(html, ak);
    for (const p of problems) {
      for (const u of p.imgs) {
        if (!/latex\.artofproblemsolving\.com/.test(u) && !(u in images)) { images[u] = await dataUrl(u); await sleep(800); }
      }
      delete p.imgs;
    }
    all[t] = { problems, wikitext, answerKeyRaw: ak };
    console.log('fetched', t, problems.length);
    window.__progress = t;
  }
  const s = JSON.stringify({ source: location.href, fetched: new Date().toISOString(), tests: all, images });
  window.__done = { tests: Object.keys(all).length, problems: Object.values(all).reduce((n, v) => n + v.problems.length, 0),
    images: Object.keys(images).length, failedImages: Object.keys(images).filter(k => !images[k]).length, bytes: s.length };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([s], { type: 'application/json' }));
  a.download = CONTEST.toLowerCase().replace('_', '') + '_data.json'; document.body.appendChild(a); a.click(); a.remove();
})();
