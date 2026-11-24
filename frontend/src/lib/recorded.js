/* A real check of the example passage, recorded with `python -m citefix serve --record` (eval/results/web-run.ndjson).
   The cover replays three of its four citations, numbered 1 to 3: one that holds, one that cites an optimizer paper
   for batch normalization, and one whose reference does not exist. The papers, verdicts, quotes and fixes are the
   recorded run's; only the numbering and the shortened reference lines are the cover's. */
import events from '../data/recorded-check.json';
import { initialState, reduce } from './check.js';

const find = (type, test = () => true) => events.find((e) => e.type === type && test(e));
const recordedItems = find('citations').items;

const REF = { 1: 1, 3: 2, 4: 3 }; // recorded reference number -> cover number
const SENTENCE = { 0: 0, 2: 1, 3: 2 }; // recorded sentence index -> cover index
const renumber = (text) => text.replace(/\[(\d+)\]/g, (match, n) => (REF[n] ? `[${REF[n]}]` : match));

const items = [0, 2, 3].map((index) => {
  const item = recordedItems.find((it) => it.index === index);
  return { ...item, index: SENTENCE[index], sentence: renumber(item.sentence), refs: item.refs.map((r) => REF[r]) };
});

export const DEMO_PASSAGE = items.map((item) => item.sentence).join(' ');
export const DEMO_REFERENCES = [
  '[1] Vaswani, A., et al. (2017). Attention is all you need. NeurIPS.',
  '[2] Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic optimization. ICLR.',
  '[3] Kowalski, A., Dubois, M., & Sato, K. (2023). Self-verifying language agents for automated literature review.',
];

const moved = (e) => ({ ...e, index: SENTENCE[e.index], ref: REF[e.ref] });
const reference = (n) => ({ ...find('reference', (e) => e.number === n), number: REF[n] });

/* The cover's events in the order a check sends them, each with when it lands (ms after Check is pressed). */
export const DEMO_EVENTS = [
  [0, { type: 'start', body: DEMO_PASSAGE, references: DEMO_REFERENCES }],
  [250, { type: 'citations', items }],
  [700, reference(1)],
  [1100, reference(3)],
  [1500, reference(4)],
  [2300, moved(find('support', (e) => e.ref === 1))],
  [3100, moved(find('support', (e) => e.ref === 3))],
  [3600, moved(find('note', (e) => e.ref === 4))],
  [3700, moved(find('agent_start', (e) => e.ref === 3))],
  [3800, moved(find('agent_start', (e) => e.ref === 4))],
  [5000, moved(find('repair', (e) => e.ref === 3))],
  [5600, moved(find('repair', (e) => e.ref === 4))],
];

export function demoState(count) {
  let state = reduce(initialState, { type: 'begin', id: 'demo' });
  for (const [, event] of DEMO_EVENTS.slice(0, count)) state = reduce(state, { type: 'event', event });
  return state.check;
}
