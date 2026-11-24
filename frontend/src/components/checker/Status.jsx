import { Fragment } from 'react';
import { ChevronRight, X } from 'lucide-react';
import { plural } from '../../lib/check.js';
import { Icon } from '../ui.jsx';

/* The status line at the top of the margin: progress while a check runs, then what it found. */
export default function Status({ status, onJump }) {
  if (!status) return <div className="status" role="status" aria-live="polite" />;
  if (status.kind === 'error') {
    return (
      <div className="status" role="status" aria-live="polite">
        <div className="alert" role="alert"><Icon as={X} /><span>{status.text}</span></div>
      </div>
    );
  }
  if (status.kind === 'summary') {
    const recorded = status.recorded ? ' (recorded)' : '';
    return (
      <div className="status" role="status" aria-live="polite">
        {plural(status.count, 'citation')} checked in {Math.round(status.seconds)} s{recorded}:{' '}
        {status.parts.map(([tone, text], i) => (
          <Fragment key={i}>
            {i ? (i === status.parts.length - 1 ? ' and ' : ', ') : ''}
            <strong className={`is-${tone}`}>{text}</strong>
          </Fragment>
        ))}
        .
        <br />
        <button type="button" className="btn btn-text jump" onClick={onJump}>
          Rate this check<Icon as={ChevronRight} />
        </button>
      </div>
    );
  }
  return (
    <div className={`status${status.tone ? ` is-${status.tone}` : ''}`} role="status" aria-live="polite">
      {status.text}
    </div>
  );
}
