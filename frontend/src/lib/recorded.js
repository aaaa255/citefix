/* A real check of the example passage, recorded with `python -m citefix serve --record` (eval/results/web-run.ndjson).
   The landing page shows it through the same reducer and components as the live checker, labelled as recorded. */
import events from '../data/recorded-check.json';
import { initialState, reduce } from './check.js';

function play(list) {
  let state = reduce(initialState, { type: 'begin', id: 'recorded' });
  for (const event of list) state = reduce(state, { type: 'event', event });
  return state;
}

/* The finished check, for the step-by-step section. */
export const recorded = play(events).check;

const find = (type, test = () => true) => events.find((e) => e.type === type && test(e));
const start = find('start');
const items = find('citations').items;
const sentence = (index) => items.find((item) => item.index === index);

/* The hero's two sentences: one supported, one citing the wrong paper, which the agent replaces. */
const heroItems = [sentence(0), sentence(2)];
const heroBody = heroItems.map((item) => item.sentence).join(' ');
const at = (e, ms) => ({ ms, event: e });
export const heroTimeline = [
  at({ ...start, body: heroBody }, 0),
  at({ type: 'citations', items: heroItems }, 380),
  at(find('reference', (e) => e.number === 1), 760),
  at(find('reference', (e) => e.number === 3), 900),
  at(find('support', (e) => e.ref === 1), 1500),
  at(find('support', (e) => e.ref === 3), 2350),
  at(find('agent_start', (e) => e.ref === 3), 2900),
  at(find('agent_step', (e) => e.ref === 3 && e.action === 'search'), 3500),
  at(find('repair', (e) => e.ref === 3), 4900),
];

export function heroState(upTo) {
  let state = reduce(initialState, { type: 'begin', id: 'hero' });
  for (const { event } of heroTimeline.slice(0, upTo)) state = reduce(state, { type: 'event', event });
  return state.check;
}

export const recordedSeconds = find('done').seconds;
