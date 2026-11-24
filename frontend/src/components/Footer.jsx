import { links } from '../content.js';
import { useI18n } from '../lib/i18n.jsx';
import { CaretMark } from './ui.jsx';

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-6 py-8 text-[13.5px] text-ink-3 md:flex-row md:items-center md:justify-between lg:px-10">
        <p className="flex items-center gap-2 text-ink">
          <CaretMark className="h-[14px] w-[14px]" />
          <span className="font-semibold tracking-[-0.02em]">citefix</span>
          <a className="text-ink-3 underline decoration-rule-strong underline-offset-[3px] hover:text-ink" href={links.buildathon} target="_blank" rel="noopener noreferrer">
            {t('footer.for')}
          </a>
        </p>
        <p>{t('footer.sources')}</p>
      </div>
    </footer>
  );
}
