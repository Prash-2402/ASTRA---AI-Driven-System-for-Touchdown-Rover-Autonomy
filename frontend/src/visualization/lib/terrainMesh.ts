import * as THREE from "three";

/** Build an indexed terrain mesh from a height grid h[i][j] (i along world x, j along world y).
 *  World (x, y, z-up) -> scene (x, z, -y). Optional skip(i, j) drops a quad (used to cut holes for detail patches).
 *  UVs are world-metres / uvScale so tiling detail textures keep a constant physical size. */
export function gridGeometry(h: number[][], x0: number, y0: number, res: number, colorFn: (x: number, y: number, z: number, slope: number, c: THREE.Color) => void,
  opts: { skip?: (i: number, j: number) => boolean; uvScale?: number; zOffset?: number } = {}) {
  const nx = h.length, ny = h[0].length;
  const pos = new Float32Array(nx * ny * 3), col = new Float32Array(nx * ny * 3), uv = new Float32Array(nx * ny * 2);
  const c = new THREE.Color();
  const uvs = opts.uvScale ?? 8;
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
    const k = i * ny + j, x = x0 + i * res, y = y0 + j * res, z = h[i][j] + (opts.zOffset ?? 0);
    pos.set([x, z, -y], k * 3);
    const gx = (h[Math.min(i + 1, nx - 1)][j] - h[Math.max(i - 1, 0)][j]) / (2 * res);
    const gy = (h[i][Math.min(j + 1, ny - 1)] - h[i][Math.max(j - 1, 0)]) / (2 * res);
    colorFn(x, y, z, Math.atan(Math.hypot(gx, gy)) * 57.2958, c);
    col.set([c.r, c.g, c.b], k * 3);
    uv.set([x / uvs, y / uvs], k * 2);
  }
  const idx: number[] = [];
  for (let i = 0; i < nx - 1; i++) for (let j = 0; j < ny - 1; j++) {
    if (opts.skip && opts.skip(i, j)) continue;
    const a = i * ny + j, b = (i + 1) * ny + j, cc = i * ny + j + 1, d = (i + 1) * ny + j + 1;
    idx.push(a, b, cc, b, d, cc);     // counter-clockwise seen from above -> normals point up
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

export function bilinear(h: number[][], x0: number, y0: number, res: number, x: number, y: number) {
  const nx = h.length, ny = h[0].length;
  const fx = Math.max(0, Math.min(nx - 1.001, (x - x0) / res)), fy = Math.max(0, Math.min(ny - 1.001, (y - y0) / res));
  const i = Math.floor(fx), j = Math.floor(fy), dx = fx - i, dy = fy - j;
  return (1 - dx) * (1 - dy) * h[i][j] + dx * (1 - dy) * h[i + 1][j] + (1 - dx) * dy * h[i][j + 1] + dx * dy * h[i + 1][j + 1];
}
