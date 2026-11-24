import { Fragment, useRef } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react';
import { ArrowRight } from 'lucide-react';
import { useI18n } from '../lib/i18n.jsx';
import { useRouter } from '../lib/router.jsx';
import HeroBackdrop from './HeroBackdrop.jsx';
import LoopDemo from './LoopDemo.jsx';
import { Icon, MagneticLink } from './ui.jsx';

const EASE = [0.16, 1, 0.3, 1];

/* The demo card leans a few degrees toward the pointer. Motion values, so moving the mouse never re-renders. */
function TiltCard({ children }) {
  const reduce = useReducedMotion();
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const rotateX = useSpring(rx, { stiffness: 160, damping: 18 });
  const rotateY = useSpring(ry, { stiffness: 160, damping: 18 });
  const move = (e) => {
    if (reduce || e.pointerType !== 'mouse') return;
    const box = e.currentTarget.getBoundingClientRect();
    ry.set(((e.clientX - box.left) / box.width - 0.5) * 6);
    rx.set(-((e.clientY - box.top) / box.height - 0.5) * 4);
  };
  const leave = () => { rx.set(0); ry.set(0); };
  return (
    <div className="[perspective:1400px]" onPointerMove={move} onPointerLeave={leave}>
      <motion.div style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}>{children}</motion.div>
    </div>
  );
}

/* The cover: the headline, one way in, and the demo playing on a loop. The checker is its own page, at /check. */
export default function Hero() {
  const { t, lang } = useI18n();
  const { navigate } = useRouter();
  const pointer = useRef({ x: 0.72, y: 0.4, active: false });
  const ripples = useRef([]);
  const reduce = useReducedMotion();
  const where = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    return { x: (e.clientX - box.left) / box.width, y: (e.clientY - box.top) / box.height };
  };
  const track = (e) => {
    if (e.pointerType !== 'mouse') return;
    pointer.current = { ...where(e), active: true };
  };
  const leave = () => { pointer.current = { ...pointer.current, active: false }; };
  // A click on the backdrop (not on a link or button) sends a ripple through the dots.
  const ripple = (e) => {
    if (reduce || e.target.closest('a, button')) return;
    ripples.current.push({ ...where(e), start: performance.now() });
  };
  const enter = (i) => ({
    initial: reduce ? false : { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.95, delay: 0.08 + i * 0.075, ease: EASE },
  });
  const headline = t('cover.headline');
  // Chinese has no spaces to split on, so it rises in by phrase.
  const words = lang === 'zh' ? headline.split(/(?<=，)/) : headline.split(' ');
  const open = (e) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate('/check');
  };

  return (
    <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden" onPointerMove={track} onPointerLeave={leave} onPointerDown={ripple}>
      <HeroBackdrop pointer={pointer} ripples={ripples} />
      <div className="mx-auto grid w-full max-w-[1400px] grid-cols-1 items-center gap-14 px-6 pb-16 pt-28 lg:grid-cols-12 lg:gap-12 lg:px-10">
        <div className="lg:col-span-6">
          <h1 key={lang} className="text-balance text-[clamp(2.6rem,4.2vw,4rem)] font-semibold leading-[1.06] tracking-[-0.042em] text-ink">
            <span className="visually-hidden">{headline}</span>
            <span aria-hidden="true">
              {words.map((word, i) => (
                <Fragment key={i}>
                  <motion.span className="inline-block" {...enter(i)}>{word}</motion.span>
                  {lang !== 'zh' && i < words.length - 1 && ' '}
                </Fragment>
              ))}
            </span>
          </h1>
          <motion.div className="mt-11" {...enter(6.5)}>
            <MagneticLink href="/check" onClick={open} className="btn btn-primary h-12 pl-6 pr-5 text-[15px]">
              {t('cover.cta')}
              <span className="btn-chip"><Icon as={ArrowRight} /></span>
            </MagneticLink>
          </motion.div>
        </div>
        <div className="lg:col-span-6">
          <TiltCard>
            <LoopDemo />
          </TiltCard>
        </div>
      </div>
    </section>
  );
}
