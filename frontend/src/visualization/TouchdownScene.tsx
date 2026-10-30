import { Line } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { TouchdownSnapshot } from "../services/types";
import { CameraRig, CamMode, FollowSun, Rocks, SkyDome, ramp, useDust } from "./lib/scene";
import { bilinear, gridGeometry } from "./lib/terrainMesh";
import { fbmField, regolith } from "./lib/textures";
import MarsLander from "./models/MarsLander";
import RelayOrbiter from "./models/RelayOrbiter";

// 1 scene unit = 1 m. World ENU (x E, y N, z Up) -> scene (x, z, -y).
const toV = (p: number[]) => new THREE.Vector3(p[0], p[2], -p[1]);
const SUN: [number, number, number] = [-0.5, 0.55, 0.45];

function useGround(scene: any, overlay: "none" | "slope" | "hazard") {
  return useMemo(() => {
    const T = scene.terrain, D = scene.detail;
    const noise = fbmField(256, 6, 5, 19);
    const nz = (x: number, y: number, s: number) => noise[((Math.floor(x * s) % 256 + 256) % 256) * 256 + ((Math.floor(y * s) % 256 + 256) % 256)];
    const tone = (x: number, y: number, _z: number, slope: number, c: THREE.Color) => {
      const v = 0.82 + (nz(x, y, 0.03) - 0.5) * 0.35;
      const dark = Math.min(1, slope / 20) * 0.18;
      c.setRGB((0.70 - dark) * v, (0.47 - dark * 0.8) * v, (0.33 - dark * 0.6) * v);
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
    const ground = (x: number, y: number) => (x > D.x0 && x < dEnd && y > D.y0 && y < dEndY
      ? bilinear(D.heights, D.x0, D.y0, D.resolution_m, x, y) : bilinear(T.heights, T.origin, T.origin, T.resolution_m, x, y));
    const rocks: [number, number, number, number][] = (scene.rocks || []).filter((r: number[]) => Math.hypot(r[0], r[1]) < 300)
      .map((r: number[]) => [r[0], ground(r[0], r[1]) + r[3] * 0.35, -r[1], Math.max(r[2], 0.25)]);
    return { coarse, detail, ground, rocks };
  }, [scene, overlay]);
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
    if (g.current.position.lengthSq() === 0) g.current.position.copy(tp.current);
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

/** Relay orbiter drawn far closer than its real ~300 km orbit so it can share the frame; the link is animated. */
function Orbiter({ landerPos, labels }: { landerPos: React.MutableRefObject<THREE.Vector3>; labels: boolean }) {
  const g = useRef<THREE.Group>(null!);
  const pulses = useRef<THREE.Mesh[]>([]);
  const line = useRef<any>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const lp = landerPos.current;
    g.current.position.set(lp.x - 260 + Math.sin(t * 0.03) * 120, Math.max(lp.y + 420, 650), lp.z - 160 + Math.cos(t * 0.03) * 60);
    g.current.lookAt(lp);
    const a = g.current.position, b = lp;
    if (line.current) line.current.geometry.setPositions([a.x, a.y, a.z, b.x, b.y, b.z]);
    pulses.current.forEach((m, i) => { if (!m) return; const k = ((t * 0.35 + i / 4) % 1); m.position.lerpVectors(b, a, k); });
  });
  return (
    <>
      <group ref={g} scale={3}><group rotation={[Math.PI / 2, 0, 0]}><RelayOrbiter labels={labels} /></group></group>
      <Line ref={line} points={[[0, 0, 0], [0, 1, 0]]} color="#4C6EF5" lineWidth={1} transparent opacity={0.45} dashed dashSize={6} gapSize={6} />
      {[0, 1, 2, 3].map((i) => <mesh key={i} ref={(m) => { if (m) pulses.current[i] = m; }}><sphereGeometry args={[1.6, 10, 8]} /><meshBasicMaterial color="#748FFC" /></mesh>)}
    </>
  );
}

const path = (pts?: number[][]) => (pts && pts.length > 1 ? pts.map(toV) : null);

export default function TouchdownScene({ snap, scene, decisions, cam, labels, overlay, showPaths }:
  { snap: TouchdownSnapshot | null; scene: any; decisions: any[]; cam: CamMode; labels: boolean; overlay: "none" | "slope" | "hazard"; showPaths: boolean }) {
  const G = useGround(scene, overlay);
  const reg = useMemo(() => regolith("mars"), []);
  const mats = useMemo(() => [1, 2].map(() => { const m = reg.map.clone(), n = reg.normal.clone(); m.needsUpdate = n.needsUpdate = true;
    return new THREE.MeshStandardMaterial({ vertexColors: true, map: m, normalMap: n, normalScale: new THREE.Vector2(1.3, 1.3), roughness: 0.96 }); }), [reg]);
  const dust = useDust({ max: 3000, gravity: 3.72, drag: 1.2, color: "#c79c74", size: 0.6 });
  const landerPos = useRef(snap ? toV(snap.frame.truth.position) : new THREE.Vector3());
  const lastDiv = [...(decisions || [])].reverse().find((d) => d.details?.alternatives);
  const tgt = snap?.frame?.target, orig = scene?.original_target;
  const heading = snap ? Math.atan2(snap.frame.truth.velocity[1], snap.frame.truth.velocity[0]) : 0;
  const hazardCells = overlay === "hazard" ? (scene.perceived?.cells || []) : [];
  const hazardGeom = useMemo(() => {
    if (!hazardCells.length) return null;
    const pos: number[] = [], col: number[] = []; const c = new THREE.Color();
    const mean = hazardCells.reduce((a: number, v: number[]) => a + v[2], 0) / hazardCells.length;
    hazardCells.forEach((v: number[]) => { pos.push(v[0], G.ground(v[0], v[1]) + 0.4, -v[1]); ramp(Math.abs(v[2] - G.ground(v[0], v[1])) / 1.0, c); col.push(c.r, c.g, c.b); });
    void mean;
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3)); return g;
  }, [hazardCells, G]);
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ fov: 48, near: 0.3, far: 9000, position: [-800, 3200, 600] }}>
      <SkyDome horizon="#d8ae86" zenith="#8b7262" sunDir={SUN} radius={7000} />
      <fog attach="fog" args={["#cfa682", 600, 4200]} />
      <hemisphereLight args={["#f2d9bd", "#5b3d29", 0.55]} />
      <FollowSun subject={() => landerPos.current} direction={SUN} intensity={2.4} color="#fff0da" size={25} />
      <directionalLight position={[-3000, 3300, 2700]} intensity={0.6} color="#fff0da" />
      <mesh geometry={G.coarse} material={mats[1]} receiveShadow />
      <mesh geometry={G.detail} material={mats[0]} receiveShadow />
      <Rocks rocks={G.rocks} color="#5f4434" />
      {hazardGeom && <points geometry={hazardGeom}><pointsMaterial vertexColors size={1.6} sizeAttenuation /></points>}
      {orig && <mesh position={toV([orig[0], orig[1], G.ground(orig[0], orig[1]) + 0.3])} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[9, 10, 64]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.7} /></mesh>}
      {tgt && <group position={toV([tgt[0], tgt[1], G.ground(tgt[0], tgt[1]) + 0.35])}>
        <mesh rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[4, 5, 64]} /><meshBasicMaterial color="#4C6EF5" /></mesh>
        <mesh position={[0, 30, 0]}><cylinderGeometry args={[0.15, 0.15, 60, 8]} /><meshBasicMaterial color="#748FFC" transparent opacity={0.35} /></mesh></group>}
      {lastDiv?.details?.alternatives?.map((a: any, i: number) => { const c = new THREE.Color(); ramp(1 - Math.max(0, Math.min(1, a.score)), c); return (
        <mesh key={i} position={toV([a.x, a.y, G.ground(a.x, a.y) + 0.5])} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[a.feasible ? 2.4 : 1.6, 24]} /><meshBasicMaterial color={a.feasible ? c : "#E03131"} transparent opacity={0.85} /></mesh>); })}
      {snap?.frame?.predicted_touchdown && <mesh position={toV([snap.frame.predicted_touchdown[0], snap.frame.predicted_touchdown[1], G.ground(snap.frame.predicted_touchdown[0], snap.frame.predicted_touchdown[1]) + 0.6])}><sphereGeometry args={[1.4, 16, 16]} /><meshBasicMaterial color="#F08C00" /></mesh>}
      {showPaths && path(snap?.actual_trajectory) && <Line points={path(snap?.actual_trajectory)!} color="#ffffff" lineWidth={2.2} />}
      {showPaths && path(snap?.estimated_trajectory) && <Line points={path(snap?.estimated_trajectory)!} color="#1C7ED6" lineWidth={1.2} dashed dashSize={8} gapSize={5} />}
      {showPaths && path(snap?.desired_trajectory) && <Line points={path(snap?.desired_trajectory)!} color="#12B886" lineWidth={1.6} />}
      {showPaths && path(snap?.predicted_trajectory) && <Line points={path(snap?.predicted_trajectory)!} color="#F08C00" lineWidth={2} dashed dashSize={10} gapSize={6} />}
      {showPaths && path(snap?.mpc_prediction) && <Line points={path(snap?.mpc_prediction)!} color="#4C6EF5" lineWidth={3} />}
      {dust.points}
      {snap && <Lander snap={snap} labels={labels} dust={dust} ground={G.ground} pos={landerPos} />}
      <Orbiter landerPos={landerPos} labels={labels} />
      <CameraRig mode={cam} subject={() => landerPos.current} heading={heading} chaseDist={13} chaseHeight={4.5} lookAhead={6} overheadHeight={140}
        observer={tgt ? toV([tgt[0] + 45, tgt[1] - 30, G.ground(tgt[0] + 45, tgt[1] - 30) + 2]) : undefined} />
    </Canvas>
  );
}
