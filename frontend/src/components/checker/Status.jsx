import { Fragment } from 'react';
import { ChevronRight, X } from 'lucide-react';
import { useI18n } from '../../lib/i18n.jsx';
import { Icon } from '../ui.jsx';

/* The status line at the top of the margin: progress while a check runs, then what it found. */
export default function Status({ status, onRate }) {
  const { t, lang } = useI18n();
  if (!status) return <div className="status" role="status" aria-live="polite" />;
  if (status.kind === 'error') {
    return (
      <div className="status" role="status" aria-live="polite">
        <div className="alert" role="alert"><Icon as={X} /><span>{status.key ? t(status.key, status.params) : status.text}</span></div>
      </div>
    );
  }
  if (status.kind === 'summary') {
    const and = { en: ' and ', es: ' y ', zh: '，' }[lang] || ' and ';
    const comma = lang === 'zh' ? '，' : ', ';
    return (
      <div className="status" role="status" aria-live="polite">
        {t('status.summary', { n: status.count, seconds: Math.round(status.seconds), recorded: status.recorded })}
        {status.parts.map(([tone, key, n], i) => (
          <Fragment key={key}>
            {i ? (i === status.parts.length - 1 ? and : comma) : ''}
            <strong className={tone === 'fix' ? 'is-fix marker-stroke' : `is-${tone}`}>{t(key, { n })}</strong>
          </Fragment>
        ))}
        {lang === 'zh' ? '。' : '.'}
        <br />
        <button type="button" className="btn btn-text jump" onClick={onRate}>
          {t('status.rate')}<Icon as={ChevronRight} />
        </button>
      </div>
    );
  }
  return (
    <div className={`status${status.tone ? ` is-${status.tone}` : ''}`} role="status" aria-live="polite">
      {status.kind === 'raw' ? status.text : t(status.key, status.params || undefined)}
    </div>
  );
}
