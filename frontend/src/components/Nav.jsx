import { useState } from 'react';
import { motion, useMotionValueEvent, useScroll } from 'motion/react';
import { CaretMark } from './ui.jsx';

const LINKS = [
  ['Checker', '#check'],
  ['How it works', '#how'],
  ['Testing', '#testing'],
  ['About', '#about'],
];

/* A clear bar over the hero that turns to frosted glass once the page scrolls. */
export default function Nav() {
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  const [hover, setHover] = useState(null);
  useMotionValueEvent(scrollY, 'change', (y) => setSolid(y > 24)); // React skips the render when the value is the same

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 border-b transition-[background-color,border-color,backdrop-filter] duration-300 ${
        solid ? 'border-rule bg-[color-mix(in_srgb,var(--bg)_72%,transparent)] backdrop-blur-xl backdrop-saturate-150' : 'border-transparent'
      }`}
    >
      <nav className="mx-auto flex h-[68px] max-w-[1400px] items-center gap-6 px-6 lg:px-10" aria-label="Main">
        <a href="#top" className="flex items-center gap-2 text-[21px] font-semibold tracking-[-0.03em] text-ink">
          <span className="grid h-7 w-7 place-items-center rounded-[9px] bg-ink text-accent-soft">
            <CaretMark className="h-[15px] w-[15px]" />
          </span>
          citefix
        </a>
        <ul className="ml-auto hidden items-center md:flex" onMouseLeave={() => setHover(null)}>
          {LINKS.map(([label, href]) => (
            <li key={href} className="relative">
              <a
                href={href}
                onMouseEnter={() => setHover(href)}
                onFocus={() => setHover(href)}
                className="relative z-10 block rounded-full px-4 py-2 text-[14.5px] text-ink-2 transition-colors hover:text-ink"
              >
                {label}
              </a>
              {hover === href && (
                <motion.span
                  layoutId="nav-hover"
                  className="absolute inset-0 rounded-full bg-[color-mix(in_srgb,var(--ink)_6%,transparent)]"
                  transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                />
              )}
            </li>
          ))}
        </ul>
        <a href="#contact" className="btn btn-ink btn-sm ml-auto md:ml-2">Contact</a>
      </nav>
    </header>
  );
}
