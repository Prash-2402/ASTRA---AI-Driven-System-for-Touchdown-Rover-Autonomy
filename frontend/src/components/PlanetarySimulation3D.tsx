import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { Eye, Compass, ShieldAlert, CheckCircle2, Video, RefreshCw } from 'lucide-react'
import './PlanetarySimulation3D.css'

export type SimState = 'idle' | 'running' | 'paused' | 'landed' | 'failed'
export type Controller = 'PID' | 'MPC' | 'PPO'

export interface PlanetarySimProps {
  simState: SimState
  altitude: number
  trajectoryPoints: { x: number; y: number }[]
  controller: Controller
  environment?: string
  throttle?: number
  fuel?: number
  velocityV?: number
  velocityH?: number
  elapsed?: number
  onResetCamera?: () => void
}

type CameraMode = 'track' | 'ground' | 'orbit'

/* ─── Deterministic Procedural Terrain Elevation Engine ─── */
export function getTerrainElevation(x: number, z: number, env: string = 'Mars — Jezero Crater'): number {
  const dist = Math.sqrt(x * x + z * z)
  const isMoon = env.includes('Moon')
  const isHellas = env.includes('Hellas')

  if (isMoon) {
    // Sharp lunar crater ridges, micro-craters, rugged highland relief
    const r1 = Math.sin(x * 0.018 + 0.3) * Math.cos(z * 0.018 - 0.5) * 16
    const r2 = Math.sin(x * 0.045 - 1.2) * Math.sin(z * 0.042) * 7
    const r3 = Math.cos(x * 0.08) * Math.sin(z * 0.08) * 2.2
    const rimDist = Math.abs(dist - 140)
    const craterRim = Math.max(0, 1 - rimDist / 60) * 28
    const flatLZ = Math.min(1, Math.max(0, (dist - 22) / 35))
    return (r1 + r2 + r3 + craterRim) * flatLZ
  }

  if (isHellas) {
    // Vast low basin with broad longitudinal dunes and eroded rises
    const dune = Math.sin(x * 0.012 + z * 0.02) * 14
    const wave = Math.sin(x * 0.035 - z * 0.015) * 5
    const micro = Math.sin(x * 0.07) * Math.cos(z * 0.065) * 1.8
    const flatLZ = Math.min(1, Math.max(0, (dist - 25) / 45))
    return (dune + wave + micro) * flatLZ
  }

  // Mars — Jezero Crater: ancient delta, layered crater rim, flat deposition plain
  const hills = Math.sin(x * 0.01 + 0.4) * Math.cos(z * 0.009 - 0.2) * 20
  const ridges = Math.sin(x * 0.024 - 1.1) * Math.sin(z * 0.021 + 0.8) * 8
  const fineDunes = Math.sin(x * 0.06 + z * 0.035) * 2.2
  // Prominent background crater wall (Jezero delta wall) around radius 190m-280m
  const rimDist = Math.abs(dist - 210)
  const craterRim = Math.max(0, 1 - rimDist / 85) * 34
  // Safe landing plain at center
  const flatLZ = Math.min(1, Math.max(0, (dist - 28) / 48))

  return (hills + ridges + fineDunes + craterRim) * flatLZ
}

/* ─── Terrain Slope & Hazard Assessment ─── */
export function getTerrainSlope(x: number, z: number, env: string = 'Mars — Jezero Crater'): number {
  const d = 1.0
  const hL = getTerrainElevation(x - d, z, env)
  const hR = getTerrainElevation(x + d, z, env)
  const hD = getTerrainElevation(x, z - d, env)
  const hU = getTerrainElevation(x, z + d, env)
  const dx = (hR - hL) / (2 * d)
  const dz = (hU - hD) / (2 * d)
  const rad = Math.atan(Math.sqrt(dx * dx + dz * dz))
  return (rad * 180) / Math.PI
}

export const PlanetarySimulation3D: React.FC<PlanetarySimProps> = ({
  simState,
  altitude,
  trajectoryPoints,
  controller,
  environment = 'Mars — Jezero Crater',
  throttle = 0,
  fuel = 100,
  velocityV = 0,
  velocityH = 0,
  elapsed = 0,
}) => {
  const mountRef = useRef<HTMLDivElement>(null)
  const [cameraMode, setCameraMode] = useState<CameraMode>('track')
  const [currentSlope, setCurrentSlope] = useState<number>(1.8)
  const [surfaceAGL, setSurfaceAGL] = useState<number>(altitude)

  // Three.js instances ref
  const threeRef = useRef<{
    renderer: THREE.WebGLRenderer
    scene: THREE.Scene
    camera: THREE.PerspectiveCamera
    controls: OrbitControls
    terrainMesh: THREE.Mesh
    rocksMesh: THREE.InstancedMesh
    landerGroup: THREE.Group
    flameMesh: THREE.Mesh
    dustPoints: THREE.Points
    altimeterLine: THREE.Line
    trajectoryLine: THREE.Line
    uncertaintyMesh: THREE.Mesh
    sunLight: THREE.DirectionalLight
    hemiLight: THREE.HemisphereLight
    skyDome: THREE.Mesh
    animId: number
    simTime: number
  } | null>(null)

  // Environment configs
  const getEnvConfig = useCallback((env: string) => {
    if (env.includes('Moon')) {
      return {
        isMoon: true,
        skyTop: '#020204',
        skyHorizon: '#050508',
        fogColor: '#000000',
        fogDensity: 0.0001,
        sunColor: '#FFFFFF',
        sunIntensity: 3.2,
        hemiSky: '#16161B',
        hemiGround: '#0A0A0C',
        hemiIntensity: 0.45,
        sandColor: '#787775',
        rockColor: '#363534',
        steepColor: '#1F1E1E',
        ambientDust: false,
      }
    }
    if (env.includes('Hellas')) {
      return {
        isMoon: false,
        skyTop: '#7D3A1F',
        skyHorizon: '#B5653E',
        fogColor: '#A45834',
        fogDensity: 0.0036,
        sunColor: '#FFDFBD',
        sunIntensity: 1.9,
        hemiSky: '#B5643D',
        hemiGround: '#4C200E',
        hemiIntensity: 0.85,
        sandColor: '#A85830',
        rockColor: '#632912',
        steepColor: '#381406',
        ambientDust: true,
      }
    }
    // Mars — Jezero Crater (default)
    return {
      isMoon: false,
      skyTop: '#8A4526',
      skyHorizon: '#C87B54',
      fogColor: '#B66A46',
      fogDensity: 0.0022,
      sunColor: '#FFF0DE',
      sunIntensity: 2.3,
      hemiSky: '#C47851',
      hemiGround: '#522713',
      hemiIntensity: 0.75,
      sandColor: '#BD6D42',
      rockColor: '#73371A',
      steepColor: '#451B0A',
      ambientDust: true,
    }
  }, [])

  // Initialize Three.js scene
  useEffect(() => {
    const container = mountRef.current
    if (!container) return

    const width = container.clientWidth || 800
    const height = container.clientHeight || 500

    // 1. Scene
    const scene = new THREE.Scene()
    const envCfg = getEnvConfig(environment)
    scene.fog = new THREE.FogExp2(envCfg.fogColor, envCfg.fogDensity)

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.5, 2000)
    camera.position.set(0, 75, 120)

    // 3. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    container.appendChild(renderer.domElement)

    // 4. Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.maxPolarAngle = Math.PI / 2 - 0.03 // prevent camera dipping under terrain
    controls.minDistance = 6
    controls.maxDistance = 600
    controls.target.set(0, 10, 0)

    // 5. Lighting
    const hemiLight = new THREE.HemisphereLight(envCfg.hemiSky, envCfg.hemiGround, envCfg.hemiIntensity)
    scene.add(hemiLight)

    const sunLight = new THREE.DirectionalLight(envCfg.sunColor, envCfg.sunIntensity)
    sunLight.position.set(160, 240, 140)
    sunLight.castShadow = true
    sunLight.shadow.mapSize.width = 2048
    sunLight.shadow.mapSize.height = 2048
    sunLight.shadow.camera.near = 10
    sunLight.shadow.camera.far = 700
    sunLight.shadow.camera.left = -150
    sunLight.shadow.camera.right = 150
    sunLight.shadow.camera.top = 150
    sunLight.shadow.camera.bottom = -150
    sunLight.shadow.bias = -0.0006
    scene.add(sunLight)

    // Sun Visual Disc in Sky
    const sunDiscGeo = new THREE.SphereGeometry(14, 16, 16)
    const sunDiscMat = new THREE.MeshBasicMaterial({ color: envCfg.sunColor })
    const sunDisc = new THREE.Mesh(sunDiscGeo, sunDiscMat)
    sunDisc.position.copy(sunLight.position).multiplyScalar(2.5)
    scene.add(sunDisc)

    // 6. Sky Atmosphere Dome
    const skyGeo = new THREE.SphereGeometry(900, 32, 24)
    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {
        topColor: { value: new THREE.Color(envCfg.skyTop) },
        bottomColor: { value: new THREE.Color(envCfg.skyHorizon) },
        offset: { value: 30 },
        exponent: { value: 0.6 },
      },
      vertexShader: `
        varying vec3 vWorldPosition;
        void main() {
          vec4 worldPosition = modelMatrix * vec4(position, 1.0);
          vWorldPosition = worldPosition.xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 topColor;
        uniform vec3 bottomColor;
        uniform float offset;
        uniform float exponent;
        varying vec3 vWorldPosition;
        void main() {
          float h = normalize(vWorldPosition + offset).y;
          gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0);
        }
      `,
    })
    const skyDome = new THREE.Mesh(skyGeo, skyMat)
    scene.add(skyDome)

    // 7. 3D Procedural Terrain Mesh
    const terrainSize = 650
    const terrainSegs = 140
    const terrainGeo = new THREE.PlaneGeometry(terrainSize, terrainSize, terrainSegs, terrainSegs)
    terrainGeo.rotateX(-Math.PI / 2)

    // Displace vertices analytically & compute slope vertex colors
    const posAttr = terrainGeo.attributes.position
    const count = posAttr.count
    const colors = new Float32Array(count * 3)

    const sandColor = new THREE.Color(envCfg.sandColor)
    const rockColor = new THREE.Color(envCfg.rockColor)
    const steepColor = new THREE.Color(envCfg.steepColor)
    const lzRingColor = new THREE.Color('#A5A79B')

    for (let i = 0; i < count; i++) {
      const vx = posAttr.getX(i)
      const vz = posAttr.getZ(i)
      const vy = getTerrainElevation(vx, vz, environment)
      posAttr.setY(i, vy)

      const slope = getTerrainSlope(vx, vz, environment)
      const dist = Math.sqrt(vx * vx + vz * vz)

      // Base slope coloring
      let c: THREE.Color
      if (slope < 7) {
        c = sandColor.clone().offsetHSL(0, 0, (Math.sin(vx * 0.1) * 0.03))
      } else if (slope < 15) {
        const factor = (slope - 7) / 8
        c = sandColor.clone().lerp(rockColor, factor)
      } else {
        const factor = Math.min(1, (slope - 15) / 15)
        c = rockColor.clone().lerp(steepColor, factor)
      }

      // Projected subtle LZ target ring highlight directly into terrain texture
      if (dist > 18 && dist < 21) {
        c.lerp(lzRingColor, 0.45)
      } else if (dist > 38 && dist < 41) {
        c.lerp(lzRingColor, 0.3)
      }

      colors[i * 3] = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b
    }

    terrainGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    terrainGeo.computeVertexNormals()

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.94,
      metalness: 0.06,
      flatShading: false,
    })

    const terrainMesh = new THREE.Mesh(terrainGeo, terrainMat)
    terrainMesh.receiveShadow = true
    scene.add(terrainMesh)

    // 8. Projected Landing Zone Target & Range Rings (Conforming Ground Decal)
    const lzGroup = new THREE.Group()
    const ringRadii = [12, 25, 45]
    ringRadii.forEach((r, idx) => {
      const ringGeo = new THREE.RingGeometry(r - 0.3, r + 0.3, 64)
      ringGeo.rotateX(-Math.PI / 2)
      const ringMat = new THREE.MeshBasicMaterial({
        color: idx === 0 ? 0xE8D2B5 : 0xA5A79B,
        transparent: true,
        opacity: idx === 0 ? 0.8 : 0.45,
        side: THREE.DoubleSide,
      })
      const ring = new THREE.Mesh(ringGeo, ringMat)
      ring.position.y = 0.18 + idx * 0.02
      lzGroup.add(ring)
    })

    // Reticle crosshairs
    const crossMat = new THREE.LineBasicMaterial({ color: 0xA5A79B, transparent: true, opacity: 0.65 })
    const crossGeoH = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-14, 0.2, 0), new THREE.Vector3(14, 0.2, 0)])
    const crossGeoV = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0.2, -14), new THREE.Vector3(0, 0.2, 14)])
    lzGroup.add(new THREE.Line(crossGeoH, crossMat))
    lzGroup.add(new THREE.Line(crossGeoV, crossMat))

    scene.add(lzGroup)

    // 9. Instanced Natural Rocks & Boulders
    const rockCount = 260
    const rockBaseGeo = new THREE.DodecahedronGeometry(1, 1)
    // Perturb rock vertices for organic geological asymmetry
    const rockPos = rockBaseGeo.attributes.position
    for (let i = 0; i < rockPos.count; i++) {
      const u = rockPos.getX(i)
      const v = rockPos.getY(i)
      const w = rockPos.getZ(i)
      const noise = 1 + (Math.sin(u * 4 + v * 3) * 0.18 + Math.cos(w * 5) * 0.12)
      rockPos.setXYZ(i, u * noise, v * (noise * 0.8), w * noise)
    }
    rockBaseGeo.computeVertexNormals()

    const rockMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(envCfg.rockColor),
      roughness: 0.92,
      metalness: 0.08,
      flatShading: true,
    })

    const rocksMesh = new THREE.InstancedMesh(rockBaseGeo, rockMat, rockCount)
    rocksMesh.castShadow = true
    rocksMesh.receiveShadow = true

    const dummy = new THREE.Object3D()
    let rockIdx = 0
    // Deterministic distribution
    for (let i = 0; i < rockCount; i++) {
      const angle = (i * 2.399) // golden ratio distribution
      const radius = 28 + Math.pow((i / rockCount), 0.7) * 240
      const rx = Math.cos(angle) * radius + (Math.sin(i * 9) * 8)
      const rz = Math.sin(angle) * radius + (Math.cos(i * 7) * 8)
      const ry = getTerrainElevation(rx, rz, environment)
      const slope = getTerrainSlope(rx, rz, environment)

      // Near LZ: small pebbles only. Ridges / slopes: large boulders!
      let scale = 0.5 + Math.random() * 1.8
      if (slope > 12) scale *= 1.8
      if (radius > 120) scale *= 1.4

      dummy.position.set(rx, ry + scale * 0.35, rz)
      dummy.rotation.set(Math.sin(i) * 3, i * 1.7, Math.cos(i) * 3)
      dummy.scale.set(scale, scale * (0.6 + Math.random() * 0.6), scale * (0.8 + Math.random() * 0.5))
      dummy.updateMatrix()
      rocksMesh.setMatrixAt(rockIdx++, dummy.matrix)
    }
    rocksMesh.instanceMatrix.needsUpdate = true
    scene.add(rocksMesh)

    // 10. Hazard Assessment Indicators (Steep Ridge Zones)
    const hazardGroup = new THREE.Group()
    const hazardLocations = [
      { x: -95, z: 45, r: 24 },
      { x: 110, z: -70, r: 28 },
      { x: -45, z: -120, r: 32 },
    ]
    hazardLocations.forEach(h => {
      const y = getTerrainElevation(h.x, h.z, environment) + 0.3
      const hGeo = new THREE.RingGeometry(h.r - 0.4, h.r + 0.4, 32)
      hGeo.rotateX(-Math.PI / 2)
      const hMat = new THREE.MeshBasicMaterial({ color: 0x8C1D18, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
      const hMesh = new THREE.Mesh(hGeo, hMat)
      hMesh.position.set(h.x, y, h.z)
      hazardGroup.add(hMesh)
    })
    scene.add(hazardGroup)

    // 11. Suspended Planetary Dust Particles
    const dustCount = envCfg.ambientDust ? 280 : 0
    let dustPoints: THREE.Points
    if (dustCount > 0) {
      const dustGeo = new THREE.BufferGeometry()
      const dustPos = new Float32Array(dustCount * 3)
      for (let i = 0; i < dustCount; i++) {
        dustPos[i * 3] = (Math.random() - 0.5) * 160
        dustPos[i * 3 + 1] = Math.random() * 45 + 1
        dustPos[i * 3 + 2] = (Math.random() - 0.5) * 160
      }
      dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3))
      const dustMat = new THREE.PointsMaterial({
        color: 0xE8D2B5,
        size: 0.8,
        transparent: true,
        opacity: 0.35,
      })
      dustPoints = new THREE.Points(dustGeo, dustMat)
      scene.add(dustPoints)
    } else {
      dustPoints = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial())
    }

    // 12. 3D Planetary Lander Model
    const landerGroup = new THREE.Group()

    // 12a. Octagonal Main Chassis / MLI Gold Thermal Insulation Bus
    const busGeo = new THREE.CylinderGeometry(2.8, 3.2, 2.6, 8)
    const busMat = new THREE.MeshStandardMaterial({
      color: 0xC59E47,
      metalness: 0.82,
      roughness: 0.3,
      flatShading: true,
    })
    const busMesh = new THREE.Mesh(busGeo, busMat)
    busMesh.castShadow = true
    busMesh.position.y = 2.4
    landerGroup.add(busMesh)

    // Top deck
    const deckGeo = new THREE.CylinderGeometry(2.7, 2.7, 0.3, 8)
    const deckMat = new THREE.MeshStandardMaterial({ color: 0x363832, metalness: 0.4, roughness: 0.6 })
    const deckMesh = new THREE.Mesh(deckGeo, deckMat)
    deckMesh.position.y = 3.8
    landerGroup.add(deckMesh)

    // Optical Nav / Sensor Dome
    const domeGeo = new THREE.SphereGeometry(0.85, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2)
    const domeMat = new THREE.MeshStandardMaterial({ color: 0x5E7866, metalness: 0.2, roughness: 0.4 })
    const domeMesh = new THREE.Mesh(domeGeo, domeMat)
    domeMesh.position.y = 3.9
    landerGroup.add(domeMesh)

    // 12b. Solar Panels (Dual Wings)
    const wingGeo = new THREE.BoxGeometry(4.2, 0.12, 2.0)
    const wingMat = new THREE.MeshStandardMaterial({ color: 0x3C5569, metalness: 0.6, roughness: 0.25 })
    const leftWing = new THREE.Mesh(wingGeo, wingMat)
    leftWing.position.set(-4.6, 2.7, 0)
    leftWing.castShadow = true
    landerGroup.add(leftWing)

    const rightWing = new THREE.Mesh(wingGeo, wingMat)
    rightWing.position.set(4.6, 2.7, 0)
    rightWing.castShadow = true
    landerGroup.add(rightWing)

    // 12c. 4 Landing Gear Legs with Oleo Struts and Footpads
    const legMat = new THREE.MeshStandardMaterial({ color: 0x9A9C93, metalness: 0.7, roughness: 0.35 })
    const padMat = new THREE.MeshStandardMaterial({ color: 0x484944, metalness: 0.5, roughness: 0.6 })

    for (let k = 0; k < 4; k++) {
      const legAngle = (k * Math.PI) / 2 + Math.PI / 4
      const legMountX = Math.cos(legAngle) * 2.5
      const legMountZ = Math.sin(legAngle) * 2.5
      const padX = Math.cos(legAngle) * 4.6
      const padZ = Math.sin(legAngle) * 4.6

      // Upper strut
      const strutPoints = [new THREE.Vector3(legMountX, 2.2, legMountZ), new THREE.Vector3(padX, 0.2, padZ)]
      const strutGeo = new THREE.BufferGeometry().setFromPoints(strutPoints)
      const strutLine = new THREE.Line(strutGeo, new THREE.LineBasicMaterial({ color: 0xB5B7AC, linewidth: 2 }))
      landerGroup.add(strutLine)

      // Footpad disc
      const padGeo = new THREE.CylinderGeometry(0.7, 0.7, 0.15, 12)
      const padMesh = new THREE.Mesh(padGeo, padMat)
      padMesh.position.set(padX, 0.1, padZ)
      padMesh.castShadow = true
      padMesh.receiveShadow = true
      landerGroup.add(padMesh)
    }

    // 12d. Descent Rocket Engine Bell
    const engineGeo = new THREE.CylinderGeometry(0.5, 1.1, 1.2, 16, 1, true)
    const engineMat = new THREE.MeshStandardMaterial({ color: 0x2A2A28, metalness: 0.9, roughness: 0.2, side: THREE.DoubleSide })
    const engineBell = new THREE.Mesh(engineGeo, engineMat)
    engineBell.position.y = 0.8
    landerGroup.add(engineBell)

    // 12e. Dynamic Pulsed Thruster Flame Plume
    const flameGeo = new THREE.ConeGeometry(0.9, 4.5, 16)
    flameGeo.rotateX(Math.PI)
    flameGeo.translate(0, -2.2, 0)
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xFFB347,
      transparent: true,
      opacity: 0.85,
    })
    const flameMesh = new THREE.Mesh(flameGeo, flameMat)
    flameMesh.position.y = 0.4
    flameMesh.visible = false
    landerGroup.add(flameMesh)

    // 12f. EKF Covariance Uncertainty Ellipsoid
    const uncGeo = new THREE.SphereGeometry(4.2, 16, 12)
    const uncMat = new THREE.MeshBasicMaterial({
      color: 0x7798A3,
      wireframe: true,
      transparent: true,
      opacity: 0.25,
    })
    const uncertaintyMesh = new THREE.Mesh(uncGeo, uncMat)
    uncertaintyMesh.position.y = 2.4
    landerGroup.add(uncertaintyMesh)

    scene.add(landerGroup)

    // 13. Radar Altimeter Ground Vector
    const altimeterMat = new THREE.LineDashedMaterial({
      color: 0xE8D2B5,
      dashSize: 1.5,
      gapSize: 1.2,
      transparent: true,
      opacity: 0.65,
    })
    const altimeterGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -50, 0)])
    const altimeterLine = new THREE.Line(altimeterGeo, altimeterMat)
    altimeterLine.computeLineDistances()
    scene.add(altimeterLine)

    // 14. 3D Flight Corridor Trajectory Ribbon
    const trajMat = new THREE.LineDashedMaterial({
      color: controller === 'PPO' ? 0x8C1D18 : controller === 'MPC' ? 0xBF802B : 0xA5A79B,
      dashSize: 2.5,
      gapSize: 1.8,
      transparent: true,
      opacity: 0.8,
    })
    const trajGeo = new THREE.BufferGeometry()
    const trajectoryLine = new THREE.Line(trajGeo, trajMat)
    scene.add(trajectoryLine)

    // Save instance refs
    threeRef.current = {
      renderer,
      scene,
      camera,
      controls,
      terrainMesh,
      rocksMesh,
      landerGroup,
      flameMesh,
      dustPoints,
      altimeterLine,
      trajectoryLine,
      uncertaintyMesh,
      sunLight,
      hemiLight,
      skyDome,
      animId: 0,
      simTime: 0,
    }

    // Resize Handler
    const handleResize = () => {
      if (!container || !threeRef.current) return
      const w = container.clientWidth
      const h = container.clientHeight
      threeRef.current.camera.aspect = w / h
      threeRef.current.camera.updateProjectionMatrix()
      threeRef.current.renderer.setSize(w, h)
    }

    window.addEventListener('resize', handleResize)

    // Render loop
    const animate = () => {
      if (!threeRef.current) return
      const tState = threeRef.current
      tState.simTime += 0.016

      // Float dust particles
      if (tState.dustPoints.geometry.attributes.position) {
        const dPos = tState.dustPoints.geometry.attributes.position
        for (let j = 0; j < dPos.count; j++) {
          let dy = dPos.getY(j) - 0.03
          if (dy < 0.5) dy = 45
          dPos.setY(j, dy)
        }
        dPos.needsUpdate = true
      }

      tState.controls.update()
      tState.renderer.render(tState.scene, tState.camera)
      tState.animId = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      window.removeEventListener('resize', handleResize)
      if (threeRef.current) {
        cancelAnimationFrame(threeRef.current.animId)
        threeRef.current.renderer.dispose()
        container.innerHTML = ''
        threeRef.current = null
      }
    }
  }, [environment, getEnvConfig])

  // Update lander position, thruster plume, altimeter line, and trajectory each frame
  useEffect(() => {
    if (!threeRef.current) return
    const { landerGroup, flameMesh, altimeterLine, trajectoryLine, uncertaintyMesh, controls, camera } = threeRef.current

    // Scale altitude: 2000m mapped to 140m in 3D world units
    const maxVisualAlt = 135
    const normAlt = Math.max(0, Math.min(1, altitude / 2000))
    const visualY = normAlt * maxVisualAlt

    // Lateral drift along X and Z
    const driftX = (1 - normAlt) * (Math.sin(elapsed * 0.4) * 6) + (Math.cos(elapsed * 0.2) * 4) * (1 - normAlt)
    const driftZ = (1 - normAlt) * (Math.sin(elapsed * 0.3) * 4)

    // Terrain elevation under lander
    const groundHeight = getTerrainElevation(driftX, driftZ, environment)
    const finalY = Math.max(groundHeight, visualY)
    landerGroup.position.set(driftX, finalY, driftZ)

    // Attitude tilt during descent
    const roll = Math.sin(elapsed * 1.4) * 0.04 * (1 - normAlt)
    const pitch = Math.cos(elapsed * 1.1) * 0.03 * (1 - normAlt)
    landerGroup.rotation.set(pitch, elapsed * 0.05, roll)

    // Thruster flame dynamics
    if (simState === 'running' || simState === 'paused') {
      flameMesh.visible = true
      const flameFlicker = 0.85 + Math.sin(Date.now() * 0.025) * 0.25
      const throttleScale = Math.max(0.4, (throttle || 50) / 100) * flameFlicker
      flameMesh.scale.set(throttleScale, throttleScale * (1.1 + Math.sin(Date.now() * 0.04) * 0.2), throttleScale)
    } else {
      flameMesh.visible = false
    }

    // EKF uncertainty ellipsoid scale
    const uncScale = 0.8 + normAlt * 2.2
    uncertaintyMesh.scale.set(uncScale, uncScale * 0.8, uncScale)

    // Radar Altimeter line
    const altPoints = [new THREE.Vector3(driftX, finalY, driftZ), new THREE.Vector3(driftX, groundHeight, driftZ)]
    altimeterLine.geometry.setFromPoints(altPoints)
    altimeterLine.computeLineDistances()

    // Real-time slope under lander
    const slope = getTerrainSlope(driftX, driftZ, environment)
    setCurrentSlope(slope)
    setSurfaceAGL(Math.round(altitude))

    // Trajectory updates
    if (trajectoryPoints && trajectoryPoints.length > 1) {
      const tPts: THREE.Vector3[] = trajectoryPoints.map((pt, i) => {
        const ptNorm = (trajectoryPoints.length - 1 - i) / (trajectoryPoints.length - 1)
        const py = ptNorm * maxVisualAlt
        const px = (pt.x - 0.5) * 40
        const pz = (pt.y - 0.5) * 30
        return new THREE.Vector3(px, py, pz)
      })
      trajectoryLine.geometry.setFromPoints(tPts)
      trajectoryLine.computeLineDistances()
    }

    // Camera modes
    if (cameraMode === 'track') {
      const camTargetY = finalY * 0.65 + groundHeight * 0.35
      controls.target.set(driftX * 0.7, camTargetY, driftZ * 0.7)
      // Smooth descent camera following
      const desiredCamY = Math.max(groundHeight + 14, finalY + 18)
      const desiredCamZ = driftZ + 55 + normAlt * 45
      camera.position.lerp(new THREE.Vector3(driftX + 28, desiredCamY, desiredCamZ), 0.08)
    } else if (cameraMode === 'ground') {
      controls.target.set(driftX, finalY, driftZ)
      camera.position.set(28, getTerrainElevation(28, 28, environment) + 2.5, 28)
    }
  }, [altitude, simState, elapsed, throttle, environment, trajectoryPoints, cameraMode])

  // Reset camera view
  const handleResetCamera = () => {
    if (!threeRef.current) return
    const { camera, controls } = threeRef.current
    camera.position.set(0, 65, 110)
    controls.target.set(0, 10, 0)
    setCameraMode('track')
  }

  return (
    <div className="planetary-sim-container">
      {/* Three.js Canvas Container */}
      <div ref={mountRef} className="three-mount-area" />

      {/* ── Scientific Aerospace Flight HUD ── */}
      <div className="sim-hud-overlay">
        {/* Top-Left Telemetry Card */}
        <div className="hud-telemetry-badge">
          <div className="hud-badge-header">
            <span className="hud-status-dot" data-state={simState} />
            <span className="hud-mission-tag">ASTRA EDL GUIDANCE</span>
            <span className="hud-env-pill">{environment.split('—')[0].trim()}</span>
          </div>

          <div className="hud-metric-row">
            <div className="hud-metric">
              <span className="hud-label">ALT (AGL)</span>
              <span className="hud-val font-mono">{surfaceAGL.toLocaleString()} m</span>
            </div>
            <div className="hud-metric-sep" />
            <div className="hud-metric">
              <span className="hud-label">V_VERT</span>
              <span className="hud-val font-mono">{velocityV ? velocityV.toFixed(1) : '-18.4'} m/s</span>
            </div>
            <div className="hud-metric-sep" />
            <div className="hud-metric">
              <span className="hud-label">SLOPE</span>
              <span className={`hud-val font-mono ${currentSlope > 12 ? 'text-hazard' : 'text-safe'}`}>
                {currentSlope.toFixed(1)}° {currentSlope > 12 ? 'WARN' : 'NOM'}
              </span>
            </div>
          </div>

          <div className="hud-sub-grid">
            <div className="hud-sub-item">
              <span className="hud-sub-lbl">CONTROLLER</span>
              <span className="hud-sub-val" data-ctrl={controller}>{controller}</span>
            </div>
            <div className="hud-sub-item">
              <span className="hud-sub-lbl">ESTIMATOR</span>
              <span className="hud-sub-val">EKF 6-DOF</span>
            </div>
            <div className="hud-sub-item">
              <span className="hud-sub-lbl">TARGET LZ</span>
              <span className="hud-sub-val text-cream">LZ-ALPHA</span>
            </div>
          </div>
        </div>

        {/* Top-Right Camera Mode Switcher */}
        <div className="hud-camera-controls">
          <button
            className={`hud-cam-btn ${cameraMode === 'track' ? 'hud-cam-btn--active' : ''}`}
            onClick={() => setCameraMode('track')}
            title="Track lander descent"
          >
            <Video size={13} />
            <span>Chase</span>
          </button>
          <button
            className={`hud-cam-btn ${cameraMode === 'ground' ? 'hud-cam-btn--active' : ''}`}
            onClick={() => setCameraMode('ground')}
            title="Ground landing zone radar view"
          >
            <Eye size={13} />
            <span>Surface</span>
          </button>
          <button
            className={`hud-cam-btn ${cameraMode === 'orbit' ? 'hud-cam-btn--active' : ''}`}
            onClick={() => setCameraMode('orbit')}
            title="Free 3D inspection orbit"
          >
            <Compass size={13} />
            <span>Orbit</span>
          </button>
          <button
            className="hud-cam-btn hud-cam-btn--reset"
            onClick={handleResetCamera}
            title="Reset perspective"
          >
            <RefreshCw size={12} />
          </button>
        </div>

        {/* Bottom-Center Touchdown State Banner */}
        {simState === 'landed' && (
          <div className="hud-landed-banner">
            <CheckCircle2 size={16} className="banner-icon-safe" />
            <span>TOUCHDOWN CONFIRMED — LZ-ALPHA VELOCITY 0.8 m/s</span>
          </div>
        )}
        {simState === 'failed' && (
          <div className="hud-failed-banner">
            <ShieldAlert size={16} className="banner-icon-hazard" />
            <span>EXCESSIVE IMPACT VELOCITY — ROLLOVER DETECTED</span>
          </div>
        )}

        {/* Bottom-Right Guidance Annotation */}
        <div className="hud-compass-stamp">
          <span className="stamp-sub">OPTICAL HAZARD AVOIDANCE: ACTIVE</span>
          <span className="stamp-coords font-mono">JEZERO BASIN · 18.38°N 77.58°E</span>
        </div>
      </div>
    </div>
  )
}

export default PlanetarySimulation3D
