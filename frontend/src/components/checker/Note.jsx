import { useContext, useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { Check, ChevronRight, Search, TriangleAlert, X } from 'lucide-react';
import { plural } from '../../lib/check.js';
import { CaretMark, Clamp, CopyButton, Icon, LayoutContext, LinkButton, Pulse, VerdictIcon } from '../ui.jsx';

/* One margin note: the verdict, the cited paper, the evidence, the agent's search and its fix.
   demo: the read-only version shown on the landing page (no buttons, no "Is this right?", the agent's trail left open);
   reasons={false} also leaves out the written reasons, for the smallest version. */
export default function Note({ pair, refEvent, hot = false, flash = false, onHot, onVote, onWhy, demo = false, reasons = true }) {
  const reduce = useReducedMotion();
  const classes = ['note', `is-${pair.tone}`, pair.repeat && 'is-repeat', hot && 'is-hot', flash && 'is-flash'].filter(Boolean).join(' ');
  const parts = reasons ? pair.parts : pair.parts.filter((part) => part.kind !== 'why');
  return (
    <motion.article
      className={classes}
      initial={reduce ? false : { opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      onMouseEnter={onHot && (() => onHot(pair.index))}
      onMouseLeave={onHot && (() => onHot(null))}
    >
      <header className="note-head">
        <span className="note-ref">[{pair.ref}]</span>
        <span className="note-verdict">
          {pair.icon ? <VerdictIcon name={pair.icon} /> : <Pulse />}
          {pair.label}
        </span>
      </header>
      {/* The start of the checked sentence, shown where the number alone cannot tell notes apart: on narrow screens,
          where the notes stack below the text, and for a number cited in more than one sentence. */}
      <p className="note-sentence" title={pair.sentence}>{pair.sentence}</p>
      <SourceLine event={refEvent} />
      <div className="note-body">
        {parts.map((part, i) => <Part key={i} part={part} pair={pair} demo={demo} />)}
        {pair.votable && !demo && <Vote pair={pair} onVote={onVote} onWhy={onWhy} />}
      </div>
    </motion.article>
  );
}

function SourceLine({ event: e }) {
  const paper = e && e.paper && e.verdict !== 'not_found' ? e.paper : null;
  return (
    <p className="note-source" title={paper ? `${paper.short} ${paper.title}` : undefined}>
      {paper && <>{paper.short.replace(/^\(|\)$/g, '')} · <cite>{paper.title}</cite></>}
      {e?.verdict === 'suspicious' && <span className="warn-text"> · {e.reason}</span>}
    </p>
  );
}

function Part({ part, pair, demo }) {
  switch (part.kind) {
    case 'why':
      return <Clamp className="why" lines={part.lines}>{part.text}</Clamp>;
    case 'evidence':
      return <Clamp as="blockquote" className={`evidence is-${part.tone}`} lines={part.lines}>“{part.text}”</Clamp>;
    case 'more':
      return <More part={part} />;
    case 'from':
      return <p className="from">{part.text}</p>;
    case 'agent':
      return pair.agent ? <AgentTrail agent={pair.agent} keepOpen={demo} /> : null;
    case 'fix':
      return pair.fixData ? <Fix pair={pair} demo={demo} /> : null;
    default:
      return null;
  }
}

function More({ part }) {
  const layoutSoon = useContext(LayoutContext);
  return (
    <details className="more" onToggle={layoutSoon}>
      <summary>What the abstract says</summary>
      <blockquote className={`evidence is-${part.tone}`}>“{part.text}”</blockquote>
    </details>
  );
}

/* Open while the agent works; collapses to "Agent searched N times" when it finishes. */
function AgentTrail({ agent, keepOpen }) {
  const [open, setOpen] = useState(true);
  const layoutSoon = useContext(LayoutContext);
  useEffect(() => {
    if (agent.finished && !keepOpen) setOpen(false);
  }, [agent.finished, keepOpen]);
  return (
    <details className="agent" open={open} onToggle={(e) => { setOpen(e.currentTarget.open); layoutSoon(); }}>
      <summary className="agent-head">
        {agent.finished
          ? <><Icon as={ChevronRight} />Agent searched {plural(agent.searches, 'time')}</>
          : <><Pulse />Agent is looking for a paper that supports this</>}
      </summary>
      <ol className="trail">
        {agent.trail.map((step, i) => {
          if (step.kind === 'search') {
            return (
              <li key={i} className="is-search">
                <Icon as={Search} /><span>“{step.detail}”</span><span className="count">{plural(step.results, 'result')}</span>
              </li>
            );
          }
          if (step.kind === 'failed') {
            return <li key={i} className="is-failed" title={step.title}><span /><span>{step.text}</span><span /></li>;
          }
          return <li key={i} className="is-rejected"><Icon as={X} /><span>Suggestion sent back: {step.detail}</span><span /></li>;
        })}
      </ol>
    </details>
  );
}

function Fix({ pair, demo }) {
  const f = pair.fixData;
  if (f.type === 'replace' || f.type === 'candidate') {
    const replace = f.type === 'replace';
    return (
      <div className="fix">
        <p className="fix-label">{replace ? <CaretMark /> : <Icon as={TriangleAlert} />}{replace ? 'Cite instead' : 'Possible source'}</p>
        <Clamp className="fix-ref" lines={3}>{f.paper.apa}</Clamp>
        {f.quote && <Clamp as="blockquote" className="evidence is-fix" lines={3}>“{f.quote}”</Clamp>}
        <p className="fix-check">{f.checkLine}</p>
        {!demo && (
          <div className="fix-actions">
            <CopyButton label="Copy reference" text={f.paper.apa} />
            <LinkButton label="Open paper" url={f.paper.url} />
          </div>
        )}
      </div>
    );
  }
  if (f.type === 'rewrite') {
    const whose = f.keeps ? `the abstract of [${pair.ref}]` : 'this abstract';
    return (
      <div className="fix">
        <p className="fix-label">
          <CaretMark />
          {f.keeps ? 'Rewrite the sentence' : `Rewrite the sentence and cite this paper instead of [${pair.ref}]`}
        </p>
        <p className="fix-text">{f.rewritten}</p>
        {!f.keeps && <Clamp className="fix-ref" lines={3}>{f.paper.apa}</Clamp>}
        {f.quote && <Clamp as="blockquote" className="evidence is-fix" lines={3}>“{f.quote}”</Clamp>}
        {f.check && <p className="fix-check">A separate check agrees {whose} supports the rewritten sentence.</p>}
        {f.explanation && !demo && <Clamp className="why" lines={2}>{f.explanation}</Clamp>}
        {!demo && (
          <div className="fix-actions">
            <CopyButton label="Copy sentence" text={f.rewritten} />
            {!f.keeps && <><CopyButton label="Copy reference" text={f.paper.apa} /><LinkButton label="Open paper" url={f.paper.url} /></>}
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="fix">
      <p className="fix-none">No supporting paper found.</p>
      {f.explanation && !demo && <Clamp className="why" lines={2}>{f.explanation}</Clamp>}
    </div>
  );
}

/* The tester's mark on a finished note. */
function Vote({ pair, onVote, onWhy }) {
  const options = [['right', Check, 'Yes'], ['wrong', X, 'No']];
  return (
    <>
      <div className="vote" role="group" aria-label={`Is the check of [${pair.ref}] right?`}>
        <span className="vote-q">Is this right?</span>
        {options.map(([value, glyph, label]) => (
          <button key={value} type="button" className="vote-btn" aria-pressed={pair.vote === value} onClick={() => onVote(pair.key, value)}>
            <Icon as={glyph} />{label}
          </button>
        ))}
      </div>
      {pair.vote === 'wrong' && (
        <textarea
          className="field vote-why"
          rows={2}
          maxLength={1000}
          placeholder="What’s wrong? (optional)"
          aria-label={`What is wrong with the check of [${pair.ref}]`}
          value={pair.why}
          onChange={(e) => onWhy(pair.key, e.target.value)}
        />
      )}
    </>
  );
}
