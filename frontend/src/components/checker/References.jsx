import { LIST_NUMBER, REFERENCE, SOURCES, safeUrl } from '../../lib/check.js';
import { useI18n } from '../../lib/i18n.jsx';
import { Pulse, VerdictIcon } from '../ui.jsx';

/* The reference list, shown above the passage once a check starts: whether each cited paper exists is the first
   thing a check settles, so it is the first thing to read. */
export default function References({ references, refs }) {
  const { t } = useI18n();
  const events = references.map((_, i) => refs[i + 1]);
  const done = events.filter(Boolean);
  const counts = {
    found: done.filter((e) => e.verdict === 'verified').length,
    differ: done.filter((e) => e.verdict === 'suspicious').length,
    missing: done.filter((e) => e.verdict === 'not_found').length,
  };
  return (
    <section className="refs-col" aria-labelledby="refs-title">
      <h2 id="refs-title">
        {t('refs.title')}
        {done.length > 0 && <span className="refs-summary">{t('refs.summary', counts)}</span>}
      </h2>
      <ol className="ref-list">
        {references.map((text, i) => (
          <RefRow key={i} number={i + 1} text={text.replace(LIST_NUMBER, '')} event={events[i]} />
        ))}
      </ol>
    </section>
  );
}

export function RefRow({ number, text, event: e }) {
  const { t } = useI18n();
  if (!e) {
    return (
      <li className="ref is-pending">
        <span className="ref-num">{number}</span>
        <span className="ref-text">{text}</span>
        <span className="ref-verdict"><Pulse />{t('refs.lookingUp')}</span>
      </li>
    );
  }
  const v = REFERENCE[e.verdict] || REFERENCE.suspicious;
  let detail = e.reason;
  if (e.verdict === 'verified' && e.paper) {
    const href = safeUrl(e.paper.url);
    detail = (
      <>
        {t('refs.matchedIn', { source: SOURCES[e.paper.source] || e.paper.source })}
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
      <span className="ref-verdict"><VerdictIcon name={v.icon} />{t(v.label)}</span>
      <span className="ref-detail">{detail}</span>
    </li>
  );
}
