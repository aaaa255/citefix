import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

/* The hero's backdrop, in three layers: a soft flow of ice white and silver (WebGL) with a satin sheen; a
   Gaussian-blur veil behind the headline only; and a field of graphite dots that a slow wave sweeps across, that
   bulge away from the pointer, and that ripple out from a click. Everything runs outside React, and it pauses off
   screen, in hidden tabs and for reduced motion. */

const VERT = 'attribute vec2 a; void main() { gl_Position = vec4(a, 0.0, 1.0); }';

// 2D simplex noise by Ian McEwan and Stefan Gustavson (Ashima Arts, MIT licence), domain-warped twice.
const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uTime;
uniform vec2 uMouse;
uniform float uPointer;
uniform float uDark;

vec3 permute(vec3 x) { return mod(((x * 34.0) + 1.0) * x, 289.0); }
float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
  vec2 i = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
  m = m * m; m = m * m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
  vec3 g;
  g.x = a0.x * x0.x + h.x * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}
float fbm(vec2 p) {
  float s = 0.0;
  float a = 0.55;
  for (int i = 0; i < 3; i++) { s += a * snoise(p); p = p * 1.9 + vec2(1.7, 9.2); a *= 0.45; }
  return s;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes;
  float aspect = uRes.x / uRes.y;
  vec2 p = vec2(uv.x * aspect, uv.y) * 1.1;
  float t = uTime * 0.075;

  // the pointer: a soft lens that pushes the flow aside and twists it a little
  vec2 m = vec2(uMouse.x * aspect, uMouse.y) * 1.1;
  vec2 d = p - m;
  float lens = exp(-dot(d, d) * 3.0) * uPointer;
  float turn = lens * 1.6;
  d = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * d;
  p = m + d * (1.0 + lens * 0.3);

  vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + 2.0 * q + vec2(1.7, 9.2) + 0.7 * t), fbm(p + 2.0 * q + vec2(8.3, 2.8) - 0.5 * t));
  float f = fbm(p + 2.2 * r);
  float v = clamp(0.5 + 0.8 * f, 0.0, 1.0);

  // ice white, mist, silver and a deeper silver; in the dark, graphite lit in silver
  vec3 ice    = mix(vec3(0.965, 0.973, 0.980), vec3(0.043, 0.051, 0.063), uDark);
  vec3 mist   = mix(vec3(0.906, 0.918, 0.937), vec3(0.090, 0.102, 0.122), uDark);
  vec3 silver = mix(vec3(0.780, 0.800, 0.830), vec3(0.231, 0.255, 0.290), uDark);
  vec3 deep   = mix(vec3(0.620, 0.650, 0.695), vec3(0.420, 0.455, 0.502), uDark);

  vec3 col = ice;
  col = mix(col, mist, smoothstep(0.2, 0.48, v));
  col = mix(col, silver, smoothstep(0.46, 0.76, v) * 0.9);
  col = mix(col, deep, smoothstep(0.78, 0.98, v) * 0.55);

  // a soft sheen riding along the crests of the flow, like light on satin
  float sheen = smoothstep(0.25, 0.9, r.x * 0.5 + 0.5) * smoothstep(0.35, 0.75, v);
  col = mix(col, mix(vec3(1.0), vec3(0.62, 0.66, 0.71), uDark), sheen * 0.4);

  // the pointer brings a soft light with it
  col = mix(col, mix(vec3(1.0), vec3(0.75, 0.79, 0.84), uDark), lens * 0.35);

  // calmer behind the headline (left) and toward the bottom edge
  float calm = smoothstep(0.5, 0.0, uv.x) * 0.4 + smoothstep(0.25, 0.0, uv.y) * 0.3;
  col = mix(col, ice, clamp(calm, 0.0, 0.6));
  gl_FragColor = vec4(col, 1.0);
}`;

function startFluid(canvas, pointer) {
  const gl = canvas.getContext('webgl', { antialias: false, depth: false, stencil: false, alpha: false, powerPreference: 'low-power' });
  if (!gl) return null;
  const compile = (type, source) => {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
  };
  const vs = compile(gl.VERTEX_SHADER, VERT);
  const fs = compile(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return null;
  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, 'a');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const u = (name) => gl.getUniformLocation(program, name);
  const uRes = u('uRes'); const uTime = u('uTime'); const uMouse = u('uMouse'); const uPointer = u('uPointer'); const uDark = u('uDark');
  const SCALE = 0.5;
  const lens = { x: 0.74, y: 0.45, s: 0 };
  let dark = 0;
  return {
    setDark(on) { dark = on ? 1 : 0; },
    resize() {
      const w = Math.max(2, Math.round(canvas.clientWidth * SCALE));
      const h = Math.max(2, Math.round(canvas.clientHeight * SCALE));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        gl.viewport(0, 0, w, h);
      }
    },
    frame(t, ease = 1) {
      const p = pointer.current;
      const k = Math.min(1, 0.06 * ease); // ease > 1 settles the lens at once, for a single still frame
      lens.x += ((p.active ? p.x : 0.74) - lens.x) * k;
      lens.y += ((p.active ? 1 - p.y : 0.45) - lens.y) * k;
      lens.s += ((p.active ? 1 : 0) - lens.s) * Math.min(1, 0.04 * ease);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, t);
      gl.uniform2f(uMouse, lens.x, lens.y);
      gl.uniform1f(uPointer, lens.s);
      gl.uniform1f(uDark, dark);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
  };
}

const smooth = (a, b, x) => {
  const k = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return k * k * (3 - 2 * k);
};

/* A grid of dots drawn in a few batches by opacity, so even two thousand of them cost little per frame. */
function startDots(canvas, pointer, ripples) {
  const ctx = canvas.getContext('2d');
  const GAP = 24;
  const LEVELS = 12;
  const buckets = Array.from({ length: LEVELS }, () => []);
  let dots = [];
  let w = 0; let h = 0; let dpr = 1; let dark = false;
  const lay = () => {
    dots = [];
    const cols = Math.ceil(w / GAP) + 1; const rows = Math.ceil(h / GAP) + 1;
    const ox = (w - (cols - 1) * GAP) / 2; const oy = (h - (rows - 1) * GAP) / 2;
    for (let j = 0; j < rows; j += 1) for (let i = 0; i < cols; i += 1) dots.push(ox + i * GAP, oy + j * GAP);
  };
  return {
    setDark(on) { dark = on; },
    resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      const nw = canvas.clientWidth; const nh = canvas.clientHeight;
      if (nw === w && nh === h) return;
      w = nw; h = nh;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      lay();
    },
    frame(t, moving = true) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      for (const bucket of buckets) bucket.length = 0;
      const p = pointer.current;
      const px = p.x * w; const py = p.y * h;
      const now = performance.now();
      while (ripples.length && now - ripples[0].start > 1700) ripples.shift();
      const rings = ripples.map((r) => ({ x: r.x * w, y: r.y * h, age: (now - r.start) / 1000 }));
      for (let i = 0; i < dots.length; i += 2) {
        let x = dots[i]; let y = dots[i + 1];
        const side = 0.28 + 0.72 * smooth(0.1, 0.55, x / w); // quieter behind the headline
        // a slow diagonal swell travelling across the field
        const swell = moving ? (0.5 + 0.5 * Math.sin((x * 0.8 + y * 0.45) / 150 - t * 1.4)) ** 7 : 0;
        let r = 0.9 + 1.1 * swell;
        let a = 0.14 + 0.24 * swell;
        if (p.active && moving) {
          const dx = x - px; const dy = y - py; const d2 = dx * dx + dy * dy;
          const k = Math.exp(-d2 / 18000);
          if (k > 0.01) {
            const dist = Math.sqrt(d2) || 1;
            x += (dx / dist) * 18 * k; y += (dy / dist) * 18 * k;
            r += 2.1 * k; a += 0.5 * k;
          }
        }
        for (const ring of rings) {
          const dx = dots[i] - ring.x; const dy = dots[i + 1] - ring.y; const dist = Math.hypot(dx, dy) || 1;
          const band = Math.exp(-(((dist - ring.age * 560) / 26) ** 2)) * Math.max(0, 1 - ring.age / 1.7);
          if (band > 0.01) {
            x += (dx / dist) * 8 * band; y += (dy / dist) * 8 * band;
            r += 2.2 * band; a += 0.55 * band;
          }
        }
        a = Math.min(0.92, a) * side;
        buckets[Math.min(LEVELS - 1, Math.floor((a / 0.92) * LEVELS))].push(x, y, r);
      }
      const rgb = dark ? '226, 231, 237' : '17, 19, 23';
      for (let level = 0; level < LEVELS; level += 1) {
        const list = buckets[level];
        if (!list.length) continue;
        ctx.fillStyle = `rgba(${rgb}, ${((level + 0.5) / LEVELS) * 0.92})`;
        ctx.beginPath();
        for (let i = 0; i < list.length; i += 3) {
          ctx.moveTo(list[i] + list[i + 2], list[i + 1]);
          ctx.arc(list[i], list[i + 1], list[i + 2], 0, 6.2832);
        }
        ctx.fill();
      }
    },
  };
}

export default function HeroBackdrop({ pointer, ripples }) {
  const wrapRef = useRef(null);
  const fluidRef = useRef(null);
  const dotsRef = useRef(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const wrap = wrapRef.current;
    const fluid = startFluid(fluidRef.current, pointer);
    const dots = startDots(dotsRef.current, pointer, ripples.current);
    wrap.classList.toggle('fluid-fallback', !fluid);
    const t0 = performance.now();
    let raf = 0; let running = false; let onScreen = true;
    const draw = (moving) => {
      const t = (performance.now() - t0) / 1000;
      fluid?.frame(reduce ? 0 : t, moving ? 1 : 40);
      dots.frame(t, moving);
    };
    const tick = () => { draw(true); if (running) raf = requestAnimationFrame(tick); };
    const play = () => { if (running || reduce) return; running = true; raf = requestAnimationFrame(tick); };
    const pause = () => { running = false; cancelAnimationFrame(raf); };
    const sync = () => (onScreen && !document.hidden ? play() : pause());
    const resize = () => { fluid?.resize(); dots.resize(); if (!running) draw(false); };
    const scheme = window.matchMedia('(prefers-color-scheme: dark)');
    const onScheme = () => { fluid?.setDark(scheme.matches); dots.setDark(scheme.matches); if (!running) draw(false); };
    onScheme();
    resize();
    const sizes = new ResizeObserver(resize);
    sizes.observe(wrap);
    const seen = new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; sync(); });
    seen.observe(wrap);
    document.addEventListener('visibilitychange', sync);
    scheme.addEventListener('change', onScheme);
    return () => {
      pause();
      sizes.disconnect();
      seen.disconnect();
      document.removeEventListener('visibilitychange', sync);
      scheme.removeEventListener('change', onScheme);
    };
  }, [pointer, ripples, reduce]);

  return (
    <div ref={wrapRef} className="melt-bottom pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
      {/* blurred as a whole, so the flow reads as soft silver mist; scaled up so the blurred edges stay off screen */}
      <canvas ref={fluidRef} className="absolute inset-0 h-full w-full scale-110 blur-[16px]" />
      <div className="veil absolute inset-0" />
      <canvas ref={dotsRef} className="absolute inset-0 h-full w-full" />
    </div>
  );
}
