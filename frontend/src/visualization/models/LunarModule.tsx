import { useMemo } from "react";
import * as THREE from "three";
import { foil } from "../lib/textures";
import { Dish, Label, MAT, Nozzle, Plume, Strut } from "./parts";

/** Apollo-class Lunar Module. Descent stage: octagonal foil-wrapped structure, four cantilever legs (primary +
 *  two secondary struts, 0.94 m footpads), 1.73 m surface-sensing probes on three legs, ladder, DPS engine bell.
 *  Ascent stage: faceted crew cabin, triangular windows, docking tunnel, four RCS quads, rendezvous radar,
 *  steerable S-band antenna. Origin = centre of mass (2.3 m above the footpad plane). */
export default function LunarModule({ throttle, rcs, engineOn, labels = false }: { throttle: number; rcs: number[]; engineOn: boolean; labels?: boolean }) {
  const gold = useMemo(() => { const f = foil("gold"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.35, metalness: 0.75 }); }, []);
  const silver = useMemo(() => { const f = foil("silver"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.3, metalness: 0.85 }); }, []);
  const cabin = useMemo(() => new THREE.MeshStandardMaterial({ color: "#8d9096", roughness: 0.55, metalness: 0.5, flatShading: true }), []);
  const blackPanel = useMemo(() => new THREE.MeshStandardMaterial({ color: "#1e1f22", roughness: 0.6, metalness: 0.3, flatShading: true }), []);
  const Y0 = -2.3;   // footpad plane
  const legs = [0, 1, 2, 3].map((i) => (i / 4) * Math.PI * 2 + Math.PI / 4);
  const rcsOn = Math.abs(rcs[0]) + Math.abs(rcs[1]) > 300;
  return (
    <group>
      {/* descent stage: octagon with foil, quadrant bays */}
      <group position={[0, Y0 + 1.95, 0]}>
        <mesh rotation={[0, Math.PI / 8, 0]} material={gold} castShadow><cylinderGeometry args={[2.05, 2.05, 1.65, 8]} /></mesh>
        <mesh position={[0, 0.84, 0]} rotation={[0, Math.PI / 8, 0]} material={silver}><cylinderGeometry args={[2.1, 2.1, 0.06, 8]} /></mesh>
        <mesh position={[0, -0.84, 0]} rotation={[0, Math.PI / 8, 0]} material={MAT.black}><cylinderGeometry args={[2.0, 2.0, 0.05, 8]} /></mesh>
        {/* DPS engine */}
        <group position={[0, -0.85, 0]}>
          <Nozzle throat={0.28} exit={0.75} length={1.0} />
          <group position={[0, -1.0, 0]}><Plume throttle={engineOn ? throttle : 0} length={7} radius={0.55} color="#c9d8ff" core="#ffffff" /></group>
        </group>
      </group>
      {/* landing gear */}
      {legs.map((a, i) => { const fx = Math.cos(a) * 4.6, fz = Math.sin(a) * 4.6; const ax = Math.cos(a) * 1.9, az = Math.sin(a) * 1.9;
        const perp = [-Math.sin(a), 0, Math.cos(a)]; return (
        <group key={i}>
          <Strut a={[ax, Y0 + 2.55, az]} b={[fx, Y0 + 0.25, fz]} r={0.09} mat={gold} />
          <Strut a={[ax + perp[0] * 1.2, Y0 + 1.25, az + perp[2] * 1.2]} b={[fx * 0.72, Y0 + 0.95, fz * 0.72]} r={0.045} mat={MAT.alu} />
          <Strut a={[ax - perp[0] * 1.2, Y0 + 1.25, az - perp[2] * 1.2]} b={[fx * 0.72, Y0 + 0.95, fz * 0.72]} r={0.045} mat={MAT.alu} />
          <Strut a={[ax * 0.95, Y0 + 1.15, az * 0.95]} b={[fx * 0.72, Y0 + 0.95, fz * 0.72]} r={0.04} mat={MAT.alu} />
          <mesh position={[fx, Y0 + 0.1, fz]} material={silver} castShadow><sphereGeometry args={[0.47, 24, 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2]} /></mesh>
          {i !== 0 && <Strut a={[fx, Y0 + 0.08, fz]} b={[fx + Math.cos(a) * 0.1, Y0 - 1.73, fz + Math.sin(a) * 0.1]} r={0.012} mat={MAT.alu} />}
          {i === 0 && [0.4, 0.8, 1.2, 1.6, 2.0].map((t) => (
            <Strut key={t} a={[ax + (fx - ax) * (t / 2.6) - perp[0] * 0.25, Y0 + 2.55 - 2.3 * (t / 2.6), az + (fz - az) * (t / 2.6) - perp[2] * 0.25]}
              b={[ax + (fx - ax) * (t / 2.6) + perp[0] * 0.25, Y0 + 2.55 - 2.3 * (t / 2.6), az + (fz - az) * (t / 2.6) + perp[2] * 0.25]} r={0.015} mat={MAT.alu} />))}
        </group>); })}
      {/* ascent stage */}
      <group position={[0, Y0 + 3.6, 0]}>
        <mesh material={cabin} castShadow><dodecahedronGeometry args={[1.45, 0]} /></mesh>
        <mesh position={[0.9, 0.1, 0]} rotation={[0, 0, -0.2]} material={blackPanel}><boxGeometry args={[0.9, 1.6, 2.4]} /></mesh>
        {[-0.55, 0.55].map((z) => <mesh key={z} position={[1.36, 0.45, z]} rotation={[0, 0, -0.35]} material={MAT.glass}><coneGeometry args={[0.28, 0.02, 3]} /></mesh>)}
        <mesh position={[1.4, -0.45, 0]} material={MAT.black}><boxGeometry args={[0.05, 0.85, 0.8]} /></mesh>
        <mesh position={[0, 1.45, 0]} material={MAT.alu}><cylinderGeometry args={[0.45, 0.5, 0.35, 20]} /></mesh>
        {[[1, 1], [1, -1], [-1, 1], [-1, -1]].map(([sx, sz], i) => (
          <group key={i} position={[sx * 1.15, 0.4, sz * 1.15]}>
            <mesh material={MAT.darkAlu}><boxGeometry args={[0.28, 0.28, 0.28]} /></mesh>
            {[[0.22, 0, 0], [0, 0.22, 0], [0, -0.22, 0], [0, 0, sz * 0.22]].map((p, k) => <mesh key={k} position={p as any} material={MAT.nozzle}><coneGeometry args={[0.05, 0.14, 10, 1, true]} /></mesh>)}
            {rcsOn && <mesh position={[0, sx * rcs[0] > 0 ? 0.35 : -0.35, 0]}><sphereGeometry args={[0.16, 10, 8]} />
              <meshBasicMaterial color="#e6f2ff" transparent opacity={0.5} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>}
          </group>))}
        <group position={[-1.0, 1.0, 0.6]}><Strut a={[0, 0, 0]} b={[0, 0.6, 0]} r={0.04} /><group position={[0, 0.65, 0]} rotation={[0.6, 0, 0.4]}><Dish radius={0.35} depth={0.12} /></group></group>
        <group position={[0.6, 1.0, -0.9]}><Strut a={[0, 0, 0]} b={[0.2, 0.4, 0]} r={0.03} /><group position={[0.25, 0.5, 0]} rotation={[0, 0, -0.7]}><Dish radius={0.3} depth={0.08} mat={MAT.alu} /></group></group>
      </group>
      <Label show={labels} position={[0, 2.6, 0]}>Ascent stage (crew cabin)</Label>
      <Label show={labels} position={[2.5, Y0 + 1.95, 0]}>Descent stage (gold MLI)</Label>
      <Label show={labels} position={[0, Y0 - 0.2, 0]}>Descent engine (45 kN, throttleable)</Label>
      <Label show={labels} position={[3.4, Y0 - 1.0, 3.4]}>Contact probe 1.73 m</Label>
      <Label show={labels} position={[1.6, 1.9, 1.6]}>RCS quad</Label>
    </group>
  );
}
