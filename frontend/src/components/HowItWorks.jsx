import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { LIST_NUMBER } from '../lib/check.js';
import { recorded } from '../lib/recorded.js';
import Note from './checker/Note.jsx';
import Proof from './checker/Proof.jsx';
import { RefRow } from './checker/References.jsx';
import { Reveal } from './ui.jsx';

const STEPS = [
  {
    title: 'Does the paper exist?',
    body: 'Each reference is looked up in OpenAlex, Crossref and arXiv, and by its DOI when it has one. Those records alone decide whether it exists.',
  },
  {
    title: 'Does it support the sentence?',
    body: 'DeepSeek reads the cited abstract against your sentence. A “supported” verdict has to quote that abstract, and citefix checks the quote is really there.',
  },
  {
    title: 'If not, which paper does?',
    body: 'An agent searches the indexes for one that does. Its pick stands only if its own search found it, the quote is in the abstract, and a second check agrees.',
  },
];

/* Every scene is cut from the same recorded check, rendered by the checker's own components. */
function sentenceOf(index) {
  const item = recorded.citations.find((c) => c.index === index);
  const keys = recorded.order.filter((key) => recorded.pairs[key].index === index);
  return { item, keys };
}

function ExistsScene() {
  const row = (n) => (
    <RefRow key={n} number={n} text={recorded.references[n - 1].replace(LIST_NUMBER, '')} event={recorded.refs[n]} />
  );
  return (
    <div>
      <p className="col-label">References</p>
      <ol className="ref-list">{[2, 4].map(row)}</ol>
    </div>
  );
}

function SentenceScene({ index }) {
  const { item, keys } = sentenceOf(index);
  const pair = recorded.pairs[keys[0]];
  return (
    <div>
      <div className="demo-text">
        <Proof body={item.sentence} citations={[item]} pairs={recorded.pairs} order={keys} />
      </div>
      <div className="mt-4 border-t border-rule pt-3">
        <Note pair={pair} refEvent={recorded.refs[pair.ref]} demo />
      </div>
    </div>
  );
}

const SCENES = [
  () => <ExistsScene />,
  () => <SentenceScene index={1} />,
  () => <SentenceScene index={3} />,
];

function SceneCard({ active }) {
  const reduce = useReducedMotion();
  const Scene = SCENES[active];
  return (
    <div className="demo relative flex min-h-[460px] flex-col justify-center rounded-[20px] border border-rule bg-surface p-7 shadow-[0_40px_80px_-56px_hsl(var(--shadow)/0.5)] sm:p-9">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={active}
          initial={reduce ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: -10 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <Scene />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export default function HowItWorks() {
  const [active, setActive] = useState(0);
  return (
    <section id="how" className="relative py-28 lg:py-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <Reveal className="max-w-3xl">
          <h2 className="h-section">Three questions for every citation.</h2>
          <p className="lede mt-5">Each one is answered from a record you can open, never from what a model remembers.</p>
        </Reveal>
        <div className="mt-10 grid grid-cols-1 gap-10 lg:mt-6 lg:grid-cols-12 lg:gap-16">
          <div className="hidden lg:col-span-7 lg:block">
            <div className="sticky top-[calc(50vh-230px)]">
              <SceneCard active={active} />
            </div>
          </div>
          <ol className="lg:col-span-5">
            {STEPS.map((step, i) => {
              const Scene = SCENES[i];
              return (
                <motion.li
                  key={step.title}
                  onViewportEnter={() => setActive(i)}
                  viewport={{ margin: '-45% 0px -45% 0px' }}
                  className={`flex flex-col justify-center py-10 transition-opacity duration-500 lg:min-h-[78vh] ${
                    active === i ? 'lg:opacity-100' : 'lg:opacity-30'
                  }`}
                >
                  <h3 className="text-[clamp(1.6rem,2.3vw,2.1rem)] font-semibold leading-[1.12] tracking-[-0.03em]">{step.title}</h3>
                  <p className="lede mt-4">{step.body}</p>
                  <div className="demo mt-8 rounded-[20px] border border-rule bg-surface p-6 lg:hidden"><Scene /></div>
                </motion.li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
