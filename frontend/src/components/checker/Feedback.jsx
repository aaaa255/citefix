import { useState } from 'react';
import { TESTER_KEY, feedbackPayload, plural } from '../../lib/check.js';

const RATINGS = [1, 2, 3, 4, 5];

/* After a check: how many notes were marked, a rating, a comment and an optional name. Nothing is sent until the
   tester presses the button. Keyed by the check, so a new check starts with an empty form. */
export default function Feedback({ check, tester, onTester, onSent, panelRef }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState('');
  const [line, setLine] = useState({ text: '', tone: '' });
  const [sending, setSending] = useState(false);
  const [sentAs, setSentAs] = useState(null); // the payload last sent, to tell when something changed since

  const pairs = check.order.map((key) => check.pairs[key]);
  const votable = pairs.filter((p) => p.votable);
  const marked = votable.filter((p) => p.vote).length;
  let marks = `You marked ${marked} of ${plural(votable.length, 'note')}.`;
  if (!votable.length) marks = 'Nothing was checked this time, but a comment still helps.';
  else if (!marked) marks = 'Mark each note above Yes or No if you can tell whether it is right.';

  const payload = feedbackPayload(check, { rating, comment, tester });
  const body = JSON.stringify(payload);
  const sent = Boolean(check.sentId);
  const changed = sent && body !== sentAs;

  async function send() {
    if (!payload.citations.some((c) => c.vote) && !payload.rating && !payload.comment) {
      setLine({ text: 'Mark a note right or wrong, choose a rating or write a comment first.', tone: 'error' });
      return;
    }
    try { localStorage.setItem(TESTER_KEY, payload.tester); } catch { /* storage blocked: the name is not remembered */ }
    setSending(true);
    setLine({ text: 'Sending…', tone: '' });
    try {
      const response = await fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message || `The server answered with an error (${response.status}).`);
      onSent(check.id, data.id);
      setSentAs(body);
      setLine({ text: 'Thank you, your feedback was sent.', tone: 'sent' });
    } catch (err) {
      setLine({
        text: err instanceof TypeError ? 'The citefix server could not be reached. Try again in a moment.' : err.message,
        tone: 'error',
      });
    } finally {
      setSending(false);
    }
  }

  const label = sent ? (changed ? 'Send update' : 'Sent') : 'Send feedback';
  const state = changed && !sending ? { text: 'Changes not sent yet.', tone: '' } : line;

  return (
    <section ref={panelRef} className="feedback" aria-labelledby="feedback-title">
      <h3 id="feedback-title">How did citefix do?</h3>
      <p className="feedback-marks">{marks}</p>
      <fieldset className="rating">
        <legend>How useful was this check?</legend>
        <div className="rating-scale">
          {RATINGS.map((n) => (
            <label key={n}>
              <input type="radio" name={`rating-${check.id}`} value={n} checked={rating === n} onChange={() => setRating(n)} />
              <span className="box">
                {n}
                {n === 1 && <span className="visually-hidden">, not useful</span>}
                {n === 5 && <span className="visually-hidden">, very useful</span>}
              </span>
            </label>
          ))}
        </div>
        <p className="rating-ends" aria-hidden="true"><span>Not useful</span><span>Very useful</span></p>
      </fieldset>
      <label className="field-label" htmlFor="fb-comment">What was wrong, confusing or missing?</label>
      <textarea id="fb-comment" className="field" rows={3} maxLength={4000} value={comment} onChange={(e) => setComment(e.target.value)} />
      <label className="field-label" htmlFor="fb-tester">Your name or initials <span className="optional">(optional)</span></label>
      <input id="fb-tester" className="field" type="text" maxLength={60} autoComplete="nickname" value={tester} onChange={(e) => onTester(e.target.value)} />
      <p className="feedback-fine">
        Sending shares your marks, rating and comment with the citefix developer, together with the cited sentences and
        references from this check. Nothing is sent until you press the button.
      </p>
      <div className="feedback-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={send} disabled={sending || (sent && !changed)}>{label}</button>
        <span className={`feedback-state${state.tone ? ` is-${state.tone}` : ''}`} role="status" aria-live="polite">{state.text}</span>
      </div>
    </section>
  );
}
