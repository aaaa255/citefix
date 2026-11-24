import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

/* The hero's backdrop, in four layers: a slow fluid gradient (WebGL) that bends around the pointer, a Gaussian-blur
   veil that keeps the headline side calm, a few motes of dust that drift up and link near the pointer like citations,
   and a fade into the page. Everything runs outside React; it pauses off screen, in hidden tabs and for reduced motion. */

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
  float a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * snoise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
  return s;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes;
  float aspect = uRes.x / uRes.y;
  vec2 p = vec2(uv.x * aspect, uv.y) * 1.25;
  float t = uTime * 0.05;

  // the pointer: a soft lens that pushes the flow aside and twists it a little
  vec2 m = vec2(uMouse.x * aspect, uMouse.y) * 1.25;
  vec2 d = p - m;
  float lens = exp(-dot(d, d) * 3.0) * uPointer;
  float turn = lens * 1.4;
  d = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * d;
  p = m + d * (1.0 + lens * 0.35);

  vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + 2.1 * q + vec2(1.7, 9.2) + 0.7 * t), fbm(p + 2.1 * q + vec2(8.3, 2.8) - 0.5 * t));
  float f = fbm(p + 2.3 * r);
  float v = clamp(0.52 + 0.8 * f, 0.0, 1.0);

  vec3 base   = mix(vec3(0.957, 0.969, 0.984), vec3(0.024, 0.043, 0.082), uDark);
  vec3 ice    = mix(vec3(0.808, 0.878, 0.996), vec3(0.047, 0.106, 0.239), uDark);
  vec3 azure  = mix(vec3(0.459, 0.627, 0.992), vec3(0.090, 0.231, 0.565), uDark);
  vec3 cobalt = mix(vec3(0.122, 0.310, 0.847), vec3(0.247, 0.435, 0.957), uDark);
  vec3 cyan   = mix(vec3(0.529, 0.839, 0.949), vec3(0.059, 0.341, 0.451), uDark);

  vec3 col = base;
  col = mix(col, ice, smoothstep(0.2, 0.52, v));
  col = mix(col, azure, smoothstep(0.48, 0.76, v) * 0.9);
  col = mix(col, cobalt, smoothstep(0.72, 0.95, v) * 0.85);
  col = mix(col, cyan, smoothstep(0.4, 1.0, length(r)) * 0.3);
  col = mix(col, mix(vec3(1.0), azure * 1.25, uDark), lens * 0.25);

  // calmer toward the headline (left) and the bottom edge
  float calm = smoothstep(0.55, 0.0, uv.x) * 0.42 + smoothstep(0.3, 0.0, uv.y) * 0.3;
  col = mix(col, base, clamp(calm, 0.0, 0.7));
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
  const SCALE = 0.45; // the veil blurs it anyway, so it renders at under half size
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
      const k = Math.min(1, 0.05 * ease); // ease > 1 settles the lens at once, for a single still frame
      lens.x += ((p.active ? p.x : 0.74) - lens.x) * k;
      lens.y += ((p.active ? 1 - p.y : 0.45) - lens.y) * k;
      lens.s += ((p.active ? 1 : 0) - lens.s) * Math.min(1, 0.035 * ease);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, t);
      gl.uniform2f(uMouse, lens.x, lens.y);
      gl.uniform1f(uPointer, lens.s);
      gl.uniform1f(uDark, dark);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
  };
}

function startDust(canvas, pointer) {
  const ctx = canvas.getContext('2d');
  const motes = [];
  let w = 0; let h = 0; let dpr = 1; let dark = false;
  const seed = () => {
    motes.length = 0;
    const count = Math.round(Math.min(70, Math.max(28, (w * h) / 17000)));
    for (let i = 0; i < count; i += 1) {
      motes.push({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.1, vy: -0.04 - Math.random() * 0.1,
        r: 0.7 + Math.random() * 1.4, a: 0.3 + Math.random() * 0.45, ph: Math.random() * 6.28, ox: 0, oy: 0,
      });
    }
  };
  return {
    setDark(on) { dark = on; },
    resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      const nw = canvas.clientWidth; const nh = canvas.clientHeight;
      if (nw === w && nh === h) return;
      const first = !w;
      w = nw; h = nh;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      if (first) seed();
    },
    frame(t, moving = true) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const p = pointer.current;
      const px = p.x * w; const py = p.y * h;
      const rgb = dark ? '157, 184, 255' : '31, 79, 216';
      for (const m of motes) {
        if (moving) {
          m.x += m.vx; m.y += m.vy;
          if (m.y < -12) { m.y = h + 12; m.x = Math.random() * w; }
          if (m.x < -12) m.x = w + 12;
          if (m.x > w + 12) m.x = -12;
        }
        let tx = 0; let ty = 0;
        if (p.active) {
          const dx = m.x - px; const dy = m.y - py; const dist = Math.hypot(dx, dy);
          if (dist < 160 && dist > 0.5) { const push = (1 - dist / 160) ** 2 * 28; tx = (dx / dist) * push; ty = (dy / dist) * push; }
        }
        m.ox += (tx - m.ox) * 0.08; m.oy += (ty - m.oy) * 0.08;
      }
      const shown = (m) => Math.min(1, Math.max(0, (m.x / w - 0.18) / 0.4)); // the headline side stays clear
      if (p.active) {
        ctx.lineWidth = 0.7;
        for (let i = 0; i < motes.length; i += 1) {
          const a = motes[i]; const ax = a.x + a.ox; const ay = a.y + a.oy;
          if (Math.hypot(ax - px, ay - py) > 230) continue;
          for (let j = i + 1; j < motes.length; j += 1) {
            const b = motes[j]; const bx = b.x + b.ox; const by = b.y + b.oy;
            const dist = Math.hypot(ax - bx, ay - by);
            if (dist > 120 || Math.hypot(bx - px, by - py) > 230) continue;
            ctx.strokeStyle = `rgba(${rgb}, ${(1 - dist / 120) * 0.28 * Math.min(shown(a), shown(b))})`;
            ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
          }
        }
      }
      for (const m of motes) {
        const twinkle = 0.65 + 0.35 * Math.sin(t * 1.2 + m.ph);
        ctx.fillStyle = `rgba(${rgb}, ${m.a * twinkle * shown(m)})`;
        ctx.beginPath(); ctx.arc(m.x + m.ox, m.y + m.oy, m.r, 0, 6.2832); ctx.fill();
      }
    },
  };
}

export default function HeroBackdrop({ pointer, calm = false }) {
  const wrapRef = useRef(null);
  const fluidRef = useRef(null);
  const dustRef = useRef(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const wrap = wrapRef.current;
    const fluid = startFluid(fluidRef.current, pointer);
    const dust = calm ? null : startDust(dustRef.current, pointer);
    wrap.classList.toggle('fluid-fallback', !fluid);
    const t0 = performance.now();
    let raf = 0; let running = false; let onScreen = true;
    const draw = (moving) => {
      const t = (performance.now() - t0) / 1000;
      fluid?.frame(reduce ? 0 : t, moving ? 1 : 40);
      dust?.frame(t, moving);
    };
    const tick = () => { draw(true); if (running) raf = requestAnimationFrame(tick); };
    const play = () => { if (running || reduce) return; running = true; raf = requestAnimationFrame(tick); };
    const pause = () => { running = false; cancelAnimationFrame(raf); };
    const sync = () => (onScreen && !document.hidden ? play() : pause());
    const resize = () => { fluid?.resize(); dust?.resize(); if (!running) draw(false); };
    const scheme = window.matchMedia('(prefers-color-scheme: dark)');
    const onScheme = () => { fluid?.setDark(scheme.matches); dust?.setDark(scheme.matches); if (!running) draw(false); };
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
  }, [pointer, reduce, calm]);

  return (
    <div
      ref={wrapRef}
      className={`pointer-events-none absolute inset-0 -z-10 overflow-hidden ${calm ? 'melt-edges' : 'melt-bottom'}`}
      aria-hidden="true"
    >
      <canvas ref={fluidRef} className="absolute inset-0 h-full w-full" />
      <div className="veil absolute inset-0" />
      {!calm && <canvas ref={dustRef} className="absolute inset-0 h-full w-full" />}
    </div>
  );
}
