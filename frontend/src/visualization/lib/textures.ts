import * as THREE from "three";

/** Procedural, tileable textures generated once in the browser (no external assets).
 *  Periodic value noise -> fBm; normal maps are derived from the same height field by finite differences. */
const cache = new Map<string, THREE.Texture>();

function hash(x: number, y: number, s: number) {
  const h = Math.sin(x * 127.1 + y * 311.7 + s * 74.7) * 43758.5453;
  return h - Math.floor(h);
}
function vnoise(x: number, y: number, period: number, s: number) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const w = (a: number) => ((a % period) + period) % period;
  const a = hash(w(xi), w(yi), s), b = hash(w(xi + 1), w(yi), s), c = hash(w(xi), w(yi + 1), s), d = hash(w(xi + 1), w(yi + 1), s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
export function fbmField(size: number, base: number, octaves: number, seed: number, gain = 0.5) {
  const out = new Float32Array(size * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let amp = 1, f = base, s = 0, n = 0;
    for (let o = 0; o < octaves; o++) { s += amp * vnoise((x / size) * f, (y / size) * f, f, seed + o); n += amp; amp *= gain; f *= 2; }
    out[y * size + x] = s / n;
  }
  return out;
}

function toTexture(size: number, fill: (i: number, img: Uint8ClampedArray, p: number) => void, srgb = true) {
  const c = document.createElement("canvas"); c.width = c.height = size;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(size, size);
  for (let i = 0; i < size * size; i++) fill(i, img.data, i * 4);
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function normalFromHeight(h: Float32Array, size: number, strength: number) {
  return toTexture(size, (i, d, p) => {
    const x = i % size, y = (i / size) | 0;
    const l = h[y * size + ((x - 1 + size) % size)], r = h[y * size + ((x + 1) % size)];
    const u = h[((y - 1 + size) % size) * size + x], dn = h[((y + 1) % size) * size + x];
    const nx = (l - r) * strength, ny = (u - dn) * strength, nz = 1;
    const k = 1 / Math.hypot(nx, ny, nz);
    d[p] = (nx * k * 0.5 + 0.5) * 255; d[p + 1] = (ny * k * 0.5 + 0.5) * 255; d[p + 2] = (nz * k * 0.5 + 0.5) * 255; d[p + 3] = 255;
  }, false);
}

/** Grey detail map (multiplied with vertex colour) + matching normal map for regolith-like ground. */
export function regolith(kind: "mars" | "moon") {
  const key = "regolith-" + kind;
  if (cache.has(key)) return { map: cache.get(key)!, normal: cache.get(key + "-n")! };
  const size = 512;
  const h1 = fbmField(size, 8, 6, kind === "mars" ? 3 : 9, 0.55);
  const h2 = fbmField(size, 64, 3, kind === "mars" ? 5 : 11, 0.6);
  const h = new Float32Array(size * size);
  for (let i = 0; i < h.length; i++) {
    const pebble = h2[i] > 0.72 ? (h2[i] - 0.72) * 3 : 0;
    h[i] = h1[i] * 0.7 + h2[i] * 0.3 + pebble;
  }
  const map = toTexture(size, (i, d, p) => { const v = 175 + (h[i] - 0.5) * 120; d[p] = d[p + 1] = d[p + 2] = Math.max(0, Math.min(255, v)); d[p + 3] = 255; });
  const normal = normalFromHeight(h, size, kind === "moon" ? 9 : 6);
  cache.set(key, map); cache.set(key + "-n", normal);
  return { map, normal };
}

/** Crinkled multi-layer insulation (gold Kapton / silver). */
export function foil(color: "gold" | "silver") {
  const key = "foil-" + color;
  if (cache.has(key)) return { map: cache.get(key)!, normal: cache.get(key + "-n")! };
  const size = 256;
  const h = fbmField(size, 12, 4, color === "gold" ? 21 : 22, 0.6);
  const base = color === "gold" ? [206, 160, 64] : [205, 208, 214];
  const map = toTexture(size, (i, d, p) => { const k = 0.75 + h[i] * 0.5; d[p] = base[0] * k; d[p + 1] = base[1] * k; d[p + 2] = base[2] * k; d[p + 3] = 255; });
  const normal = normalFromHeight(h, size, 14);
  cache.set(key, map); cache.set(key + "-n", normal);
  return { map, normal };
}

/** Photovoltaic array: dark blue cells separated by silver bus bars. */
export function solarCells(cols = 12, rows = 4) {
  const key = `solar-${cols}-${rows}`;
  if (cache.has(key)) return cache.get(key)!;
  const size = 512;
  const t = toTexture(size, (i, d, p) => {
    const x = (i % size) / size, y = ((i / size) | 0) / size;
    const cx = (x * cols) % 1, cy = (y * rows) % 1;
    const gap = cx < 0.04 || cy < 0.06;
    const finger = Math.abs(((cx * 6) % 1) - 0.5) < 0.03;
    if (gap) { d[p] = 170; d[p + 1] = 176; d[p + 2] = 186; }
    else { const s = finger ? 40 : 0; d[p] = 18 + s; d[p + 1] = 34 + s; d[p + 2] = 78 + s; }
    d[p + 3] = 255;
  });
  cache.set(key, t);
  return t;
}
