/* AMC 10 Problem Atlas — hash-routed static app.
   Routes:  #/            home (all topics)
            #/c/<cat>     one topic, newest → oldest
            #/p/<id>      single problem
            #/s/<query>   search
            #/review      problems starred for review */
(function () {
  'use strict';

  // .lg parts are hidden on phones so a card's buttons fit on one row
  const ANSWER_LABEL = '<span class="lg">Show a</span><span class="sm">A</span>nswer';
  const SOLVED_LABEL = '✓<span class="lg">&nbsp;Solved</span>';
  const UNSOLVED_LABEL = '<span class="lg">Mark solved</span><span class="sm" aria-label="Mark solved">✓</span>';
  const PAGE = 30; // problems rendered per "page" (MathJax is the slow part)
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };
  const state = {
    solved: new Set(store.get('amc-solved', [])),
    starred: new Set(store.get('amc-starred', [])),
    prefs: Object.assign({ diff: 'all', secondary: false, hideSolved: false }, store.get('amc-prefs', {})),
  };
  let DB, CATS = {}, AREAS = [], BY_CAT = {}, BY_SEC = {}, BY_ID = {}, YEARS = [];

  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const DIFF = n => n <= 10 ? { k: 'easy', label: 'Easy · 1–10', color: '#2f7d4f' }
    : n <= 20 ? { k: 'mid', label: 'Medium · 11–20', color: '#b9852a' }
    : { k: 'hard', label: 'Hard · 21–25', color: '#c8412b' };

  // ---------- data ----------
  fetch('data.json').then(r => r.json()).then(init).catch(err => {
    $('#main').innerHTML = `<p class="empty">Could not load data.json (${esc(err.message)}). If you opened the file directly, serve the folder with a web server instead.</p>`;
  });

  function init(data) {
    DB = data;
    AREAS = data.taxonomy.areas;
    data.taxonomy.categories.forEach(c => { CATS[c.id] = c; BY_CAT[c.id] = []; BY_SEC[c.id] = []; });
    data.problems.forEach(p => {
      BY_ID[p.id] = p;
      (BY_CAT[p.cat] = BY_CAT[p.cat] || []).push(p);
      p.sec.forEach(s => (BY_SEC[s] = BY_SEC[s] || []).push(p));
      p._text = (p.html.replace(/<[^>]+>/g, ' ') + ' ' + p.label + ' ' + p.idea).toLowerCase();
    });
    YEARS = [...new Set(data.problems.map(p => p.year))].sort((a, b) => a - b);
    renderSidebar();
    updateProgress();
    window.addEventListener('hashchange', route);
    route();
  }

  // ---------- sidebar ----------
  function renderSidebar() {
    const collapsed = new Set(store.get('amc-collapsed', []));
    $('#sidebar').innerHTML =
      `<div class="side-progress"><span id="sideProgressText"></span><span class="progress-bar"><span id="sideProgressFill"></span></span></div>` +
      `<div class="side-area"><ul><li><a href="#/" data-cat="__home"><span>All topics</span><span class="n">${DB.problems.length}</span></a></li>` +
      `<li><a href="#/review" data-cat="__review"><span>★ Review list</span><span class="n" id="starCount">${state.starred.size}</span></a></li></ul></div>` +
      AREAS.map(a => {
        const cats = catsOf(a.id);
        return `<div class="side-area${collapsed.has(a.id) ? ' collapsed' : ''}" data-area="${a.id}">
          <h3>${esc(a.name)}</h3><ul>${cats.map(c => `<li><a href="#/c/${c.id}" data-cat="${c.id}">
            <span>${esc(c.name)}</span><span class="n">${doneCount(c.id) === BY_CAT[c.id].length ? '<span class="done-tick">✓</span> ' : ''}${BY_CAT[c.id].length}</span></a></li>`).join('')}</ul></div>`;
      }).join('');
    $('#sidebar').querySelectorAll('.side-area h3').forEach(h => h.addEventListener('click', () => {
      const box = h.parentElement; box.classList.toggle('collapsed');
      store.set('amc-collapsed', [...document.querySelectorAll('.side-area.collapsed')].map(e => e.dataset.area));
    }));
  }
  const catsOf = area => DB.taxonomy.categories.filter(c => c.area === area && BY_CAT[c.id].length);
  const doneCount = cat => BY_CAT[cat].filter(p => state.solved.has(p.id)).length;

  function markActive(cat) {
    document.querySelectorAll('.sidebar a').forEach(a => a.classList.toggle('active', a.dataset.cat === cat));
    document.body.classList.remove('nav-open');
  }

  function updateProgress() {
    const n = state.solved.size, total = DB.problems.length;
    $('#progressText').textContent = `${n} / ${total} solved`;
    $('#progressFill').style.width = (100 * n / total) + '%';
    const st = $('#sideProgressText'); if (st) st.textContent = `${n} / ${total} solved`;
    const sf = $('#sideProgressFill'); if (sf) sf.style.width = (100 * n / total) + '%';
    const sc = $('#starCount'); if (sc) sc.textContent = state.starred.size;
  }

  // ---------- routing ----------
  function route() {
    const h = decodeURIComponent(location.hash.replace(/^#\/?/, ''));
    const [kind, ...rest] = h.split('/');
    const arg = rest.join('/');
    window.scrollTo(0, 0);
    if (kind === 'c' && CATS[arg]) return renderCategory(arg);
    if (kind === 'p' && BY_ID[arg]) return renderSingle(arg);
    if (kind === 's') { $('#search').value = arg; return renderSearch(arg); }
    if (kind === 'review') return renderList('__review', 'Review list', 'Problems you starred to come back to.', DB.problems.filter(p => state.starred.has(p.id)));
    renderHome();
  }

  // ---------- home ----------
  function renderHome() {
    markActive('__home');
    const total = DB.problems.length;
    const usedCats = DB.taxonomy.categories.filter(c => BY_CAT[c.id].length).length;
    $('#main').innerHTML = `
      <section class="hero">
        <div class="crumb">${DB.tests.length} contests · ${YEARS[0]}–${YEARS[YEARS.length - 1]}</div>
        <h1>Every AMC&nbsp;10 problem,<br><span class="scribble">sorted by idea.</span></h1>
        <p>Pick a topic and work through every past problem of that kind, newest contest first.
           Check your answer, open the AoPS solutions, and mark what you've solved. Progress is saved in this browser.</p>
      </section>
      <div class="stats">
        <div><b>${total}</b>problems</div>
        <div><b>${usedCats}</b>topics</div>
        <div><b>${state.solved.size}</b>solved by you</div>
        <div><b>${state.starred.size}</b>starred</div>
      </div>
      ${AREAS.map((a, ai) => {
        const cats = catsOf(a.id).sort((x, y) => BY_CAT[y.id].length - BY_CAT[x.id].length);
        const n = cats.reduce((s, c) => s + BY_CAT[c.id].length, 0);
        return `<section class="area-block"><h2>${esc(a.name)} <small>${n} problems · ${cats.length} topics</small></h2>
          <div class="tiles">${cats.map((c, i) => tile(c, ai * 4 + i)).join('')}</div></section>`;
      }).join('')}`;
  }

  function tile(c, i) {
    const list = BY_CAT[c.id];
    const perYear = YEARS.map(y => list.filter(p => p.year === y).length);
    const max = Math.max(...perYear, 1);
    const done = doneCount(c.id);
    return `<a class="tile" href="#/c/${c.id}" style="animation-delay:${Math.min(i * 18, 600)}ms" title="${esc(c.desc)}">
      <h4>${esc(c.name)}</h4>
      <div class="meta"><span>${list.length} problems</span><span>${done ? done + ' solved' : ''}</span></div>
      <div class="yearstrip" title="Problems per year, ${YEARS[0]} → ${YEARS[YEARS.length - 1]}">${perYear.map((n, k) =>
        n ? `<i style="height:${30 + 70 * n / max}%" title="${YEARS[k]}: ${n}"></i>` : `<i class="z" title="${YEARS[k]}: 0"></i>`).join('')}</div>
      <div class="mini"><span style="width:${100 * done / list.length}%"></span></div>
    </a>`;
  }

  // ---------- topic page ----------
  function renderCategory(cat) {
    const c = CATS[cat];
    const area = AREAS.find(a => a.id === c.area);
    let list = BY_CAT[cat].slice();
    if (state.prefs.secondary) list = list.concat(BY_SEC[cat].filter(p => p.cat !== cat));
    renderList(cat, c.name, c.desc, list, `<a href="#/">${esc(area.name)}</a>`, true);
  }

  function renderList(key, title, desc, list, crumb = '', isCat = false) {
    markActive(key);
    list = list.slice().sort((a, b) => b.order - a.order || a.num - b.num);
    const pr = state.prefs;
    const filtered = list.filter(p => (pr.diff === 'all' || DIFF(p.num).k === pr.diff) && !(pr.hideSolved && state.solved.has(p.id)));
    $('#main').innerHTML = `
      <div class="cat-head">
        <div class="crumb">${crumb || 'Collection'}</div>
        <h1>${esc(title)}</h1>
        <p class="desc">${esc(desc)}</p>
      </div>
      <div class="toolbar">
        <span class="seg" id="diffSeg">${[['all', 'All'], ['easy', '1–10'], ['mid', '11–20'], ['hard', '21–25']]
          .map(([k, l]) => `<button data-k="${k}" class="${pr.diff === k ? 'on' : ''}">${l}</button>`).join('')}</span>
        ${isCat ? `<label><input type="checkbox" id="secBox" ${pr.secondary ? 'checked' : ''}> include related<span class="lg">&nbsp;(secondary topic)</span></label>` : ''}
        <label><input type="checkbox" id="hideBox" ${pr.hideSolved ? 'checked' : ''}> hide solved</label>
        <span class="count">${filtered.length} of ${list.length} shown</span>
      </div>
      <div id="plist"></div>`;
    $('#diffSeg').addEventListener('click', e => { const k = e.target.dataset.k; if (k) { pr.diff = k; savePrefs(); route(); } });
    const sb = $('#secBox'); if (sb) sb.addEventListener('change', () => { pr.secondary = sb.checked; savePrefs(); route(); });
    $('#hideBox').addEventListener('change', e => { pr.hideSolved = e.target.checked; savePrefs(); route(); });
    paginate($('#plist'), filtered, isCat ? key : null);
  }
  const savePrefs = () => store.set('amc-prefs', state.prefs);

  function paginate(box, list, ctxCat) {
    if (!list.length) { box.innerHTML = '<p class="empty">Nothing here yet.</p>'; return; }
    let shown = 0;
    const more = () => {
      const chunk = list.slice(shown, shown + PAGE);
      const frag = document.createElement('div');
      frag.innerHTML = chunk.map(p => card(p, ctxCat)).join('');
      const old = box.querySelector('.more'); if (old) old.remove();
      box.append(...frag.children);
      shown += chunk.length;
      typeset(box);
      if (shown < list.length) {
        const b = document.createElement('button');
        b.className = 'btn more'; b.textContent = `Show ${Math.min(PAGE, list.length - shown)} more (${list.length - shown} left)`;
        b.onclick = more; box.append(b);
      }
    };
    more();
  }

  function card(p, ctxCat) {
    const d = DIFF(p.num);
    const tags = [p.cat].concat(p.sec).map(t => CATS[t]
      ? `<a class="tag${t === p.cat ? ' prim' : ''}" href="#/c/${t}" title="${t === p.cat ? 'Main topic' : 'Also involves'}">${esc(CATS[t].name)}</a>` : '').join('');
    return `<article class="problem${state.solved.has(p.id) ? ' solved' : ''}" data-id="${p.id}" style="--diff:${d.color}">
      <div class="p-head">
        <a class="p-src" href="#/p/${p.id}">${esc(p.label)} · Problem ${p.num}</a>
        <span class="diff" title="${d.label}">${d.label.split(' · ')[0]}</span>
        ${ctxCat && p.cat !== ctxCat ? '<span class="tag">related</span>' : ''}
      </div>
      <div class="p-body">${p.html}</div>
      ${p.idea ? `<div class="idea"><b>KEY IDEA</b>${esc(p.idea)}</div>` : ''}
      <div class="p-actions">
        ${p.idea ? '<button class="btn hint">Hint</button>' : ''}
        <button class="btn answer" data-a="${p.answer}">${ANSWER_LABEL}</button>
        <a class="btn" href="${esc(p.url)}" target="_blank" rel="noopener">Solution<span class="lg">s</span>&nbsp;↗</a>
        <button class="btn solve${state.solved.has(p.id) ? ' on' : ''}" title="Mark solved">${state.solved.has(p.id) ? SOLVED_LABEL : UNSOLVED_LABEL}</button>
        <button class="btn star${state.starred.has(p.id) ? ' on' : ''}" title="Add to review list">★</button>
        <span class="tags">${tags}</span>
      </div>
    </article>`;
  }

  // Event delegation for card buttons
  document.addEventListener('click', e => {
    const btn = e.target.closest('.problem .btn'); if (!btn) return;
    const art = btn.closest('.problem'), id = art.dataset.id;
    if (btn.classList.contains('answer')) {
      const shown = btn.classList.toggle('shown');
      btn.innerHTML = shown ? `<span class="lg">Answer:&nbsp;</span>(${btn.dataset.a})` : ANSWER_LABEL;
    } else if (btn.classList.contains('hint')) {
      art.querySelector('.idea').classList.toggle('shown');
    } else if (btn.classList.contains('solve')) {
      const on = !state.solved.has(id);
      on ? state.solved.add(id) : state.solved.delete(id);
      store.set('amc-solved', [...state.solved]);
      btn.classList.toggle('on', on); btn.innerHTML = on ? SOLVED_LABEL : UNSOLVED_LABEL;
      art.classList.toggle('solved', on);
      renderSidebar(); updateProgress(); markActive(currentKey());
    } else if (btn.classList.contains('star')) {
      const on = !state.starred.has(id);
      on ? state.starred.add(id) : state.starred.delete(id);
      store.set('amc-starred', [...state.starred]);
      btn.classList.toggle('on', on); updateProgress();
    }
  });
  const currentKey = () => {
    const h = location.hash.replace(/^#\/?/, '');
    if (h.startsWith('c/')) return h.slice(2);
    if (h.startsWith('review')) return '__review';
    return h ? '' : '__home';
  };

  // ---------- single problem ----------
  function renderSingle(id) {
    const p = BY_ID[id], c = CATS[p.cat];
    markActive(p.cat);
    const siblings = BY_CAT[p.cat];
    const i = siblings.indexOf(p);
    const nav = (q, l) => q ? `<a class="btn" href="#/p/${q.id}">${l}</a>` : '';
    $('#main').innerHTML = `
      <div class="cat-head"><div class="crumb"><a href="#/c/${c.id}">${esc(c.name)}</a> · ${i + 1} of ${siblings.length}</div></div>
      <div id="plist">${card(p)}</div>
      <div class="p-actions">${nav(siblings[i - 1], '← Newer')} ${nav(siblings[i + 1], 'Older →')}
        <a class="btn" href="#/c/${c.id}">All ${esc(c.name)}</a></div>`;
    typeset($('#plist'));
  }

  // ---------- search ----------
  let searchTimer;
  $('#search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    searchTimer = setTimeout(() => { location.hash = q ? '#/s/' + encodeURIComponent(q) : '#/'; }, 250);
  });
  function renderSearch(q) {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    const catHits = DB.taxonomy.categories.filter(c => BY_CAT[c.id].length && terms.every(t => (c.name + ' ' + c.desc).toLowerCase().includes(t)));
    // "2019 10A 12" style lookups
    const hits = DB.problems.filter(p => terms.every(t => p._text.includes(t) || p.id.toLowerCase().includes(t)));
    renderList('', `Search: “${q}”`, catHits.length ? '' : 'Searching problem text, contest names and key ideas.', hits, 'Search');
    if (catHits.length) {
      $('.desc').innerHTML = 'Matching topics: ' + catHits.map(c => `<a href="#/c/${c.id}">${esc(c.name)}</a>`).join(', ');
    }
  }

  // ---------- MathJax ----------
  function typeset(el) {
    const go = () => window.MathJax.typesetPromise([el]).catch(err => console.warn('MathJax', err));
    if (window.MathJax && window.MathJax.typesetPromise) go();
    else { const t = setInterval(() => { if (window.MathJax && window.MathJax.typesetPromise) { clearInterval(t); go(); } }, 100); }
  }

  // ---------- chrome ----------
  $('#menuBtn').addEventListener('click', () => document.body.classList.toggle('nav-open'));
  $('#scrim').addEventListener('click', () => document.body.classList.remove('nav-open'));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') document.body.classList.remove('nav-open', 'search-open'); });
  $('#searchBtn').addEventListener('click', () => {
    const open = document.body.classList.toggle('search-open');
    if (open) $('#search').focus();
  });
  if ($('#search').value) document.body.classList.add('search-open');
  $('#themeBtn').addEventListener('click', () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('amc-theme', root.dataset.theme); } catch (e) {}
  });
})();
