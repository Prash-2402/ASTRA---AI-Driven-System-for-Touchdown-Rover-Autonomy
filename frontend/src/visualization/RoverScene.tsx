import { Line } from "@react-three/drei";
import { Canvas, ThreeEvent, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { RoverSnapshot } from "../services/types";
import { CameraRig, CamMode, FollowSun, Rocks, SkyDome, StableLine, ramp, useDust } from "./lib/scene";
import { bilinear, gridGeometry } from "./lib/terrainMesh";
import { fbmField, regolith } from "./lib/textures";
import MarsLander from "./models/MarsLander";
import RoverModel from "./models/RoverModel";

const SUN: [number, number, number] = [0.55, 0.62, 0.45];
const G_MARS = 3.72076;
const toS = (x: number, y: number, z: number) => new THREE.Vector3(x, z, -y);
const CLASS_RGB = [[0.55, 0.40, 0.31], [0.69, 0.46, 0.31], [0.80, 0.60, 0.40], [0.45, 0.33, 0.26]];

export type Overlay = "none" | "cost" | "slope";

function useMarsGround(t: any) {
  return useMemo(() => {
    const H: number[][] = t.heights; const res = t.resolution_m; const half = t.size_m / 2;
    const ph = (x: number, y: number) => bilinear(H, -half, -half, res, Math.max(-half, Math.min(half, x)), Math.max(-half, Math.min(half, y)));
    const noise = fbmField(256, 6, 5, 13);
    const nz = (x: number, y: number, s: number) => noise[((Math.floor(x * s) % 256 + 256) % 256) * 256 + ((Math.floor(y * s) % 256 + 256) % 256)];
    // ---- simulated arena (exact physics heightfield) ----
    const patch = gridGeometry(H, -half, -half, res, (x, y, _z, slope, c) => {
      const ci = Math.min(59, Math.max(0, Math.floor(x + half))), cj = Math.min(59, Math.max(0, Math.floor(y + half)));
      const rgb = CLASS_RGB[t.classes[ci][cj]] || CLASS_RGB[1];
      const v = 0.86 + (nz(x, y, 3) - 0.5) * 0.35 - Math.min(slope, 30) * 0.004;
      c.setRGB(rgb[0] * v, rgb[1] * v, rgb[2] * v);
    }, { uvScale: 2.5 });
    // ---- crater context terrain (visual only): floor, terraced inner wall, raised rim, ejecta ----
    const floorZ = ph(0, 0);
    const N = 121, R = 720, cres = R / (N - 1) * 2, c0 = -R;
    const crater = (x: number, y: number) => {
      const r = Math.hypot(x, y);
      const wall = r < 140 ? 0 : r < 260 ? 70 * Math.pow((r - 140) / 120, 1.8) : 70 + 12 * Math.exp(-(((r - 270) / 25) ** 2)) - (r - 260) * 0.06;
      const rough = (nz(x, y, 0.08) - 0.5) * (r < 140 ? 3 : 14) + (nz(x, y, 0.4) - 0.5) * 1.5;
      return floorZ + wall + rough;
    };
    const CH: number[][] = [];
    for (let i = 0; i < N; i++) { const row: number[] = []; for (let j = 0; j < N; j++) {
      const x = c0 + i * cres, y = c0 + j * cres; const d = Math.max(Math.abs(x), Math.abs(y));
      const blend = Math.max(0, Math.min(1, (d - 32) / 40));
      row.push((ph(x, y) - 0.35) * (1 - blend) + crater(x, y) * blend); } CH.push(row); }
    const context = gridGeometry(CH, c0, c0, cres, (x, y, z, slope, c) => {
      const v = 0.8 + (nz(x, y, 0.05) - 0.5) * 0.4; const wallTone = Math.min(1, slope / 25);
      c.setRGB((0.66 - wallTone * 0.12) * v, (0.45 - wallTone * 0.1) * v, (0.32 - wallTone * 0.07) * v);
    }, { uvScale: 14, skip: (i, j) => { const x = c0 + i * cres, y = c0 + j * cres; return Math.abs(x) < 29 && Math.abs(y) < 29 && Math.abs(x + cres) < 29 && Math.abs(y + cres) < 29; } });
    const ground = (x: number, y: number) => (Math.abs(x) < half && Math.abs(y) < half ? ph(x, y) : bilinear(CH, c0, c0, cres, x, y));
    const rocks: [number, number, number, number][] = t.obstacles.map((o: number[]) => [o[0], ph(o[0], o[1]) + o[3] - o[2], -o[1], o[2]]);
    const deco: [number, number, number, number][] = [];
    for (let k = 0; k < 420; k++) { const a = k * 2.399, r = 36 + ((k * 97) % 230); const x = Math.cos(a) * r, y = Math.sin(a) * r;
      deco.push([x, ground(x, y) + 0.05, -y, 0.15 + ((k * 37) % 10) / 10 * 0.6]); }
    return { patch, context, ground, rocks, deco };
  }, [t]);
}

function OverlayCells({ t, grid, kind, ground }: { t: any; grid: any; kind: Overlay; ground: (x: number, y: number) => number }) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  useEffect(() => {
    if (!grid) return;
    const m = new THREE.Matrix4(), c = new THREE.Color();
    let n = 0;
    const src: number[][] = kind === "cost" ? grid.cost : grid.slope;
    for (let i = 0; i < 60; i++) for (let j = 0; j < 60; j++) {
      if (!grid.seen[i][j] && kind === "slope") continue;
      const v = src[i][j]; const x = -30 + i + 0.5, y = -30 + j + 0.5;
      m.makeTranslation(x, ground(x, y) + 0.07, -y); ref.current.setMatrixAt(n, m);
      // red is reserved for BLOCKED cells; drivable ground shades green -> amber on a fixed scale (cost 1 .. 7+),
      // so one expensive patch elsewhere cannot make ordinary ground look alarming
      if (kind === "cost") { if (v < 0) c.set("#e63946"); else ramp(Math.min((v - 1) / 6, 1) * 0.5, c); }
      else ramp(v / 25, c);
      ref.current.setColorAt(n, c); n++;
    }
    ref.current.count = n;
    ref.current.instanceMatrix.needsUpdate = true;
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true;
  }, [grid, kind, ground]);
  return <instancedMesh ref={ref} args={[undefined, undefined, 3600]} frustumCulled={false}><boxGeometry args={[0.96, 0.02, 0.96]} /><meshBasicMaterial transparent opacity={0.5} depthWrite={false} /></instancedMesh>;
}

function quatFromRPY(r: number, p: number, y: number) {
  const qe = new THREE.Quaternion().setFromEuler(new THREE.Euler(r, p, y, "ZYX"));
  const B = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1));
  return B.clone().multiply(qe).multiply(B.invert());
}

/** Traverse: rover pose, joints and wheel speeds straight from PyBullet telemetry (render-interpolated). */
function TraverseRover({ snap, labels, roverPos }: { snap: RoverSnapshot; labels: boolean; roverPos: React.MutableRefObject<THREE.Vector3> }) {
  const g = useRef<THREE.Group>(null!);
  const f = snap.frame;
  const tp = useRef(new THREE.Vector3()), tq = useRef(new THREE.Quaternion());
  useEffect(() => { const p = f.truth.position; tp.current.set(p[0], p[2], -p[1]); tq.current.copy(quatFromRPY(f.truth.rpy[0], f.truth.rpy[1], f.truth.rpy[2])); }, [f]);
  useFrame((_, dt) => {
    // jump straight to the pose on a new run / reset instead of gliding there
    if (g.current.position.lengthSq() === 0 || g.current.position.distanceTo(tp.current) > 3) { g.current.position.copy(tp.current); g.current.quaternion.copy(tq.current); }
    g.current.position.lerp(tp.current, Math.min(1, dt * 8)); g.current.quaternion.slerp(tq.current, Math.min(1, dt * 8));
    roverPos.current.copy(g.current.position);
  });
  const j = f.wheels.joints || {};
  const la = f.controller?.lookahead;
  const yaw = la ? Math.atan2(la[1] - f.estimate.position[1], la[0] - f.estimate.position[0]) - f.estimate.heading : 0;
  const mastYaw = Math.atan2(Math.sin(yaw), Math.cos(yaw)) * 0.7;
  return (
    <group ref={g}>
      <RoverModel pose={{ rockerL: j.rocker_L_joint ?? 0, rockerR: j.rocker_R_joint ?? 0, bogieL: j.bogie_L_joint ?? 0, bogieR: j.bogie_R_joint ?? 0 }}
        wheelSpeeds={f.wheels.speed} wheelHealth={f.wheels.health_est} mastYaw={mastYaw} labels={labels} faultGlow={f.faults_active.length > 0} />
    </group>
  );
}

/** Wind-blown dust for storms: particles advected by the wind around the rover, density from the storm level. */
function StormDust({ level, wind, center }: { level: number; wind: number; center: React.MutableRefObject<THREE.Vector3> }) {
  const N = 2600;
  const geom = useMemo(() => { const g = new THREE.BufferGeometry(); const p = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) p.set([(Math.random() - 0.5) * 90, Math.random() * 14, (Math.random() - 0.5) * 90], i * 3);
    g.setAttribute("position", new THREE.BufferAttribute(p, 3)); return g; }, []);
  const ref = useRef<THREE.Points>(null!);
  useFrame((_, dt) => {
    const a = geom.attributes.position as THREE.BufferAttribute; const v = Math.max(1.5, wind) * 0.6;
    for (let i = 0; i < N; i++) { let x = a.getX(i) + v * dt, z = a.getZ(i) - v * 0.3 * dt; const y = a.getY(i) + Math.sin(i + x * 0.2) * dt * 0.3;
      if (x > 45) x -= 90; if (z < -45) z += 90; a.setXYZ(i, x, y, z); }
    a.needsUpdate = true;
    ref.current.position.set(center.current.x, center.current.y - 2, center.current.z);
    (ref.current.material as THREE.PointsMaterial).opacity = Math.min(0.75, level * 0.9);
  });
  return <points ref={ref} geometry={geom} visible={level > 0.03} frustumCulled={false}><pointsMaterial color="#b9845a" size={0.18} transparent opacity={0} depthWrite={false} sizeAttenuation /></points>;
}

const TASK_ICON: Record<string, string> = { collect_sand: "#f2b35b", collect_sample: "#c084fc", capture_image: "#38bdf8" };
const TASK_STATUS: Record<string, string> = { done: "#22c55e", skipped: "#9ca3af", working: "#f59e0b", active: "#ffffff", pending: "#e5e7eb" };

export default function RoverScene({ snap, scene, cam, labels, lidar, overlay, costmap, placing = false, onPlace }:
  { snap: RoverSnapshot | null; scene: any; cam: CamMode; labels: boolean; lidar: boolean; overlay: Overlay; costmap: any; placing?: boolean; onPlace?: (x: number, y: number) => void }) {
  const mode = "traverse" as const;
  const t = scene.terrain;
  const G = useMarsGround(t);
  const reg = useMemo(() => regolith("mars"), []);
  const mats = useMemo(() => [1, 2].map(() => {
    const m = reg.map.clone(), n = reg.normal.clone(); m.needsUpdate = n.needsUpdate = true;
    return new THREE.MeshStandardMaterial({ vertexColors: true, map: m, normalMap: n, normalScale: new THREE.Vector2(1.4, 1.4), roughness: 0.96 });
  }), [reg]);
  const dust = useDust({ max: 2500, gravity: G_MARS, drag: 1.4, color: "#c49a72", size: 0.12 });
  dust.groundRef.current = (x, z) => G.ground(x, -z);
  const roverPos = useRef(new THREE.Vector3(t.start[0], G.ground(t.start[0], t.start[1]) + 0.6, -t.start[1]));
  const subject = () => roverPos.current;
  const heading = snap?.frame?.truth?.rpy?.[2] ?? 0;
  const ops = (snap as any)?.ops;
  const envr = (snap as any)?.environment || { sandstorm: 0, wind_speed: 0, comms: true };
  const storm = envr.sandstorm ?? 0;
  const reticle = useRef<THREE.Group>(null!);
  const terrainEvents = placing ? {
    onPointerMove: (e: ThreeEvent<PointerEvent>) => { if (reticle.current) { reticle.current.visible = true; reticle.current.position.copy(e.point).add(new THREE.Vector3(0, 0.05, 0)); } },
    onClick: (e: ThreeEvent<MouseEvent>) => { if (e.delta > 4 || !onPlace) return; e.stopPropagation(); onPlace(e.point.x, -e.point.z); },
  } : {};
  const V = (p: number[], lift = 0.08) => toS(p[0], p[1], G.ground(p[0], p[1]) + lift);
  const planned = snap?.planned_path && snap.planned_path.length > 1 ? snap.planned_path.map((p) => V(p, 0.14)) : null;
  const actual = snap?.actual_path && snap.actual_path.length > 1 ? snap.actual_path.map((p) => V(p, 0.1)) : null;
  const est = snap?.estimated_path && snap.estimated_path.length > 1 ? snap.estimated_path.map((p) => V(p, 0.12)) : null;
  const old = snap?.path_history ? snap.path_history.slice(0, -1).filter((h) => h.path?.length > 1) : [];
  // one persistent GPU buffer for the lidar cloud, refilled in place (was a new geometry every telemetry update)
  const lidarGeom = useMemo(() => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3 * 2000), 3)); g.setDrawRange(0, 0); return g; }, []);
  useEffect(() => () => lidarGeom.dispose(), [lidarGeom]);
  useEffect(() => {
    const pts: number[][] = (snap as any)?.lidar || [];
    const a = lidarGeom.getAttribute("position") as THREE.BufferAttribute; const n = Math.min(pts.length, 2000);
    for (let k = 0; k < n; k++) a.setXYZ(k, pts[k][0], pts[k][2], -pts[k][1]);
    a.needsUpdate = true; lidarGeom.setDrawRange(0, n); lidarGeom.computeBoundingSphere();
  }, [(snap as any)?.lidar, lidarGeom]);
  const goal = snap?.goal ?? t.target;
  const goalV = V(goal, 0);
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ fov: 50, near: 0.05, far: 6000, position: [t.start[0] - 30, 40, -t.start[1] + 30] }} style={{ cursor: placing ? "crosshair" : undefined }}>
      <SkyDome horizon={storm > 0.05 ? "#c58c62" : "#d6ab83"} zenith={storm > 0.05 ? "#9b6c4c" : "#8a6f5c"} sunDir={SUN} sunColor="#fff0d8" />
      <fog attach="fog" args={[storm > 0.05 ? "#bf8a62" : "#cfa47e", 90 * (1 - 0.85 * storm) + 4, 700 * (1 - 0.9 * storm) + 25]} />
      <hemisphereLight args={["#f3dcc0", "#5a3d2a", 0.55]} />
      <FollowSun subject={subject} direction={SUN} intensity={2.4 * (1 - 0.55 * storm)} color="#fff1dc" size={18} />
      <mesh geometry={G.context} material={mats[1]} receiveShadow {...terrainEvents} />
      <mesh geometry={G.patch} material={mats[0]} receiveShadow {...terrainEvents} />
      {placing && <group ref={reticle} visible={false}><mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.55, 0.75, 32]} /><meshBasicMaterial color="#ef4444" transparent opacity={0.9} depthWrite={false} /></mesh></group>}
      {ops && <group position={V(ops.lander, 0)} rotation={[0, Math.atan2(ops.home[1] - ops.lander[1], ops.home[0] - ops.lander[0]), 0]}>
        <MarsLander throttle={0} lateral={[0, 0]} torque={[0, 0, 0]} labels={labels} landed /></group>}
      {ops && <mesh position={V(ops.home, 0.04)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[1.0, 1.2, 40]} /><meshBasicMaterial color="#e5e7eb" transparent opacity={0.6} /></mesh>}
      {ops?.tasks?.map((k: any) => <group key={k.id} position={V([k.x, k.y], 0)}>
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[1.3, 1.5, 40]} /><meshBasicMaterial color={TASK_STATUS[k.status] || "#fff"} transparent opacity={0.85} /></mesh>
        <mesh position={[0, 1.1, 0]}><cylinderGeometry args={[0.025, 0.025, 2.2, 8]} /><meshStandardMaterial color="#d8dde5" metalness={0.6} roughness={0.3} /></mesh>
        <mesh position={[0, 2.25, 0]}><octahedronGeometry args={[0.22]} /><meshStandardMaterial color={TASK_ICON[k.kind] || "#fff"} emissive={TASK_ICON[k.kind] || "#fff"} emissiveIntensity={k.status === "done" ? 0.1 : 0.6} /></mesh>
      </group>)}
      <StormDust level={storm} wind={envr.wind_speed ?? 0} center={roverPos} />
      <Rocks rocks={G.rocks} color="#6e4f3d" />
      <Rocks rocks={G.deco} color="#7a5a45" />
      {mode === "traverse" && overlay !== "none" && costmap && <OverlayCells t={t} grid={costmap} kind={overlay} ground={G.ground} />}
      {!ops && <mesh position={V(t.start, 0.04)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.7, 0.9, 48]} /><meshBasicMaterial color="#E7EEF7" transparent opacity={0.7} /></mesh>}
      {!ops && <group position={goalV}>
        <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.8, 1.1, 48]} /><meshBasicMaterial color="#6FD3A8" /></mesh>
        <mesh position={[0, 1.2, 0]}><cylinderGeometry args={[0.025, 0.025, 2.4, 8]} /><meshStandardMaterial color="#d8dde5" metalness={0.6} roughness={0.3} /></mesh>
        <mesh position={[0.25, 2.2, 0]}><boxGeometry args={[0.5, 0.3, 0.01]} /><meshStandardMaterial color="#6FD3A8" emissive="#6FD3A8" emissiveIntensity={0.4} /></mesh>
      </group>}
      {ops && <mesh position={V(goal, 0.06)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.35, 0.5, 32]} /><meshBasicMaterial color="#6FD3A8" /></mesh>}
      {mode === "traverse" && old.map((h, i) => <StableLine key={i} points={h.path.map((p) => V(p, 0.12))} color="#6FD3A8" lineWidth={1} opacity={0.25} />)}
      {mode === "traverse" && planned && <StableLine points={planned} color="#6FD3A8" lineWidth={3.2} />}
      {mode === "traverse" && actual && <StableLine points={actual} color="#ffffff" lineWidth={2} />}
      {mode === "traverse" && est && <StableLine points={est} color="#67B7F7" lineWidth={1.4} dashed dashSize={0.4} gapSize={0.25} />}
      {mode === "traverse" && lidar && <points geometry={lidarGeom}><pointsMaterial color="#67F7E1" size={0.07} sizeAttenuation /></points>}
      {dust.points}
      {snap && <TraverseRover snap={snap} labels={labels} roverPos={roverPos} />}
      <CameraRig mode={cam} subject={subject} heading={heading} chaseDist={4.2} chaseHeight={1.8} lookAhead={2} overheadHeight={32}
        observer={toS(t.start[0] + 9, t.start[1] - 7, G.ground(t.start[0], t.start[1]) + 1.7)} />
    </Canvas>
  );
}
