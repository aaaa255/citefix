import { useEffect, useRef } from 'react';
import { AnimatePresence, animate, motion, useReducedMotion } from 'motion/react';
import { ArrowUpRight, Library, Quote, Search, X } from 'lucide-react';
import { links } from '../content.js';
import { useCheck, useMenu } from '../lib/CheckContext.jsx';
import { LANGS, useI18n } from '../lib/i18n.jsx';
import { Link, useRouter } from '../lib/router.jsx';
import Feedback from './checker/Feedback.jsx';
import { CaretMark, Icon } from './ui.jsx';

const TABS = [['about', 'menu.about'], ['feedback', 'menu.feedback'], ['settings', 'menu.settings']];

/* From README.md ("How it was tested"); nothing here is invented or rounded up. */
const RESULTS = [
  { value: 10, of: 10, label: 'about.r1' },
  { value: 14, of: 14, label: 'about.r2' },
  { value: 7, of: 7, label: 'about.r3' },
  { value: 4.2, of: 5, label: 'about.r4', decimals: 1 },
];

/* A figure that counts up from zero when it appears. It writes to the DOM directly, never through React state. */
function Count({ value, decimals = 0 }) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (reduce) { node.textContent = value.toFixed(decimals); return undefined; }
    const controls = animate(0, value, {
      duration: 1.1, delay: 0.25, ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => { node.textContent = v.toFixed(decimals); },
    });
    return () => controls.stop();
  }, [value, decimals, reduce]);
  return <span ref={ref}>{(0).toFixed(decimals)}</span>;
}

const rise = {
  hidden: { opacity: 0, x: 16 },
  shown: (i) => ({ opacity: 1, x: 0, transition: { delay: 0.06 + i * 0.045, duration: 0.5, ease: [0.16, 1, 0.3, 1] } }),
};
const Item = ({ i, as = 'div', ...props }) => {
  const Tag = motion[as];
  return <Tag custom={i} variants={rise} initial="hidden" animate="shown" {...props} />;
};

function About({ t }) {
  const steps = [[Library, 'about.step1'], [Quote, 'about.step2'], [Search, 'about.step3']];
  return (
    <>
      <Item i={0} as="h2" className="drawer-h">{t('about.how')}</Item>
      <ol className="mt-3 grid gap-0.5">
        {steps.map(([glyph, key], i) => (
          <Item key={key} i={i + 1} as="li" className="grid grid-cols-[36px_1fr] gap-3 rounded-[14px] px-3 py-2.5 transition-colors hover:bg-[color-mix(in_srgb,var(--ink)_4%,transparent)]">
            <span className="grid h-9 w-9 place-items-center rounded-full border border-rule bg-surface text-ink-2"><Icon as={glyph} className="h-[16px] w-[16px]" /></span>
            <div>
              <h3 className="text-[15px] font-semibold text-ink">{t(key)}</h3>
              <p className="mt-1 text-[14px] leading-[1.55] text-ink-2">{t(`${key}.body`)}</p>
            </div>
          </Item>
        ))}
      </ol>
      <Item i={4} as="h2" className="drawer-h mt-7">{t('about.tested')}</Item>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-5">
        {RESULTS.map((r, i) => (
          <Item key={r.label} i={5 + i} className="flex flex-col border-t border-rule pt-3">
            <dt className="order-last mt-1 text-[13px] leading-snug text-ink-3">{t(r.label)}</dt>
            <dd className="text-[28px] font-semibold leading-none tracking-[-0.04em] tabular-nums text-ink">
              <Count value={r.value} decimals={r.decimals} /><span className="text-ink-3">/{r.of}</span>
            </dd>
          </Item>
        ))}
      </dl>
      <Item i={9} as="p" className="mt-4 text-[13px] leading-relaxed text-ink-3">{t('about.caveat')}</Item>
      <Item i={10} className="mt-7 flex flex-wrap gap-2">
        <a href={links.contact} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm">{t('nav.contact')}<Icon as={ArrowUpRight} /></a>
        <a href={links.repo} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">{t('about.code')}<Icon as={ArrowUpRight} /></a>
      </Item>
    </>
  );
}

function FeedbackTab({ t, onClose }) {
  const { state } = useCheck();
  const { path } = useRouter();
  const check = state.check;
  if (!check || check.running) {
    return (
      <Item i={0} className="rounded-[14px] border border-dashed border-rule-strong p-5">
        <p className="text-[14.5px] leading-relaxed text-ink-2">{t('fb.none')}</p>
        {path !== '/check' && (
          <Link to="/check" onClick={onClose} className="btn btn-primary btn-sm mt-4">{t('cover.cta')}</Link>
        )}
      </Item>
    );
  }
  return <Item i={0}><Feedback key={check.id} check={check} /></Item>;
}

function Settings({ t }) {
  const { lang, setLang } = useI18n();
  const { tester, setTester } = useCheck();
  return (
    <>
      <Item i={0} as="h2" className="drawer-h">{t('settings.language')}</Item>
      <Item i={1} className="mt-3 grid grid-cols-3 gap-2" role="radiogroup" aria-label={t('settings.language')}>
        {LANGS.map((l) => (
          <button
            key={l.code}
            type="button"
            role="radio"
            aria-checked={lang === l.code}
            onClick={() => setLang(l.code)}
            className={`h-11 rounded-full border text-[14px] font-medium transition-colors ${
              lang === l.code ? 'border-primary bg-primary text-on-primary' : 'border-rule-strong text-ink-2 hover:border-ink-3 hover:text-ink'
            }`}
          >
            {l.name}
          </button>
        ))}
      </Item>
      <Item i={2} as="p" className="mt-3 text-[13px] leading-relaxed text-ink-3">{t('settings.note')}</Item>
      <Item i={3} as="h2" className="drawer-h mt-8">{t('settings.name')} <span className="text-[14px] font-normal tracking-normal text-ink-3">{t('settings.optional')}</span></Item>
      <Item i={4}>
        <input
          className="field mt-3"
          type="text"
          maxLength={60}
          autoComplete="nickname"
          value={tester}
          aria-label={t('settings.name')}
          onChange={(e) => setTester(e.target.value)}
        />
        <p className="mt-2 text-[13px] text-ink-3">{t('settings.nameHint')}</p>
      </Item>
    </>
  );
}

/* The menu, a frosted sheet that slides in from the right with three tabs: About, Feedback (the "How did citefix
   do?" form for the latest check) and Settings (language and your name). Esc, the close button or a click outside
   closes it; focus stays inside while it is open and returns to the button that opened it. */
export default function MenuDrawer() {
  const { t } = useI18n();
  const { menu, closeMenu, setTab } = useMenu();
  const panel = useRef(null);
  const reduce = useReducedMotion();
  const open = menu != null;

  useEffect(() => {
    if (!open) return undefined;
    const opener = document.activeElement;
    const html = document.documentElement;
    const gap = window.innerWidth - html.clientWidth; // keep the page from shifting when its scrollbar goes
    html.style.overflow = 'hidden';
    html.style.paddingRight = `${gap}px`;
    const focusables = () => [...(panel.current?.querySelectorAll('a[href], button:not([disabled]), input, textarea') || [])];
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); closeMenu(); return; }
      if (e.key !== 'Tab') return;
      const list = focusables();
      if (!list.length) return;
      const first = list[0]; const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    const focusTimer = setTimeout(() => focusables()[0]?.focus(), 60);
    return () => {
      clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKey);
      html.style.overflow = '';
      html.style.paddingRight = '';
      opener?.focus?.({ preventScroll: true });
    };
  }, [open, closeMenu]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-[color-mix(in_srgb,var(--ink)_16%,transparent)] backdrop-blur-[3px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={closeMenu}
          />
          <motion.aside
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label={t('menu.title')}
            className="drawer-panel absolute bottom-3 right-3 top-3 flex w-[min(440px,calc(100vw-24px))] flex-col overflow-y-auto rounded-[20px] px-7 pb-7 pt-5"
            initial={reduce ? { opacity: 0 } : { x: '108%' }}
            animate={reduce ? { opacity: 1 } : { x: 0 }}
            exit={reduce ? { opacity: 0 } : { x: '108%' }}
            transition={reduce ? { duration: 0.2 } : { type: 'spring', stiffness: 280, damping: 34 }}
          >
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-2 text-[17px] font-semibold tracking-[-0.02em] text-ink">
                <span className="grid h-6 w-6 place-items-center rounded-[7px] bg-[#0f1114] text-accent ring-1 ring-white/10">
                  <CaretMark className="h-[13px] w-[13px]" />
                </span>
                citefix
              </p>
              <button
                type="button"
                onClick={closeMenu}
                aria-label={t('menu.close')}
                className="grid h-9 w-9 place-items-center rounded-full text-ink-2 transition-[background-color,transform] duration-300 hover:rotate-90 hover:bg-[color-mix(in_srgb,var(--ink)_7%,transparent)] hover:text-ink"
              >
                <Icon as={X} className="h-[18px] w-[18px]" />
              </button>
            </div>

            <div className="relative mt-6 grid grid-cols-3 rounded-full bg-[color-mix(in_srgb,var(--ink)_6%,transparent)] p-1" role="tablist">
              {TABS.map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  aria-selected={menu === tab}
                  onClick={() => setTab(tab)}
                  className={`relative z-10 h-9 rounded-full text-[13.5px] font-medium transition-colors ${menu === tab ? 'text-ink' : 'text-ink-3 hover:text-ink-2'}`}
                >
                  {menu === tab && (
                    <motion.span layoutId="menu-tab" className="absolute inset-0 -z-10 rounded-full bg-surface shadow-[0_1px_3px_hsl(var(--shadow)/0.18)]" transition={{ type: 'spring', stiffness: 420, damping: 36 }} />
                  )}
                  {t(label)}
                </button>
              ))}
            </div>

            <div key={menu} className="mt-7" role="tabpanel">
              {menu === 'about' && <About t={t} />}
              {menu === 'feedback' && <FeedbackTab t={t} onClose={closeMenu} />}
              {menu === 'settings' && <Settings t={t} />}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
