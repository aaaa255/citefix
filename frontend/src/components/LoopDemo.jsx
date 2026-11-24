import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { MousePointer2 } from 'lucide-react';
import { useI18n } from '../lib/i18n.jsx';
import { DEMO_EVENTS, DEMO_PASSAGE, DEMO_REFERENCES, demoState } from '../lib/recorded.js';
import Proof from './checker/Proof.jsx';
import { CaretMark, Icon, Pulse, VerdictIcon } from './ui.jsx';

/* The cover's demo, looping like a short film: the passage is typed in, its references pasted below, Check is
   pressed, and the recorded check plays: the references are looked up first, then each sentence gets its verdict,
   and the agent writes in the papers that do support the two that fail. */

const TYPE_START = 500;
const TYPE_RATE = 0.11; // characters per millisecond
const TYPE_END = TYPE_START + DEMO_PASSAGE.length / TYPE_RATE;
const REFS_START = TYPE_END + 250;
const REF_GAP = 230;
const CURSOR_START = REFS_START + REF_GAP * 4 + 250;
const PRESS = CURSOR_START + 700;
const CHECK_START = PRESS + 260;
const LAST_EVENT = CHECK_START + DEMO_EVENTS[DEMO_EVENTS.length - 1][0];
const SUMMARY = LAST_EVENT + 700;
const FADE = SUMMARY + 3600;
const LOOP = FADE + 700;

const short = (line) => line.replace(/^\[\d+\]\s*/, '');

export default function LoopDemo() {
  const { t } = useI18n();
  const reduce = useReducedMotion();
  const [clock, setClock] = useState(reduce ? SUMMARY + 1 : 0);

  useEffect(() => {
    if (reduce) { setClock(SUMMARY + 1); return undefined; }
    let start = performance.now();
    let last = start;
    const id = setInterval(() => {
      const now = performance.now();
      if (document.hidden) { start += now - last; last = now; return; } // a hidden tab holds the film still
      last = now;
      let at = now - start;
      if (at > LOOP) { start = now; at = 0; }
      setClock(at);
    }, 40);
    return () => clearInterval(id);
  }, [reduce]);

  const checking = clock >= CHECK_START;
  const applied = checking ? DEMO_EVENTS.filter(([ms]) => CHECK_START + ms <= clock).length : 0;
  const check = useMemo(() => demoState(applied), [applied]);
  const final = useMemo(() => demoState(DEMO_EVENTS.length), []);

  const typed = DEMO_PASSAGE.slice(0, Math.max(0, Math.floor((clock - TYPE_START) * TYPE_RATE)));
  const refsShown = Math.max(0, Math.min(4, Math.floor((clock - REFS_START) / REF_GAP) + 1)); // header, then 3 lines
  const cursor = Math.min(1, Math.max(0, (clock - CURSOR_START) / (PRESS - CURSOR_START)));
  const pressed = clock >= PRESS && clock < CHECK_START;
  const fading = clock >= FADE;

  return (
    <motion.div
      className="demo glass relative overflow-hidden rounded-[20px]"
      initial={reduce ? false : { opacity: 0, y: 28 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1.1, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center justify-between gap-4 border-b border-rule px-6 py-3.5 text-[13px]">
        <p className="flex items-center gap-2 font-semibold text-ink">
          <span className="grid h-[20px] w-[20px] place-items-center rounded-[6px] bg-[#0f1114] text-accent ring-1 ring-white/10">
            <CaretMark className="h-[12px] w-[12px]" />
          </span>
          {t('demo.label')}
        </p>
        <span className={`btn btn-primary btn-sm pointer-events-none h-8 px-3.5 text-[12.5px] transition-transform duration-150 ${pressed ? 'scale-[0.94]' : ''} ${checking ? 'opacity-40' : ''}`}>
          {t('checker.check')}
        </span>
      </div>

      {/* Both finished views sit invisibly underneath, so the card keeps one size the whole way through. */}
      <div className={`grid grid-cols-1 px-6 pb-6 pt-5 transition-opacity duration-500 [&>*]:col-start-1 [&>*]:row-start-1 ${fading ? 'opacity-0' : 'opacity-100'}`}>
        <div className="invisible" aria-hidden="true"><Editor typed={DEMO_PASSAGE} refsShown={4} /></div>
        <div className="invisible" aria-hidden="true"><Results check={final} summary t={t} /></div>
        <AnimatePresence mode="wait" initial={false}>
          {checking ? (
            <motion.div key="results" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
              <Results check={check} summary={clock >= SUMMARY} t={t} />
            </motion.div>
          ) : (
            <motion.div key="editor" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.3 }}>
              <Editor typed={typed} refsShown={refsShown} caret />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* the pointer that presses Check */}
      {!checking && cursor > 0 && (
        <span
          className="pointer-events-none absolute text-ink drop-shadow-[0_2px_3px_rgba(0,0,0,0.25)]"
          style={{ right: `${18 + (1 - easeOut(cursor)) * 150}px`, top: `${30 + (1 - easeOut(cursor)) * 230}px` }}
          aria-hidden="true"
        >
          <Icon as={MousePointer2} className={`h-[18px] w-[18px] fill-surface transition-transform duration-150 ${pressed ? 'scale-90' : ''}`} />
        </span>
      )}

      {/* how far through the loop the film is */}
      <span
        className="absolute bottom-0 left-0 h-[2px] bg-ink/25"
        style={{ width: `${Math.min(100, (clock / LOOP) * 100)}%` }}
        aria-hidden="true"
      />
    </motion.div>
  );
}

const easeOut = (x) => 1 - (1 - x) ** 3;

function Editor({ typed, refsShown, caret = false }) {
  const typing = refsShown === 0;
  return (
    <div className="demo-editor">
      <p>
        {typed}
        {caret && typing && <span className="type-caret" aria-hidden="true" />}
      </p>
      {refsShown > 0 && (
        <div className="mt-4">
          <p className="text-ink-2">References</p>
          {DEMO_REFERENCES.slice(0, refsShown - 1).map((line) => <p key={line} className="text-ink-2">{line}</p>)}
        </div>
      )}
    </div>
  );
}

function Results({ check, summary, t }) {
  const order = check.order.map((key) => check.pairs[key]);
  return (
    <div className="grid gap-4">
      <ol className="grid gap-1.5">
        {check.references.map((line, i) => {
          const e = check.refs[i + 1];
          const tone = !e ? 'pending' : e.verdict === 'verified' ? 'ok' : e.verdict === 'not_found' ? 'bad' : 'warn';
          return (
            <li key={line} className={`demo-ref is-${tone}`}>
              <span className="ref-num">{i + 1}</span>
              <span className="demo-ref-text">{short(line)}</span>
              <span className="ref-verdict">
                {e ? <><VerdictIcon name={tone === 'ok' ? 'check' : tone === 'bad' ? 'cross' : 'query'} />{t(tone === 'ok' ? 'refs.found' : tone === 'bad' ? 'refs.notFound' : 'refs.differ')}</> : <><Pulse />{t('refs.lookingUp')}</>}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="demo-text border-t border-rule pt-4">
        {check.citations.length
          ? <Proof body={check.body} citations={check.citations} pairs={check.pairs} order={check.order} />
          : <p className="proof">{check.body}</p>}
      </div>
      <ul className="grid gap-1.5 border-t border-rule pt-3.5 text-[13px]">
        {order.map((pair) => (
          <li key={pair.key} className={`demo-note is-${pair.tone}`}>
            <span className="note-ref">[{pair.ref}]</span>
            <span className="note-verdict">{pair.icon ? <VerdictIcon name={pair.icon} /> : <Pulse />}{t(pair.label)}</span>
            {pair.fix === 'replace' && (
              <span className="demo-fix">
                <CaretMark className="h-[12px] w-[12px]" />
                <span className="marker-stroke">{t('fix.citeInstead')}</span>
                <span className="text-ink-2">{pair.fixData.paper.short}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className={`text-[13px] font-medium text-ink transition-opacity duration-500 ${summary ? 'opacity-100' : 'opacity-0'}`}>
        {t('demo.summary')}
      </p>
    </div>
  );
}
