import { CaretMark } from '../ui.jsx';

/* The empty state: what each mark means, before the first check. */
export default function Legend() {
  return (
    <div className="legend">
      <p className="legend-intro">Each citation gets a mark in the text and a note in this margin.</p>
      <dl>
        <div>
          <dt><span className="sample is-ok">says what you cite it for</span></dt>
          <dd>Supported. The note quotes the abstract sentence that shows it.</dd>
        </div>
        <div>
          <dt><span className="sample is-warn">only part of it holds</span></dt>
          <dd>Partly supported, or the abstract is too brief to tell.</dd>
        </div>
        <div>
          <dt><span className="sample is-bad">a claim the paper never makes</span></dt>
          <dd>Not supported, or the reference does not exist.</dd>
        </div>
        <div>
          <dt>
            <span className="marker is-struck">[3]</span>
            <ins className="insert"><CaretMark />(Ioffe &amp; Szegedy, 2015)</ins>
          </dt>
          <dd>A real paper the agent found, quoted, and checked a second time.</dd>
        </div>
      </dl>
      <p className="legend-fine">
        Nothing is taken on the model’s word. Papers come from OpenAlex, Crossref and arXiv, every quote is matched
        against the abstract it came from, and the agent can only suggest papers its own searches returned.
      </p>
    </div>
  );
}
