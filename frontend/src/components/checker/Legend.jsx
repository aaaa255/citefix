import { useI18n } from '../../lib/i18n.jsx';
import { CaretMark } from '../ui.jsx';

/* The empty state: what each mark means, before the first check. */
export default function Legend() {
  const { t } = useI18n();
  return (
    <div className="legend">
      <dl>
        <div>
          <dt><span className="sample is-ok">{t('legend.ok.sample')}</span></dt>
          <dd>{t('legend.ok')}</dd>
        </div>
        <div>
          <dt><span className="sample is-warn">{t('legend.warn.sample')}</span></dt>
          <dd>{t('legend.warn')}</dd>
        </div>
        <div>
          <dt><span className="sample is-bad">{t('legend.bad.sample')}</span></dt>
          <dd>{t('legend.bad')}</dd>
        </div>
        <div>
          <dt>
            <span className="marker is-struck">[3]</span>
            <ins className="insert"><CaretMark />(Ioffe &amp; Szegedy, 2015)</ins>
          </dt>
          <dd>{t('legend.fix')}</dd>
        </div>
      </dl>
    </div>
  );
}
