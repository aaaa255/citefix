import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react';
import { Square } from 'lucide-react';
import { TESTER_KEY, checkId, initialState, plural, readEvents, reduce } from '../../lib/check.js';
import { prefersReducedMotion, useMediaQuery } from '../../lib/hooks.js';
import { Icon, LayoutContext } from '../ui.jsx';
import Feedback from './Feedback.jsx';
import Legend from './Legend.jsx';
import Note from './Note.jsx';
import Proof from './Proof.jsx';
import References from './References.jsx';
import Status from './Status.jsx';

const PLACEHOLDER = `Paste a passage that cites its sources, for example: “…and rely entirely on attention mechanisms [1].”

Then a line that says References, and one reference per line:

References
[1] Vaswani, A., et al. (2017). Attention is all you need. NeurIPS.`;

const readTester = () => {
  try { return localStorage.getItem(TESTER_KEY) || ''; } catch { return ''; }
};

/* The checker: streams one check from /api/review and writes the results on the passage as proof marks,
   with each verdict in the margin beside its sentence. */
export default function Checker() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const { mode, check, status, notices, progress, feedbackOpen } = state;
  const running = Boolean(check?.running);
  const [text, setText] = useState('');
  const [exampleLoading, setExampleLoading] = useState(false);
  const [hot, setHot] = useState(null);
  const [flash, setFlash] = useState(null);
  const [tester, setTester] = useState(readTester);
  const example = useRef({ text: null, load: null });
  const controller = useRef(null);
  const inputRef = useRef(null);
  const proofRef = useRef(null);
  const notesRef = useRef(null);
  const feedbackRef = useRef(null);
  const clauses = useRef(new Map());
  const flashTimer = useRef(0);
  const narrow = useMediaQuery('(max-width: 960px)');

  /* ---------- note layout: each note sits beside its sentence, pushed down to avoid overlap ---------- */

  const layout = useCallback(() => {
    const box = notesRef.current;
    if (!box) return;
    const slots = [...box.children];
    if (narrow) {
      for (const slot of slots) { slot.style.transform = ''; slot.dataset.placed = ''; }
      box.style.height = '';
      return;
    }
    const origin = box.getBoundingClientRect().top;
    const placed = slots.map((slot, order) => {
      const clause = clauses.current.get(Number(slot.dataset.sentence));
      return { slot, order, anchor: clause ? clause.getBoundingClientRect().top - origin - 8 : Infinity };
    }).sort((a, b) => (a.anchor - b.anchor) || (a.order - b.order));
    let y = 0;
    for (const { slot, anchor } of placed) {
      const top = Math.round(Math.max(Number.isFinite(anchor) ? anchor : y, y));
      const value = `translateY(${top}px)`;
      if (slot.dataset.placed !== '1') { // a new note appears in place; only later moves slide
        slot.style.transition = 'none';
        slot.style.transform = value;
        void slot.offsetHeight;
        slot.style.transition = '';
        slot.dataset.placed = '1';
      } else if (slot.style.transform !== value) {
        slot.style.transform = value;
      }
      y = top + slot.offsetHeight + 8;
    }
    box.style.height = `${y}px`;
  }, [narrow]);

  const queued = useRef(false);
  const layoutSoon = useCallback(() => {
    if (queued.current) return;
    queued.current = true;
    requestAnimationFrame(() => { queued.current = false; layout(); });
  }, [layout]);

  // The text and every note are watched for size changes, so a note that grows or shrinks on its own (a reason
  // opened, the agent's trail folded, a font arriving late) moves its neighbours without waiting for the next event.
  const observer = useRef(null);
  const watch = (ro) => {
    if (proofRef.current) ro.observe(proofRef.current);
    for (const slot of notesRef.current?.children || []) ro.observe(slot);
  };

  useLayoutEffect(() => {
    layout();
    if (observer.current) watch(observer.current);
  });

  useEffect(() => {
    // Laid out inside the callback, which runs after layout and before paint, so no frame shows notes overlapping.
    // Safe from resize loops: layout() only moves the notes and sets the height of their box, which is not watched.
    const ro = new ResizeObserver(() => layout());
    observer.current = ro;
    watch(ro);
    window.addEventListener('resize', layoutSoon);
    document.fonts?.ready.then(layoutSoon);
    return () => {
      ro.disconnect();
      observer.current = null;
      window.removeEventListener('resize', layoutSoon);
    };
  }, [layout, layoutSoon]);

  /* ---------- the example, fetched as soon as the page opens so Load example rarely has to wait ---------- */

  const fetchExample = useCallback(() => {
    const ex = example.current;
    ex.load ||= fetch('/api/example')
      .then((response) => {
        if (!response.ok) throw new Error(`The server answered with an error (${response.status}).`);
        return response.json();
      })
      .then((data) => { ex.text = data.text || ''; return ex.text; })
      .catch((err) => { ex.load = null; throw err; }); // the next click tries again
    return ex.load;
  }, []);

  useEffect(() => { fetchExample().catch(() => { /* Load example tries again and says so if it still fails */ }); }, [fetchExample]);

  const focusEditor = () => requestAnimationFrame(() => {
    const input = inputRef.current;
    if (!input) return;
    input.focus({ preventScroll: true });
    input.setSelectionRange(0, 0);
    input.scrollTop = 0;
  });

  async function loadExample() {
    if (example.current.text == null) {
      // Until the text is in the editor, a check would only find an empty passage.
      setExampleLoading(true);
      try {
        await fetchExample();
      } catch {
        dispatch({ type: 'warn', text: 'The example could not be loaded.' });
        return;
      } finally {
        setExampleLoading(false);
      }
    }
    setText(example.current.text);
    dispatch({ type: 'edit' });
    focusEditor();
  }

  /* ---------- running a check ---------- */

  async function run() {
    if (exampleLoading) return;
    if (running) {
      controller.current?.abort();
      return;
    }
    const passage = text.trim();
    if (!passage) {
      if (mode === 'proof') dispatch({ type: 'edit' });
      dispatch({ type: 'warn', text: 'Paste a passage and its references first, or load the example.' });
      focusEditor();
      return;
    }
    const id = checkId();
    const abort = new AbortController();
    controller.current = abort;
    setHot(null);
    dispatch({ type: 'begin', id });
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: passage, repair: true }),
        signal: abort.signal,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.message || `The server answered with an error (${response.status}).`);
      }
      await readEvents(response.body, (event) => dispatch({ type: 'event', event }));
    } catch (err) {
      if (err.name === 'AbortError') {
        dispatch({ type: 'aborted' });
      } else {
        dispatch({
          type: 'failed',
          message: err instanceof TypeError
            ? 'The citefix server could not be reached. Check that it is still running, then try again.'
            : err.message,
        });
      }
    } finally {
      dispatch({ type: 'finished', id });
    }
  }

  /* ---------- moving between the text and its notes ---------- */

  const motionBehavior = () => (prefersReducedMotion() ? 'auto' : 'smooth');

  const showNote = (index, ref) => {
    const key = `${index}-${ref}`;
    const slot = notesRef.current?.querySelector(`[data-key="${key}"]`);
    if (!slot) return false;
    slot.scrollIntoView({ block: 'nearest', behavior: motionBehavior() });
    setFlash(key);
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), 1400);
    return true;
  };

  const showSentence = (index) => {
    notesRef.current?.querySelector(`[data-sentence="${index}"]`)?.scrollIntoView({ block: 'nearest', behavior: motionBehavior() });
  };

  const jumpToFeedback = () => {
    const panel = feedbackRef.current;
    if (!panel) return;
    panel.scrollIntoView({ behavior: motionBehavior(), block: 'start' });
    panel.querySelector('input[type="radio"]')?.focus({ preventScroll: true });
  };

  const vote = useCallback((key, value) => dispatch({ type: 'vote', key, vote: value }), []);
  const why = useCallback((key, value) => dispatch({ type: 'why', key, text: value }), []);
  const sent = useCallback((id, sentId) => dispatch({ type: 'sent', checkId: id, id: sentId }), []);

  const usage = check?.usage;

  return (
    <LayoutContext.Provider value={layoutSoon}>
      <div className="sheet">
        <div className="sheet-bar">
          <h3 className="sheet-title">
            Manuscript
            {mode === 'proof' && (
              <button type="button" className="btn btn-text" onClick={() => { dispatch({ type: 'edit' }); focusEditor(); }} disabled={running}>
                Edit text
              </button>
            )}
          </h3>
          <div className="sheet-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={loadExample} disabled={running || exampleLoading}>
              {exampleLoading ? 'Loading example…' : 'Load example'}
            </button>
            <button type="button" className={`btn btn-sm ${running ? 'btn-ghost' : 'btn-primary'}`} onClick={run} disabled={exampleLoading}>
              {running ? <><Icon as={Square} />Stop</> : 'Check citations'}
            </button>
          </div>
        </div>

        <section className="text-col" aria-label="Manuscript">
          <label className="visually-hidden" htmlFor="input">Passage and reference list</label>
          <textarea
            id="input"
            ref={inputRef}
            className="editor"
            spellCheck={false}
            placeholder={PLACEHOLDER}
            value={text}
            hidden={mode !== 'edit'}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run(); }
            }}
          />
          {mode === 'proof' && check && (
            <Proof
              innerRef={proofRef}
              body={check.body}
              citations={check.citations}
              pairs={check.pairs}
              order={check.order}
              hot={hot}
              onHot={setHot}
              onClause={showSentence}
              onMarker={showNote}
              clauses={clauses}
            />
          )}
        </section>

        {mode === 'proof' && check && check.references.length > 0 && (
          <References references={check.references} refs={check.refs} />
        )}

        <aside className="margin-col" aria-labelledby="checks-title">
          <h3 id="checks-title" className="col-label">Checks</h3>
          <Status status={status} onJump={jumpToFeedback} />
          {notices.map((n, i) => <p key={i} className={`notice${n.replay ? ' is-replay' : ''}`}>{n.text}</p>)}
          {progress !== 'hidden' && (
            <div className={`progress${progress == null ? ' is-indeterminate' : ''}`}>
              <span style={progress == null ? undefined : { width: `${Math.round(progress * 100)}%` }} />
            </div>
          )}
          {mode === 'proof' && check && (
            <div className="notes" ref={notesRef}>
              {check.order.map((key) => {
                const pair = check.pairs[key];
                return (
                  <div key={key} className="note-slot" data-key={key} data-sentence={pair.index}>
                    <Note
                      pair={pair}
                      refEvent={check.refs[pair.ref]}
                      hot={hot === pair.index}
                      flash={flash === key}
                      onHot={setHot}
                      onVote={vote}
                      onWhy={why}
                    />
                  </div>
                );
              })}
            </div>
          )}
          {feedbackOpen && check && (
            <Feedback key={check.id} check={check} tester={tester} onTester={setTester} onSent={sent} panelRef={feedbackRef} />
          )}
          {mode === 'edit' && <Legend />}
        </aside>
      </div>
      <p className="mt-4 min-h-[1.5em] px-2 text-[13px] tabular-nums text-ink-3">
        {usage && `Last check${usage.recorded ? ' (recorded)' : ''}: ${usage.seconds} s, ${plural(usage.calls, 'model call')}, ${Number(usage.tokens).toLocaleString('en')} tokens`}
      </p>
    </LayoutContext.Provider>
  );
}
