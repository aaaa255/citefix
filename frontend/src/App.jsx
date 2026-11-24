import { useEffect, useLayoutEffect, useRef } from 'react';
import { MotionConfig, motion, useReducedMotion } from 'motion/react';
import Checker from './components/checker/Checker.jsx';
import Footer from './components/Footer.jsx';
import Hero from './components/Hero.jsx';
import MenuDrawer from './components/MenuDrawer.jsx';
import Nav from './components/Nav.jsx';
import { CheckProvider, MenuProvider } from './lib/CheckContext.jsx';
import { I18nProvider, useI18n } from './lib/i18n.jsx';
import { RouterProvider, useRouter } from './lib/router.jsx';

/* A page fades in on arrival and opens at the top; its heading takes focus so screen readers announce the change. */
function Page({ children, label }) {
  const reduce = useReducedMotion();
  const heading = useRef(null);
  useLayoutEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, []);
  useEffect(() => { heading.current?.querySelector('h1, h2')?.focus?.({ preventScroll: true }); }, []);
  return (
    <motion.main
      ref={heading}
      aria-label={label}
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.main>
  );
}

function CheckPage() {
  const { t } = useI18n();
  return (
    <section className="px-6 pb-24 pt-28 lg:px-10 lg:pt-32">
      <div className="mx-auto max-w-[1400px]">
        <h1 tabIndex={-1} className="h-section mb-9 outline-none">{t('checker.title')}</h1>
        <Checker />
      </div>
    </section>
  );
}

/* The new page replaces the old one at once and fades in; nothing waits on the old page's exit, so a switch can
   never stall while the browser holds back frames (a hidden tab, a covered window). */
function Pages() {
  const { path } = useRouter();
  const { t } = useI18n();
  return path === '/check' ? (
    <Page key="check" label={t('checker.title')}>
      <CheckPage />
      <Footer />
    </Page>
  ) : (
    <Page key="cover" label={t('cover.headline')}>
      <Hero />
      <Footer />
    </Page>
  );
}

export default function App() {
  return (
    <RouterProvider>
      <I18nProvider>
        <CheckProvider>
          <MenuProvider>
            <MotionConfig reducedMotion="user">
              <Nav />
              <Pages />
              <MenuDrawer />
            </MotionConfig>
          </MenuProvider>
        </CheckProvider>
      </I18nProvider>
    </RouterProvider>
  );
}
