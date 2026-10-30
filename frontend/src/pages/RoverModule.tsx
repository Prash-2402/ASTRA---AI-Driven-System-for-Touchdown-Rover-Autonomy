import React, { useState, useEffect, useRef } from 'react'
import {
  Navigation2, Play, Pause, Square, RefreshCw, Zap,
  AlertTriangle, ShieldAlert, Cpu, Activity, Gauge,
  Compass, Radio, Layers, CheckCircle2, RotateCcw, AlertCircle
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './RoverModule.css'

type ControllerMode = 'ASTRA_ADAPTIVE' | 'FSM_BASELINE'
type SimStatus = 'idle' | 'running' | 'paused' | 'completed' | 'hazard_diversion'

interface FaultState {
  sensorDropout: boolean
  terrainMisclass: boolean
  powerDrain: boolean
  actuatorDegradation: boolean
}

interface RoverTelemetryPoint {
  t: number
  battery: number
  velocity: number
  wheelSlip: number
  ekfUncertainty: number
}

const TERRAINS = [
  { id: 'jezero', name: 'Jezero Delta Sand & Boulder Field', roughness: 'Moderate', slipCoeff: 0.18 },
  { id: 'olympus', name: 'Olympus Scarp Regolith Slope', roughness: 'High', slipCoeff: 0.32 },
  { id: 'valles', name: 'Valles Marineris Floor', roughness: 'Low-Moderate', slipCoeff: 0.12 },
  { id: 'gale', name: 'Gale Crater Dune Field', roughness: 'Extreme', slipCoeff: 0.45 },
]

export const RoverModule: React.FC = () => {
  // Config state
  const [terrain, setTerrain] = useState(TERRAINS[0].id)
  const [controllerMode, setControllerMode] = useState<ControllerMode>('ASTRA_ADAPTIVE')
  const [initialBattery, setInitialBattery] = useState(96)
  const [maxSpeed, setMaxSpeed] = useState(0.8) // m/s
  const [replanThreshold, setReplanThreshold] = useState(0.4)

  // Simulation execution state
  const [simStatus, setSimStatus] = useState<SimStatus>('idle')
  const [simTime, setSimTime] = useState(0)
  const [posX, setPosX] = useState(12.4)
  const [posY, setPosY] = useState(8.2)
  const [velocity, setVelocity] = useState(0)
  const [heading, setHeading] = useState(42.5)
  const [battery, setBattery] = useState(initialBattery)
  const [wheelTorque, setWheelTorque] = useState(18.2)
  const [wheelSlip, setWheelSlip] = useState(4.2)
  const [ekfResidual, setEkfResidual] = useState(0.04)
  const [replanCount, setReplanCount] = useState(0)

  // Faults
  const [faults, setFaults] = useState<FaultState>({
    sensorDropout: false,
    terrainMisclass: false,
    powerDrain: false,
    actuatorDegradation: false
  })

  // Wheel status: FL, FR, ML, MR, RL, RR
  const [wheelHealth, setWheelHealth] = useState<number[]>([100, 100, 100, 100, 100, 100])

  // Telemetry buffer
  const [telemetryHistory, setTelemetryHistory] = useState<RoverTelemetryPoint[]>([])

  // Logs
  const [logs, setLogs] = useState<string[]>([
    '[INIT] ASTRA Rover Autonomy Subsystem v2.4 initialized.',
    '[EKF] 6-wheel odometry + Visual SLAM fused prior ready.',
    '[NAV] Global path planned via Rapid A* with Slip Risk Heuristic.'
  ])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const simTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Handle fault toggle
  const toggleFault = (key: keyof FaultState) => {
    setFaults(prev => {
      const next = { ...prev, [key]: !prev[key] }
      const stateStr = next[key] ? 'INJECTED' : 'CLEARED'
      addLog(`[FAULT-INJECTOR] ${key} status changed to ${stateStr}.`)
      return next
    })
  }

  const addLog = (msg: string) => {
    setLogs(prev => [msg, ...prev.slice(0, 19)])
  }

  // Simulation step
  useEffect(() => {
    if (simStatus === 'running') {
      simTimerRef.current = setInterval(() => {
        setSimTime(t => +(t + 0.2).toFixed(1))

        // Battery consumption calculation
        const drainRate = (faults.powerDrain ? 0.35 : 0.08) * (controllerMode === 'ASTRA_ADAPTIVE' ? 0.85 : 1.15)
        setBattery(b => {
          const next = +(b - drainRate).toFixed(2)
          return next <= 0 ? 0 : next
        })

        // Position progression toward target (85, 70)
        setPosX(x => +(x + (Math.cos((heading * Math.PI) / 180) * 0.16)).toFixed(2))
        setPosY(y => +(y + (Math.sin((heading * Math.PI) / 180) * 0.16)).toFixed(2))
        setVelocity(+(0.55 + Math.sin(simTime * 0.8) * 0.12).toFixed(2))

        // Dynamic slip & uncertainty
        const slipVal = faults.actuatorDegradation ? 18.4 + Math.random() * 5 : 3.8 + Math.random() * 2
        setWheelSlip(+slipVal.toFixed(1))

        const ekfVal = faults.sensorDropout ? 0.28 + Math.random() * 0.15 : 0.03 + Math.random() * 0.02
        setEkfResidual(+ekfVal.toFixed(3))

        // Actuator health
        if (faults.actuatorDegradation) {
          setWheelHealth([72, 98, 48, 95, 88, 92])
        } else {
          setWheelHealth([99, 100, 98, 99, 100, 99])
        }

        // Adaptive replanning trigger
        if (faults.terrainMisclass && replanCount === 0) {
          setReplanCount(1)
          addLog('[ADAPTIVE-PLANNER] Terrain obstacle boundary conflict detected! Replanning path bypass...')
        }

        // Update telemetry chart history
        setTelemetryHistory(prev => [
          ...prev.slice(-40),
          {
            t: +(simTime).toFixed(1),
            battery: battery,
            velocity: velocity,
            wheelSlip: slipVal,
            ekfUncertainty: ekfVal * 100
          }
        ])
      }, 200)
    } else {
      if (simTimerRef.current) clearInterval(simTimerRef.current)
    }
    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current)
    }
  }, [simStatus, simTime, faults, controllerMode, battery, velocity, heading, replanCount])

  // Canvas visualizer
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId: number

    const render = () => {
      const w = canvas.width
      const h = canvas.height

      // Background - Mars terrain surface
      ctx.fillStyle = '#E3D8C8'
      ctx.fillRect(0, 0, w, h)

      // Elevation contour rings / terrain texture
      ctx.strokeStyle = 'rgba(168, 140, 110, 0.25)'
      ctx.lineWidth = 1
      for (let i = 40; i < w; i += 45) {
        ctx.beginPath()
        ctx.arc(w / 2, h / 2, i + Math.sin(i + simTime * 0.05) * 6, 0, Math.PI * 2)
        ctx.stroke()
      }

      // Sand ripple subtle lines
      ctx.strokeStyle = 'rgba(195, 170, 145, 0.35)'
      for (let y = 30; y < h; y += 35) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.bezierCurveTo(w * 0.3, y - 8, w * 0.7, y + 8, w, y)
        ctx.stroke()
      }

      // Boulder Hazards
      const hazards = [
        { x: 180, y: 150, r: 38, label: 'Crater Ridge' },
        { x: 380, y: 260, r: 48, label: 'Unstable Escarpment' },
        { x: 520, y: 140, r: 34, label: 'Rock Cluster' },
        { x: 320, y: 400, r: 42, label: 'Soft Sand Trap' },
      ]

      hazards.forEach(hz => {
        // Hazard exclusion zone
        ctx.fillStyle = 'rgba(199, 108, 100, 0.12)'
        ctx.strokeStyle = 'rgba(199, 108, 100, 0.45)'
        ctx.lineWidth = 1.5
        ctx.setLineDash([5, 5])
        ctx.beginPath()
        ctx.arc(hz.x, hz.y, hz.r + 14, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        ctx.setLineDash([])

        // Boulder body
        ctx.fillStyle = '#8C6C58'
        ctx.beginPath()
        ctx.ellipse(hz.x, hz.y, hz.r, hz.r * 0.8, 0.3, 0, Math.PI * 2)
        ctx.fill()

        // Highlight
        ctx.fillStyle = 'rgba(255, 240, 225, 0.35)'
        ctx.beginPath()
        ctx.arc(hz.x - hz.r * 0.3, hz.y - hz.r * 0.3, hz.r * 0.35, 0, Math.PI * 2)
        ctx.fill()

        // Label
        ctx.fillStyle = '#6E4E3D'
        ctx.font = '10px Space Mono'
        ctx.fillText(hz.label, hz.x - 30, hz.y + hz.r + 20)
      })

      // Start & Target Waypoints
      const startPos = { x: 90, y: 420 }
      const targetPos = { x: 590, y: 90 }

      // Waypoint connections
      // 1. Baseline FSM Path (Straight / Inflexible through edge of hazard)
      if (controllerMode === 'FSM_BASELINE') {
        ctx.strokeStyle = 'rgba(132, 144, 132, 0.65)'
        ctx.lineWidth = 2.5
        ctx.setLineDash([6, 6])
        ctx.beginPath()
        ctx.moveTo(startPos.x, startPos.y)
        ctx.lineTo(340, 290)
        ctx.lineTo(targetPos.x, targetPos.y)
        ctx.stroke()
        ctx.setLineDash([])
      }

      // 2. ASTRA Adaptive Path (Safe spline bypassing escarpment)
      ctx.strokeStyle = '#536F59'
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.moveTo(startPos.x, startPos.y)
      if (replanCount > 0) {
        // Dynamic reroute around obstacle
        ctx.bezierCurveTo(170, 380, 260, 480, 440, 360)
        ctx.bezierCurveTo(520, 280, 560, 180, targetPos.x, targetPos.y)
      } else {
        ctx.bezierCurveTo(200, 320, 300, 200, targetPos.x, targetPos.y)
      }
      ctx.stroke()

      // Target Pin
      ctx.fillStyle = '#648C65'
      ctx.beginPath()
      ctx.arc(targetPos.x, targetPos.y, 8, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#26372D'
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.fillStyle = '#26372D'
      ctx.font = 'bold 11px Inter'
      ctx.fillText('TARGET WAYPOINT', targetPos.x - 45, targetPos.y - 14)

      // Start Pin
      ctx.fillStyle = '#779477'
      ctx.beginPath()
      ctx.arc(startPos.x, startPos.y, 6, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillText('START', startPos.x - 18, startPos.y + 18)

      // Rover Rendering at current simulated position
      // Map posX/posY from meters to canvas coords
      const rvCanvasX = startPos.x + (posX - 12.4) * 5.2
      const rvCanvasY = startPos.y - (posY - 8.2) * 5.2

      ctx.save()
      ctx.translate(rvCanvasX, rvCanvasY)
      ctx.rotate((heading * Math.PI) / 180)

      // EKF Uncertainty Ellipse
      ctx.strokeStyle = faults.sensorDropout ? 'rgba(199, 108, 100, 0.7)' : 'rgba(119, 152, 163, 0.65)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.ellipse(0, 0, 36 + ekfResidual * 100, 24 + ekfResidual * 60, 0, 0, Math.PI * 2)
      ctx.stroke()
      ctx.setLineDash([])

      // Rover Chassis (top-down view)
      ctx.fillStyle = '#536F59'
      ctx.fillRect(-18, -12, 36, 24)
      ctx.fillStyle = '#779477'
      ctx.fillRect(-14, -9, 28, 18)

      // Solar Deck
      ctx.fillStyle = '#7798A3'
      ctx.fillRect(-8, -6, 16, 12)

      // Mast / Camera
      ctx.fillStyle = '#26372D'
      ctx.beginPath()
      ctx.arc(10, 0, 4, 0, Math.PI * 2)
      ctx.fill()

      // 6 Wheels
      ctx.fillStyle = faults.actuatorDegradation ? '#C76C64' : '#26372D'
      const wheels = [
        [-16, -16], [0, -16], [16, -16],
        [-16, 13],  [0, 13],  [16, 13],
      ]
      wheels.forEach(([wx, wy]) => {
        ctx.fillRect(wx - 4, wy - 3, 8, 6)
      })

      // Heading Sensor Cone
      ctx.fillStyle = 'rgba(119, 148, 119, 0.22)'
      ctx.beginPath()
      ctx.moveTo(12, 0)
      ctx.lineTo(48, -20)
      ctx.lineTo(48, 20)
      ctx.closePath()
      ctx.fill()

      ctx.restore()

      // Overlay HUD details on canvas
      ctx.fillStyle = 'rgba(255, 254, 247, 0.92)'
      ctx.strokeStyle = 'rgba(83, 111, 89, 0.2)'
      ctx.lineWidth = 1
      ctx.fillRect(16, 16, 220, 72)
      ctx.strokeRect(16, 16, 220, 72)

      ctx.fillStyle = '#26372D'
      ctx.font = 'bold 11px Space Mono'
      ctx.fillText(`LOC: X=${posX.toFixed(1)}m | Y=${posY.toFixed(1)}m`, 28, 36)
      ctx.font = '10px Space Mono'
      ctx.fillStyle = '#526257'
      ctx.fillText(`TERRAIN SLIP: ${wheelSlip.toFixed(1)}%`, 28, 52)
      ctx.fillText(`EKF COVARIANCE: ±${(ekfResidual * 10).toFixed(2)}m`, 28, 68)

      animationFrameId = requestAnimationFrame(render)
    }

    render()
    return () => cancelAnimationFrame(animationFrameId)
  }, [posX, posY, heading, wheelSlip, ekfResidual, faults, controllerMode, replanCount, simTime])

  const handleStart = () => setSimStatus('running')
  const handlePause = () => setSimStatus(s => (s === 'running' ? 'paused' : 'running'))
  const handleStop = () => {
    setSimStatus('idle')
    setSimTime(0)
    setPosX(12.4)
    setPosY(8.2)
    setBattery(initialBattery)
    setReplanCount(0)
  }

  return (
    <div className="rover-root">
      {/* ── LEFT PANEL: CONFIGURATION & FAULT INJECTION ── */}
      <aside className="rv-config-panel">
        <div className="rv-panel-header">
          <Navigation2 size={16} className="text-primary-dark" />
          <span>ROVER MISSION CONFIG</span>
        </div>

        {/* Terrain & Environment */}
        <div className="rv-config-section">
          <label className="rv-label">Planetary Terrain Map</label>
          <select
            value={terrain}
            onChange={e => setTerrain(e.target.value)}
            className="rv-select"
          >
            {TERRAINS.map(t => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        {/* Controller Architecture Selection */}
        <div className="rv-config-section">
          <label className="rv-label">Autonomy Controller Architecture</label>
          <div className="rv-mode-selector">
            <button
              className={`rv-mode-btn ${controllerMode === 'ASTRA_ADAPTIVE' ? 'active' : ''}`}
              onClick={() => setControllerMode('ASTRA_ADAPTIVE')}
            >
              <div className="rv-mode-title">ASTRA Adaptive</div>
              <div className="rv-mode-desc">Fault-tolerant Dynamic Replanning</div>
            </button>
            <button
              className={`rv-mode-btn ${controllerMode === 'FSM_BASELINE' ? 'active' : ''}`}
              onClick={() => setControllerMode('FSM_BASELINE')}
            >
              <div className="rv-mode-title">FSM Baseline</div>
              <div className="rv-mode-desc">Static Waypoint State Machine</div>
            </button>
          </div>
        </div>

        {/* Battery & Speed sliders */}
        <div className="rv-config-section">
          <div className="rv-slider-header">
            <label className="rv-label">Initial Battery Reserve</label>
            <span className="rv-value-tag">{initialBattery}%</span>
          </div>
          <input
            type="range"
            min="30"
            max="100"
            value={initialBattery}
            onChange={e => setInitialBattery(+e.target.value)}
            className="rv-slider"
          />

          <div className="rv-slider-header mt-3">
            <label className="rv-label">Max Autonomous Speed</label>
            <span className="rv-value-tag">{maxSpeed} m/s</span>
          </div>
          <input
            type="range"
            min="0.2"
            max="1.5"
            step="0.1"
            value={maxSpeed}
            onChange={e => setMaxSpeed(+e.target.value)}
            className="rv-slider"
          />
        </div>

        {/* Fault Injection Panel */}
        <div className="rv-config-section rv-fault-section">
          <div className="rv-section-title">
            <ShieldAlert size={14} className="text-warning" />
            <span>FAULT INJECTION SUITE</span>
          </div>
          <p className="rv-section-hint">Test system resilience by introducing real-time subsystem degradations.</p>

          <div className="rv-fault-list">
            {/* Fault 1: Sensor Dropout */}
            <div className={`rv-fault-card ${faults.sensorDropout ? 'active danger' : ''}`}>
              <div className="rv-fault-info">
                <span className="rv-fault-name">Sensor Dropout</span>
                <span className="rv-fault-badge badge-high">HIGH SEVERITY</span>
              </div>
              <button
                className={`rv-fault-toggle ${faults.sensorDropout ? 'on' : ''}`}
                onClick={() => toggleFault('sensorDropout')}
              >
                {faults.sensorDropout ? 'ACTIVE' : 'INJECT'}
              </button>
            </div>

            {/* Fault 2: Terrain Misclassification */}
            <div className={`rv-fault-card ${faults.terrainMisclass ? 'active warning' : ''}`}>
              <div className="rv-fault-info">
                <span className="rv-fault-name">Terrain Misclassification</span>
                <span className="rv-fault-badge badge-med">MED SEVERITY</span>
              </div>
              <button
                className={`rv-fault-toggle ${faults.terrainMisclass ? 'on' : ''}`}
                onClick={() => toggleFault('terrainMisclass')}
              >
                {faults.terrainMisclass ? 'ACTIVE' : 'INJECT'}
              </button>
            </div>

            {/* Fault 3: Power Drain Spike */}
            <div className={`rv-fault-card ${faults.powerDrain ? 'active danger' : ''}`}>
              <div className="rv-fault-info">
                <span className="rv-fault-name">Power Drain Spike</span>
                <span className="rv-fault-badge badge-high">HIGH SEVERITY</span>
              </div>
              <button
                className={`rv-fault-toggle ${faults.powerDrain ? 'on' : ''}`}
                onClick={() => toggleFault('powerDrain')}
              >
                {faults.powerDrain ? 'ACTIVE' : 'INJECT'}
              </button>
            </div>

            {/* Fault 4: Actuator Degradation */}
            <div className={`rv-fault-card ${faults.actuatorDegradation ? 'active info' : ''}`}>
              <div className="rv-fault-info">
                <span className="rv-fault-name">Actuator Degradation</span>
                <span className="rv-fault-badge badge-low">LOW SEVERITY</span>
              </div>
              <button
                className={`rv-fault-toggle ${faults.actuatorDegradation ? 'on' : ''}`}
                onClick={() => toggleFault('actuatorDegradation')}
              >
                {faults.actuatorDegradation ? 'ACTIVE' : 'INJECT'}
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* ── CENTER AREA: TERRAIN CANVAS & SIM CONTROLS ── */}
      <section className="rv-viewport-area">
        <div className="rv-viewport-header">
          <div className="rv-viewport-title">
            <span className="rv-status-dot" style={{ backgroundColor: simStatus === 'running' ? 'var(--success)' : 'var(--muted)' }} />
            <span>ASTRA 2D/3D TERRAIN INTERACTION &amp; REPLANNING CANVAS</span>
          </div>
          <div className="rv-viewport-badges">
            <span className="badge-pill">Controller: {controllerMode}</span>
            <span className="badge-pill">Terrain: {TERRAINS.find(t => t.id === terrain)?.roughness} Roughness</span>
          </div>
        </div>

        {/* Interactive Canvas */}
        <div className="rv-canvas-container">
          <canvas ref={canvasRef} width={680} height={480} className="rv-canvas" />
        </div>

        {/* Simulation Controls Strip */}
        <div className="rv-control-strip">
          <div className="rv-control-buttons">
            <button
              className={`rv-ctrl-btn ${simStatus === 'running' ? 'active-green' : ''}`}
              onClick={handleStart}
              disabled={simStatus === 'running'}
            >
              <Play size={14} />
              <span>Simulate</span>
            </button>
            <button
              className="rv-ctrl-btn"
              onClick={handlePause}
              disabled={simStatus === 'idle'}
            >
              <Pause size={14} />
              <span>Pause</span>
            </button>
            <button className="rv-ctrl-btn" onClick={handleStop}>
              <Square size={13} />
              <span>Reset</span>
            </button>
          </div>

          <div className="rv-sim-progress">
            <span className="rv-progress-label">MISSION TIME: T+{simTime}s</span>
            <div className="rv-progress-track">
              <div className="rv-progress-fill" style={{ width: `${Math.min(100, (simTime / 60) * 100)}%` }} />
            </div>
          </div>

          <div className="rv-status-tags">
            {replanCount > 0 && (
              <span className="rv-replan-tag">
                <RotateCcw size={12} />
                <span>DYNAMIC REPLAN x{replanCount}</span>
              </span>
            )}
          </div>
        </div>

        {/* Live Decision & Event Log */}
        <div className="rv-decision-log">
          <div className="rv-log-header">
            <Activity size={13} />
            <span>AUTONOMY DECISION LOG</span>
          </div>
          <div className="rv-log-content">
            {logs.map((log, idx) => (
              <div key={idx} className="rv-log-line">
                <span className="rv-log-time">[{simTime.toFixed(1)}s]</span>
                <span>{log}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── RIGHT PANEL: TELEMETRY & 6-WHEEL HEALTH ── */}
      <aside className="rv-telemetry-panel">
        <div className="rv-panel-header">
          <Gauge size={16} className="text-primary-dark" />
          <span>ROVER TELEMETRY</span>
        </div>

        {/* Primary Gauges */}
        <div className="rv-gauges-grid">
          <div className="rv-gauge-card">
            <div className="rv-gauge-label">VELOCITY</div>
            <div className="rv-gauge-val">{velocity} <span className="rv-unit">m/s</span></div>
          </div>
          <div className="rv-gauge-card">
            <div className="rv-gauge-label">BATTERY</div>
            <div className={`rv-gauge-val ${battery < 25 ? 'text-danger' : 'text-success'}`}>
              {battery.toFixed(1)} <span className="rv-unit">%</span>
            </div>
          </div>
          <div className="rv-gauge-card">
            <div className="rv-gauge-label">HEADING</div>
            <div className="rv-gauge-val">{heading.toFixed(1)}°</div>
          </div>
          <div className="rv-gauge-card">
            <div className="rv-gauge-label">WHEEL SLIP</div>
            <div className="rv-gauge-val">{wheelSlip.toFixed(1)} <span className="rv-unit">%</span></div>
          </div>
        </div>

        {/* 6-Wheel Subsystem Actuator Health */}
        <div className="rv-wheel-health-card">
          <div className="rv-card-title">
            <Cpu size={13} />
            <span>6-WHEEL ACTUATOR HEALTH</span>
          </div>
          <div className="rv-wheels-grid">
            {['FL', 'FR', 'ML', 'MR', 'RL', 'RR'].map((name, i) => (
              <div key={name} className="rv-wheel-item">
                <span className="rv-wheel-label">{name}</span>
                <div
                  className="rv-wheel-dot"
                  style={{
                    backgroundColor:
                      wheelHealth[i] > 80 ? 'var(--success)' : wheelHealth[i] > 50 ? 'var(--warning)' : 'var(--danger)',
                  }}
                />
                <span className="rv-wheel-val">{wheelHealth[i]}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* EKF Uncertainty Matrix */}
        <div className="rv-ekf-card">
          <div className="rv-card-title">
            <Radio size={13} />
            <span>EKF COVARIANCE MATRIX</span>
          </div>
          <div className="rv-ekf-grid">
            <div className="rv-ekf-cell">
              <span className="ekf-key">cov_x:</span>
              <span className="ekf-val">{ekfResidual.toFixed(4)}</span>
            </div>
            <div className="rv-ekf-cell">
              <span className="ekf-key">cov_y:</span>
              <span className="ekf-val">{(ekfResidual * 1.1).toFixed(4)}</span>
            </div>
            <div className="rv-ekf-cell">
              <span className="ekf-key">cov_θ:</span>
              <span className="ekf-val">0.0018</span>
            </div>
            <div className="rv-ekf-cell">
              <span className="ekf-key">cov_v:</span>
              <span className="ekf-val">0.0042</span>
            </div>
          </div>
        </div>

        {/* Live Recharts: Battery & Velocity */}
        <div className="rv-chart-card">
          <div className="rv-card-title">BATTERY CONSUMPTION PROFILE</div>
          <div className="rv-chart-wrap">
            <ResponsiveContainer width="100%" height={95}>
              <LineChart data={telemetryHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(83, 111, 89, 0.15)" />
                <XAxis dataKey="t" hide />
                <YAxis domain={[0, 100]} hide />
                <Tooltip
                  contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', fontSize: '11px' }}
                />
                <Line type="monotone" dataKey="battery" stroke="#590907" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Baseline Comparative Metrics */}
        <div className="rv-baseline-card">
          <div className="rv-card-title">ASTRA vs FSM BASELINE</div>
          <div className="rv-compare-table">
            <div className="rv-compare-header">
              <span>METRIC</span>
              <span>ASTRA</span>
              <span>FSM</span>
            </div>
            <div className="rv-compare-row">
              <span>Energy Eff.</span>
              <span className="text-success">+24.8%</span>
              <span className="text-muted">1.0x</span>
            </div>
            <div className="rv-compare-row">
              <span>Slip Mitigation</span>
              <span className="text-success">98.2%</span>
              <span className="text-warning">64.5%</span>
            </div>
            <div className="rv-compare-row">
              <span>Fault Recovery</span>
              <span className="text-success">Automatic</span>
              <span className="text-danger">Failed</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}

export default RoverModule
