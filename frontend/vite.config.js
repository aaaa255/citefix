import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// The Python server (python -m citefix serve) answers /api; in development Vite forwards those requests to it.
//   npm run dev                  -> http://localhost:5173, API on :8765 (live checks, uses your keys)
//   npm run dev -- --mode replay -> http://localhost:5174, API on :8766 (serve --replay: a recorded check, no keys)
// CITEFIX_API overrides the API address in either mode.
export default defineConfig(({ mode }) => {
  const replay = mode === 'replay';
  const api = process.env.CITEFIX_API || (replay ? 'http://127.0.0.1:8766' : 'http://127.0.0.1:8765');
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: replay ? 5174 : 5173,
      strictPort: true,
      proxy: { '/api': { target: api, changeOrigin: true } },
    },
  };
});
