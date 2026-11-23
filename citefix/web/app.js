'use strict';

/* citefix front end: streams one check from /api/review and writes the results as proof marks.
   Every string from the server or the passage goes in through textContent, never innerHTML. */

const $ = (id) => document.getElementById(id);
const ui = {
  input: $('input'), proof: $('proof'), refs: $('refs'), refList: $('ref-list'),
  run: $('run'), example: $('example'), edit: $('edit'),
  status: $('status'), progress: $('progress'), notes: $('notes'), legend: $('legend'), usage: $('usage'),
};
const narrow = window.matchMedia('(max-width: 960px)');

const ICONS = {
  check: '<path d="M4.5 10.5l3.5 3.5 7.5-8"/>',
  cross: '<path d="M6 6l8 8M14 6l-8 8"/>',
  query: '<path d="M10 3.75l6.75 12H3.25z"/><path d="M10 8.25v3.25"/><path d="M10 14v.01"/>',
  caret: '<path d="M4.5 15.5L10 5.5l5.5 10"/>',
  search: '<circle cx="8.75" cy="8.75" r="4.75"/><path d="M12.25 12.25L16.5 16.5"/>',
  external: '<path d="M8.5 4.5h-4v11h11v-4"/><path d="M11.5 3.5h5v5"/><path d="M16.5 3.5l-7 7"/>',
  copy: '<rect x="7" y="7" width="9.5" height="9.5" rx="2"/><path d="M13 7V5a1.5 1.5 0 0 0-1.5-1.5h-6A1.5 1.5 0 0 0 4 5v6a1.5 1.5 0 0 0 1.5 1.5H7"/>',
  chevron: '<path d="M7.5 5l5 5-5 5"/>',
};
const SUPPORT = {
  supported: { tone: 'ok', label: 'Supported', icon: 'check' },
  partially_supported: { tone: 'warn', label: 'Partly supported', icon: 'query' },
  not_supported: { tone: 'bad', label: 'Not supported', icon: 'cross' },
  insufficient_evidence: { tone: 'warn', label: 'Can’t tell from the abstract', icon: 'query' },
};
const REFERENCE = {
  verified: { tone: 'ok', label: 'Found', icon: 'check' },
  suspicious: { tone: 'warn', label: 'Details differ', icon: 'query' },
  not_found: { tone: 'bad', label: 'Not found', icon: 'cross' },
};
const SOURCES = { openalex: 'OpenAlex', crossref: 'Crossref', arxiv: 'arXiv', semantic_scholar: 'Semantic Scholar' };
const TONE_RANK = { ok: 0, pending: 1, warn: 2, bad: 3 };
const MARKER = /\[(\d+(?:\s*[,–-]\s*\d+)*)\]/g;
const LIST_NUMBER = /^\s*(?:\[\d+\]|\(\d+\)|\d+[.)])\s+/;

let current = null; // the check in progress or the last one

/* ---------- small helpers ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function icon(name) {
  const span = el('span', 'icon');
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return span;
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

function listOf(names) {
  return names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

function safeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null;
}

function sourceName(error) {
  const key = String(error).split(':')[0].trim();
  return SOURCES[key] || key;
}

/* Long text shows a few lines; clicking it (or Enter) shows the rest. */
function clamp(node, lines) {
  node.classList.add('clamp');
  node.style.setProperty('--lines', String(lines));
  requestAnimationFrame(() => {
    if (node.scrollHeight <= node.clientHeight + 1) return; // fits, nothing to open
    node.tabIndex = 0;
    node.setAttribute('aria-expanded', 'false');
    node.classList.add('is-clamped');
    const toggle = () => {
      const open = node.classList.toggle('is-open');
      node.setAttribute('aria-expanded', String(open));
      layoutSoon();
    };
    node.addEventListener('click', toggle);
    node.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
  });
  return node;
}

function linkButton(label, url) {
  const href = safeUrl(url);
  if (!href) return document.createTextNode('');
  const a = el('a', 'button small');
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.append(icon('external'), label);
  return a;
}

function copyButton(label, text) {
  const button = el('button', 'button small');
  button.type = 'button';
  const caption = document.createTextNode(label);
  button.append(icon('copy'), caption);
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(text);
      caption.textContent = 'Copied';
    } catch {
      caption.textContent = 'Copy failed';
    }
    setTimeout(() => { caption.textContent = label; }, 1600);
  });
  return button;
}

/* ---------- page modes ---------- */

function showEditor() {
  ui.input.hidden = false;
  ui.proof.hidden = true;
  ui.refs.hidden = true;
  ui.edit.hidden = true;
  ui.notes.hidden = true;
  ui.progress.hidden = true;
  ui.legend.hidden = false;
  ui.status.replaceChildren();
  document.querySelectorAll('.notice').forEach((n) => n.remove());
}

function showProof() {
  ui.input.hidden = true;
  ui.proof.hidden = false;
  ui.edit.hidden = false;
  ui.legend.hidden = true;
  ui.notes.hidden = false;
}

function setStatus(text, tone) {
  ui.status.className = tone ? `status is-${tone}` : 'status';
  ui.status.replaceChildren(text);
}

function showError(message) {
  const box = el('div', 'alert');
  box.setAttribute('role', 'alert');
  box.append(icon('cross'), el('span', '', message));
  ui.status.className = 'status';
  ui.status.replaceChildren(box);
  ui.progress.hidden = true;
}

function setProgress(fraction) {
  ui.progress.hidden = false;
  ui.progress.classList.toggle('is-indeterminate', fraction == null);
  ui.progress.firstElementChild.style.width = fraction == null ? '' : `${Math.round(fraction * 100)}%`;
}

/* ---------- the manuscript as a proof ---------- */

function findSentence(body, sentence, taken) {
  const wanted = sentence.trim();
  const free = (start, end) => taken.every((r) => end <= r.start || start >= r.end);
  for (let at = body.indexOf(wanted); at !== -1; at = body.indexOf(wanted, at + 1)) {
    if (free(at, at + wanted.length)) return [at, at + wanted.length];
  }
  const head = wanted.slice(0, 40); // the model sometimes changes a character late in the sentence
  const at = head.length >= 20 ? body.indexOf(head) : -1;
  if (at === -1) return null;
  const stop = body.slice(at).search(/[.!?](\s|$)/);
  const end = stop === -1 ? body.length : at + stop + 1;
  return free(at, end) ? [at, end] : null;
}

function expandRefs(spec) {
  const out = [];
  for (const part of spec.split(',')) {
    const [a, b] = part.split(/[–-]/).map((s) => parseInt(s, 10));
    if (Number.isFinite(a) && Number.isFinite(b) && b >= a && b - a < 60) {
      for (let n = a; n <= b; n += 1) out.push(n);
    } else if (Number.isFinite(a)) {
      out.push(a);
    }
  }
  return out;
}

function clauseSpan(text, index) {
  const span = el('span', 'clause is-pending');
  span.dataset.sentence = String(index);
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    if (m.index > last) span.append(text.slice(last, m.index));
    const marker = el('span', 'marker', m[0]);
    marker.dataset.refs = expandRefs(m[1]).join(',');
    span.append(marker);
    last = m.index + m[0].length;
  }
  if (last < text.length) span.append(text.slice(last));
  span.addEventListener('mouseenter', () => hot(index, true));
  span.addEventListener('mouseleave', () => hot(index, false));
  span.addEventListener('click', () => {
    const note = ui.notes.querySelector(`.note[data-sentence="${index}"]`);
    if (note) note.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });
  return span;
}

function renderProof(body, citations) {
  const ranges = [];
  for (const item of citations) {
    const at = findSentence(body, item.sentence, ranges);
    if (at) ranges.push({ start: at[0], end: at[1], index: item.index });
  }
  ranges.sort((a, b) => a.start - b.start);
  const paragraphs = [];
  const breaks = /\n\s*\n/g;
  let from = 0;
  for (let m = breaks.exec(body); m; m = breaks.exec(body)) {
    paragraphs.push([from, m.index]);
    from = m.index + m[0].length;
  }
  paragraphs.push([from, body.length]);
  ui.proof.replaceChildren();
  for (const [start, end] of paragraphs) {
    const p = el('p');
    let cursor = start;
    for (const r of ranges) {
      if (r.start < start || r.end > end) continue;
      if (r.start > cursor) p.append(body.slice(cursor, r.start));
      p.append(clauseSpan(body.slice(r.start, r.end), r.index));
      cursor = r.end;
    }
    if (cursor < end) p.append(body.slice(cursor, end));
    if (p.textContent.trim()) ui.proof.append(p);
  }
}

function clauseFor(index) {
  return ui.proof.querySelector(`.clause[data-sentence="${index}"]`);
}

function paintClause(index) {
  const clause = clauseFor(index);
  if (!clause) return;
  let worst = 'ok';
  for (const pair of current.pairs.values()) {
    if (pair.index === index && TONE_RANK[pair.tone] > TONE_RANK[worst]) worst = pair.tone;
  }
  for (const tone of Object.keys(TONE_RANK)) clause.classList.toggle(`is-${tone}`, tone === worst);
}

function markInsertion(pair, shortCite) {
  const clause = clauseFor(pair.index);
  if (!clause) return;
  for (const marker of clause.querySelectorAll('.marker')) {
    if (marker.dataset.refs === String(pair.ref)) marker.classList.add('is-struck');
  }
  const ins = el('ins', 'insert');
  ins.title = 'Suggested citation';
  ins.append(icon('caret'), shortCite);
  clause.after(ins);
}

function hot(index, on) {
  clauseFor(index)?.classList.toggle('is-hot', on);
  for (const note of ui.notes.querySelectorAll(`.note[data-sentence="${index}"]`)) note.classList.toggle('is-hot', on);
}

/* ---------- references ---------- */

function renderReferences(list) {
  ui.refList.replaceChildren(...list.map((text, i) => {
    const li = el('li', 'ref is-pending');
    li.dataset.ref = String(i + 1);
    const verdict = el('span', 'ref-verdict');
    verdict.append(el('span', 'pulse'), 'Looking up');
    li.append(el('span', 'ref-num', String(i + 1)), el('span', 'ref-text', text.replace(LIST_NUMBER, '')), verdict);
    return li;
  }));
  ui.refs.hidden = false;
}

function updateReference(e) {
  const li = ui.refList.querySelector(`[data-ref="${e.number}"]`);
  if (!li) return;
  const v = REFERENCE[e.verdict] || REFERENCE.suspicious;
  li.className = `ref is-${v.tone}`;
  li.querySelector('.ref-verdict').replaceChildren(icon(v.icon), v.label);
  li.querySelector('.ref-detail')?.remove();
  const detail = el('span', 'ref-detail');
  if (e.verdict === 'verified' && e.paper) {
    detail.append(`Matched in ${SOURCES[e.paper.source] || e.paper.source}`);
    const href = safeUrl(e.paper.url);
    if (href) {
      const a = el('a', 'data', e.paper.doi ? `doi:${e.paper.doi}` : href.replace(/^https?:\/\//, ''));
      a.href = href;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      detail.append(' · ', a);
    }
  } else {
    detail.textContent = e.reason;
  }
  li.append(detail);
}

/* ---------- margin notes ---------- */

function pairFor(e) {
  return current.pairs.get(`${e.index}-${e.ref}`);
}

function addPair(item, ref) {
  const key = `${item.index}-${ref}`;
  const note = el('article', 'note is-pending is-new');
  note.dataset.sentence = String(item.index);
  const head = el('header', 'note-head');
  const verdict = el('span', 'note-verdict');
  verdict.append(el('span', 'pulse'), 'Checking…');
  head.append(el('span', 'note-ref', `[${ref}]`), verdict);
  const source = el('p', 'note-source');
  const body = el('div', 'note-body');
  note.append(head, source, body);
  note.addEventListener('mouseenter', () => hot(item.index, true));
  note.addEventListener('mouseleave', () => hot(item.index, false));
  ui.notes.append(note);
  requestAnimationFrame(() => requestAnimationFrame(() => note.classList.remove('is-new')));
  const pair = { key, index: item.index, ref, note, verdict, source, body, tone: 'pending', done: false, fix: null };
  current.pairs.set(key, pair);
  const known = current.refs.get(ref);
  if (known) showSource(pair, known);
}

function showSource(pair, e) {
  pair.source.replaceChildren();
  if (e.paper && e.verdict !== 'not_found') {
    pair.source.append(`${e.paper.short.replace(/^\(|\)$/g, '')} · `, el('cite', '', e.paper.title));
    pair.source.title = `${e.paper.short} ${e.paper.title}`;
  }
  if (e.verdict === 'suspicious') pair.source.append(el('span', 'warn-text', ` · ${e.reason}`));
}

function setVerdict(pair, tone, label, iconName) {
  pair.tone = tone;
  pair.note.classList.remove('is-pending', 'is-ok', 'is-warn', 'is-bad');
  pair.note.classList.add(`is-${tone}`);
  pair.verdict.replaceChildren(icon(iconName), label);
  paintClause(pair.index);
}

function finish(pair) {
  if (pair.done) return;
  pair.done = true;
  current.finished += 1;
  if (current.total) setProgress(current.finished / current.total);
}

/* ---------- note layout: each note sits beside its sentence, pushed down to avoid overlap ---------- */

let layoutQueued = false;
function layoutSoon() {
  if (layoutQueued) return;
  layoutQueued = true;
  requestAnimationFrame(() => { layoutQueued = false; layoutNotes(); });
}

function layoutNotes() {
  const notes = [...ui.notes.children];
  if (narrow.matches || ui.notes.hidden) {
    for (const note of notes) note.style.top = '';
    ui.notes.style.height = '';
    return;
  }
  const origin = ui.notes.getBoundingClientRect().top;
  const placed = notes.map((note, order) => {
    const clause = clauseFor(note.dataset.sentence);
    return { note, order, anchor: clause ? clause.getBoundingClientRect().top - origin - 8 : Infinity };
  }).sort((a, b) => (a.anchor - b.anchor) || (a.order - b.order));
  let y = 0;
  for (const { note, anchor } of placed) {
    const top = Math.max(Number.isFinite(anchor) ? anchor : y, y);
    note.style.top = `${top}px`;
    y = top + note.offsetHeight + 8;
  }
  ui.notes.style.height = `${y}px`;
}

/* ---------- events from the server ---------- */

const handlers = {
  replay(e) {
    current.replay = true;
    ui.status.after(el('p', 'notice is-replay', e.text));
  },

  start(e) {
    current.body = e.body;
    showProof();
    renderProof(e.body, []);
    renderReferences(e.references);
    setStatus(`Looking up ${plural(e.references.length, 'reference')} and finding the citations…`);
    setProgress(null);
  },

  reference(e) {
    current.refs.set(e.number, e);
    updateReference(e);
    for (const pair of current.pairs.values()) if (pair.ref === e.number) showSource(pair, e);
  },

  citations(e) {
    renderProof(current.body, e.items);
    for (const item of e.items) for (const ref of item.refs) addPair(item, ref);
    for (const item of e.items) paintClause(item.index);
    current.total = current.pairs.size;
    if (current.total) {
      setStatus(`Checking ${plural(current.total, 'citation')}…`);
      setProgress(0);
    } else {
      setStatus('No citations found. Cite with [1] or (Author, Year) so each one points into the reference list.', 'warn');
      ui.progress.hidden = true;
    }
  },

  note(e) {
    const pair = pairFor(e);
    if (!pair) return;
    if (e.kind === 'reference_not_found') {
      setVerdict(pair, 'bad', 'Reference not found', 'cross');
    } else {
      setVerdict(pair, 'warn', 'No abstract to check', 'query');
      finish(pair);
    }
    pair.body.append(clamp(el('p', 'why', e.text), 2));
  },

  support(e) {
    const pair = pairFor(e);
    if (!pair) return;
    const v = SUPPORT[e.verdict] || SUPPORT.insufficient_evidence;
    setVerdict(pair, v.tone, v.label, v.icon);
    if (e.verdict === 'supported') {
      if (e.quote) pair.body.append(clamp(el('blockquote', 'evidence is-ok', `“${e.quote}”`), 4));
      finish(pair);
    } else {
      if (e.explanation) pair.body.append(clamp(el('p', 'why', e.explanation), 3));
      if (e.quote) {
        const more = el('details', 'more');
        more.append(el('summary', '', 'What the abstract says'), el('blockquote', `evidence is-${v.tone}`, `“${e.quote}”`));
        more.addEventListener('toggle', layoutSoon);
        pair.body.append(more);
      }
    }
    if (e.quote && !e.quote_found) pair.body.append(el('p', 'from', 'This quote was not found in the abstract.'));
  },

  agent_start(e) {
    const pair = pairFor(e);
    if (!pair) return;
    const box = el('details', 'agent');
    box.open = true;
    const head = el('summary', 'agent-head');
    head.append(el('span', 'pulse'), 'Agent is looking for a paper that supports this');
    const trail = el('ol', 'trail');
    box.append(head, trail);
    box.addEventListener('toggle', layoutSoon);
    pair.body.append(box);
    pair.agent = { box, head, trail, searches: 0 };
    setStatus(`The agent is looking for a better source for [${pair.ref}]…`);
  },

  agent_step(e) {
    const pair = pairFor(e);
    if (!pair || !pair.agent) return;
    if (e.action === 'search') {
      pair.agent.searches += 1;
      const li = el('li', 'is-search');
      li.append(icon('search'), el('span', '', `“${e.detail}”`), el('span', 'count', plural(e.results, 'result')));
      pair.agent.trail.append(li);
      const failed = [...new Set((e.errors || []).map(sourceName))];
      if (failed.length && !e.results) {
        const why = el('li', 'is-failed');
        why.title = e.errors.join('\n');
        why.append(el('span'), el('span', '', `${listOf(failed)} did not answer`), el('span'));
        pair.agent.trail.append(why);
      }
    } else if (e.action === 'rejected') {
      const li = el('li', 'is-rejected');
      li.append(icon('cross'), el('span', '', `Suggestion sent back: ${e.detail}`), el('span'));
      pair.agent.trail.append(li);
    }
  },

  repair(e) {
    const pair = pairFor(e);
    if (!pair) return;
    if (pair.agent) {
      pair.agent.head.replaceChildren(icon('chevron'), `Agent searched ${plural(pair.agent.searches, 'time')}`);
      pair.agent.box.open = false;
    }
    const block = el('div', 'fix');
    if (e.decision === 'replace' && e.paper) {
      const label = el('p', 'fix-label');
      label.append(icon('caret'), 'Cite instead');
      block.append(label, clamp(el('p', 'fix-ref', e.paper.apa), 3));
      if (e.quote) block.append(clamp(el('blockquote', 'evidence is-fix', `“${e.quote}”`), 3));
      const verdict = e.check === 'partially_supported' ? 'partly supports' : 'supports';
      block.append(el('p', 'fix-check', `A separate check agrees this abstract ${verdict} your sentence.`));
      const actions = el('div', 'fix-actions');
      actions.append(copyButton('Copy reference', e.paper.apa), linkButton('Open paper', e.paper.url));
      block.append(actions);
      pair.fix = 'replace';
      markInsertion(pair, e.paper.short);
    } else if (e.decision === 'revise_claim' && e.revised_claim) {
      const label = el('p', 'fix-label');
      label.append(icon('caret'), 'Rewrite the sentence');
      block.append(label, el('p', 'fix-text', e.revised_claim));
      if (e.explanation) block.append(clamp(el('p', 'why', e.explanation), 2));
      const actions = el('div', 'fix-actions');
      actions.append(copyButton('Copy sentence', e.revised_claim));
      block.append(actions);
      pair.fix = 'rewrite';
    } else {
      block.append(el('p', 'fix-none', 'No supporting paper found.'));
      if (e.explanation) block.append(clamp(el('p', 'why', e.explanation), 2));
    }
    pair.body.append(block);
    finish(pair);
  },

  claim_error(e) {
    const pair = pairFor(e);
    if (!pair) return;
    setVerdict(pair, 'warn', 'This check failed', 'query');
    pair.body.append(clamp(el('p', 'why', e.message), 2));
    finish(pair);
  },

  notice(e) {
    ui.status.after(el('p', 'notice', e.text));
  },

  done(e) {
    for (const pair of current.pairs.values()) {
      if (pair.tone === 'pending') setVerdict(pair, 'warn', 'Not checked', 'query');
      finish(pair);
    }
    const recorded = current.replay ? ' (recorded)' : '';
    ui.usage.textContent = `Last check${recorded}: ${e.seconds} s · ${plural(e.calls, 'model call')} · ${e.tokens.toLocaleString('en')} tokens`;
    const pairs = [...current.pairs.values()];
    ui.progress.hidden = true;
    if (!pairs.length) return;
    const supported = pairs.filter((p) => p.tone === 'ok').length;
    const replaced = pairs.filter((p) => p.fix === 'replace').length;
    const rewrite = pairs.filter((p) => p.fix === 'rewrite').length;
    const open = pairs.length - supported - replaced - rewrite;
    const parts = [];
    if (supported) parts.push(['ok', `${supported} supported`]);
    if (replaced) parts.push(['fix', `${replaced} with a better source`]);
    if (rewrite) parts.push(['fix', `${rewrite} to rewrite`]);
    if (open) parts.push(['bad', `${open} unresolved`]);
    ui.status.className = 'status';
    ui.status.replaceChildren(`${plural(pairs.length, 'citation')} checked in ${Math.round(e.seconds)} s${recorded}: `);
    parts.forEach(([tone, text], i) => {
      if (i) ui.status.append(i === parts.length - 1 ? ' and ' : ', ');
      ui.status.append(el('strong', `is-${tone}`, text));
    });
    ui.status.append('.');
  },

  error(e) {
    showError(e.message);
  },
};

/* ---------- running a check ---------- */

async function readEvents(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    for (let nl = buffer.indexOf('\n'); nl >= 0; nl = buffer.indexOf('\n')) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

function setRunning(on) {
  ui.run.textContent = on ? 'Stop' : 'Check citations';
  ui.run.classList.toggle('is-stop', on);
  ui.example.disabled = on;
  ui.edit.disabled = on;
}

async function start() {
  if (current && current.running) {
    current.controller.abort();
    return;
  }
  const text = ui.input.value.trim();
  if (!text) {
    if (ui.input.hidden) showEditor();
    ui.input.focus();
    setStatus('Paste a passage and its references first, or load the example.', 'warn');
    return;
  }
  current = { controller: new AbortController(), running: true, replay: false, body: '', refs: new Map(), pairs: new Map(), total: 0, finished: 0 };
  ui.notes.replaceChildren();
  document.querySelectorAll('.notice').forEach((n) => n.remove());
  ui.usage.textContent = '';
  setRunning(true);
  try {
    const response = await fetch('/api/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, repair: true }),
      signal: current.controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.message || `The server answered with an error (${response.status}).`);
    }
    await readEvents(response.body, (event) => {
      const handle = handlers[event.type];
      if (handle) handle(event);
      layoutSoon();
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      setStatus('Stopped. The results so far are kept.', 'warn');
      ui.progress.hidden = true;
    } else {
      showError(err instanceof TypeError
        ? 'The citefix server could not be reached. Check that it is still running, then try again.'
        : err.message);
    }
  } finally {
    current.running = false;
    setRunning(false);
    layoutSoon();
  }
}

async function loadExample() {
  try {
    const response = await fetch('/api/example');
    const data = await response.json();
    ui.input.value = data.text || '';
    showEditor();
    ui.input.focus();
    ui.input.setSelectionRange(0, 0);
    ui.input.scrollTop = 0;
  } catch {
    setStatus('The example could not be loaded.', 'warn');
  }
}

ui.run.addEventListener('click', start);
ui.example.addEventListener('click', loadExample);
ui.edit.addEventListener('click', () => { showEditor(); ui.input.focus(); });
ui.input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    start();
  }
});
window.addEventListener('resize', layoutSoon);
narrow.addEventListener('change', layoutSoon);
new ResizeObserver(layoutSoon).observe(ui.proof);
document.fonts?.ready.then(layoutSoon);
