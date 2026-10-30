import { Line } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { CameraRig, CamMode, FollowSun, Rocks, Stars, useDust } from "./lib/scene";
import { bilinear, gridGeometry } from "./lib/terrainMesh";
import { fbmField, regolith } from "./lib/textures";
import LunarModule from "./models/LunarModule";

const SUN: [number, number, number] = [-0.95, 0.21, 0.22];       // ~12 deg elevation, behind the approach (Apollo-like)
const G_MOON = 1.625;
const toS = (p: number[]) => new THREE.Vector3(p[0], p[2], -p[1]);

function useLunarGround(scene: any) {
  return useMemo(() => {
    const T = scene.terrain;
    const C = T.coarse, D = T.detail;
    const noise = fbmField(128, 6, 4, 77);
    const albedo = (x: number, y: number, z: number, slope: number, c: THREE.Color) => {
      const n = noise[((Math.floor(x / 37) % 128 + 128) % 128) * 128 + ((Math.floor(y / 37) % 128 + 128) % 128)];
      const v = 0.42 + (n - 0.5) * 0.18 + Math.min(slope, 30) / 30 * 0.12;     // brighter fresh slopes / rims
      c.setRGB(v * 1.0, v * 0.985, v * 0.96);
    };
    const nDx = D.heights.length, dEnd = D.x0 + (nDx - 1) * D.res, dEndY = D.y0 + (D.heights[0].length - 1) * D.res;
    const coarse = gridGeometry(C.heights, C.x0, C.y0, C.res, albedo, {
      uvScale: 24, skip: (i, j) => { const x = C.x0 + i * C.res, y = C.y0 + j * C.res; return x > D.x0 && x + C.res < dEnd && y > D.y0 && y + C.res < dEndY; } });
    const detail = gridGeometry(D.heights, D.x0, D.y0, D.res, albedo, { uvScale: 6 });
    const ground = (x: number, y: number) => {
      if (x > D.x0 && x < dEnd && y > D.y0 && y < dEndY) return bilinear(D.heights, D.x0, D.y0, D.res, x, y);
      return bilinear(C.heights, C.x0, C.y0, C.res, x, y);
    };
    const rocks: [number, number, number, number][] = T.boulders.map((b: number[]) => [b[0], b[2] + b[3] * 0.25, -b[1], b[3] * 0.6]);
    return { coarse, detail, ground, rocks };
  }, [scene]);
}

function Earth() {
  const tex = useMemo(() => {
    const n = 256, f = fbmField(n, 5, 5, 31), cl = fbmField(n, 7, 4, 41);
    const c = document.createElement("canvas"); c.width = c.height = n; const ctx = c.getContext("2d")!; const img = ctx.createImageData(n, n);
    for (let i = 0; i < n * n; i++) { const land = f[i] > 0.56, cloud = cl[i] > 0.55; const p = i * 4;
      const rgb = cloud ? [235, 240, 245] : land ? [92, 120, 70] : [22, 60, 130]; img.data.set([...rgb, 255], p); }
    ctx.putImageData(img, 0, 0); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  }, []);
  return (
    <mesh position={[900, 1500, 2600]} rotation={[0.4, 0, 0.2]}>
      <sphereGeometry args={[60, 48, 32]} />
      <meshStandardMaterial map={tex} roughness={0.8} emissive="#0b1a33" emissiveIntensity={0.15} />
    </mesh>
  );
}

function Vehicle({ snap, labels, dust }: { snap: any; labels: boolean; dust: ReturnType<typeof useDust> }) {
  const g = useRef<THREE.Group>(null!);
  const f = snap.frame;
  const tgt = useRef(toS(f.truth.position));
  useEffect(() => { tgt.current = toS(f.truth.position); }, [f]);
  useFrame((_, dt) => {
    g.current.position.lerp(tgt.current, Math.min(1, dt * 10));
    g.current.rotation.set(0, 0, 0);
    g.current.rotateZ(-f.truth.pitch);       // pitch about crossrange: thrust tilts toward +x
    g.current.rotateX(f.truth.roll);         // roll: thrust crossrange component -sin(phi) maps to scene +z
    // dust driven by the physics-reported erosion rate (kg/s): ~350 particles per kg, ejected at 1-4 deg
    const rate = f.dust_rate || 0;
    if (rate > 0.002) {
      const p = g.current.position;
      const gy = dust.groundRef.current(p.x, p.z);
      dust.emit(Math.min(220, Math.round(rate * 350 * dt * 60)), p.x, gy + 0.05, p.z, 40, 180, 1, 4, 3 + (p.y - gy) * 0.25, 4);
    }
    dust.step(Math.min(dt, 0.05));
  });
  return <group ref={g}><LunarModule throttle={f.engine.throttle} rcs={f.engine.rcs_torque} engineOn={f.engine.on} labels={labels} /></group>;
}

export default function MoonScene({ snap, scene, cam, labels, showPlan }: { snap: any; scene: any; cam: CamMode; labels: boolean; showPlan: boolean }) {
  const ground = useLunarGround(scene);
  const reg = useMemo(() => regolith("moon"), []);
  const mats = useMemo(() => [6, 24].map((rep) => {
    const m = reg.map.clone(), n = reg.normal.clone(); m.needsUpdate = n.needsUpdate = true;
    return new THREE.MeshStandardMaterial({ vertexColors: true, map: m, normalMap: n, normalScale: new THREE.Vector2(1.2, 1.2), roughness: 0.97, metalness: 0 });
  }), [reg]);
  const dust = useDust({ max: 6000, gravity: G_MOON, drag: 0, color: "#cfc9bf", size: 0.35 });
  dust.groundRef.current = (x, z) => ground.ground(x, -z);
  const f = snap?.frame;
  const pos = useRef(new THREE.Vector3());
  const subject = () => (f ? pos.current.lerp(toS(f.truth.position), 0.2) : new THREE.Vector3());
  const shadowFocus = () => {
    if (!f) return new THREE.Vector3();
    const p = toS(f.truth.position); const gz = ground.ground(f.truth.position[0], f.truth.position[1]);
    const h = p.y - gz; const s = new THREE.Vector3(...SUN).normalize();
    return new THREE.Vector3(p.x - (s.x / s.y) * h * 0.5, gz, p.z - (s.z / s.y) * h * 0.5);
  };
  const target = f ? toS(f.target) : new THREE.Vector3();
  const trail = snap?.trail?.length > 1 ? snap.trail.map(toS) : null;
  const plan = showPlan && snap?.plan?.length > 1 ? snap.plan.map(toS) : null;
  const sheet = Math.min(1, (f?.dust_rate ?? 0) / 1.5);
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ fov: 50, near: 0.5, far: 12000, position: [-4500, 2300, 400] }} gl={{ antialias: true }}>
      <color attach="background" args={["#000000"]} />
      <Stars count={450} radius={3500} size={1.6} opacity={0.6} />
      <Earth />
      <ambientLight intensity={0.035} />
      <hemisphereLight args={["#9bb4d8", "#1a1a1a", 0.06]} />
      <FollowSun subject={shadowFocus} direction={SUN} intensity={3.2} color="#fffaf0" size={70} mapSize={2048} />
      <directionalLight position={[-9000, 2000, 2000]} intensity={0.9} color="#fffaf0" />
      <mesh geometry={ground.coarse} material={mats[1]} receiveShadow />
      <mesh geometry={ground.detail} material={mats[0]} receiveShadow castShadow />
      <Rocks rocks={ground.rocks} color="#8a8781" />
      <mesh position={[target.x, target.y + 0.15, target.z]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[7, 7.6, 64]} /><meshBasicMaterial color="#6FD3A8" transparent opacity={0.8} /></mesh>
      <mesh position={[target.x, target.y + 0.15, target.z]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.6, 1.0, 32]} /><meshBasicMaterial color="#6FD3A8" /></mesh>
      {trail && <Line points={trail} color="#E7EEF7" lineWidth={1.6} transparent opacity={0.8} />}
      {plan && <Line points={plan} color="#6FD3A8" lineWidth={2} dashed dashSize={20} gapSize={12} />}
      {f && sheet > 0.02 && (() => { const p = toS(f.truth.position); const gy = ground.ground(f.truth.position[0], f.truth.position[1]); return (
        <mesh position={[p.x, gy + 0.3, p.z]} rotation={[-Math.PI / 2, 0, 0]}><circleGeometry args={[12 + 30 * sheet, 48]} />
          <meshBasicMaterial color="#d8d2c6" transparent opacity={0.22 * sheet} depthWrite={false} /></mesh>); })()}
      {dust.points}
      {snap && <Vehicle snap={snap} labels={labels} dust={dust} />}
      {f && <CameraRig mode={cam} subject={subject} heading={0} chaseDist={28} chaseHeight={9} lookAhead={15}
        observer={new THREE.Vector3(target.x + 60, target.y + 8, target.z - 45)} overheadHeight={160} />}
    </Canvas>
  );
}
