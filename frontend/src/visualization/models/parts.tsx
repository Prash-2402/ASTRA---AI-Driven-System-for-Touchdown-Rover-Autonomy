import { Html } from "@react-three/drei";
import { ReactNode, useMemo } from "react";
import * as THREE from "three";

/** Shared materials (created once) and small building blocks used by every vehicle model. */
export const MAT = {
  white: new THREE.MeshStandardMaterial({ color: "#e9e5dc", roughness: 0.55, metalness: 0.08 }),
  offwhite: new THREE.MeshStandardMaterial({ color: "#cfcac0", roughness: 0.6, metalness: 0.1 }),
  alu: new THREE.MeshStandardMaterial({ color: "#b9bec6", roughness: 0.35, metalness: 0.85 }),
  darkAlu: new THREE.MeshStandardMaterial({ color: "#6d737c", roughness: 0.45, metalness: 0.8 }),
  black: new THREE.MeshStandardMaterial({ color: "#16181c", roughness: 0.5, metalness: 0.2 }),
  graphite: new THREE.MeshStandardMaterial({ color: "#2b2f36", roughness: 0.7, metalness: 0.3 }),
  glass: new THREE.MeshStandardMaterial({ color: "#0b1a2a", roughness: 0.05, metalness: 0.9 }),
  copper: new THREE.MeshStandardMaterial({ color: "#b4734a", roughness: 0.4, metalness: 0.8 }),
  nozzle: new THREE.MeshStandardMaterial({ color: "#3a3532", roughness: 0.6, metalness: 0.7, side: THREE.DoubleSide }),
  red: new THREE.MeshStandardMaterial({ color: "#F07167", emissive: "#F07167", emissiveIntensity: 0.6 }),
};

/** A cylinder spanning two points (used for struts, tubes, cables). */
export function Strut({ a, b, r = 0.02, mat = MAT.alu, seg = 8 }: { a: number[]; b: number[]; r?: number; mat?: THREE.Material; seg?: number }) {
  const { pos, quat, len } = useMemo(() => {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
    const d = B.clone().sub(A);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize());
    return { pos: A.clone().add(B).multiplyScalar(0.5), quat: q, len: d.length() };
  }, [a, b]);
  return <mesh position={pos} quaternion={quat} castShadow material={mat}><cylinderGeometry args={[r, r, len, seg]} /></mesh>;
}

/** Bell-shaped rocket nozzle (lathe profile), opening along -Y. */
export function Nozzle({ throat = 0.05, exit = 0.16, length = 0.3, mat = MAT.nozzle }: { throat?: number; exit?: number; length?: number; mat?: THREE.Material }) {
  const geom = useMemo(() => {
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 16; i++) { const t = i / 16; pts.push(new THREE.Vector2(throat + (exit - throat) * Math.pow(t, 0.6), -t * length)); }
    return new THREE.LatheGeometry(pts, 28);
  }, [throat, exit, length]);
  return <mesh geometry={geom} material={mat} castShadow />;
}

/** Parabolic dish antenna opening along +Y. */
export function Dish({ radius = 0.3, depth = 0.08, mat = MAT.offwhite, sides = 32 }: { radius?: number; depth?: number; mat?: THREE.Material; sides?: number }) {
  const geom = useMemo(() => {
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 12; i++) { const r = (i / 12) * radius; pts.push(new THREE.Vector2(r, (r * r) / (radius * radius) * depth)); }
    return new THREE.LatheGeometry(pts, sides);
  }, [radius, depth, sides]);
  return <mesh geometry={geom} castShadow><primitive object={mat} attach="material" side={THREE.DoubleSide} /></mesh>;
}

/** Engine exhaust: two nested additive cones whose length/opacity follow the throttle. */
export function Plume({ throttle, length = 2, radius = 0.25, color = "#ffb070", core = "#fff3d6", visible = true }:
  { throttle: number; length?: number; radius?: number; color?: string; core?: string; visible?: boolean }) {
  const k = Math.max(0, Math.min(1, throttle));
  if (!visible || k < 0.02) return null;
  const L = length * (0.35 + 0.65 * k);
  return (
    <group>
      <mesh position={[0, -L / 2, 0]}><coneGeometry args={[radius * (0.9 + k), L, 24, 1, true]} />
        <meshBasicMaterial color={color} transparent opacity={0.18 + 0.32 * k} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} /></mesh>
      <mesh position={[0, -L * 0.28, 0]} rotation={[Math.PI, 0, 0]}><coneGeometry args={[radius * 0.45, L * 0.56, 16, 1, true]} />
        <meshBasicMaterial color={core} transparent opacity={0.35 + 0.5 * k} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} /></mesh>
    </group>
  );
}

/** Floating component annotation (toggleable). */
export function Label({ show, position, children }: { show: boolean; position: [number, number, number]; children: ReactNode }) {
  if (!show) return null;
  return (
    <Html position={position} center distanceFactor={undefined} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
      <div style={{ font: "500 10.5px Inter, sans-serif", color: "#E7EEF7", background: "rgba(7,11,20,.78)", border: "1px solid rgba(111,211,168,.5)",
        padding: "2px 7px", borderRadius: 6, whiteSpace: "nowrap", transform: "translateY(-14px)" }}>{children}</div>
    </Html>
  );
}
