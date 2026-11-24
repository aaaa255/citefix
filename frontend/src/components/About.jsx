import { ArrowUpRight } from 'lucide-react';
import { links, maker } from '../content.js';
import { CaretMark, Icon, Reveal } from './ui.jsx';

function Avatar() {
  if (maker.photo) {
    return <img src={maker.photo} alt={maker.name} className="h-20 w-20 shrink-0 rounded-full object-cover" width="80" height="80" />;
  }
  // No photo yet: the citefix mark on the hero's blue, until one is added in content.js.
  return (
    <div
      className="grid h-20 w-20 shrink-0 place-items-center rounded-full text-white"
      style={{ background: 'radial-gradient(circle at 30% 25%, #a9c3ff 0%, #3b6cf0 45%, #10296f 100%)' }}
      aria-hidden="true"
    >
      <CaretMark className="h-8 w-8" />
    </div>
  );
}

export default function About() {
  return (
    <section id="about" className="py-28 lg:py-36">
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 items-center gap-14 px-6 lg:grid-cols-12 lg:px-10">
        <Reveal className="lg:col-span-6">
          <h2 className="h-section">Why it exists.</h2>
          <p className="lede mt-6">
            Language models write convincing references that do not exist, and real references get attached to sentences
            they never support.
          </p>
          <p className="lede mt-4">
            Checking every citation by hand means opening every paper. citefix does the lookup and the reading, and shows its
            evidence so you can check each verdict yourself.
          </p>
        </Reveal>

        <Reveal className="lg:col-span-5 lg:col-start-8" delay={0.1}>
          <article className="glass relative overflow-hidden rounded-[20px] p-7 sm:p-8">
            <div
              className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full opacity-60 blur-3xl"
              style={{ background: 'radial-gradient(circle, color-mix(in srgb, var(--accent) 35%, transparent), transparent 70%)' }}
              aria-hidden="true"
            />
            <div className="relative flex items-center gap-5">
              <Avatar />
              <div className="min-w-0">
                <h3 className="text-[21px] font-semibold tracking-[-0.025em] text-ink">{maker.name}</h3>
                <p className="mt-1 text-[14.5px] text-ink-3">{maker.role}</p>
              </div>
            </div>
            <p className="relative mt-6 text-[15.5px] leading-[1.65] text-ink-2">{maker.bio}</p>
            <div className="relative mt-7 flex flex-wrap gap-3">
              <a className="btn btn-ghost btn-sm" href={links.repo} target="_blank" rel="noopener noreferrer">
                Code on GitHub<Icon as={ArrowUpRight} />
              </a>
              <a className="btn btn-ghost btn-sm" href={links.buildathon} target="_blank" rel="noopener noreferrer">
                The Buildathon<Icon as={ArrowUpRight} />
              </a>
            </div>
          </article>
        </Reveal>
      </div>
    </section>
  );
}
