import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { foil, solarCells } from "../lib/textures";
import { Dish, Label, MAT, Strut } from "./parts";

/** Mars relay orbiter (MRO-class): foil-wrapped bus, two articulated solar-array wings, 3 m high-gain dish on a
 *  boom with gimbal, nadir telescope (HiRISE-like), star trackers, UHF relay antenna, thruster clusters. */
export default function RelayOrbiter({ labels = false, dishTarget }: { labels?: boolean; dishTarget?: THREE.Vector3 }) {
  const gold = useMemo(() => { const f = foil("gold"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.35, metalness: 0.75 }); }, []);
  const silver = useMemo(() => { const f = foil("silver"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.3, metalness: 0.85 }); }, []);
  const pv = useMemo(() => new THREE.MeshStandardMaterial({ map: solarCells(14, 5), roughness: 0.25, metalness: 0.4, side: THREE.DoubleSide }), []);
  const wings = useRef<THREE.Group[]>([]);
  useFrame(({ clock }) => wings.current.forEach((w) => w && (w.rotation.x = Math.sin(clock.elapsedTime * 0.1) * 0.15)));
  return (
    <group>
      <mesh material={gold} castShadow><boxGeometry args={[2.2, 2.6, 2.2]} /></mesh>
      <mesh position={[0, 1.31, 0]} material={silver}><boxGeometry args={[2.25, 0.04, 2.25]} /></mesh>
      {[-1, 1].map((s, i) => (
        <group key={s} position={[s * 1.1, 0.3, 0]}>
          <Strut a={[0, 0, 0]} b={[s * 1.6, 0, 0]} r={0.06} mat={MAT.alu} />
          <group ref={(g) => { if (g) wings.current[i] = g; }} position={[s * 1.6, 0, 0]}>
            {[0, 1].map((k) => <mesh key={k} position={[s * (2.6 + k * 5.1), 0, 0]} material={pv} castShadow><boxGeometry args={[5, 0.05, 2.6]} /></mesh>)}
          </group>
        </group>))}
      <group position={[0, -1.3, 0]}>
        <Strut a={[0, 0, 0]} b={[0, -1.6, 1.0]} r={0.07} mat={MAT.alu} />
        <group position={[0, -1.7, 1.1]} rotation={[Math.PI + 0.5, 0, 0]}><Dish radius={1.5} depth={0.45} mat={MAT.white} /></group>
      </group>
      <mesh position={[0.4, 1.55, 0.3]} material={MAT.black}><cylinderGeometry args={[0.5, 0.5, 0.5, 24]} /></mesh>
      <mesh position={[0.4, 1.81, 0.3]} material={MAT.glass}><cylinderGeometry args={[0.45, 0.45, 0.02, 24]} /></mesh>
      {[[-0.8, 1.35, -0.8], [-0.5, 1.35, -0.8]].map((p, i) => <mesh key={i} position={p as any} material={MAT.black}><boxGeometry args={[0.18, 0.2, 0.18]} /></mesh>)}
      <group position={[-0.9, 1.3, 0.9]}><Strut a={[0, 0, 0]} b={[0, 0.7, 0]} r={0.025} mat={MAT.offwhite} /></group>
      {[[1.1, -1.25, 1.1], [-1.1, -1.25, 1.1], [1.1, -1.25, -1.1], [-1.1, -1.25, -1.1]].map((p, i) => <mesh key={i} position={p as any} material={MAT.nozzle}><coneGeometry args={[0.1, 0.2, 12, 1, true]} /></mesh>)}
      <Label show={labels} position={[0, 3.2, 0]}>Relay orbiter (UHF relay, 3 m HGA)</Label>
      <Label show={labels} position={[6, 1, 0]}>Solar-array wing</Label>
    </group>
  );
}
