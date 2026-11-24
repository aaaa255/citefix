import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Square } from 'lucide-react';
import { useCheck, useMenu } from '../../lib/CheckContext.jsx';
import { prefersReducedMotion, useMediaQuery } from '../../lib/hooks.js';
import { useI18n } from '../../lib/i18n.jsx';
import { Icon, LayoutContext } from '../ui.jsx';
import Legend from './Legend.jsx';
import Note from './Note.jsx';
import Proof from './Proof.jsx';
import References from './References.jsx';
import Status from './Status.jsx';

/* The checker: the references first (does each paper exist?), then the passage with its marks and each verdict in
   the margin beside its sentence. The check itself lives in CheckContext; this is its view. */
export default function Checker() {
  const { t } = useI18n();
  const { state, dispatch, text, setText, exampleLoading, loadExample, run } = useCheck();
  const { openMenu } = useMenu();
  const { mode, check, status, notices, progress } = state;
  const running = Boolean(check?.running);
  const [hot, setHot] = useState(null);
  const [flash, setFlash] = useState(null);
  const inputRef = useRef(null);
  const proofRef = useRef(null);
  const notesRef = useRef(null);
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

  /* ---------- actions ---------- */

  const focusEditor = () => requestAnimationFrame(() => {
    const input = inputRef.current;
    if (!input) return;
    input.focus({ preventScroll: true });
    input.setSelectionRange(0, 0);
    input.scrollTop = 0;
  });

  const onLoadExample = async () => { if (await loadExample()) focusEditor(); };
  const onRun = async () => {
    setHot(null);
    if (await run() === 'empty') focusEditor();
  };

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

  const vote = useCallback((key, value) => dispatch({ type: 'vote', key, vote: value }), [dispatch]);
  const why = useCallback((key, value) => dispatch({ type: 'why', key, text: value }), [dispatch]);

  return (
    <LayoutContext.Provider value={layoutSoon}>
      <div className="sheet">
        <div className="sheet-bar">
          <h3 className="sheet-title">
            {t('checker.manuscript')}
            {mode === 'proof' && (
              <button type="button" className="btn btn-text" onClick={() => { dispatch({ type: 'edit' }); focusEditor(); }} disabled={running}>
                {t('checker.edit')}
              </button>
            )}
          </h3>
          <div className="sheet-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onLoadExample} disabled={running || exampleLoading}>
              {exampleLoading ? t('checker.loadingExample') : t('checker.loadExample')}
            </button>
            <button type="button" className={`btn btn-sm ${running ? 'btn-ghost' : 'btn-primary'}`} onClick={onRun} disabled={exampleLoading}>
              {running ? <><Icon as={Square} />{t('checker.stop')}</> : t('checker.check')}
            </button>
          </div>
        </div>

        {mode === 'proof' && check && check.references.length > 0 && (
          <References references={check.references} refs={check.refs} />
        )}

        <section className="text-col" aria-label={t('checker.manuscript')}>
          <label className="visually-hidden" htmlFor="input">{t('checker.inputLabel')}</label>
          <textarea
            id="input"
            ref={inputRef}
            className="editor"
            spellCheck={false}
            placeholder={t('checker.placeholder')}
            value={text}
            hidden={mode !== 'edit'}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); onRun(); }
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

        <aside className="margin-col" aria-labelledby="checks-title">
          <h3 id="checks-title" className="col-label">{t('checker.checks')}</h3>
          <Status status={status} onRate={() => openMenu('feedback')} />
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
          {mode === 'edit' && <Legend />}
        </aside>
      </div>
    </LayoutContext.Provider>
  );
}
