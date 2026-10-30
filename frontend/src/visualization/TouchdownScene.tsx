import { Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { TouchdownSnapshot } from "../services/types";

// world ENU metres -> scene units: x=E, y=Up, z=-N ; 1 unit = 10 m. Lander drawn exaggerated (labelled in UI).
const S = 0.1;
const toV = (p: number[]) => new THREE.Vector3(p[0] * S, p[2] * S, -p[1] * S);

function Terrain({ scene }: { scene: any }) {
  const geom = useMemo(() => {
    const h: number[][] = scene.terrain.heights;
    const n = h.length, res = scene.terrain.resolution_m, o = scene.terrain.origin;
    const g = new THREE.PlaneGeometry((n - 1) * res * S, (n - 1) * res * S, n - 1, n - 1);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position as THREE.BufferAttribute;
    const col = new Float32Array(pos.count * 3);
    let lo = Infinity, hi = -Infinity; h.forEach((r) => r.forEach((v) => { lo = Math.min(lo, v); hi = Math.max(hi, v); }));
    const c1 = new THREE.Color("#8a5a3c"), c2 = new THREE.Color("#c99a6b"), c3 = new THREE.Color("#e6c9a3"), tmp = new THREE.Color();
    for (let k = 0; k < pos.count; k++) {
      const x = pos.getX(k) / S, zN = -pos.getZ(k) / S;
      const i = Math.round((x - o) / res), j = Math.round((zN - o) / res);
      const v = h[Math.min(n - 1, Math.max(0, i))][Math.min(n - 1, Math.max(0, j))];
      pos.setY(k, v * S);
      const f = (v - lo) / Math.max(hi - lo, 1e-6);
      tmp.copy(c1).lerp(c2, Math.min(1, f * 1.6)); if (f > 0.6) tmp.lerp(c3, (f - 0.6) / 0.4);
      col.set([tmp.r, tmp.g, tmp.b], k * 3);
    }
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.translate(o * S + ((n - 1) * res * S) / 2, 0, -(o * S + ((n - 1) * res * S) / 2));
    g.computeVertexNormals();
    return g;
  }, [scene]);
  return <mesh geometry={geom} receiveShadow><meshStandardMaterial vertexColors roughness={0.95} metalness={0} /></mesh>;
}

function Rocks({ rocks }: { rocks: number[][] }) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  const near = useMemo(() => rocks.filter((r) => Math.hypot(r[0], r[1]) < 450), [rocks]);
  useEffect(() => {
    const m = new THREE.Matrix4();
    near.forEach((r, i) => { m.makeScale(r[2] * S * 2.5, r[3] * S * 2.5, r[2] * S * 2.5); m.setPosition(r[0] * S, 0.0, -r[1] * S); ref.current.setMatrixAt(i, m); });
    ref.current.instanceMatrix.needsUpdate = true;
  }, [near]);
  return <instancedMesh ref={ref} args={[undefined, undefined, Math.max(near.length, 1)]}><dodecahedronGeometry args={[1, 0]} /><meshStandardMaterial color="#5b3f2e" roughness={1} /></instancedMesh>;
}

function Lander({ snap, exaggeration }: { snap: TouchdownSnapshot; exaggeration: number }) {
  const g = useRef<THREE.Group>(null!);
  const plume = useRef<THREE.Mesh>(null!);
  const tgt = useRef(new THREE.Vector3());
  const q = useRef(new THREE.Quaternion());
  const f = snap.frame;
  useEffect(() => {
    tgt.current.copy(toV(f.truth.position));
    const [r, p, y] = f.truth.euler; // ZYX body->world in ENU; convert to scene axes
    const qe = new THREE.Quaternion().setFromEuler(new THREE.Euler(r, p, y, "ZYX"));
    const basis = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1));
    q.current.copy(basis).multiply(qe).multiply(basis.clone().invert());
  }, [f]);
  useFrame((_, dt) => {
    // render-side interpolation only (simulation truth is never modified)
    g.current.position.lerp(tgt.current, Math.min(1, dt * 8));
    g.current.quaternion.slerp(q.current, Math.min(1, dt * 8));
    const th = f.actuators.throttle;
    plume.current.scale.set(1, Math.max(0.01, th) * 1.0, 1);
    (plume.current.material as THREE.MeshBasicMaterial).opacity = 0.25 + 0.6 * th;
  });
  const k = exaggeration * S;
  return (
    <group ref={g}>
      <group scale={[k, k, k]}>
        <mesh position={[0, 1.4, 0]} castShadow><cylinderGeometry args={[1.3, 1.6, 1.4, 16]} /><meshStandardMaterial color="#f4efe2" metalness={0.3} roughness={0.4} /></mesh>
        <mesh position={[0, 2.35, 0]}><sphereGeometry args={[0.9, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2]} /><meshStandardMaterial color="#d9cfb8" metalness={0.4} roughness={0.35} /></mesh>
        {[0, 1, 2, 3].map((i) => { const a = (i * Math.PI) / 2 + Math.PI / 4; return (
          <mesh key={i} position={[Math.cos(a) * 1.7, 0.45, Math.sin(a) * 1.7]} rotation={[Math.sin(a) * 0.5, 0, -Math.cos(a) * 0.5]}>
            <cylinderGeometry args={[0.07, 0.07, 1.6, 6]} /><meshStandardMaterial color="#536F59" /></mesh>); })}
        <mesh ref={plume} position={[0, -0.6, 0]} rotation={[Math.PI, 0, 0]}><coneGeometry args={[0.55, 2.4, 16, 1, true]} /><meshBasicMaterial color="#ffb36b" transparent opacity={0.6} depthWrite={false} /></mesh>
      </group>
    </group>
  );
}

function Follow({ snap, follow }: { snap: TouchdownSnapshot; follow: boolean }) {
  const { camera, controls } = useThree() as any;
  const last = useRef(new THREE.Vector3());
  useFrame(() => {
    if (!follow || !controls) return;
    const p = toV(snap.frame.truth.position);
    const d = p.clone().sub(last.current);
    camera.position.add(d); controls.target.add(d); last.current.copy(p);
    controls.update();
  });
  useEffect(() => { last.current.copy(toV(snap.frame.truth.position)); }, [follow]); // eslint-disable-line
  return null;
}

const path = (pts?: number[][]) => (pts && pts.length > 1 ? pts.map(toV) : null);

export default function TouchdownScene({ snap, scene, decisions, follow, exaggeration = 4 }: { snap: TouchdownSnapshot | null; scene: any; decisions: any[]; follow: boolean; exaggeration?: number }) {
  const lastDiv = [...(decisions || [])].reverse().find((d) => d.details?.alternatives);
  const actual = path(snap?.actual_trajectory), predicted = path(snap?.predicted_trajectory), desired = path(snap?.desired_trajectory),
    mpc = path(snap?.mpc_prediction), est = path(snap?.estimated_trajectory);
  const tgt = snap?.frame?.target, orig = scene?.original_target;
  const start = snap ? toV(snap.frame.truth.position) : new THREE.Vector3(0, 20, 0);
  return (
    <Canvas shadows camera={{ position: [start.x + 60, start.y + 25, start.z + 70], fov: 45, near: 0.1, far: 5000 }} dpr={[1, 1.75]}>
      <color attach="background" args={["#efe9dc"]} />
      <fog attach="fog" args={["#efe9dc", 180, 900]} />
      <hemisphereLight args={["#fff8ec", "#8a6a4d", 0.7]} />
      <directionalLight position={[-120, 200, 80]} intensity={1.6} castShadow />
      {scene && <Terrain scene={scene} />}
      {scene && <Rocks rocks={scene.rocks || []} />}
      {orig && <mesh position={toV([orig[0], orig[1], orig[2] + 0.5])} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[1.6, 2.0, 48]} /><meshBasicMaterial color="#849084" side={THREE.DoubleSide} /></mesh>}
      {tgt && <mesh position={toV([tgt[0], tgt[1], tgt[2] + 0.6])} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.9, 1.4, 48]} /><meshBasicMaterial color="#536F59" side={THREE.DoubleSide} /></mesh>}
      {snap?.frame?.predicted_touchdown && <mesh position={toV(snap.frame.predicted_touchdown)}><sphereGeometry args={[0.6, 16, 16]} /><meshBasicMaterial color="#D69B4D" /></mesh>}
      {lastDiv?.details?.alternatives?.map((a: any, i: number) => (
        <mesh key={i} position={toV([a.x, a.y, (tgt?.[2] ?? 0) + 0.8])}><boxGeometry args={[0.6, 0.15, 0.6]} /><meshBasicMaterial color={a.feasible ? "#648C65" : "#C76C64"} /></mesh>
      ))}
      {actual && <Line points={actual} color="#26372D" lineWidth={2.2} />}
      {est && <Line points={est} color="#7798A3" lineWidth={1.2} dashed dashSize={1} gapSize={0.6} />}
      {desired && <Line points={desired} color="#779477" lineWidth={1.5} />}
      {predicted && <Line points={predicted} color="#D69B4D" lineWidth={1.8} dashed dashSize={1.2} gapSize={0.8} />}
      {mpc && <Line points={mpc} color="#7798A3" lineWidth={2.4} />}
      {snap && <Lander snap={snap} exaggeration={exaggeration} />}
      <OrbitControls makeDefault enableDamping target={[start.x, start.y * 0.6, start.z]} />
      {snap && <Follow snap={snap} follow={follow} />}
    </Canvas>
  );
}
