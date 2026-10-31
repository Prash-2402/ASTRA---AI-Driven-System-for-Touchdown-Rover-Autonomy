import { Line } from "@react-three/drei";
import { Canvas, ThreeEvent, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { TouchdownSnapshot } from "../services/types";
import { CameraRig, CamMode, FollowSun, Rocks, SkyDome, Stars, ramp, useDust } from "./lib/scene";
import { bilinear, gridGeometry } from "./lib/terrainMesh";
import { fbmField, regolith } from "./lib/textures";
import MarsLander from "./models/MarsLander";
import RelayOrbiter from "./models/RelayOrbiter";

// 1 scene unit = 1 m. World ENU (x E, y N, z Up) -> scene (x, z, -y).
const toV = (p: number[]) => new THREE.Vector3(p[0], p[2], -p[1]);
export type LandingEnv = "mars" | "moon";

/** Colours of the two bodies. Mars follows the reference photograph: butterscotch haze sky, ochre dunes, darker
 *  basaltic sand in hollows. The Moon is airless: black sky, grey regolith, hard light, sparse stars. */
const THEME = {
  mars: { sky: ["#f2b987", "#d58e5c"], fog: "#e3a678", fogNear: 2200, fogFar: 17000, hemi: ["#f8d6b2", "#6b3f25", 0.62] as [string, string, number],
    sun: [-0.55, 0.42, 0.45] as [number, number, number], sunColor: "#ffe7cc", sunI: 2.5,
    ground: [0.78, 0.46, 0.27], groundDark: [0.50, 0.27, 0.15], rock: "#5e3a26" },
  moon: { sky: ["#000000", "#000000"], fog: "#000000", fogNear: 30000, fogFar: 60000, hemi: ["#9bb4d8", "#1a1a1a", 0.08] as [string, string, number],
    sun: [-0.85, 0.32, 0.30] as [number, number, number], sunColor: "#fffaf0", sunI: 3.0,
    ground: [0.50, 0.49, 0.47], groundDark: [0.33, 0.32, 0.31], rock: "#8a8781" },
};

const R_VIS = 60000;               // visual curvature radius of the far field (exaggerated so the horizon visibly bends)

function useGround(scene: any, overlay: "none" | "slope" | "hazard", env: LandingEnv) {
  return useMemo(() => {
    const th = THEME[env];
    const T = scene.terrain, D = scene.detail;
    const noise = fbmField(256, 6, 5, 19);
    const nz = (x: number, y: number, s: number) => noise[((Math.floor(x * s) % 256 + 256) % 256) * 256 + ((Math.floor(y * s) % 256 + 256) % 256)];
    const craters: number[][] = scene.craters || [];
    // crater shading on the simulated terrain: darker bowls, bright ejecta rims (heights are the physics heights)
    const craterTone = (x: number, y: number) => {
      let k = 1;
      for (const [cx, cy, r] of craters) { const d = Math.hypot(x - cx, y - cy) / r; if (d < 1) k *= 0.80 + 0.2 * d * d; else if (d < 1.35) k *= 1 + 0.10 * Math.exp(-(((d - 1.05) / 0.12) ** 2)); }
      return k;
    };
    const tone = (x: number, y: number, _z: number, slope: number, c: THREE.Color) => {
      const v = (0.84 + (nz(x, y, 0.03) - 0.5) * 0.36) * craterTone(x, y);
      const dk = Math.min(1, slope / 18) * 0.55 + Math.max(0, nz(x, y, 0.011) - 0.62) * 1.4;
      const g = th.ground, gd = th.groundDark;
      c.setRGB((g[0] + (gd[0] - g[0]) * dk) * v, (g[1] + (gd[1] - g[1]) * dk) * v, (g[2] + (gd[2] - g[2]) * dk) * v);
    };
    const n = D.heights.length;
    const dEnd = D.x0 + (n - 1) * D.resolution_m, dEndY = D.y0 + (n - 1) * D.resolution_m;
    const coarse = gridGeometry(T.heights, T.origin, T.origin, T.resolution_m, tone, { uvScale: 30,
      skip: (i, j) => { const x = T.origin + i * T.resolution_m, y = T.origin + j * T.resolution_m;
        return x > D.x0 && x + T.resolution_m < dEnd && y > D.y0 && y + T.resolution_m < dEndY; } });
    const slopeTone = (x: number, y: number, z: number, slope: number, c: THREE.Color) => {
      if (overlay === "slope") { const i = Math.round((x - D.x0) / D.resolution_m), j = Math.round((y - D.y0) / D.resolution_m);
        const sd = D.slope_deg[Math.min(n - 1, Math.max(0, i))][Math.min(n - 1, Math.max(0, j))]; ramp(sd / 15, c); c.multiplyScalar(0.9); return; }
      tone(x, y, z, slope, c);
    };
    const detail = gridGeometry(D.heights, D.x0, D.y0, D.resolution_m, slopeTone, { uvScale: 6 });
    const half = -T.origin, simH = (x: number, y: number) => bilinear(T.heights, T.origin, T.origin, T.resolution_m, x, y);
    const ground = (x: number, y: number) => (x > D.x0 && x < dEnd && y > D.y0 && y < dEndY
      ? bilinear(D.heights, D.x0, D.y0, D.resolution_m, x, y) : simH(x, y));
    const rocks: [number, number, number, number][] = (scene.rocks || []).filter((r: number[]) => Math.hypot(r[0], r[1]) < 320)
      .map((r: number[]) => [r[0], ground(r[0], r[1]) + r[3] * 0.35, -r[1], Math.max(r[2], 0.25)]);

    // ---- far field (visual only): rolling dunes, distant hills and craters out to the curved horizon ----
    const big = fbmField(256, 4, 6, 41), ridge = fbmField(256, 3, 5, 53);
    const nb = (f: Float32Array, x: number, y: number, s: number) => {
      const u = x * s, v = y * s, i = Math.floor(u), j = Math.floor(v), du = u - i, dv = v - j, w = (a: number) => ((a % 256) + 256) % 256;
      const a = f[w(i) * 256 + w(j)], b = f[w(i + 1) * 256 + w(j)], c = f[w(i) * 256 + w(j + 1)], d = f[w(i + 1) * 256 + w(j + 1)];
      return a + (b - a) * du + (c - a) * dv + (a - b - c + d) * du * dv;
    };
    const farCraters: number[][] = [];
    for (let k = 0; k < (env === "moon" ? 160 : 70); k++) {
      const a = k * 2.399963, r = 1500 + ((k * 7919) % 1000) / 1000 * 15000, rad = 40 + ((k * 104729) % 1000) / 1000 * (env === "moon" ? 700 : 450);
      farCraters.push([Math.cos(a) * r, Math.sin(a) * r, rad]);
    }
    const farH = (x: number, y: number) => {
      const r = Math.hypot(x, y);
      const dunes = (nb(big, x, y, 1 / 900) - 0.5) * (env === "moon" ? 30 : 60) + (nb(big, x, y, 1 / 260) - 0.5) * 14;
      const hills = Math.pow(Math.max(0, nb(ridge, x, y, 1 / 4200) - 0.38), 1.6) * (env === "moon" ? 1600 : 2200) * THREE.MathUtils.smoothstep(r, 2500, 9000);
      let cr = 0;
      for (const [cx, cy, rad] of farCraters) { const d = Math.hypot(x - cx, y - cy) / rad; if (d < 1.6) cr += d < 1 ? 0.22 * rad * (d * d - 1) : 0.06 * rad * Math.exp(-(((d - 1) / 0.25) ** 2)); }
      return dunes + hills + cr;
    };
    const edgeH = simH(Math.max(-half, Math.min(half, 0)), 0);
    const rings: number[] = []; for (let k = 0, r = 880; r < 32000; k++) { rings.push(r); r *= 1.055 + k * 0.0004; }
    const SEG = 256, pos: number[] = [], col: number[] = [], uv: number[] = [], idx: number[] = []; const c = new THREE.Color();
    rings.forEach((r) => { for (let s = 0; s < SEG; s++) {
      const a = (s / SEG) * Math.PI * 2, x = Math.cos(a) * r, y = Math.sin(a) * r;
      const inside = Math.abs(x) < half && Math.abs(y) < half;
      const bx = Math.max(-half, Math.min(half, x)), by = Math.max(-half, Math.min(half, y));
      const blend = THREE.MathUtils.smoothstep(Math.max(Math.abs(x), Math.abs(y)), half, half + 900);
      let h = inside ? simH(x, y) - 4 : simH(bx, by) * (1 - blend) + (edgeH + farH(x, y)) * blend;
      h -= Math.max(0, r - 1100) ** 2 / (2 * R_VIS);
      pos.push(x, h, -y); uv.push(x / 30, y / 30);
      const e = 0.01 * r; const slope = Math.abs(farH(x + e, y) - farH(x - e, y)) / (2 * e);
      tone(x, y, h, Math.atan(slope) * 57.3, c); col.push(c.r, c.g, c.b);
    } });
    for (let i = 0; i < rings.length - 1; i++) for (let s = 0; s < SEG; s++) {
      const a = i * SEG + s, b = i * SEG + ((s + 1) % SEG), cc = (i + 1) * SEG + s, d = (i + 1) * SEG + ((s + 1) % SEG);
      idx.push(a, cc, b, b, cc, d);
    }
    const far = new THREE.BufferGeometry();
    far.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); far.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    far.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); far.setIndex(idx); far.computeVertexNormals();
    return { coarse, detail, far, ground, rocks };
  }, [scene, overlay, env]);
}

function Lander({ snap, labels, dust, ground, pos }: { snap: TouchdownSnapshot; labels: boolean; dust: ReturnType<typeof useDust>; ground: (x: number, y: number) => number; pos: React.MutableRefObject<THREE.Vector3> }) {
  const g = useRef<THREE.Group>(null!);
  const f = snap.frame;
  const tq = useRef(new THREE.Quaternion());
  const tp = useRef(toV(f.truth.position));
  useEffect(() => {
    // the lander's body origin is its CoM, 1.2 m above the footpad plane
    tp.current = toV(f.truth.position).add(new THREE.Vector3(0, -1.2, 0));
    const [r, p, y] = f.truth.euler;
    const qe = new THREE.Quaternion().setFromEuler(new THREE.Euler(r, p, y, "ZYX"));
    const B = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1));
    tq.current.copy(B).multiply(qe).multiply(B.clone().invert());
  }, [f]);
  useFrame((_, dt) => {
    // jump straight to the pose on a new run / reset instead of gliding there
    if (g.current.position.lengthSq() === 0 || g.current.position.distanceTo(tp.current) > 150) { g.current.position.copy(tp.current); g.current.quaternion.copy(tq.current); }
    g.current.position.lerp(tp.current, Math.min(1, dt * 8));
    g.current.quaternion.slerp(tq.current, Math.min(1, dt * 8));
    pos.current.copy(g.current.position);
    const agl = f.truth.agl;
    if (agl < 30 && f.actuators.throttle > 0.05) {
      const p = g.current.position; const gy = ground(p.x, -p.z);
      dust.emit(Math.round(f.actuators.throttle * (30 - agl) * 3), p.x, gy + 0.05, p.z, 4, 22, 3, 25, 2 + agl * 0.3, 3.5);
    }
    dust.step(Math.min(dt, 0.05));
  });
  const scanning = ["SITE ASSESSMENT", "DIVERSION", "LANDING APPROACH"].includes(snap.phase) && f.truth.agl < 900;
  return <group ref={g}><MarsLander throttle={f.actuators.throttle} lateral={f.actuators.lateral} torque={f.actuators.torque} labels={labels} lidarScanning={scanning} /></group>;
}

/** Relay orbiter drawn far closer than its real ~300 km orbit so it can share the frame. */
function Orbiter({ landerPos, labels }: { landerPos: React.MutableRefObject<THREE.Vector3>; labels: boolean }) {
  const g = useRef<THREE.Group>(null!);
  const line = useRef<any>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const lp = landerPos.current;
    g.current.position.set(lp.x - 260 + Math.sin(t * 0.03) * 120, Math.max(lp.y + 420, 650), lp.z - 160 + Math.cos(t * 0.03) * 60);
    g.current.lookAt(lp);
    const a = g.current.position, b = lp;
    if (line.current) line.current.geometry.setPositions([a.x, a.y, a.z, b.x, b.y, b.z]);
  });
  return (
    <>
      <group ref={g} scale={3}><group rotation={[Math.PI / 2, 0, 0]}><RelayOrbiter labels={labels} /></group></group>
      <Line ref={line} points={[[0, 0, 0], [0, 1, 0]]} color="#4C6EF5" lineWidth={1} transparent opacity={0.3} dashed dashSize={6} gapSize={6} />
    </>
  );
}

/** Lidar surroundings scan: footprint ring of the latest scan, a rotating sweep, beam edges from the sensor and
 *  the rocks the lidar actually perceived (red = above the hazard limit). Everything drawn comes from the
 *  perceived hazard map, not ground truth. */
function ScanViz({ perception, ground, landerPos, active }: { perception: any; ground: (x: number, y: number) => number; landerPos: React.MutableRefObject<THREE.Vector3>; active: boolean }) {
  const sweep = useRef<THREE.Mesh>(null!);
  const pulse = useRef<THREE.Mesh>(null!);
  const beams = useRef<any[]>([]);
  const reg: number[] | null = perception?.region ?? null;
  const center = reg ? new THREE.Vector3(reg[0], ground(reg[0], reg[1]) + 0.6, -reg[1]) : null;
  useFrame(({ clock }) => {
    if (!center || !reg) return;
    const t = clock.elapsedTime;
    if (sweep.current) sweep.current.rotation.z = -t * 1.6;
    if (pulse.current) { const k = (t * 0.6) % 1; pulse.current.scale.setScalar(0.05 + k); (pulse.current.material as THREE.MeshBasicMaterial).opacity = 0.35 * (1 - k); }
    const lp = landerPos.current;
    beams.current.forEach((l, i) => { if (!l) return; const a = t * 1.6 + (i * Math.PI) / 2; const x = reg[0] + Math.cos(a) * reg[2], y = reg[1] - Math.sin(a) * reg[2];
      l.geometry.setPositions([lp.x, lp.y - 0.8, lp.z, x, ground(x, y) + 0.5, -y]); });
  });
  const rocks: number[][] = perception?.rocks || [];
  const lim = perception?.hazard_limit_m ?? 0.35;
  const rockGeom = useMemo(() => {
    const g = new THREE.BufferGeometry(); const p: number[] = [], c: number[] = [];
    rocks.forEach(([x, y, h]) => { p.push(x, ground(x, y) + 0.9, -y); const hz = h > lim; c.push(hz ? 1 : 1, hz ? 0.25 : 0.75, hz ? 0.22 : 0.2); });
    g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(c, 3)); return g;
  }, [rocks, ground, lim]);
  if (!center || !reg) return null;
  return (
    <group>
      <mesh position={center} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[reg[2] - 1.2, reg[2], 96]} /><meshBasicMaterial color="#67e8f9" transparent opacity={0.75} depthWrite={false} /></mesh>
      {active && <mesh ref={sweep} position={center} rotation={[-Math.PI / 2, 0, 0]}><circleGeometry args={[reg[2], 48, 0, Math.PI / 5]} /><meshBasicMaterial color="#67e8f9" transparent opacity={0.16} depthWrite={false} side={THREE.DoubleSide} /></mesh>}
      {active && <mesh ref={pulse} position={center} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[reg[2] * 0.97, reg[2], 96]} /><meshBasicMaterial color="#a5f3fc" transparent opacity={0.3} depthWrite={false} /></mesh>}
      {active && [0, 1, 2, 3].map((i) => <Line key={i} ref={(l) => { beams.current[i] = l; }} points={[[0, 0, 0], [0, 1, 0]]} color="#67e8f9" lineWidth={1} transparent opacity={0.35} />)}
      {rocks.length > 0 && <points geometry={rockGeom}><pointsMaterial vertexColors size={2.6} sizeAttenuation transparent opacity={0.95} depthWrite={false} /></points>}
    </group>
  );
}

/** Vertical beacon over a landing pad (as in the path-guidance reference): a beam, a ground ring and a cross. */
function Beacon({ at, color, height = 260, ring = 6 }: { at: THREE.Vector3; color: string; height?: number; ring?: number }) {
  return (
    <group position={at}>
      <Line points={[[0, 0, 0], [0, height, 0]]} color={color} lineWidth={2.4} transparent opacity={0.9} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.3, 0]}><ringGeometry args={[ring - 0.9, ring, 64]} /><meshBasicMaterial color={color} transparent opacity={0.9} depthWrite={false} /></mesh>
      <Line points={[[-ring * 0.6, 0.35, 0], [ring * 0.6, 0.35, 0]]} color={color} lineWidth={1.4} />
      <Line points={[[0, 0.35, -ring * 0.6], [0, 0.35, ring * 0.6]]} color={color} lineWidth={1.4} />
    </group>
  );
}

const path = (pts?: number[][]) => (pts && pts.length > 1 ? pts.map(toV) : null);
export const PATH_COLORS = { flown: "#34d399", target: "#22d3ee", replanned: "#fbbf24", abandoned: "#f87171", forecast: "#a78bfa" };

export default function TouchdownScene({ snap, scene, decisions, cam, labels, overlay, showPaths, showScan = true, env = "mars", placing = false, onPlace }:
  { snap: TouchdownSnapshot | null; scene: any; decisions: any[]; cam: CamMode; labels: boolean; overlay: "none" | "slope" | "hazard"; showPaths: boolean;
    showScan?: boolean; env?: LandingEnv; placing?: boolean; onPlace?: (x: number, y: number) => void }) {
  const th = THEME[env];
  const G = useGround(scene, overlay, env);
  const reg = useMemo(() => regolith(env), [env]);
  const mats = useMemo(() => [6, 30, 30].map(() => { const m = reg.map.clone(), n = reg.normal.clone(); m.needsUpdate = n.needsUpdate = true;
    return new THREE.MeshStandardMaterial({ vertexColors: true, map: m, normalMap: n, normalScale: new THREE.Vector2(1.3, 1.3), roughness: 0.96 }); }), [reg]);
  const dust = useDust({ max: 3000, gravity: env === "moon" ? 1.625 : 3.72, drag: env === "moon" ? 0 : 1.2, color: env === "moon" ? "#cfc9bf" : "#c79c74", size: 0.6 });
  const landerPos = useRef(snap ? toV(snap.frame.truth.position) : new THREE.Vector3());
  const lastDiv = [...(decisions || [])].reverse().find((d) => d.details?.alternatives);
  const tgt = snap?.frame?.target, orig = (snap as any)?.original_target ?? scene?.original_target;
  const diverted = !!(tgt && orig && Math.hypot(tgt[0] - orig[0], tgt[1] - orig[1]) > 1);
  // front-facing cameras need a heading that does not jitter when the horizontal velocity becomes small
  const headingRef = useRef(0);
  if (snap) { const v = snap.frame.truth.velocity; if (Math.hypot(v[0], v[1]) > 1.5) headingRef.current = Math.atan2(v[1], v[0]); }
  // the target path that was abandoned at the last diversion (kept per run so the replanning stays visible)
  const abandoned = useRef<{ run?: string; div: number; pts: number[][] | null; prev: number[][] | null }>({ div: 0, pts: null, prev: null });
  if (snap) {
    const a = abandoned.current;
    if (a.run !== snap.run_uid) { a.run = snap.run_uid; a.div = 0; a.pts = null; a.prev = null; }
    if ((snap.diversions ?? 0) > a.div) { a.div = snap.diversions; a.pts = a.prev; }
    else if (snap.desired_trajectory?.length) a.prev = snap.desired_trajectory;
  }
  const hazardCells = overlay === "hazard" ? (scene.perceived?.cells || []) : [];
  const hazardGeom = useMemo(() => {
    if (!hazardCells.length) return null;
    const pos: number[] = [], col: number[] = []; const c = new THREE.Color();
    hazardCells.forEach((v: number[]) => { pos.push(v[0], G.ground(v[0], v[1]) + 0.4, -v[1]); ramp(Math.abs(v[2] - G.ground(v[0], v[1])) / 1.0, c); col.push(c.r, c.g, c.b); });
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3)); return g;
  }, [hazardCells, G]);
  // obstacle placement: hover reticle + click (ignored when the pointer was dragged, e.g. orbiting the free camera)
  const reticle = useRef<THREE.Group>(null!);
  const onMove = (e: ThreeEvent<PointerEvent>) => { if (!placing || !reticle.current) return; reticle.current.visible = true; reticle.current.position.copy(e.point).add(new THREE.Vector3(0, 0.4, 0)); };
  const onClick = (e: ThreeEvent<MouseEvent>) => { if (!placing || !onPlace || e.delta > 4) return; e.stopPropagation(); onPlace(e.point.x, -e.point.z); };
  const terrainEvents = placing ? { onPointerMove: onMove, onClick } : {};
  const dustFog = env === "mars" ? 1 - 0.75 * ((snap as any)?.environment?.dust ?? 0) : 1;
  const flownCol = PATH_COLORS.flown;
  const fc = snap?.mpc_prediction?.length ? snap.mpc_prediction : snap?.predicted_trajectory;
  const perception = (snap as any)?.perception;
  const scanActive = !!snap && ["SITE ASSESSMENT", "DIVERSION", "LANDING APPROACH"].includes(snap.phase) && snap.frame.truth.agl < (perception?.assessment_agl ?? 450) + 20;
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ fov: 48, near: 0.3, far: 60000, position: [-800, 3200, 600] }} style={{ cursor: placing ? "crosshair" : undefined }}>
      {env === "moon" ? <><color attach="background" args={["#000000"]} /><Stars count={450} radius={40000} size={1.6} opacity={0.6} /></>
        : <SkyDome horizon={th.sky[0]} zenith={th.sky[1]} sunDir={th.sun} radius={45000} />}
      <fog attach="fog" args={[th.fog, th.fogNear * dustFog, th.fogFar * dustFog]} />
      <hemisphereLight args={th.hemi} />
      <FollowSun subject={() => landerPos.current} direction={th.sun} intensity={th.sunI} color={th.sunColor} size={25} />
      <directionalLight position={[th.sun[0] * 6000, th.sun[1] * 6000, th.sun[2] * 6000]} intensity={0.7} color={th.sunColor} />
      <mesh geometry={G.far} material={mats[2]} receiveShadow {...terrainEvents} />
      <mesh geometry={G.coarse} material={mats[1]} receiveShadow {...terrainEvents} />
      <mesh geometry={G.detail} material={mats[0]} receiveShadow {...terrainEvents} />
      <Rocks rocks={G.rocks} color={th.rock} />
      {hazardGeom && <points geometry={hazardGeom}><pointsMaterial vertexColors size={1.6} sizeAttenuation /></points>}
      {placing && <group ref={reticle} visible={false}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[11, 12.5, 48]} /><meshBasicMaterial color="#ef4444" transparent opacity={0.85} depthWrite={false} /></mesh>
        <Line points={[[0, 0, 0], [0, 40, 0]]} color="#ef4444" lineWidth={1.5} /></group>}
      {((snap as any)?.obstacles || []).map((o: any, i: number) => <mesh key={i} position={toV([o.x, o.y, G.ground(o.x, o.y) + 0.5])} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[o.radius - 0.8, o.radius, 64]} /><meshBasicMaterial color="#ef4444" transparent opacity={0.55} depthWrite={false} /></mesh>)}
      {showPaths && diverted && orig && <Beacon at={toV([orig[0], orig[1], G.ground(orig[0], orig[1])])} color={PATH_COLORS.abandoned} />}
      {showPaths && tgt && <Beacon at={toV([tgt[0], tgt[1], G.ground(tgt[0], tgt[1])])} color={diverted ? "#22c55e" : PATH_COLORS.target} ring={5} />}
      {!showPaths && tgt && <mesh position={toV([tgt[0], tgt[1], G.ground(tgt[0], tgt[1]) + 0.35])} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[4, 5, 64]} /><meshBasicMaterial color="#4C6EF5" /></mesh>}
      {showPaths && lastDiv?.details?.alternatives?.map((a: any, i: number) => (
        <mesh key={i} position={toV([a.x, a.y, G.ground(a.x, a.y) + 0.5])} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[a.feasible ? 2.0 : 1.4, a.feasible ? 2.6 : 1.9, 24]} /><meshBasicMaterial color={a.feasible ? "#22c55e" : "#ef4444"} transparent opacity={0.8} depthWrite={false} /></mesh>))}
      {showScan && <ScanViz perception={perception} ground={G.ground} landerPos={landerPos} active={scanActive} />}
      {showPaths && path(snap?.actual_trajectory) && <Line points={path(snap?.actual_trajectory)!} color={flownCol} lineWidth={3} />}
      {showPaths && abandoned.current.pts && path(abandoned.current.pts) && <Line points={path(abandoned.current.pts)!} color={PATH_COLORS.abandoned} lineWidth={2} dashed dashSize={10} gapSize={8} transparent opacity={0.8} />}
      {showPaths && path(snap?.desired_trajectory) && <Line points={path(snap?.desired_trajectory)!} color={diverted ? PATH_COLORS.replanned : PATH_COLORS.target} lineWidth={2.8} />}
      {showPaths && path(fc) && <Line points={path(fc)!} color={PATH_COLORS.forecast} lineWidth={2.4} dashed dashSize={6} gapSize={5} />}
      {dust.points}
      {snap && <Lander snap={snap} labels={labels} dust={dust} ground={G.ground} pos={landerPos} />}
      <Orbiter landerPos={landerPos} labels={labels} />
      <CameraRig mode={cam} subject={() => landerPos.current} heading={headingRef.current} chaseDist={13} chaseHeight={4.5} lookAhead={6} overheadHeight={140}
        observer={tgt ? toV([tgt[0] + 45, tgt[1] - 30, G.ground(tgt[0] + 45, tgt[1] - 30) + 2]) : undefined} />
    </Canvas>
  );
}
