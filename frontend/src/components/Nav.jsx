import { useState } from 'react';
import { useMotionValueEvent, useScroll } from 'motion/react';
import { Menu } from 'lucide-react';
import { links } from '../content.js';
import { useMenu } from '../lib/CheckContext.jsx';
import { useI18n } from '../lib/i18n.jsx';
import { Link } from '../lib/router.jsx';
import { CaretMark, Icon } from './ui.jsx';

/* A clear bar that turns to frosted glass once the page scrolls: the wordmark (back to the cover), Menu (which
   slides the menu out) and Contact. */
export default function Nav() {
  const { t } = useI18n();
  const { menu, openMenu } = useMenu();
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, 'change', (y) => setSolid(y > 24)); // React skips the render when the value is the same

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 border-b transition-[background-color,border-color,backdrop-filter] duration-300 ${
        solid ? 'border-rule bg-[color-mix(in_srgb,var(--bg)_72%,transparent)] backdrop-blur-xl backdrop-saturate-150' : 'border-transparent'
      }`}
    >
      <nav className="mx-auto flex h-[68px] max-w-[1400px] items-center gap-3 px-6 lg:px-10" aria-label="Main">
        <Link to="/" aria-label={t('nav.home')} className="mr-auto flex items-center gap-2 text-[21px] font-semibold tracking-[-0.03em] text-ink">
          {/* the brand tile stays graphite in both themes, like the favicon */}
          <span className="grid h-7 w-7 place-items-center rounded-[9px] bg-[#0f1114] text-accent ring-1 ring-white/10">
            <CaretMark className="h-[15px] w-[15px]" />
          </span>
          citefix
        </Link>
        <button
          type="button"
          className="btn btn-ghost btn-sm group"
          aria-haspopup="dialog"
          aria-expanded={menu != null}
          onClick={() => openMenu('about')}
        >
          <Icon as={Menu} className="transition-transform duration-300 group-hover:scale-110" />
          {t('nav.menu')}
        </button>
        <a href={links.contact} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm">{t('nav.contact')}</a>
      </nav>
    </header>
  );
}
