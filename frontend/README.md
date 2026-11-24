# citefix front end

React + Vite, Tailwind CSS v4, Motion (the library formerly called Framer Motion) and Lucide React.
The checker is a port of `citefix/web/app.js`: the same `/api/review` event stream, proof marks, margin notes,
agent trail, fixes and tester feedback. `python -m citefix serve` serves the build in `dist/` and falls back to the
classic page in `citefix/web/` when there is none; the Dockerfile builds it for Render.

A change to how the page reads the server's events belongs in both `src/lib/check.js` and `citefix/web/app.js`
for as long as the classic page is kept as the fallback.

## Run it

```bash
npm install
npm run dev                  # http://localhost:5173, forwards /api to python -m citefix serve on :8765 (live checks)
npm run dev -- --mode replay # http://localhost:5174, forwards /api to :8766, for serve --replay (a recorded check, no keys)
npm run build                # static files in dist/
```

For the replay mode, start the API with
`python -m citefix serve --port 8766 --replay eval/results/web-run.ndjson` from the repository root.

## Where things are

Two pages: the cover at `/` and the checker at `/check` (the Python server answers both with the page).

- `src/content.js`: where the Contact button and the footer link to.
- `src/lib/i18n.jsx`: every word the page shows, in English (the default), Chinese and Spanish; a language picked in
  Settings is remembered. Explanations from the model and quotes from abstracts are shown as they come.
- `src/lib/check.js`: the check's state, rebuilt from the server's events (mirrors `app.js`), as translation keys.
- `src/lib/CheckContext.jsx`: the running check and the menu, shared by both pages.
- `src/lib/router.jsx`: the two pages, kept in the address bar.
- `src/components/Hero.jsx` and `HeroBackdrop.jsx`: the cover, its silver WebGL flow, the blur veil, and the dot
  field that waves, bulges around the pointer and ripples on a click.
- `src/components/LoopDemo.jsx`: the cover's looping demo (typing, Check, then the recorded results).
- `src/components/MenuDrawer.jsx`: the menu that slides out on the right: About, Feedback ("How did citefix do?"
  for the latest check) and Settings (language and your name).
- `src/components/checker/`: the references, the manuscript, margin notes and the feedback form.
- `src/data/recorded-check.json`: a copy of `eval/results/web-run.ndjson`; the cover replays three of its citations.
