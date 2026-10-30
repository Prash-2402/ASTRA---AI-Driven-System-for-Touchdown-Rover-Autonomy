declare module 'three' {
  const THREE: any
  export = THREE
}

declare namespace THREE {
  type WebGLRenderer = any
  type Scene = any
  type PerspectiveCamera = any
  type Mesh = any
  type InstancedMesh = any
  type Group = any
  type Points = any
  type Line = any
  type DirectionalLight = any
  type HemisphereLight = any
  type Color = any
  type Vector3 = any
  type BufferGeometry = any
  type BufferAttribute = any
  type Material = any
  type Object3D = any
}

declare module 'three/examples/jsm/controls/OrbitControls.js' {
  export class OrbitControls {
    constructor(object: any, domElement?: HTMLElement)
    enabled: boolean
    target: any
    minDistance: number
    maxDistance: number
    minPolarAngle: number
    maxPolarAngle: number
    enableDamping: boolean
    dampingFactor: number
    update(): boolean
    dispose(): void
  }
}
