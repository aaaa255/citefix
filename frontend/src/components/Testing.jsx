import { useRef } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { Activity, Bot, ChevronLeft, ChevronRight, FlaskConical, RotateCcw, User } from 'lucide-react';
import { Icon, Reveal } from './ui.jsx';

/* Numbers and changes from README.md ("How it was tested"); nothing here is invented or rounded up. */
const RESULTS = [
  { figure: '10 of 10', label: 'made-up references caught', detail: 'Step 1, on 28 references in four styles' },
  { figure: '14 of 14', label: 'claim and reference pairs judged right', detail: 'Step 2, with all 13 quotes found in their abstracts' },
  { figure: '7 of 7', label: 'failing citations given a real source or a rewrite', detail: 'Step 3, on 5 wrong citations and 2 false claims' },
  { figure: '4.2 of 5', label: 'a classmate’s average rating', detail: 'Five checks on the live site, all six notes marked right' },
];

/* Who ran each test is written on its card, as the README records it. */
const CHANGES = [
  {
    who: 'Test sets', icon: FlaskConical,
    found: 'GAN (2014) was marked suspicious: a better-cited 2020 paper with almost the same title ranked first.',
    changed: 'The checker now searches again within the cited year.',
  },
  {
    who: 'Test sets', icon: FlaskConical,
    found: 'OpenAlex writes GPT-3’s first author as “Brown, Tom B.”, which broke author matching.',
    changed: 'Matching now ignores name order.',
  },
  {
    who: 'Live run', icon: Activity,
    found: 'arXiv timed out and left the agent with no results.',
    changed: 'Timeouts no longer retry, Crossref became a search source, and failed sources show in the agent’s trail.',
  },
  {
    who: 'Simulated user, an AI agent', icon: Bot,
    found: '“Cite instead” appeared for a paper that only partly supported the sentence.',
    changed: '“Cite instead” now needs a clear failure and a replacement that fully supports it. Anything else is a possible source.',
  },
  {
    who: 'Simulated user, an AI agent', icon: Bot,
    found: 'Two verdicts in one sentence shared one underline.',
    changed: 'Each citation number now takes its own verdict’s ink.',
  },
  {
    who: 'Classmate', icon: User,
    found: 'A reference with BERT’s NAACL 2019 DOI was shown as the 2018 arXiv preprint.',
    changed: 'References are also looked up by DOI, and a DOI that leads to a different paper makes a reference suspicious.',
  },
  {
    who: 'Classmate', icon: User,
    found: 'A rewritten sentence lost its “[1]”.',
    changed: 'Rewrites keep their citation numbers, on screen and when copied.',
  },
  {
    who: 'Rerun of step 1', icon: RotateCcw,
    found: 'The version picked for BERT, RAG and ResNet changed between runs.',
    changed: 'citefix now prefers the cited year, then the published version. All 28 verdicts stayed the same.',
  },
];

export default function Testing() {
  const track = useRef(null);
  const reduce = useReducedMotion();
  const scroll = (direction) => {
    const el = track.current;
    if (!el) return;
    const card = el.querySelector('li');
    const step = card ? card.getBoundingClientRect().width + 16 : 360;
    el.scrollBy({ left: direction * step, behavior: reduce ? 'auto' : 'smooth' });
  };

  return (
    <section id="testing" className="relative overflow-hidden bg-bg-deep py-28 lg:py-36">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-10">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-16">
          <Reveal className="lg:col-span-5">
            <h2 className="h-section">What testing caught, and what it changed.</h2>
            <p className="lede mt-6">
              Small hand-written test sets built on well-known papers, so the numbers are a sanity check, not a benchmark.
              The model may already know these papers.
            </p>
          </Reveal>
          <dl className="grid grid-cols-1 gap-x-10 gap-y-10 sm:grid-cols-2 lg:col-span-7">
            {RESULTS.map((r, i) => (
              <motion.div
                key={r.figure + r.label}
                className="flex flex-col border-t border-rule-strong pt-5"
                initial={reduce ? false : { opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: 0.7, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              >
                <dt className="text-[15px] font-medium text-ink">{r.label}</dt>
                <dd className="order-first mb-2 text-[clamp(2.4rem,3.6vw,3.25rem)] font-semibold leading-none tracking-[-0.04em] tabular-nums text-ink">{r.figure}</dd>
                <dd className="mt-1.5 text-[13.5px] text-ink-3">{r.detail}</dd>
              </motion.div>
            ))}
          </dl>
        </div>

        <div className="mt-24 flex items-end justify-between gap-6">
          <Reveal as="h3" className="text-[clamp(1.4rem,2vw,1.75rem)] font-semibold tracking-[-0.025em]">
            Each round of testing changed the build.
          </Reveal>
          <div className="hidden gap-2 sm:flex">
            <button type="button" className="btn btn-ghost h-11 w-11 px-0" onClick={() => scroll(-1)} aria-label="Earlier changes"><Icon as={ChevronLeft} /></button>
            <button type="button" className="btn btn-ghost h-11 w-11 px-0" onClick={() => scroll(1)} aria-label="Later changes"><Icon as={ChevronRight} /></button>
          </div>
        </div>
        {/* One row per part of a card (who, what was found, what changed), shared through subgrid so the
            "Changed" rules line up across every card. */}
        <ol
          ref={track}
          className="no-scrollbar -mx-6 mt-8 grid auto-cols-[min(340px,82vw)] grid-flow-col grid-rows-[auto_auto_auto] gap-x-4 overflow-x-auto scroll-px-6 px-6 pb-4 snap-x snap-mandatory lg:-mx-10 lg:scroll-px-10 lg:px-10"
          aria-label="What each test found and what changed"
        >
          {CHANGES.map((c, i) => (
            <li key={i} className="row-span-3 grid snap-start grid-rows-subgrid rounded-[20px] border border-rule bg-surface px-6 pb-6 pt-5">
              <p className="flex items-center gap-2 text-[13px] font-medium text-ink-3"><Icon as={c.icon} className="h-[15px] w-[15px]" />{c.who}</p>
              <p className="mt-4 text-[15.5px] leading-[1.55] text-ink">{c.found}</p>
              <div className="mt-6 border-t border-dashed border-rule-strong pt-4">
                <p className="text-[13px] font-semibold text-accent">Changed</p>
                <p className="mt-1.5 text-[14.5px] leading-[1.55] text-ink-2">{c.changed}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
