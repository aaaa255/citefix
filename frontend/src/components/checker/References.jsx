import { LIST_NUMBER, REFERENCE, SOURCES, safeUrl } from '../../lib/check.js';
import { Pulse, VerdictIcon } from '../ui.jsx';

/* The reference list under the manuscript, each labelled found, details differ or not found. */
export default function References({ references, refs }) {
  return (
    <section className="refs-col" aria-labelledby="refs-title">
      <h2 id="refs-title">References</h2>
      <ol className="ref-list">
        {references.map((text, i) => (
          <RefRow key={i} number={i + 1} text={text.replace(LIST_NUMBER, '')} event={refs[i + 1]} />
        ))}
      </ol>
    </section>
  );
}

export function RefRow({ number, text, event: e }) {
  if (!e) {
    return (
      <li className="ref is-pending">
        <span className="ref-num">{number}</span>
        <span className="ref-text">{text}</span>
        <span className="ref-verdict"><Pulse />Looking up</span>
      </li>
    );
  }
  const v = REFERENCE[e.verdict] || REFERENCE.suspicious;
  let detail = e.reason;
  if (e.verdict === 'verified' && e.paper) {
    const href = safeUrl(e.paper.url);
    detail = (
      <>
        Matched in {SOURCES[e.paper.source] || e.paper.source}
        {href && (
          <> · <a className="data" href={href} target="_blank" rel="noopener noreferrer">
            {e.paper.doi ? `doi:${e.paper.doi}` : href.replace(/^https?:\/\//, '')}
          </a></>
        )}
      </>
    );
  }
  return (
    <li className={`ref is-${v.tone}`}>
      <span className="ref-num">{number}</span>
      <span className="ref-text">{text}</span>
      <span className="ref-verdict"><VerdictIcon name={v.icon} />{v.label}</span>
      <span className="ref-detail">{detail}</span>
    </li>
  );
}
