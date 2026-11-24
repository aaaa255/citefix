import { createContext, useContext, useLayoutEffect, useRef, useState } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react';
import { Check, Copy, ExternalLink, TriangleAlert, X } from 'lucide-react';
import { safeUrl } from '../lib/check.js';
import { useI18n } from '../lib/i18n.jsx';

/* Lucide icons, one stroke width for the whole page. */
export function Icon({ as: Glyph, className = '', ...props }) {
  return <Glyph className={`icon ${className}`} strokeWidth={1.75} aria-hidden="true" {...props} />;
}

/* The citefix mark: a proof-reader's insertion caret. It is the brand mark (also the favicon), so it is drawn here. */
export function CaretMark({ className = '' }) {
  return (
    <svg className={`icon ${className}`} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.9"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4.5 15.5L10 5.5l5.5 10" />
    </svg>
  );
}

const VERDICT_ICONS = { check: Check, cross: X, query: TriangleAlert };
export function VerdictIcon({ name }) {
  if (name === 'caret') return <CaretMark />;
  const Glyph = VERDICT_ICONS[name];
  return Glyph ? <Icon as={Glyph} /> : null;
}

export const Pulse = () => <span className="pulse" aria-hidden="true" />;

/* Asks the margin to lay its notes out again after something inside one changed height. */
export const LayoutContext = createContext(() => {});

/* Long text shows a few lines; clicking it (or Enter) shows the rest. */
export function Clamp({ as: Tag = 'p', className = '', lines = 3, children }) {
  const ref = useRef(null);
  const [clamped, setClamped] = useState(false);
  const [open, setOpen] = useState(false);
  const layoutSoon = useContext(LayoutContext);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || open) return;
    setClamped(node.scrollHeight > node.clientHeight + 1);
  }, [children, open]);
  const toggle = () => {
    setOpen((o) => !o);
    layoutSoon();
  };
  const classes = ['clamp', className, clamped && 'is-clamped', open && 'is-open'].filter(Boolean).join(' ');
  return (
    <Tag
      ref={ref}
      className={classes}
      style={{ '--lines': String(lines) }}
      tabIndex={clamped ? 0 : undefined}
      aria-expanded={clamped ? open : undefined}
      onClick={clamped ? toggle : undefined}
      onKeyDown={clamped ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } } : undefined}
    >
      {children}
    </Tag>
  );
}

export function CopyButton({ label, text }) {
  const { t } = useI18n();
  const [state, setState] = useState(null); // null, 'copy.done' or 'copy.failed', shown for a moment
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setState('copy.done');
    } catch {
      setState('copy.failed');
    }
    setTimeout(() => setState(null), 1600);
  };
  return (
    <button type="button" className="chip-btn" onClick={copy}>
      <Icon as={Copy} />{state ? t(state) : label}
    </button>
  );
}

export function LinkButton({ label, url }) {
  const href = safeUrl(url);
  if (!href) return null;
  return (
    <a className="chip-btn" href={href} target="_blank" rel="noopener noreferrer">
      <Icon as={ExternalLink} />{label}
    </a>
  );
}

/* Content that rises into place the first time it scrolls into view. */
export function Reveal({ as = 'div', delay = 0, y = 22, className, children, ...rest }) {
  const reduce = useReducedMotion();
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/* A link that leans toward the pointer. Motion values, so moving the mouse never re-renders React. */
export function MagneticLink({ className, children, strength = 0.22, ...props }) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 220, damping: 18, mass: 0.6 });
  const move = (e) => {
    if (reduce || e.pointerType !== 'mouse') return;
    const box = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - box.left - box.width / 2) * strength);
    y.set((e.clientY - box.top - box.height / 2) * strength);
  };
  const leave = () => { x.set(0); y.set(0); };
  return (
    <motion.a className={className} style={{ x: sx, y: sy }} onPointerMove={move} onPointerLeave={leave} {...props}>
      {children}
    </motion.a>
  );
}
