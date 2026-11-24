/* One check, rebuilt from the server's events. POST /api/review streams one JSON object per line; each event goes
   through reduce() below, which mirrors the handlers of the original front end (citefix/web/app.js). Everything the
   server or the passage sends is rendered by React as text, never as HTML. */

export const SUPPORT = {
  supported: { tone: 'ok', label: 'Supported', icon: 'check' },
  partially_supported: { tone: 'warn', label: 'Partly supported', icon: 'query' },
  not_supported: { tone: 'bad', label: 'Not supported', icon: 'cross' },
  insufficient_evidence: { tone: 'warn', label: 'Can’t tell from the abstract', icon: 'query' },
};
export const REFERENCE = {
  verified: { tone: 'ok', label: 'Found', icon: 'check' },
  suspicious: { tone: 'warn', label: 'Details differ', icon: 'query' },
  not_found: { tone: 'bad', label: 'Not found', icon: 'cross' },
};
export const SOURCES = { openalex: 'OpenAlex', crossref: 'Crossref', arxiv: 'arXiv', semantic_scholar: 'Semantic Scholar' };
export const TONE_RANK = { ok: 0, pending: 1, warn: 2, bad: 3 };
// "Cite instead" needs a citation that clearly fails; a paper found for any other one is only a possible source.
const CLEAR_FAILURE = new Set(['reference_not_found', 'not_supported']);
const MARKER = /\[(\d+(?:\s*[,–-]\s*\d+)*)\]/g;
export const LIST_NUMBER = /^\s*(?:\[\d+\]|\(\d+\)|\d+[.)])\s+/;
export const TESTER_KEY = 'citefix.tester';

/* ---------- small helpers ---------- */

export function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function listOf(names) {
  return names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

export function safeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null;
}

function sourceName(error) {
  const key = String(error).split(':')[0].trim();
  return SOURCES[key] || key;
}

export function expandRefs(spec) {
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

export function worstTone(tones, start = 'ok') {
  return tones.reduce((worst, tone) => (TONE_RANK[tone] > TONE_RANK[worst] ? tone : worst), start);
}

export function checkId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/* Splits a sentence into plain text and citation numbers such as [1] or [2, 4-6]. */
export function splitMarkers(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    out.push({ marker: m[0], refs: expandRefs(m[1]) });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
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

/* The passage as paragraphs of plain text and checked sentences ("clauses"). */
export function proofLayout(body, citations) {
  const ranges = [];
  for (const item of citations) {
    const at = findSentence(body, item.sentence || '', ranges);
    if (at) ranges.push({ start: at[0], end: at[1], index: item.index });
  }
  ranges.sort((a, b) => a.start - b.start);
  const bounds = [];
  const breaks = /\n\s*\n/g;
  let from = 0;
  for (let m = breaks.exec(body); m; m = breaks.exec(body)) {
    bounds.push([from, m.index]);
    from = m.index + m[0].length;
  }
  bounds.push([from, body.length]);
  const paragraphs = [];
  for (const [start, end] of bounds) {
    const pieces = [];
    let cursor = start;
    for (const r of ranges) {
      if (r.start < start || r.end > end) continue;
      if (r.start > cursor) pieces.push({ text: body.slice(cursor, r.start) });
      pieces.push({ clause: r.index, text: body.slice(r.start, r.end) });
      cursor = r.end;
    }
    if (cursor < end) pieces.push({ text: body.slice(cursor, end) });
    if (pieces.some((p) => p.text.trim())) paragraphs.push({ key: start, pieces });
  }
  return paragraphs;
}

/* ---------- fixes ---------- */

/* Puts a citation in before the sentence's last stop. */
export function withCite(text, cite) {
  const stop = text.search(/[.!?]["”’]*\s*$/);
  return stop === -1 ? `${text} ${cite}` : `${text.slice(0, stop)} ${cite}${text.slice(stop)}`;
}

/* The agent rewrites the claim, which carries no citation numbers; the sentence's own numbers go back in before its last stop. */
function withMarkers(text, pair) {
  const markers = [...pair.sentence.matchAll(MARKER)]
    .filter((m) => expandRefs(m[1]).some((ref) => pair.refs.includes(ref)))
    .map((m) => m[0]);
  const missing = [...new Set(markers)].filter((m) => !text.includes(m));
  return missing.length ? withCite(text, missing.join(', ')) : text;
}

/* The line under a suggested paper: what the second check found and, for a possible source, why it is only that. */
function secondCheck(pair, e) {
  const lines = [];
  if (pair.verdictKey === 'insufficient_evidence') {
    lines.push(`[${pair.ref}] may still be right: its abstract does not settle this, so check its full text first.`);
  } else if (pair.verdictKey === 'partially_supported') {
    lines.push(`[${pair.ref}] partly supports this sentence, so this paper may belong beside it rather than in its place.`);
  }
  lines.push(e.check === 'partially_supported'
    ? 'A separate check finds this abstract only partly supports your sentence.'
    : 'A separate check agrees this abstract supports your sentence.');
  return lines.join(' ');
}

/* ---------- state ---------- */

export const initialState = {
  mode: 'edit', // 'edit': the editor; 'proof': the passage with its marks
  check: null, // the check in progress or the last one
  status: null, // { kind: 'text' | 'error' | 'summary', ... }
  notices: [],
  progress: 'hidden', // 'hidden', null (still working, no fraction yet) or a fraction from 0 to 1
  feedbackOpen: false,
};

function freshCheck(id) {
  return {
    id, running: true, replay: false, body: '', references: [], refs: {}, citations: [],
    pairs: {}, order: [], total: 0, finished: 0, seconds: null, searching: [], usage: null, sentId: null,
  };
}

function newPair(item, ref) {
  const sentence = item.sentence || item.claim || '';
  return {
    key: `${item.index}-${ref}`, index: item.index, ref, refs: item.refs || [], sentence, claim: item.claim || item.sentence,
    tone: 'pending', label: 'Checking…', icon: null, repeat: false,
    parts: [], agent: null, fix: null, fixData: null,
    done: false, failed: false, votable: false, vote: null, why: '',
    verdictKey: '', quote: '', suggested: '', // for feedback
  };
}

function searchingStatus(c) {
  const refs = [...new Set(c.searching.map((key) => c.pairs[key]?.ref))]
    .filter((ref) => ref != null).sort((a, b) => a - b).map((ref) => `[${ref}]`);
  if (refs.length) {
    return { kind: 'text', text: `The agent is looking for ${refs.length === 1 ? 'a supporting paper' : 'supporting papers'} for ${listOf(refs)}…` };
  }
  if (c.total) return { kind: 'text', text: `Checking ${plural(c.total, 'citation')}…` };
  return null;
}

function summary(c) {
  const pairs = c.order.map((key) => c.pairs[key]);
  const supported = pairs.filter((p) => p.tone === 'ok').length;
  const replaced = pairs.filter((p) => p.fix === 'replace').length;
  const possible = pairs.filter((p) => p.fix === 'candidate').length;
  const rewrite = pairs.filter((p) => p.fix === 'rewrite').length;
  const open = pairs.length - supported - replaced - possible - rewrite;
  const parts = [];
  if (supported) parts.push(['ok', `${supported} supported`]);
  if (replaced) parts.push(['fix', `${replaced} with a better source`]);
  if (possible) parts.push(['fix', `${possible} with a possible source to check`]);
  if (rewrite) parts.push(['fix', `${rewrite} to rewrite`]);
  if (open) parts.push(['bad', `${open} unresolved`]);
  return { kind: 'summary', count: pairs.length, seconds: c.seconds, recorded: c.replay, parts };
}

function reduceEvent(state, e) {
  if (!state.check) return state;
  const s = { ...state, check: { ...state.check, pairs: { ...state.check.pairs } } };
  const c = s.check;
  // A pair is copied before it changes, so React sees a new object.
  const take = (key) => {
    const p = c.pairs[key];
    if (!p) return null;
    const copy = { ...p, parts: [...p.parts], agent: p.agent && { ...p.agent, trail: [...p.agent.trail] } };
    c.pairs[key] = copy;
    return copy;
  };
  const keyOf = (ev) => `${ev.index}-${ev.ref}`;
  const setVerdict = (pair, tone, label, icon) => { pair.tone = tone; pair.label = label; pair.icon = icon; };
  // Called once a note has its final content: it then gets the tester's "Is this right?" row.
  const finish = (pair) => {
    if (pair.done) return;
    pair.done = true;
    c.finished += 1;
    if (c.total) s.progress = c.finished / c.total;
    if (!pair.failed) pair.votable = true;
  };
  const stopSearching = (pair) => {
    if (!c.searching.includes(pair.key)) return;
    c.searching = c.searching.filter((key) => key !== pair.key);
    s.status = searchingStatus(c) || s.status;
  };

  switch (e.type) {
    case 'replay':
      c.replay = true;
      s.notices = [...s.notices, { text: e.text, replay: true }];
      break;

    case 'queued':
      s.status = { kind: 'text', text: e.text };
      s.progress = null;
      break;

    case 'start':
      c.body = e.body || '';
      c.references = e.references || [];
      s.mode = 'proof';
      s.status = { kind: 'text', text: `Looking up ${plural(c.references.length, 'reference')} and finding the citations…` };
      s.progress = null;
      break;

    case 'reference':
      c.refs = { ...c.refs, [e.number]: e };
      break;

    case 'citations': {
      c.citations = e.items || [];
      c.order = [...c.order];
      for (const item of c.citations) {
        for (const ref of item.refs || []) {
          const key = `${item.index}-${ref}`;
          if (c.pairs[key]) continue;
          c.pairs[key] = newPair(item, ref);
          c.order.push(key);
        }
      }
      for (const key of c.order) {
        const pair = take(key);
        pair.repeat = c.order.some((other) => other !== key && c.pairs[other].ref === pair.ref);
      }
      c.total = c.order.length;
      if (c.total) {
        s.status = { kind: 'text', text: `Checking ${plural(c.total, 'citation')}…` };
        s.progress = 0;
      } else {
        s.status = { kind: 'text', tone: 'warn', text: 'No citations found. Cite with [1] or (Author, Year) so each one points into the reference list.' };
        s.progress = 'hidden';
      }
      break;
    }

    case 'note': {
      const pair = take(keyOf(e));
      if (!pair) break;
      const missing = e.kind === 'reference_not_found';
      pair.verdictKey = e.kind;
      if (missing) setVerdict(pair, 'bad', 'Reference not found', 'cross');
      else setVerdict(pair, 'warn', 'No abstract to check', 'query');
      pair.parts.push({ kind: 'why', text: e.text, lines: 2 });
      if (!missing) finish(pair); // a missing reference goes on to the agent
      break;
    }

    case 'support': {
      const pair = take(keyOf(e));
      if (!pair) break;
      const v = SUPPORT[e.verdict] || SUPPORT.insufficient_evidence;
      pair.verdictKey = e.verdict;
      pair.quote = e.quote || '';
      setVerdict(pair, v.tone, v.label, v.icon);
      if (e.verdict === 'supported') {
        if (e.quote) pair.parts.push({ kind: 'evidence', tone: 'ok', text: e.quote, lines: 4 });
      } else {
        if (e.explanation) pair.parts.push({ kind: 'why', text: e.explanation, lines: 3 });
        if (e.quote) pair.parts.push({ kind: 'more', tone: v.tone, text: e.quote });
      }
      if (e.quote && !e.quote_found) pair.parts.push({ kind: 'from', text: 'This quote was not found in the abstract.' });
      if (e.verdict === 'supported') finish(pair);
      break;
    }

    case 'agent_start': {
      const pair = take(keyOf(e));
      if (!pair) break;
      pair.agent = { searches: 0, trail: [], finished: false };
      pair.parts.push({ kind: 'agent' });
      c.searching = [...c.searching, pair.key];
      s.status = searchingStatus(c) || s.status;
      break;
    }

    case 'agent_step': {
      const pair = take(keyOf(e));
      if (!pair || !pair.agent) break;
      if (e.action === 'search') {
        pair.agent.searches += 1;
        pair.agent.trail.push({ kind: 'search', detail: e.detail, results: e.results || 0 });
        const failed = [...new Set((e.errors || []).map(sourceName))];
        if (failed.length && !e.results) {
          pair.agent.trail.push({ kind: 'failed', text: `${listOf(failed)} did not answer`, title: e.errors.join('\n') });
        }
      } else if (e.action === 'rejected') {
        pair.agent.trail.push({ kind: 'rejected', detail: e.detail });
      }
      break;
    }

    case 'repair': {
      const pair = take(keyOf(e));
      if (!pair) break;
      stopSearching(pair);
      if (pair.agent) pair.agent.finished = true;
      if (e.decision === 'replace' && e.paper) {
        // Only a full replacement for a citation that clearly fails is marked in the text as the one to cite.
        const replace = CLEAR_FAILURE.has(pair.verdictKey) && e.check === 'supported';
        pair.fixData = { type: replace ? 'replace' : 'candidate', paper: e.paper, quote: e.quote || '', checkLine: secondCheck(pair, e) };
        pair.fix = replace ? 'replace' : 'candidate';
        pair.suggested = e.paper.apa;
      } else if (e.decision === 'revise_claim' && e.revised_claim) {
        // A rewrite keeps the sentence's number only when the cited paper supports it; otherwise it cites the
        // paper that does. Recordings made before keeps_citation existed always kept the number.
        const keeps = e.keeps_citation !== false || !e.paper;
        const rewritten = keeps ? withMarkers(e.revised_claim, pair) : withCite(e.revised_claim, e.paper.short);
        pair.fixData = {
          type: 'rewrite', keeps, rewritten, paper: e.paper || null, quote: e.quote || '',
          check: Boolean(e.check), explanation: e.explanation || '',
        };
        pair.fix = 'rewrite';
        pair.suggested = keeps ? rewritten : `${rewritten} ${e.paper.apa}`;
      } else {
        pair.fixData = { type: 'none', explanation: e.explanation || '' };
        pair.fix = 'none';
      }
      pair.parts.push({ kind: 'fix' });
      finish(pair);
      break;
    }

    case 'claim_error': {
      const pair = take(keyOf(e));
      if (!pair) break;
      stopSearching(pair);
      if (pair.agent) pair.agent.finished = true;
      pair.failed = true;
      pair.verdictKey = 'error';
      setVerdict(pair, 'warn', 'This check failed', 'query');
      pair.parts.push({ kind: 'why', text: e.message, lines: 2 });
      finish(pair);
      break;
    }

    case 'notice':
      s.notices = [...s.notices, { text: e.text }];
      break;

    case 'done': {
      c.seconds = e.seconds;
      for (const key of c.order) {
        const pair = take(key);
        if (pair.tone === 'pending') {
          pair.failed = true;
          pair.verdictKey = 'not_checked';
          setVerdict(pair, 'warn', 'Not checked', 'query');
        }
        if (pair.agent) pair.agent.finished = true;
        finish(pair);
      }
      c.usage = { seconds: e.seconds, calls: e.calls, tokens: e.tokens, recorded: c.replay };
      s.progress = 'hidden';
      if (c.order.length) s.status = summary(c);
      break;
    }

    case 'error':
      s.status = { kind: 'error', text: e.message };
      s.progress = 'hidden';
      break;

    default:
      return state;
  }
  return s;
}

export function reduce(state, action) {
  switch (action.type) {
    case 'begin':
      return {
        ...state, check: freshCheck(action.id), notices: [], feedbackOpen: false,
        status: { kind: 'text', text: 'Starting the check…' }, progress: null,
      };
    case 'event':
      return reduceEvent(state, action.event);
    case 'aborted':
      return { ...state, status: { kind: 'text', tone: 'warn', text: 'Stopped. The results so far are kept.' }, progress: 'hidden' };
    case 'failed':
      return { ...state, status: { kind: 'error', text: action.message }, progress: 'hidden' };
    case 'finished':
      if (!state.check || state.check.id !== action.id) return state;
      return { ...state, check: { ...state.check, running: false }, feedbackOpen: true };
    case 'edit':
      return { ...state, mode: 'edit', status: null, notices: [], progress: 'hidden', feedbackOpen: false };
    case 'warn':
      return { ...state, status: { kind: 'text', tone: 'warn', text: action.text } };
    case 'vote':
    case 'why': {
      const c = state.check;
      const pair = c?.pairs[action.key];
      if (!pair) return state;
      const next = action.type === 'vote'
        ? { ...pair, vote: pair.vote === action.vote ? null : action.vote }
        : { ...pair, why: action.text };
      return { ...state, check: { ...c, pairs: { ...c.pairs, [action.key]: next } } };
    }
    case 'sent':
      if (!state.check || state.check.id !== action.checkId) return state;
      return { ...state, check: { ...state.check, sentId: action.id } };
    default:
      return state;
  }
}

/* ---------- talking to the server ---------- */

export async function readEvents(stream, onEvent) {
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

export function feedbackPayload(check, { rating, comment, tester }) {
  return {
    check: check.id,
    replay: check.replay,
    seconds: check.seconds,
    rating: rating || null,
    comment: comment.trim(),
    tester: tester.trim(),
    citations: check.order.map((key) => check.pairs[key]).map((p) => ({
      ref: p.ref,
      claim: p.claim,
      reference: check.references[p.ref - 1] || '',
      existence: check.refs[p.ref]?.verdict || '',
      verdict: p.verdictKey,
      quote: p.quote,
      fix: p.fix || '',
      suggested: p.suggested,
      vote: p.vote,
      why: p.vote === 'wrong' ? p.why.trim() : '',
    })),
  };
}
