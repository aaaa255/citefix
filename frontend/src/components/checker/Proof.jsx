import { Fragment, useMemo } from 'react';
import { proofLayout, splitMarkers, worstTone } from '../../lib/check.js';
import { CaretMark } from '../ui.jsx';

const noop = () => false;

/* The manuscript as a proof: each checked sentence is underlined in the ink of its worst verdict, each citation
   number in its own verdict's ink, and a "Cite instead" fix is written in after the sentence in blue pencil. */
export default function Proof({
  body, citations, pairs, order, hot = null, onHot = noop, onClause = noop, onMarker = noop, clauses, innerRef,
}) {
  const paragraphs = useMemo(() => proofLayout(body, citations), [body, citations]);
  const bySentence = useMemo(() => {
    const map = new Map();
    for (const key of order) {
      const pair = pairs[key];
      if (!map.has(pair.index)) map.set(pair.index, []);
      map.get(pair.index).push(pair);
    }
    return map;
  }, [pairs, order]);

  return (
    <article ref={innerRef} className="proof" aria-label="Manuscript with marks">
      {paragraphs.map((paragraph) => (
        <p key={paragraph.key}>
          {paragraph.pieces.map((piece, i) => (piece.clause == null
            ? <Fragment key={i}>{piece.text}</Fragment>
            : (
              <Clause
                key={`c${piece.clause}`}
                index={piece.clause}
                text={piece.text}
                pairs={bySentence.get(piece.clause) || []}
                hot={hot === piece.clause}
                onHot={onHot}
                onClause={onClause}
                onMarker={onMarker}
                clauses={clauses}
              />
            )))}
        </p>
      ))}
    </article>
  );
}

function Clause({ index, text, pairs, hot, onHot, onClause, onMarker, clauses }) {
  const segments = useMemo(() => splitMarkers(text), [text]);
  const tone = pairs.length ? worstTone(pairs.map((p) => p.tone)) : 'pending';
  const byRef = new Map(pairs.map((p) => [p.ref, p]));
  const replaced = pairs.filter((p) => p.fix === 'replace' && p.fixData?.paper);
  const struck = new Set(replaced.map((p) => String(p.ref)));
  const register = (node) => {
    if (!clauses) return;
    if (node) clauses.current.set(index, node);
    else clauses.current.delete(index);
  };

  return (
    <>
      <span
        ref={register}
        className={`clause is-${tone}${hot ? ' is-hot' : ''}`}
        data-sentence={index}
        onMouseEnter={() => onHot(index)}
        onMouseLeave={() => onHot(null)}
        onClick={() => onClause(index)}
      >
        {segments.map((seg, i) => {
          if (!seg.marker) return <Fragment key={i}>{seg.text}</Fragment>;
          const mine = seg.refs.map((ref) => byRef.get(ref)).filter(Boolean);
          const markTone = mine.length ? worstTone(mine.map((p) => p.tone)) : null;
          const classes = ['marker', markTone && `is-${markTone}`, struck.has(seg.refs.join(',')) && 'is-struck'].filter(Boolean).join(' ');
          return (
            <span
              key={i}
              className={classes}
              title={mine.map((p) => `[${p.ref}] ${p.label}`).join('\n') || undefined}
              onClick={(e) => {
                // a number leads to its own note, not the sentence's first one
                if (seg.refs.length && onMarker(index, seg.refs[0])) e.stopPropagation();
              }}
            >
              {seg.marker}
            </span>
          );
        })}
      </span>
      {replaced.map((p) => (
        <ins key={p.key} className="insert" title="Suggested citation">
          <CaretMark />{p.fixData.paper.short}
        </ins>
      ))}
    </>
  );
}
