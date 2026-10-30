import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { bakeMars } from "./marsBake";

/** Shared scroll state written by the landing page, read inside the render loop (no React re-renders). */
export const scrollState = { progress: 0, section: 0 };

const NOISE = /* glsl */ `
vec3 hash3(vec3 p){ p = vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6)));
  return -1.0 + 2.0*fract(sin(p)*43758.5453123); }
float noise(vec3 p){ vec3 i=floor(p), f=fract(p); vec3 u=f*f*(3.0-2.0*f);
  return mix(mix(mix(dot(hash3(i+vec3(0,0,0)),f-vec3(0,0,0)),dot(hash3(i+vec3(1,0,0)),f-vec3(1,0,0)),u.x),
                 mix(dot(hash3(i+vec3(0,1,0)),f-vec3(0,1,0)),dot(hash3(i+vec3(1,1,0)),f-vec3(1,1,0)),u.x),u.y),
             mix(mix(dot(hash3(i+vec3(0,0,1)),f-vec3(0,0,1)),dot(hash3(i+vec3(1,0,1)),f-vec3(1,0,1)),u.x),
                 mix(dot(hash3(i+vec3(0,1,1)),f-vec3(0,1,1)),dot(hash3(i+vec3(1,1,1)),f-vec3(1,1,1)),u.x),u.y),u.z); }
float fbm(vec3 p){ float a=0.5, s=0.0; for(int i=0;i<6;i++){ s+=a*noise(p); p*=2.03; a*=0.5; } return s; }
float craters(vec3 p){ vec3 i=floor(p), f=fract(p); float d=1.0;
  for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++){ vec3 g=vec3(x,y,z); vec3 o=0.5+0.5*hash3(i+g); d=min(d,length(g+o-f)); }
  return d; }
`;

const planetVert = /* glsl */ `
varying vec3 vPos; varying vec3 vNormalW; varying vec3 vViewDir;
void main(){ vPos = position; vec4 wp = modelMatrix*vec4(position,1.0);
  vNormalW = normalize(mat3(modelMatrix)*normal); vViewDir = normalize(cameraPosition - wp.xyz);
  gl_Position = projectionMatrix*viewMatrix*wp; }`;



const atmoFrag = /* glsl */ `
uniform vec3 uSun; varying vec3 vNormalW; varying vec3 vViewDir; varying vec3 vPos;
void main(){
  // back-face shell: -dot(n, v) is ~1 just outside the planet limb and falls to 0 at the shell silhouette
  float limb = clamp(-dot(vNormalW, vViewDir), 0.0, 1.0);
  float glow = pow(limb, 2.6);
  float day = smoothstep(-0.35, 0.6, dot(vNormalW, normalize(uSun)));
  vec3 c = mix(vec3(0.62,0.80,0.68), vec3(0.95,0.78,0.6), 0.3);
  gl_FragColor = vec4(c, glow*day*0.85);
}`;

const cloudFrag = /* glsl */ `
uniform vec3 uSun; uniform float uTime; varying vec3 vPos; varying vec3 vNormalW; varying vec3 vViewDir;
${NOISE}
void main(){
  vec3 p = normalize(vPos);
  float n = fbm(p*3.0 + vec3(uTime*0.01, 0.0, uTime*0.006));
  float a = smoothstep(0.12, 0.5, n) * 0.16;
  float day = smoothstep(-0.1, 0.5, dot(vNormalW, normalize(uSun)));
  gl_FragColor = vec4(vec3(0.95,0.86,0.76)*day, a*day);
}`;

/** Irregular small moon (noise-displaced icosahedron). */
function SmallMoon({ radius, seed }: { radius: number; seed: number }) {
  const geom = useMemo(() => {
    const g = new THREE.IcosahedronGeometry(radius, 3); const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const k = 1 + 0.18 * Math.sin(x * 9 + seed) * Math.cos(y * 7 + seed) + 0.1 * Math.sin(z * 13 + seed * 2);
      p.setXYZ(i, x * k * 1.35, y * k * 0.9, z * k); }
    g.computeVertexNormals(); return g;
  }, [radius, seed]);
  return <mesh geometry={geom}><meshStandardMaterial color="#6e6058" roughness={1} flatShading /></mesh>;
}

function Moons() {
  const phobos = useRef<THREE.Group>(null!), deimos = useRef<THREE.Group>(null!);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    phobos.current.position.set(Math.cos(t * 0.22) * 2.75, Math.sin(t * 0.22) * 0.05, Math.sin(t * 0.22) * 2.75);
    phobos.current.rotation.y = -t * 0.22;
    deimos.current.position.set(Math.cos(t * 0.07 + 2) * 4.3, 0.04, Math.sin(t * 0.07 + 2) * 4.3);
  });
  return (<><group ref={phobos}><SmallMoon radius={0.05} seed={1} /></group><group ref={deimos}><SmallMoon radius={0.032} seed={4} /></group></>);
}

function Planet() {
  const { gl } = useThree();
  const maps = useMemo(() => bakeMars(gl, 2048), [gl]);
  const surface = useMemo(() => new THREE.MeshStandardMaterial({ map: maps.color, bumpMap: maps.height, bumpScale: 9, roughness: 0.96, metalness: 0 }), [maps]);
  const spin = useRef<THREE.Mesh>(null!);
  const group = useRef<THREE.Group>(null!);
  const clouds = useRef<THREE.Mesh>(null!);
  const sun = useMemo(() => new THREE.Vector3(-5, 1.6, 1.8), []);
  const uniforms = useMemo(() => ({ uSun: { value: sun }, uTime: { value: 0 } }), [sun]);
  const target = useRef(new THREE.Vector3());
  // scroll choreography: per-section planet placement [x, y, scale]
  // section index -> [x, y, scale]; the planet always sits opposite the copy column
  const stops: [number, number, number][] = [[1.7, -1.15, 1.25], [2.2, 0.0, 0.95], [-2.3, 0.2, 0.85], [2.3, -0.2, 0.85],
    [0.0, -2.7, 1.9], [-2.4, 0.3, 0.75], [2.3, 0.2, 0.8], [0.0, -2.2, 1.5], [0.0, -3.4, 2.2]];
  useFrame((state, dt) => {
    uniforms.uTime.value += dt;
    const p = scrollState.progress * (stops.length - 1);
    const i = Math.min(Math.floor(p), stops.length - 2);
    const f = p - i;
    const e = f * f * (3 - 2 * f);
    const a = stops[i], b = stops[i + 1];
    target.current.set(a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e);
    const g = group.current;
    g.position.x += (target.current.x - g.position.x) * Math.min(1, dt * 3);
    g.position.y += (target.current.y - g.position.y) * Math.min(1, dt * 3);
    const s = g.scale.x + (target.current.z - g.scale.x) * Math.min(1, dt * 3);
    g.scale.setScalar(s);
    spin.current.rotation.y += dt * 0.045;           // sidereal rotation (visually accelerated)
    clouds.current.rotation.y += dt * 0.052;
    state.camera.position.x = Math.sin(state.clock.elapsedTime * 0.05) * 0.15 + state.pointer.x * 0.12;
    state.camera.position.y = state.pointer.y * 0.08;
    state.camera.lookAt(0, 0, 0);
  });
  return (
    <group ref={group} rotation={[0.18, 0, 0.4392]}>{/* axial tilt 25.19 deg */}
      <mesh ref={spin} material={surface} rotation={[0, 1.9, 0]}>
        <sphereGeometry args={[1.6, 192, 128]} />
      </mesh>
      <Moons />
      <mesh ref={clouds} scale={1.012}>
        <sphereGeometry args={[1.6, 96, 96]} />
        <shaderMaterial vertexShader={planetVert} fragmentShader={cloudFrag} uniforms={uniforms} transparent depthWrite={false} />
      </mesh>
      <mesh scale={1.14}>
        <sphereGeometry args={[1.6, 96, 96]} />
        <shaderMaterial vertexShader={planetVert} fragmentShader={atmoFrag} uniforms={uniforms} transparent
          blending={THREE.AdditiveBlending} side={THREE.BackSide} depthWrite={false} />
      </mesh>
      <OrbitRing />
    </group>
  );
}

function OrbitRing() {
  const sat = useRef<THREE.Mesh>(null!);
  const pts = useMemo(() => {
    const c = new THREE.EllipseCurve(0, 0, 2.35, 2.35, 0, Math.PI * 2, false, 0);
    return c.getPoints(160).map((p) => new THREE.Vector3(p.x, 0, p.y));
  }, []);
  const geom = useMemo(() => new THREE.BufferGeometry().setFromPoints(pts), [pts]);
  useFrame(({ clock }) => {
    const a = clock.elapsedTime * 0.25;
    sat.current.position.set(Math.cos(a) * 2.35, 0, Math.sin(a) * 2.35);
  });
  return (
    <group rotation={[1.2, 0.2, -0.35]}>
      <lineLoop geometry={geom}>
        <lineBasicMaterial color="#b9d4b0" transparent opacity={0.22} />
      </lineLoop>
      <mesh ref={sat}><sphereGeometry args={[0.025, 12, 12]} /><meshBasicMaterial color="#e8f5e0" /></mesh>
    </group>
  );
}

function Stars({ count = 5000 }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 40 + Math.random() * 40;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      pos.set([r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), r * Math.cos(ph)], i * 3);
      const w = 0.7 + Math.random() * 0.3; col.set([w, w * (0.95 + Math.random() * 0.05), w * (0.9 + Math.random() * 0.1)], i * 3);
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return g;
  }, [count]);
  const ref = useRef<THREE.Points>(null!);
  useFrame((_, dt) => { ref.current.rotation.y += dt * 0.004; ref.current.rotation.x = scrollState.progress * 0.25; });
  return <points ref={ref} geometry={geom}><pointsMaterial size={0.09} vertexColors sizeAttenuation transparent opacity={0.9} /></points>;
}

function Dust({ count = 700 }) {
  const ref = useRef<THREE.Points>(null!);
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) pos.set([(Math.random() - .5) * 14, (Math.random() - .5) * 9, (Math.random() - .5) * 6], i * 3);
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, [count]);
  useFrame((_, dt) => {
    const a = ref.current.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) { let y = a.getY(i) + dt * 0.05; if (y > 4.5) y = -4.5; a.setY(i, y); }
    a.needsUpdate = true;
  });
  return <points ref={ref} geometry={geom}><pointsMaterial size={0.018} color="#d8e8cf" transparent opacity={0.45} depthWrite={false} /></points>;
}

export default function PlanetScene() {
  return (
    <Canvas camera={{ position: [0, 0, 6.2], fov: 42 }} dpr={[1, 1.75]} gl={{ antialias: true, powerPreference: "high-performance", toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 0.95 }}>
      <color attach="background" args={["#04060a"]} />
      <ambientLight intensity={0.035} />
      <directionalLight position={[-5, 1.6, 1.8]} intensity={2.4} color="#fff4e8" />
      <Stars />
      <Dust />
      <Planet />
    </Canvas>
  );
}
