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

- `src/content.js`: your name, photo, bio and links for the About and Contact sections.
- `src/lib/check.js`: the check's state, rebuilt from the server's events (mirrors `app.js`).
- `src/components/checker/`: the manuscript, margin notes, references and feedback panel.
- `src/components/HeroBackdrop.jsx`: the WebGL fluid, the blur veil and the dust that follows the pointer.
- `src/data/recorded-check.json`: a copy of `eval/results/web-run.ndjson`, shown on the landing page as a recorded check.
