import { useMemo } from "react";
import * as THREE from "three";
import { foil } from "../lib/textures";
import { Label, MAT, Nozzle, Plume, Strut } from "./parts";

/** Sky-crane descent stage: octagonal truss, four propellant tanks, eight canted throttleable engines on
 *  four outriggers, bridle-umbilical device (BUD), terminal-descent radar. Scaled to the ASTRA rover. */
export default function DescentStage({ throttle, labels = false }: { throttle: number; labels?: boolean }) {
  const gold = useMemo(() => { const f = foil("gold"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.35, metalness: 0.75 }); }, []);
  const ring = Array.from({ length: 8 }, (_, i) => (i / 8) * Math.PI * 2 + Math.PI / 8);
  const R = 0.7;
  return (
    <group>
      {/* octagonal deck */}
      <mesh rotation={[0, Math.PI / 8, 0]} material={gold} castShadow><cylinderGeometry args={[R, R, 0.12, 8]} /></mesh>
      <mesh position={[0, -0.09, 0]} rotation={[0, Math.PI / 8, 0]} material={MAT.darkAlu}><cylinderGeometry args={[R * 0.85, R * 0.85, 0.06, 8]} /></mesh>
      {ring.map((a, i) => <Strut key={i} a={[Math.cos(a) * R, 0.06, Math.sin(a) * R]} b={[Math.cos(a + Math.PI / 4) * R, 0.06, Math.sin(a + Math.PI / 4) * R]} r={0.015} mat={MAT.alu} />)}
      {/* propellant tanks */}
      {[0, 1, 2, 3].map((i) => { const a = (i / 4) * Math.PI * 2 + Math.PI / 4; return (
        <mesh key={i} position={[Math.cos(a) * 0.38, 0.14, Math.sin(a) * 0.38]} material={MAT.offwhite} castShadow><sphereGeometry args={[0.15, 20, 14]} /></mesh>); })}
      <mesh position={[0, 0.16, 0]} material={MAT.alu}><sphereGeometry args={[0.12, 18, 12]} /></mesh>
      {/* engine outriggers: two canted MLEs each */}
      {[0, 1, 2, 3].map((i) => { const a = (i / 4) * Math.PI * 2; const x = Math.cos(a) * (R + 0.18), z = Math.sin(a) * (R + 0.18); return (
        <group key={i}>
          <Strut a={[Math.cos(a) * R * 0.8, 0, Math.sin(a) * R * 0.8]} b={[x, -0.02, z]} r={0.03} mat={MAT.darkAlu} />
          {[-0.12, 0.12].map((o, k) => (
            <group key={k} position={[x - Math.sin(a) * o, -0.05, z + Math.cos(a) * o]} rotation={[Math.sin(a) * 0.3, 0, -Math.cos(a) * 0.3]}>
              <Nozzle throat={0.025} exit={0.07} length={0.16} />
              <group position={[0, -0.16, 0]}><Plume throttle={throttle} length={1.0} radius={0.07} color="#ffd9a6" core="#ffffff" /></group>
            </group>))}
        </group>); })}
      {/* Bridle-Umbilical Device (winch) */}
      <mesh position={[0, -0.16, 0]} rotation={[Math.PI / 2, 0, 0]} material={MAT.graphite}><cylinderGeometry args={[0.1, 0.1, 0.14, 18]} /></mesh>
      {/* terminal-descent radar antennas */}
      {[0, 1, 2, 3, 4, 5].map((i) => { const a = (i / 6) * Math.PI * 2; return (
        <mesh key={i} position={[Math.cos(a) * 0.45, -0.13, Math.sin(a) * 0.45]} rotation={[-Math.PI / 2 + 0.3 * Math.cos(a), 0, 0.3 * Math.sin(a)]} material={MAT.offwhite}>
          <cylinderGeometry args={[0.05, 0.05, 0.02, 14]} /></mesh>); })}
      <Label show={labels} position={[0, 0.45, 0]}>Descent stage · 8 throttleable engines</Label>
      <Label show={labels} position={[0, -0.32, 0]}>Bridle-umbilical device</Label>
    </group>
  );
}
