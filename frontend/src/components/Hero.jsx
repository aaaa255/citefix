import { Fragment, useRef } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight } from 'lucide-react';
import HeroBackdrop from './HeroBackdrop.jsx';
import HeroProof from './HeroProof.jsx';
import { Icon, MagneticLink } from './ui.jsx';

const EASE = [0.16, 1, 0.3, 1];
const HEADLINE = 'Every citation, checked against its source.';

export default function Hero() {
  const pointer = useRef({ x: 0.72, y: 0.4, active: false });
  const reduce = useReducedMotion();
  const track = (e) => {
    if (e.pointerType !== 'mouse') return;
    const box = e.currentTarget.getBoundingClientRect();
    pointer.current = { x: (e.clientX - box.left) / box.width, y: (e.clientY - box.top) / box.height, active: true };
  };
  const leave = () => { pointer.current = { ...pointer.current, active: false }; };
  const enter = (i) => ({
    initial: reduce ? false : { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.95, delay: 0.08 + i * 0.075, ease: EASE },
  });
  const words = HEADLINE.split(' ');

  return (
    <section id="top" className="relative isolate overflow-hidden" onPointerMove={track} onPointerLeave={leave}>
      <HeroBackdrop pointer={pointer} />
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 items-center gap-14 px-6 pb-24 pt-32 lg:grid-cols-12 lg:gap-12 lg:px-10 lg:pb-32 lg:pt-40">
        <div className="lg:col-span-7">
          <h1 className="text-balance text-[clamp(2.6rem,4.2vw,4rem)] font-semibold leading-[1.03] tracking-[-0.042em] text-ink">
            <span className="visually-hidden">{HEADLINE}</span>
            <span aria-hidden="true">
              {words.map((word, i) => (
                <Fragment key={i}>
                  <motion.span className="inline-block" {...enter(i)}>{word}</motion.span>
                  {i < words.length - 1 && ' '}
                </Fragment>
              ))}
            </span>
          </h1>
          <motion.p className="lede mt-7 max-w-[44ch] text-[18px]" {...enter(6)}>
            citefix checks that every cited paper exists, supports its sentence, and finds a real one when it doesn’t.
          </motion.p>
          <motion.div className="mt-10 flex flex-wrap items-center gap-3" {...enter(7.5)}>
            <MagneticLink href="#check" className="btn btn-primary h-12 px-6 text-[15px]">
              Check a passage<Icon as={ArrowRight} />
            </MagneticLink>
            <a href="#how" className="btn btn-ghost h-12 px-6 text-[15px]">How it works</a>
          </motion.div>
        </div>
        <div className="lg:col-span-5">
          <HeroProof />
        </div>
      </div>
    </section>
  );
}
