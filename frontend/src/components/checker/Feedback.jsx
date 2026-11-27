import { useState } from 'react';
import { feedbackPayload } from '../../lib/check.js';
import { useCheck } from '../../lib/CheckContext.jsx';
import { useI18n } from '../../lib/i18n.jsx';

const RATINGS = [1, 2, 3, 4, 5];

/* "How did citefix do?", in the menu: how many notes were marked, a rating and a comment for the latest check.
   Nothing is sent until the tester presses the button. Keyed by the check, so a new check starts with an empty form. */
export default function Feedback({ check }) {
  const { t } = useI18n();
  const { dispatch, tester } = useCheck();
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState('');
  const [line, setLine] = useState({ key: '', tone: '' });
  const [sending, setSending] = useState(false);
  const [sentAs, setSentAs] = useState(null); // the payload last sent, to tell when something changed since

  const pairs = check.order.map((key) => check.pairs[key]);
  const votable = pairs.filter((p) => p.votable);
  const marked = votable.filter((p) => p.vote).length;
  let marks = t('fb.marked', { marked, total: votable.length });
  if (!votable.length) marks = t('fb.nothing');
  else if (!marked) marks = t('fb.markSome');

  const payload = feedbackPayload(check, { rating, comment, tester });
  const body = JSON.stringify(payload);
  const sent = Boolean(check.sentId);
  const changed = sent && body !== sentAs;

  async function send() {
    if (!payload.citations.some((c) => c.vote) && !payload.rating && !payload.comment) {
      setLine({ key: 'fb.empty', tone: 'error' });
      return;
    }
    setSending(true);
    setLine({ key: 'fb.sending', tone: '' });
    try {
      const response = await fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || t('status.serverError', { code: response.status }));
      dispatch({ type: 'sent', checkId: check.id, id: data.id });
      setSentAs(body);
      setLine({ key: 'fb.thanks', tone: 'sent' });
    } catch (err) {
      setLine(err instanceof TypeError ? { key: 'fb.unreachable', tone: 'error' } : { text: err.message, tone: 'error' });
    } finally {
      setSending(false);
    }
  }

  const label = sent ? (changed ? t('fb.update') : t('fb.sent')) : t('fb.send');
  const state = changed && !sending ? { key: 'fb.changed', tone: '' } : line;

  return (
    <section className="feedback" aria-labelledby="feedback-title">
      <h3 id="feedback-title">{t('fb.title')}</h3>
      <p className="feedback-marks">{marks}</p>
      <fieldset className="rating">
        <legend>{t('fb.useful')}</legend>
        <div className="rating-scale">
          {RATINGS.map((n) => (
            <label key={n}>
              <input type="radio" name={`rating-${check.id}`} value={n} checked={rating === n} onChange={() => setRating(n)} />
              <span className="box">
                {n}
                {n === 1 && <span className="visually-hidden">, {t('fb.notUseful')}</span>}
                {n === 5 && <span className="visually-hidden">, {t('fb.veryUseful')}</span>}
              </span>
            </label>
          ))}
        </div>
        <p className="rating-ends" aria-hidden="true"><span>{t('fb.notUseful')}</span><span>{t('fb.veryUseful')}</span></p>
      </fieldset>
      <label className="field-label" htmlFor="fb-comment">{t('fb.comment')}</label>
      <textarea id="fb-comment" className="field" rows={3} maxLength={4000} value={comment} onChange={(e) => setComment(e.target.value)} />
      <p className="feedback-fine">{t('fb.fine')}</p>
      <div className="feedback-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={send} disabled={sending || (sent && !changed)}>{label}</button>
        <span className={`feedback-state${state.tone ? ` is-${state.tone}` : ''}`} role="status" aria-live="polite">
          {state.key ? t(state.key) : state.text}
        </span>
      </div>
      <p className="feedback-fine">{tester.trim() ? t('fb.signed', { name: tester.trim() }) : t('fb.unsigned')}</p>
    </section>
  );
}
