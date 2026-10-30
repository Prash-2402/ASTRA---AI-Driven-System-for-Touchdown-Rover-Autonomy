import { useMemo } from "react";
import * as THREE from "three";
import { foil, solarCells } from "../lib/textures";
import { Label, MAT, Nozzle, Plume, Strut } from "./parts";
import RoverModel from "./RoverModel";

/** ASTRA TOUCHDOWN lander (1.55 t class), each actuator modelled where the physics model applies it:
 *  main engine along body +z, four lateral thrusters (body ±x, ±y), RCS quads at the deck corners,
 *  four legs (footpad circle 2.2 m), landing radar and a gimballed hazard-detection lidar,
 *  two folded decagonal solar arrays, and the stowed rover payload on the deck.
 *  Local frame: +y = body thrust axis (up), +x = body x. 1 unit = 1 m. */
export default function MarsLander({ throttle, lateral, torque, labels = false, lidarScanning = false, landed = false }:
  { throttle: number; lateral: number[]; torque: number[]; labels?: boolean; lidarScanning?: boolean; landed?: boolean }) {
  const silver = useMemo(() => { const f = foil("silver"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.3, metalness: 0.85 }); }, []);
  const gold = useMemo(() => { const f = foil("gold"); return new THREE.MeshStandardMaterial({ map: f.map, normalMap: f.normal, roughness: 0.35, metalness: 0.75 }); }, []);
  const pv = useMemo(() => new THREE.MeshStandardMaterial({ map: solarCells(10, 3), roughness: 0.25, metalness: 0.4, side: THREE.DoubleSide }), []);
  const legs = [0, 1, 2, 3].map((i) => (i / 4) * Math.PI * 2 + Math.PI / 4);
  const latPods: [number, number, number][] = [[1, 0, 0], [-1, 0, 0], [0, 0, -1], [0, 0, 1]];   // body +x, -x, +y(=-z), -y
  const latCmd = [Math.max(-lateral[0], 0), Math.max(lateral[0], 0), Math.max(-lateral[1], 0), Math.max(lateral[1], 0)];
  return (
    <group>
      {/* main body: hexagonal bus with foil, top deck */}
      <mesh position={[0, 1.15, 0]} material={gold} castShadow><cylinderGeometry args={[1.05, 1.15, 0.7, 6]} /></mesh>
      <mesh position={[0, 1.52, 0]} material={MAT.offwhite}><cylinderGeometry args={[1.1, 1.1, 0.05, 6]} /></mesh>
      {/* propellant tanks visible under the bus */}
      {[-0.45, 0.45].map((x) => <mesh key={x} position={[x, 0.65, 0]} material={silver} castShadow><sphereGeometry args={[0.38, 24, 16]} /></mesh>)}
      {/* main engine + plume (body +z thrust -> exhaust downward) */}
      <group position={[0, 0.55, 0]}>
        <Nozzle throat={0.12} exit={0.42} length={0.75} />
        <group position={[0, -0.75, 0]}><Plume throttle={throttle} length={9} radius={0.45} /></group>
      </group>
      {/* lateral thruster pods - plume on the side opposite to the commanded force */}
      {latPods.map((d, i) => (
        <group key={i} position={[d[0] * 1.12, 1.1, d[2] * 1.12]} rotation={[d[2] * -Math.PI / 2, 0, d[0] * Math.PI / 2]}>
          <mesh material={MAT.graphite}><boxGeometry args={[0.18, 0.18, 0.18]} /></mesh>
          <group position={[0, -0.1, 0]}><Nozzle throat={0.025} exit={0.06} length={0.12} />
            <group position={[0, -0.12, 0]}><Plume throttle={latCmd[i]} length={2.2} radius={0.08} color="#cfe7ff" core="#ffffff" /></group></group>
        </group>))}
      {/* RCS quads */}
      {legs.map((a, i) => (
        <group key={i} position={[Math.cos(a) * 1.1, 1.45, Math.sin(a) * 1.1]}>
          <mesh material={MAT.darkAlu}><boxGeometry args={[0.14, 0.1, 0.14]} /></mesh>
          {Math.abs(torque[i % 3] ?? 0) > 0.15 && <mesh position={[Math.cos(a) * 0.15, 0, Math.sin(a) * 0.15]}><sphereGeometry args={[0.09, 10, 8]} />
            <meshBasicMaterial color="#dff1ff" transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>}
        </group>))}
      {/* landing legs: primary strut + two secondaries + footpad (pad circle radius 2.2 m) */}
      {legs.map((a, i) => { const fx = Math.cos(a) * 2.2, fz = Math.sin(a) * 2.2; const hx = Math.cos(a) * 0.95, hz = Math.sin(a) * 0.95;
        const p = [-Math.sin(a) * 0.45, 0, Math.cos(a) * 0.45]; return (
        <group key={i}>
          <Strut a={[hx, 1.0, hz]} b={[fx, 0.12, fz]} r={0.05} mat={MAT.alu} />
          <Strut a={[hx * 0.8 + p[0], 0.55, hz * 0.8 + p[2]]} b={[fx * 0.75, 0.35, fz * 0.75]} r={0.025} mat={MAT.darkAlu} />
          <Strut a={[hx * 0.8 - p[0], 0.55, hz * 0.8 - p[2]]} b={[fx * 0.75, 0.35, fz * 0.75]} r={0.025} mat={MAT.darkAlu} />
          <mesh position={[fx, 0.05, fz]} material={MAT.alu} castShadow><cylinderGeometry args={[0.32, 0.26, 0.08, 24]} /></mesh>
        </group>); })}
      {/* folded decagonal solar arrays */}
      {[-1, 1].map((s) => (
        <group key={s} position={[0, 1.58, s * 0.62]} rotation={[s * 0.12, 0, 0]}>
          <mesh material={pv} castShadow><cylinderGeometry args={[0.55, 0.55, 0.03, 10]} /></mesh>
        </group>))}
      {/* stowed rover payload (scaled) - gone once the rover has deployed onto the surface */}
      {!landed && <group position={[0, 1.83, 0]} scale={0.55} rotation={[0, Math.PI / 2, 0]}>
        <RoverModel pose={{ rockerL: 0, rockerR: 0, bogieL: 0, bogieR: 0 }} wheelSpeeds={[0, 0, 0, 0, 0, 0]} />
      </group>}
      {/* landing radar (6 antennas) and hazard-detection lidar */}
      {[0, 1, 2, 3, 4, 5].map((i) => { const a = (i / 6) * Math.PI * 2; return (
        <mesh key={i} position={[Math.cos(a) * 0.6, 0.78, Math.sin(a) * 0.6]} material={MAT.offwhite}><cylinderGeometry args={[0.09, 0.09, 0.03, 16]} /></mesh>); })}
      <group position={[1.05, 0.85, 0]}>
        <Strut a={[0, 0, 0]} b={[0.3, -0.1, 0]} r={0.02} mat={MAT.darkAlu} />
        <mesh position={[0.36, -0.12, 0]} material={MAT.black}><sphereGeometry args={[0.08, 16, 12]} /></mesh>
        {lidarScanning && <mesh position={[0.36, -0.12, 0]} rotation={[0, 0, 0]}><coneGeometry args={[6, 40, 24, 1, true]} />
          <meshBasicMaterial color="#67B7F7" transparent opacity={0.05} depthWrite={false} side={THREE.DoubleSide} /></mesh>}
      </group>
      <Label show={labels} position={[0, -0.6, 0]}>Main engine (10 kN, Isp 225 s)</Label>
      <Label show={labels} position={[1.6, 1.2, 0]}>Lateral thruster pod</Label>
      <Label show={labels} position={[1.5, 0.6, 0]}>Hazard-detection lidar</Label>
      <Label show={labels} position={[2.3, 0.3, 0]}>Landing leg + footpad</Label>
      <Label show={labels} position={[0, 2.35, 0]}>Rover payload</Label>
      <Label show={labels} position={[-0.8, 1.0, 0]}>Propellant tanks</Label>
    </group>
  );
}
