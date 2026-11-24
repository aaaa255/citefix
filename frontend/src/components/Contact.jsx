import { useRef } from 'react';
import { ArrowUpRight, Mail } from 'lucide-react';
import { links } from '../content.js';
import HeroBackdrop from './HeroBackdrop.jsx';
import { CaretMark, Icon, MagneticLink, Reveal } from './ui.jsx';

export function Contact() {
  const pointer = useRef({ x: 0.7, y: 0.5, active: false });
  const track = (e) => {
    if (e.pointerType !== 'mouse') return;
    const box = e.currentTarget.getBoundingClientRect();
    pointer.current = { x: (e.clientX - box.left) / box.width, y: (e.clientY - box.top) / box.height, active: true };
  };
  return (
    <section
      id="contact"
      className="relative isolate overflow-hidden"
      onPointerMove={track}
      onPointerLeave={() => { pointer.current = { ...pointer.current, active: false }; }}
    >
      <HeroBackdrop pointer={pointer} calm />
      <div className="mx-auto max-w-[1400px] px-6 py-32 lg:px-10 lg:py-44">
        <Reveal className="max-w-3xl">
          <h2 className="h-section">Found a citation it got wrong?</h2>
          <p className="lede mt-5">
            Mark that note “No” and say why, or open an issue on GitHub. Both reach the developer.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <MagneticLink href={links.issues} target="_blank" rel="noopener noreferrer" className="btn btn-primary h-12 px-6 text-[15px]">
              Open an issue<Icon as={ArrowUpRight} />
            </MagneticLink>
            <a href={links.repo} target="_blank" rel="noopener noreferrer" className="btn btn-ghost h-12 px-6 text-[15px]">
              View the code<Icon as={ArrowUpRight} />
            </a>
            {links.email && (
              <a href={`mailto:${links.email}`} className="btn btn-ghost h-12 px-6 text-[15px]"><Icon as={Mail} />Email</a>
            )}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  const source = (href, label) => <a className="underline decoration-rule-strong underline-offset-[3px] hover:text-ink" href={href} target="_blank" rel="noopener noreferrer">{label}</a>;
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 px-6 py-12 text-[13.5px] leading-relaxed text-ink-3 md:grid-cols-12 lg:px-10">
        <div className="md:col-span-4">
          <p className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.02em] text-ink">
            <CaretMark className="h-[14px] w-[14px] text-accent" />citefix
          </p>
          <p className="mt-2">Prototype for the {source(links.buildathon, 'Silicon Valley Buildathon')} 2026.</p>
        </div>
        <p className="md:col-span-4">
          Records from {source('https://openalex.org', 'OpenAlex')}, {source('https://www.crossref.org', 'Crossref')},{' '}
          {source('https://arxiv.org', 'arXiv')} and {source('https://www.semanticscholar.org', 'Semantic Scholar')}.
          Judgments by {source('https://www.deepseek.com', 'DeepSeek')}.
        </p>
        <p className="md:col-span-4">Set in Geist and Literata. Built with React, Vite, Tailwind CSS, Motion and Lucide.</p>
      </div>
    </footer>
  );
}
