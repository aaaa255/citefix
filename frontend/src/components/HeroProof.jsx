import { useEffect, useMemo, useRef, useState } from 'react';
import { motion, useInView, useReducedMotion } from 'motion/react';
import { RotateCcw } from 'lucide-react';
import { heroState, heroTimeline } from '../lib/recorded.js';
import Note from './checker/Note.jsx';
import Proof from './checker/Proof.jsx';
import { CaretMark, Icon, Pulse } from './ui.jsx';

const LAST = heroTimeline.length;
const FINAL = heroState(LAST);

/* The landing page's product preview: a recorded check of two sentences from the example, played through the
   checker's own reducer and components. One citation holds; the other cites an optimizer paper for batch
   normalization, and the agent finds the paper that does say it. */
export default function HeroProof() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.35 });
  const reduce = useReducedMotion();
  const [step, setStep] = useState(reduce ? LAST : 1);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (reduce) { setStep(LAST); return undefined; }
    if (!inView) return undefined;
    setStep(1);
    const timers = heroTimeline.slice(1).map(({ ms }, i) => setTimeout(() => setStep(i + 2), 650 + ms));
    return () => timers.forEach(clearTimeout);
  }, [inView, round, reduce]);

  const check = useMemo(() => heroState(step), [step]);
  const done = step >= LAST;
  const note = check.pairs['2-3'];

  return (
    <motion.div
      ref={ref}
      className="demo glass relative rounded-[20px] p-6 sm:p-7"
      initial={reduce ? false : { opacity: 0, y: 28 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1.1, delay: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="mb-5 flex h-6 items-center justify-between gap-4 text-[13px]">
        <p className="flex items-center gap-2 font-semibold text-accent"><CaretMark className="h-[15px] w-[15px]" />A recorded check</p>
        {done ? (
          <button type="button" className="inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-ink-3 transition-colors hover:text-ink" onClick={() => setRound((r) => r + 1)}>
            <Icon as={RotateCcw} className="h-[13px] w-[13px]" />Replay
          </button>
        ) : (
          <span className="inline-flex items-center gap-2 text-ink-3"><Pulse />Checking</span>
        )}
      </div>
      {/* The finished state sits invisibly underneath, so the card keeps its final size while the check plays. */}
      <div className="grid grid-cols-1 [&>*]:col-start-1 [&>*]:row-start-1">
        <div className="invisible" aria-hidden="true"><Scene check={FINAL} /></div>
        <Scene check={check} note={note} />
      </div>
    </motion.div>
  );
}

function Scene({ check, note = check.pairs['2-3'] }) {
  return (
    <div>
      <div className="demo-text">
        <Proof body={check.body} citations={check.citations} pairs={check.pairs} order={check.order} />
      </div>
      <div className="mt-4 border-t border-rule pt-3">
        {note && <Note pair={note} refEvent={check.refs[note.ref]} demo reasons={false} />}
      </div>
    </div>
  );
}
