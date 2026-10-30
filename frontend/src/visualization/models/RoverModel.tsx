import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Dish, Label, MAT, Strut } from "./parts";

/**
 * Perseverance-class six-wheel rover, dimensioned to match the ASTRA physics model (URDF):
 *   rocker pivot (0.10, -0.05, ±0.38), front wheel (+0.45, -0.25), bogie pivot (-0.40, -0.15) on the rocker,
 *   middle/rear wheels (±0.27, -0.10) on the bogie, wheel radius 0.16 m.
 * Local frame: +x forward, +y up, -z = rover left. Joint angles come straight from simulation telemetry.
 */
export interface RoverPose { rockerL: number; rockerR: number; bogieL: number; bogieR: number }

const R_WHEEL = 0.16, W_WHEEL = 0.1;

function Wheel({ spin, side, health = 1 }: { spin: { current: number }; side: number; health?: number }) {
  const g = useRef<THREE.Group>(null!);
  const grousers = useMemo(() => Array.from({ length: 16 }, (_, i) => (i / 16) * Math.PI * 2), []);
  useFrame(() => { g.current.rotation.z = -spin.current; });
  return (
    <group ref={g}>
      {/* rim / tyre skin */}
      <mesh rotation={[Math.PI / 2, 0, 0]} castShadow material={MAT.alu}><cylinderGeometry args={[R_WHEEL - 0.008, R_WHEEL - 0.008, W_WHEEL, 36, 1, true]} /></mesh>
      {/* chevron grousers */}
      {grousers.map((a, i) => (
        <group key={i} rotation={[0, 0, a]}>
          <mesh position={[0, R_WHEEL - 0.004, -0.025]} rotation={[0.45, 0, 0]} material={MAT.alu}><boxGeometry args={[0.008, 0.008, 0.05]} /></mesh>
          <mesh position={[0, R_WHEEL - 0.004, 0.025]} rotation={[-0.45, 0, 0]} material={MAT.alu}><boxGeometry args={[0.008, 0.008, 0.05]} /></mesh>
        </group>))}
      {/* inner disc with titanium flexure spokes */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, side * 0.03]} material={MAT.darkAlu}><cylinderGeometry args={[R_WHEEL * 0.92, R_WHEEL * 0.92, 0.006, 32]} /></mesh>
      {Array.from({ length: 6 }, (_, i) => (
        <mesh key={i} rotation={[0, 0, (i / 6) * Math.PI * 2 + 0.3]} position={[0, 0, side * 0.035]} material={MAT.alu}>
          <boxGeometry args={[0.012, R_WHEEL * 1.7, 0.008]} /></mesh>))}
      {/* hub drive motor */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -side * 0.01]} material={health < 0.9 ? MAT.red : MAT.graphite}><cylinderGeometry args={[0.045, 0.045, 0.09, 16]} /></mesh>
    </group>
  );
}

export default function RoverModel({ pose, wheelSpeeds, wheelHealth, mastYaw = 0, labels = false, armDeployed = false, faultGlow = false }:
  { pose: RoverPose; wheelSpeeds: number[]; wheelHealth?: number[]; mastYaw?: number; labels?: boolean; armDeployed?: boolean; faultGlow?: boolean }) {
  const spins = useRef(Array.from({ length: 6 }, () => ({ current: 0 })));
  const ws = useRef(wheelSpeeds);
  ws.current = wheelSpeeds;
  const mast = useRef<THREE.Group>(null!);
  useFrame((_, dt) => {
    ws.current.forEach((w, i) => { spins.current[i].current += (w || 0) * Math.min(dt, 0.05); });
    mast.current.rotation.y += (mastYaw - mast.current.rotation.y) * Math.min(1, dt * 2);
  });
  const h = wheelHealth || [1, 1, 1, 1, 1, 1];

  // one side of the rocker-bogie; s = +1 left (-z), -1 right
  const Suspension = ({ s, rocker, bogie, idx }: { s: number; rocker: number; bogie: number; idx: number[] }) => {
    const z = -s * 0.38;
    return (
      <group position={[0.1, -0.05, z]} rotation={[0, 0, -rocker]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={MAT.graphite}><cylinderGeometry args={[0.035, 0.035, 0.06, 16]} /></mesh>
        <Strut a={[0, 0, 0]} b={[0.45, -0.25, 0]} r={0.022} />
        <Strut a={[0, 0, 0]} b={[-0.4, -0.15, 0]} r={0.022} />
        <Strut a={[0.45, -0.25, 0]} b={[0.45, -0.25, -s * 0.06]} r={0.018} mat={MAT.darkAlu} />
        <group position={[0.45, -0.25, -s * 0.09]}><Wheel spin={spins.current[idx[0]]} side={s} health={h[idx[0]]} /></group>
        <group position={[-0.4, -0.15, 0]} rotation={[0, 0, -bogie]}>
          <mesh rotation={[Math.PI / 2, 0, 0]} material={MAT.graphite}><cylinderGeometry args={[0.03, 0.03, 0.05, 14]} /></mesh>
          <Strut a={[-0.27, -0.1, 0]} b={[0.27, -0.1, 0]} r={0.02} />
          <Strut a={[0, 0, 0]} b={[0, -0.1, 0]} r={0.02} />
          {[0.27, -0.27].map((x, k) => (
            <group key={k}>
              <Strut a={[x, -0.1, 0]} b={[x, -0.1, -s * 0.06]} r={0.016} mat={MAT.darkAlu} />
              <group position={[x, -0.1, -s * 0.09]}><Wheel spin={spins.current[idx[k + 1]]} side={s} health={h[idx[k + 1]]} /></group>
            </group>))}
        </group>
      </group>
    );
  };

  const diff = (pose.rockerL - pose.rockerR) / 2;
  return (
    <group>
      {/* Warm Electronics Box (chassis) */}
      <mesh castShadow receiveShadow material={MAT.white}><boxGeometry args={[0.9, 0.2, 0.6]} /></mesh>
      <mesh position={[0, 0.102, 0]} material={MAT.offwhite}><boxGeometry args={[0.88, 0.006, 0.58]} /></mesh>
      {[-0.3, -0.1, 0.1].map((x) => <mesh key={x} position={[x, 0.106, 0.15]} material={MAT.graphite}><boxGeometry args={[0.12, 0.012, 0.18]} /></mesh>)}
      {/* side panel seams */}
      {[-0.225, 0, 0.225].map((x) => <mesh key={x} position={[x, 0, 0.301]} material={MAT.offwhite}><boxGeometry args={[0.004, 0.18, 0.002]} /></mesh>)}
      {/* front hazcams */}
      {[-0.08, 0.08].map((z) => <mesh key={z} position={[0.455, -0.05, z]} material={MAT.black}><boxGeometry args={[0.02, 0.035, 0.05]} /></mesh>)}
      {[-0.08, 0.08].map((z) => <mesh key={"l" + z} position={[0.466, -0.05, z]} rotation={[0, 0, Math.PI / 2]} material={MAT.glass}><cylinderGeometry args={[0.009, 0.009, 0.004, 12]} /></mesh>)}
      {/* Differential bar across the deck + links to rockers */}
      <group position={[-0.05, 0.135, 0]} rotation={[0, diff * 0.8, 0]}>
        <Strut a={[0, 0, -0.36]} b={[0, 0, 0.36]} r={0.014} mat={MAT.darkAlu} />
        <mesh material={MAT.graphite}><cylinderGeometry args={[0.03, 0.03, 0.03, 12]} /></mesh>
      </group>
      <Strut a={[-0.05, 0.135, -0.36]} b={[0.1, -0.05, -0.38]} r={0.009} mat={MAT.darkAlu} />
      <Strut a={[-0.05, 0.135, 0.36]} b={[0.1, -0.05, 0.38]} r={0.009} mat={MAT.darkAlu} />
      {/* Radioisotope power system (MMRTG) with cooling fins, rear */}
      <group position={[-0.53, 0.1, 0]} rotation={[0, 0, 0.55]}>
        <mesh material={MAT.graphite} castShadow><cylinderGeometry args={[0.07, 0.07, 0.24, 18]} /></mesh>
        {Array.from({ length: 8 }, (_, i) => (
          <mesh key={i} rotation={[0, (i / 8) * Math.PI * 2, 0]} position={[0, 0, 0]} material={MAT.black}>
            <boxGeometry args={[0.2, 0.22, 0.006]} /></mesh>))}
      </group>
      {/* Remote Sensing Mast + head (Mastcam-Z pair, SuperCam) */}
      <group position={[0.3, 0.1, 0.2]}>
        <Strut a={[0, 0, 0]} b={[0, 0.5, 0]} r={0.022} mat={MAT.white} />
        <group ref={mast} position={[0, 0.52, 0]}>
          <mesh material={MAT.white} castShadow><boxGeometry args={[0.1, 0.07, 0.2]} /></mesh>
          <mesh position={[0.056, 0.0, 0]} rotation={[0, 0, Math.PI / 2]} material={MAT.graphite}><cylinderGeometry args={[0.03, 0.03, 0.02, 20]} /></mesh>
          <mesh position={[0.067, 0.0, 0]} rotation={[0, 0, Math.PI / 2]} material={MAT.glass}><cylinderGeometry args={[0.022, 0.022, 0.004, 20]} /></mesh>
          {[-0.07, 0.07].map((z) => (
            <group key={z} position={[0.056, -0.005, z]}>
              <mesh rotation={[0, 0, Math.PI / 2]} material={MAT.black}><cylinderGeometry args={[0.014, 0.014, 0.03, 14]} /></mesh>
              <mesh position={[0.016, 0, 0]} rotation={[0, 0, Math.PI / 2]} material={MAT.glass}><cylinderGeometry args={[0.01, 0.01, 0.003, 14]} /></mesh>
            </group>))}
        </group>
      </group>
      {/* High-gain antenna (hexagonal) on gimbal + UHF antenna */}
      <group position={[-0.2, 0.12, -0.18]}>
        <Strut a={[0, 0, 0]} b={[0, 0.07, 0]} r={0.012} mat={MAT.darkAlu} />
        <group position={[0, 0.08, 0]} rotation={[0.2, 0, 0.5]}><Dish radius={0.11} depth={0.015} mat={MAT.offwhite} sides={6} /></group>
      </group>
      <group position={[-0.32, 0.12, 0.2]}><Strut a={[0, 0, 0]} b={[0, 0.12, 0]} r={0.008} mat={MAT.offwhite} />
        <mesh position={[0, 0.13, 0]} material={MAT.offwhite}><cylinderGeometry args={[0.02, 0.03, 0.03, 12]} /></mesh></group>
      {/* Robotic arm (5-DOF), stowed across the front; turret with drill */}
      <group position={[0.46, 0.0, -0.22]}>
        <mesh material={MAT.graphite}><cylinderGeometry args={[0.03, 0.03, 0.06, 14]} /></mesh>
        <Strut a={[0, 0, 0]} b={armDeployed ? [0.3, 0.05, 0.05] : [0.03, 0.02, 0.36]} r={0.016} mat={MAT.white} />
        <Strut a={armDeployed ? [0.3, 0.05, 0.05] : [0.03, 0.02, 0.36]} b={armDeployed ? [0.5, -0.15, 0.08] : [0.06, 0.08, 0.1]} r={0.014} mat={MAT.white} />
        <group position={armDeployed ? [0.5, -0.18, 0.08] : [0.07, 0.1, 0.08]}>
          <mesh material={MAT.darkAlu}><boxGeometry args={[0.07, 0.07, 0.07]} /></mesh>
          <Strut a={[0, -0.03, 0]} b={[0, -0.1, 0]} r={0.006} mat={MAT.alu} />
          <mesh position={[0.04, 0, 0]} material={MAT.graphite}><cylinderGeometry args={[0.018, 0.018, 0.04, 12]} /></mesh>
        </group>
      </group>
      <Suspension s={1} rocker={pose.rockerL} bogie={pose.bogieL} idx={[0, 1, 2]} />
      <Suspension s={-1} rocker={pose.rockerR} bogie={pose.bogieR} idx={[3, 4, 5]} />
      {faultGlow && <pointLight position={[0, 0.5, 0]} color="#F07167" intensity={0.8} distance={2} />}
      <Label show={labels} position={[0.3, 0.75, 0.2]}>Remote Sensing Mast · Mastcam-Z · SuperCam</Label>
      <Label show={labels} position={[-0.55, 0.32, 0]}>MMRTG power source</Label>
      <Label show={labels} position={[-0.2, 0.3, -0.18]}>High-gain antenna</Label>
      <Label show={labels} position={[0.55, 0.12, -0.2]}>Robotic arm (stowed)</Label>
      <Label show={labels} position={[0.0, 0.05, -0.55]}>Rocker-bogie suspension</Label>
      <Label show={labels} position={[-0.05, 0.22, 0]}>Differential bar</Label>
      <Label show={labels} position={[0.55, -0.45, -0.5]}>Wheel · grousers · hub motor</Label>
    </group>
  );
}
