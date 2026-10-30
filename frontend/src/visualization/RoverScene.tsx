import { Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { RoverSnapshot } from "../services/types";

// world (x E, y N, z Up) metres -> scene (x, y=up, z=-y), 1 unit = 1 m
const CLASS_COLORS = ["#b39b7e", "#c8a179", "#e4cfa5", "#7d6655"];

function heightAt(t: any, x: number, y: number) {
  const h: number[][] = t.heights, n = h.length, r = t.resolution_m, half = t.size_m / 2;
  const i = Math.max(0, Math.min(n - 1, Math.round((x + half) / r))), j = Math.max(0, Math.min(n - 1, Math.round((y + half) / r)));
  return h[i][j];
}
const V = (t: any, p: number[], lift = 0.06) => new THREE.Vector3(p[0], heightAt(t, p[0], p[1]) + lift, -p[1]);

function Ground({ t }: { t: any }) {
  const geom = useMemo(() => {
    const h: number[][] = t.heights, n = h.length, res = t.resolution_m, half = t.size_m / 2;
    const g = new THREE.PlaneGeometry(t.size_m, t.size_m, n - 1, n - 1);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position as THREE.BufferAttribute;
    const col = new Float32Array(pos.count * 3);
    const tmp = new THREE.Color();
    const m = t.classes.length;
    for (let k = 0; k < pos.count; k++) {
      const x = pos.getX(k), y = -pos.getZ(k);
      const i = Math.round((x + half) / res), j = Math.round((y + half) / res);
      pos.setY(k, h[Math.min(n - 1, Math.max(0, i))][Math.min(n - 1, Math.max(0, j))]);
      const ci = Math.min(m - 1, Math.max(0, Math.floor(x + half))), cj = Math.min(m - 1, Math.max(0, Math.floor(y + half)));
      tmp.set(CLASS_COLORS[t.classes[ci][cj]] || CLASS_COLORS[0]);
      const shade = 0.92 + 0.08 * Math.sin(x * 3.1 + y * 2.3);
      col.set([tmp.r * shade, tmp.g * shade, tmp.b * shade], k * 3);
    }
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.computeVertexNormals();
    return g;
  }, [t]);
  return <mesh geometry={geom} receiveShadow><meshStandardMaterial vertexColors roughness={0.96} /></mesh>;
}

function Obstacles({ t }: { t: any }) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  useEffect(() => {
    const m = new THREE.Matrix4();
    t.obstacles.forEach((o: number[], i: number) => {
      const z = heightAt(t, o[0], o[1]) + o[3] - o[2];
      m.makeScale(o[2], o[2], o[2]); m.setPosition(o[0], z, -o[1]); ref.current.setMatrixAt(i, m);
    });
    ref.current.instanceMatrix.needsUpdate = true;
  }, [t]);
  return <instancedMesh ref={ref} args={[undefined, undefined, Math.max(1, t.obstacles.length)]} castShadow><icosahedronGeometry args={[1, 1]} /><meshStandardMaterial color="#6b5546" roughness={1} flatShading /></instancedMesh>;
}

function Cells({ t, cells, color }: { t: any; cells: number[][]; color: string }) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  useEffect(() => {
    const m = new THREE.Matrix4();
    cells.forEach(([i, j], k) => { const x = -30 + i + 0.5, y = -30 + j + 0.5; m.makeScale(0.92, 1, 0.92); m.setPosition(x, heightAt(t, x, y) + 0.04, -y); ref.current.setMatrixAt(k, m); });
    ref.current.count = cells.length;
    ref.current.instanceMatrix.needsUpdate = true;
  }, [cells, t]);
  return <instancedMesh ref={ref} args={[undefined, undefined, 3600]}><boxGeometry args={[1, 0.02, 1]} /><meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} /></instancedMesh>;
}

function Rover({ snap, t }: { snap: RoverSnapshot; t: any }) {
  const g = useRef<THREE.Group>(null!);
  const wheels = useRef<THREE.Mesh[]>([]);
  const angles = useRef(new Array(6).fill(0));
  const target = useRef(new THREE.Vector3());
  const quat = useRef(new THREE.Quaternion());
  const f = snap.frame;
  useEffect(() => {
    const p = f.truth.position;
    target.current.set(p[0], p[2] - 0.12, -p[1]);
    const [r, pi, y] = f.truth.rpy;
    const qe = new THREE.Quaternion().setFromEuler(new THREE.Euler(r, pi, y, "ZYX"));
    const B = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1));
    quat.current.copy(B).multiply(qe).multiply(B.clone().invert());
  }, [f]);
  useFrame((_, dt) => {
    g.current.position.lerp(target.current, Math.min(1, dt * 10));
    g.current.quaternion.slerp(quat.current, Math.min(1, dt * 10));
    f.wheels.speed.forEach((w, i) => { angles.current[i] += w * dt; if (wheels.current[i]) wheels.current[i].rotation.z = -angles.current[i]; });
  });
  const j = f.wheels.joints || {};
  const faulty = f.faults_active.length > 0;
  // wheel order FL ML RL FR MR RR ; local frame: x fwd, y up, z = -left
  const side = (s: number, rocker: number, bogie: number, idx: number[]) => (
    <group position={[0.1, -0.05, -s * 0.38]} rotation={[0, 0, rocker]}>
      <mesh position={[0, -0.12, 0]} rotation={[0, 0, 0.35]}><boxGeometry args={[0.95, 0.05, 0.04]} /><meshStandardMaterial color="#779477" /></mesh>
      <Wheel at={[0.45, -0.25, -s * 0.09]} k={idx[0]} />
      <group position={[-0.4, -0.15, 0]} rotation={[0, 0, bogie]}>
        <mesh position={[0, -0.05, 0]}><boxGeometry args={[0.6, 0.05, 0.04]} /><meshStandardMaterial color="#779477" /></mesh>
        <Wheel at={[0.27, -0.1, -s * 0.09]} k={idx[1]} />
        <Wheel at={[-0.27, -0.1, -s * 0.09]} k={idx[2]} />
      </group>
    </group>
  );
  const Wheel = ({ at, k }: { at: [number, number, number]; k: number }) => {
    const health = f.wheels.health_est?.[k] ?? 1;
    return (
      <mesh ref={(m) => { if (m) wheels.current[k] = m; }} position={at} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.1, 18]} />
        <meshStandardMaterial color={health < 0.9 ? "#C76C64" : "#2f3a33"} roughness={0.8} />
      </mesh>
    );
  };
  return (
    <group ref={g}>
      <mesh castShadow><boxGeometry args={[0.9, 0.2, 0.6]} /><meshStandardMaterial color="#f3eee0" roughness={0.5} /></mesh>
      <mesh position={[0.32, 0.32, 0]}><boxGeometry args={[0.08, 0.45, 0.08]} /><meshStandardMaterial color="#536F59" /></mesh>
      <mesh position={[0.36, 0.58, 0]}><boxGeometry args={[0.14, 0.1, 0.22]} /><meshStandardMaterial color="#26372D" /></mesh>
      <mesh position={[-0.15, 0.12, 0]} rotation={[-0.2, 0, 0]}><boxGeometry args={[0.5, 0.02, 0.5]} /><meshStandardMaterial color="#3d4f61" metalness={0.5} roughness={0.3} /></mesh>
      {side(1, j.rocker_L_joint ?? 0, j.bogie_L_joint ?? 0, [0, 1, 2])}
      {side(-1, j.rocker_R_joint ?? 0, j.bogie_R_joint ?? 0, [3, 4, 5])}
      {faulty && <mesh position={[0, 0.9, 0]}><sphereGeometry args={[0.08, 12, 12]} /><meshBasicMaterial color="#C76C64" /></mesh>}
    </group>
  );
}

export default function RoverScene({ snap, scene, follow }: { snap: RoverSnapshot | null; scene: any; follow: boolean }) {
  const t = scene?.terrain;
  const controls = useRef<any>(null);
  const planned = snap?.planned_path && t && snap.planned_path.length > 1 ? snap.planned_path.map((p) => V(t, p, 0.12)) : null;
  const actual = snap?.actual_path && t && snap.actual_path.length > 1 ? snap.actual_path.map((p) => V(t, p, 0.08)) : null;
  const est = snap?.estimated_path && t && snap.estimated_path.length > 1 ? snap.estimated_path.map((p) => V(t, p, 0.1)) : null;
  const old = snap?.path_history && t ? snap.path_history.slice(0, -1).filter((h) => h.path?.length > 1) : [];
  if (!t) return <div className="h-full grid place-items-center eyebrow">Loading terrain…</div>;
  // initial camera: behind the start point, looking along the start -> target direction
  const dx = t.target[0] - t.start[0], dy = t.target[1] - t.start[1], dn = Math.hypot(dx, dy) || 1;
  const cam: [number, number, number] = [t.start[0] - (dx / dn) * 7, heightAt(t, t.start[0], t.start[1]) + 7, -(t.start[1] - (dy / dn) * 7)];
  return (
    <Canvas shadows camera={{ position: cam, fov: 48 }} dpr={[1, 1.75]}>
      <color attach="background" args={["#efe9dc"]} />
      <fog attach="fog" args={["#efe9dc", 45, 120]} />
      <hemisphereLight args={["#fffaf0", "#7c6450", 0.75]} />
      <directionalLight position={[-25, 40, 18]} intensity={1.5} castShadow shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-35} shadow-camera-right={35} shadow-camera-top={35} shadow-camera-bottom={-35} />
      <Ground t={t} />
      <Obstacles t={t} />
      {snap?.perceived && <Cells t={t} cells={snap.perceived.obstacles} color="#C76C64" />}
      {snap?.perceived && <Cells t={t} cells={snap.perceived.untraversable} color="#D69B4D" />}
      <mesh position={V(t, t.start, 0.05)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.5, 0.7, 40]} /><meshBasicMaterial color="#26372D" side={THREE.DoubleSide} /></mesh>
      <mesh position={V(t, snap?.goal ?? t.target, 0.05)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.6, 0.95, 40]} /><meshBasicMaterial color="#536F59" side={THREE.DoubleSide} /></mesh>
      <mesh position={V(t, snap?.goal ?? t.target, 1.2)}><cylinderGeometry args={[0.04, 0.04, 2.4, 8]} /><meshBasicMaterial color="#536F59" /></mesh>
      {old.map((h, i) => <Line key={i} points={h.path.map((p) => V(t, p, 0.1))} color="#AFC3A7" lineWidth={1} transparent opacity={0.6} />)}
      {planned && <Line points={planned} color="#536F59" lineWidth={3} />}
      {actual && <Line points={actual} color="#26372D" lineWidth={2} />}
      {est && <Line points={est} color="#7798A3" lineWidth={1.3} dashed dashSize={0.4} gapSize={0.25} />}
      {snap && <Rover snap={snap} t={t} />}
      <OrbitControls ref={controls} makeDefault enableDamping maxPolarAngle={Math.PI / 2.1}
        target={[t.start[0] + (dx / dn) * 4, heightAt(t, t.start[0], t.start[1]), -(t.start[1] + (dy / dn) * 4)]} />
      {snap && follow && <FollowRover snap={snap} controls={controls} />}
    </Canvas>
  );
}

function FollowRover({ snap, controls }: { snap: RoverSnapshot; controls: any }) {
  const last = useRef<THREE.Vector3 | null>(null);
  useFrame(({ camera }) => {
    const p = snap.frame.truth.position;
    const v = new THREE.Vector3(p[0], p[2], -p[1]);
    if (!controls.current) return;
    if (!last.current) { last.current = v.clone(); controls.current.target.copy(v); return; }
    const d = v.clone().sub(last.current);
    camera.position.add(d); controls.current.target.add(d); last.current.copy(v);
  });
  return null;
}
