import { OrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { regolith } from "./textures";

export type CamMode = "chase" | "observer" | "overhead" | "cinematic" | "free" | "window" | "orbiter";

/** Camera rig: each non-free mode defines a desired eye/look-at pair from the subject's pose; the camera eases
 *  toward it every frame (smooth transitions). 'free' hands control to OrbitControls around the subject. */
export function CameraRig({ mode, subject, heading = 0, observer, overheadHeight = 40, chaseDist = 6, chaseHeight = 2.5, lookAhead = 0 }:
  { mode: CamMode; subject: () => THREE.Vector3; heading?: number; observer?: THREE.Vector3; overheadHeight?: number; chaseDist?: number; chaseHeight?: number; lookAhead?: number }) {
  const { camera } = useThree();
  const controls = useRef<any>(null);
  const look = useRef(new THREE.Vector3());
  const eye = new THREE.Vector3();
  const first = useRef(true);
  useFrame(({ clock }, dt) => {
    const s = subject();
    if (mode === "free") { if (controls.current) { controls.current.target.lerp(s, Math.min(1, dt * 3)); controls.current.update(); } return; }
    const fwd = new THREE.Vector3(Math.cos(heading), 0, -Math.sin(heading));
    let target = s.clone();
    if (mode === "chase") { eye.copy(s).addScaledVector(fwd, -chaseDist).add(new THREE.Vector3(0, chaseHeight, 0)); target = s.clone().addScaledVector(fwd, lookAhead); }
    else if (mode === "observer") { eye.copy(observer ?? s.clone().add(new THREE.Vector3(30, 5, 30))); }
    else if (mode === "overhead") { eye.copy(s).add(new THREE.Vector3(0.01, overheadHeight, 0.01)); }
    else if (mode === "cinematic") { const a = clock.elapsedTime * 0.12; eye.copy(s).add(new THREE.Vector3(Math.cos(a) * chaseDist * 1.6, chaseHeight * 1.4, Math.sin(a) * chaseDist * 1.6)); }
    else if (mode === "window") { eye.copy(s).add(new THREE.Vector3(0, 1.3, 0)).addScaledVector(fwd, 1.5); target = s.clone().addScaledVector(fwd, 60).add(new THREE.Vector3(0, -40, 0)); }
    else if (mode === "orbiter") { eye.copy(s).add(new THREE.Vector3(-chaseDist * 6, chaseDist * 14, chaseDist * 4)); }
    const k = first.current ? 1 : Math.min(1, dt * 2.2);
    first.current = false;
    camera.position.lerp(eye, k);
    look.current.lerp(target, Math.min(1, dt * 4));
    camera.lookAt(look.current);
  });
  useEffect(() => { look.current.copy(subject()); }, []); // eslint-disable-line
  return mode === "free" ? <OrbitControls ref={controls} makeDefault enableDamping maxPolarAngle={Math.PI / 2.02} /> : null;
}

/** Directional sun whose shadow camera is re-centred on the subject every frame. */
export function FollowSun({ subject, direction, intensity = 2.2, color = "#fff4e6", size = 30, mapSize = 2048 }:
  { subject: () => THREE.Vector3; direction: [number, number, number]; intensity?: number; color?: string; size?: number; mapSize?: number }) {
  const light = useRef<THREE.DirectionalLight>(null!);
  const dir = useMemo(() => new THREE.Vector3(...direction).normalize(), [direction]);
  useFrame(() => {
    const s = subject();
    light.current.position.copy(s).addScaledVector(dir, size * 3);
    light.current.target.position.copy(s);
    light.current.target.updateMatrixWorld();
  });
  return (
    <directionalLight ref={light} intensity={intensity} color={color} castShadow shadow-mapSize={[mapSize, mapSize]} shadow-bias={-0.0004} shadow-normalBias={0.02}
      shadow-camera-left={-size} shadow-camera-right={size} shadow-camera-top={size} shadow-camera-bottom={-size} shadow-camera-near={0.5} shadow-camera-far={size * 8} />
  );
}

/** Irregular boulders: noise-displaced icosahedra in several variants, instanced. rocks: [x, yUp, z, size] in scene coords. */
export function Rocks({ rocks, color = "#6b5040", roughness = 0.95 }: { rocks: [number, number, number, number][]; color?: string; roughness?: number }) {
  const variants = useMemo(() => Array.from({ length: 5 }, (_, v) => {
    const g = new THREE.IcosahedronGeometry(1, 2);
    const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const n = 1 + 0.22 * Math.sin(x * 3.1 + v * 1.7) * Math.cos(z * 2.7 + v) + 0.12 * Math.sin(y * 5.3 + v * 2.3);
      p.setXYZ(i, x * n * (1 + 0.15 * v / 5), y * n * 0.7, z * n);
    }
    g.computeVertexNormals();
    return g;
  }), []);
  const mat = useMemo(() => { const r = regolith("mars"); return new THREE.MeshStandardMaterial({ color, roughness, normalMap: r.normal, flatShading: true }); }, [color, roughness]);
  const groups = useMemo(() => variants.map((_, v) => rocks.filter((_, i) => i % 5 === v)), [rocks, variants]);
  return <>{groups.map((list, v) => <InstancedRocks key={v} geom={variants[v]} mat={mat} list={list} seed={v} />)}</>;
}
function InstancedRocks({ geom, mat, list, seed }: { geom: THREE.BufferGeometry; mat: THREE.Material; list: [number, number, number, number][]; seed: number }) {
  const ref = useRef<THREE.InstancedMesh>(null!);
  useEffect(() => {
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    list.forEach(([x, y, z, r], i) => {
      q.setFromEuler(new THREE.Euler(0, (i * 2.399 + seed) % (Math.PI * 2), 0));
      s.set(r, r, r); p.set(x, y, z); m.compose(p, q, s); ref.current.setMatrixAt(i, m);
    });
    ref.current.count = list.length;
    ref.current.instanceMatrix.needsUpdate = true;
  }, [list, seed]);
  return <instancedMesh ref={ref} args={[geom, mat, Math.max(1, list.length)]} castShadow receiveShadow />;
}

/** Gradient sky dome (Mars: butterscotch horizon -> grey-blue zenith; Moon: black). */
export function SkyDome({ horizon, zenith, sunDir, sunColor = "#fff2dc", radius = 4000 }: { horizon: string; zenith: string; sunDir: [number, number, number]; sunColor?: string; radius?: number }) {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { h: { value: new THREE.Color(horizon) }, z: { value: new THREE.Color(zenith) }, s: { value: new THREE.Vector3(...sunDir).normalize() }, sc: { value: new THREE.Color(sunColor) } },
    vertexShader: "varying vec3 vd; void main(){ vd = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_Position.z = gl_Position.w; }",
    fragmentShader: `uniform vec3 h; uniform vec3 z; uniform vec3 s; uniform vec3 sc; varying vec3 vd;
      void main(){ float e = clamp(vd.y, 0.0, 1.0); vec3 c = mix(h, z, pow(e, 0.55));
        float sd = max(dot(normalize(vd), s), 0.0); c += sc * (pow(sd, 600.0) * 2.0 + pow(sd, 12.0) * 0.18);
        gl_FragColor = vec4(c, 1.0); }`,
  }), [horizon, zenith, sunDir, sunColor]);
  return <mesh material={mat} frustumCulled={false}><sphereGeometry args={[radius, 32, 16]} /></mesh>;
}

/** Starfield for airless bodies. */
export function Stars({ count = 3000, radius = 3500 }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry(); const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) { const th = Math.random() * Math.PI * 2, ph = Math.acos(Math.random()); pos.set([radius * Math.sin(ph) * Math.cos(th), radius * Math.cos(ph), radius * Math.sin(ph) * Math.sin(th)], i * 3); }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); return g;
  }, [count, radius]);
  return <points geometry={geom} frustumCulled={false}><pointsMaterial size={2.2} sizeAttenuation={false} color="#ffffff" transparent opacity={0.85} fog={false} /></points>;
}

/** Ballistic particle system. emit(n, origin) is driven by the physics-reported dust rate. With drag=0 (Moon)
 *  trajectories are exact parabolas under the given gravity; on Mars a linear drag term decelerates the dust. */
export function useDust({ max = 4000, gravity, drag = 0, color = "#bdb6ab", size = 0.25 }: { max?: number; gravity: number; drag?: number; color?: string; size?: number }) {
  const state = useMemo(() => ({ pos: new Float32Array(max * 3), vel: new Float32Array(max * 3), life: new Float32Array(max), head: 0 }), [max]);
  const geom = useMemo(() => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(state.pos, 3)); return g; }, [state]);
  const mat = useMemo(() => new THREE.PointsMaterial({ color, size, transparent: true, opacity: 0.55, depthWrite: false, sizeAttenuation: true }), [color, size]);
  const groundRef = useRef<(x: number, z: number) => number>(() => 0);
  const step = (dt: number) => {
    const { pos, vel, life } = state;
    for (let i = 0; i < max; i++) {
      if (life[i] <= 0) { pos[i * 3 + 1] = -1e5; continue; }
      life[i] -= dt;
      vel[i * 3 + 1] -= gravity * dt;
      if (drag) { const k = Math.exp(-drag * dt); vel[i * 3] *= k; vel[i * 3 + 1] *= k; vel[i * 3 + 2] *= k; }
      pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
      if (pos[i * 3 + 1] < groundRef.current(pos[i * 3], pos[i * 3 + 2]) - 0.05) life[i] = 0;
    }
    (geom.attributes.position as THREE.BufferAttribute).needsUpdate = true;
  };
  const emit = (n: number, ox: number, oy: number, oz: number, speedMin: number, speedMax: number, elevMinDeg: number, elevMaxDeg: number, ring = 1.5, lifetime = 6) => {
    for (let k = 0; k < n; k++) {
      const i = state.head; state.head = (state.head + 1) % max;
      const a = Math.random() * Math.PI * 2, sp = speedMin + Math.random() * (speedMax - speedMin);
      const el = ((elevMinDeg + Math.random() * (elevMaxDeg - elevMinDeg)) * Math.PI) / 180;
      state.pos.set([ox + Math.cos(a) * ring * Math.random(), oy, oz + Math.sin(a) * ring * Math.random()], i * 3);
      state.vel.set([Math.cos(a) * Math.cos(el) * sp, Math.sin(el) * sp, Math.sin(a) * Math.cos(el) * sp], i * 3);
      state.life[i] = lifetime * (0.6 + Math.random() * 0.4);
    }
  };
  const points = <points geometry={geom} material={mat} frustumCulled={false} />;
  return { points, step, emit, groundRef };
}

/** Diverging colour ramp for gradient overlays (0 -> mint, 0.5 -> amber, 1 -> red). */
export function ramp(t: number, out: THREE.Color) {
  t = Math.max(0, Math.min(1, t));
  const a = new THREE.Color("#2a9d8f"), b = new THREE.Color("#f2b35b"), c = new THREE.Color("#e63946");
  return t < 0.5 ? out.copy(a).lerp(b, t * 2) : out.copy(b).lerp(c, (t - 0.5) * 2);
}
