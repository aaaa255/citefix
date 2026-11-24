import { MotionConfig } from 'motion/react';
import About from './components/About.jsx';
import Checker from './components/checker/Checker.jsx';
import { Contact, Footer } from './components/Contact.jsx';
import Hero from './components/Hero.jsx';
import HowItWorks from './components/HowItWorks.jsx';
import Nav from './components/Nav.jsx';
import Testing from './components/Testing.jsx';
import { Reveal } from './components/ui.jsx';

function CheckSection() {
  return (
    <section id="check" className="relative scroll-mt-4 px-6 pb-12 pt-10 lg:px-10">
      <div className="mx-auto max-w-[1400px]">
        <Reveal className="mb-10 max-w-3xl">
          <h2 className="h-section">Paste a passage. Read the margin.</h2>
          <p className="lede mt-5">
            Put the text first, then a line that says References, then one reference per line. Each citation gets a mark in
            the text and a note beside it.
          </p>
        </Reveal>
        <Checker />
      </div>
    </section>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Nav />
      <main>
        <Hero />
        <CheckSection />
        <HowItWorks />
        <Testing />
        <About />
        <Contact />
      </main>
      <Footer />
    </MotionConfig>
  );
}
