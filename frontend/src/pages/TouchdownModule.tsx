import React, { useState, useEffect, useRef } from 'react'
import { Play, Pause, Square, RefreshCw, Settings2, Target, AlertTriangle, CheckCircle2, ChevronDown } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './TouchdownModule.css'

type Controller = 'PID' | 'MPC' | 'PPO'
type SimState = 'idle' | 'running' | 'paused' | 'landed' | 'failed'

interface TelemetryPoint {
  t: number
  altitude: number
  velocityV: number
  velocityH: number
  fuel: number
  throttle: number
}

const CONTROLLERS: { id: Controller; label: string; desc: string; color: string }[] = [
  { id: 'PID', label: 'PID Controller', desc: 'Classic proportional-integral-derivative feedback', color: '#77796F' },
  { id: 'MPC', label: 'Model Predictive', desc: 'Receding horizon optimal control', color: '#BF802B' },
  { id: 'PPO', label: 'PPO (RL Agent)', desc: 'Proximal policy optimization learned policy', color: '#590907' },
]

const ENVIRONMENTS = ['Mars — Jezero Crater', 'Moon — South Pole', 'Mars — Hellas Basin']

/* ─── Simulation Viewport ─── */
const SimViewport: React.FC<{
  simState: SimState
  altitude: number
  trajectoryPoints: { x: number; y: number }[]
  controller: Controller
}> = ({ simState, altitude, trajectoryPoints, controller }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const resize = () => {
      canvas.width = canvas.offsetWidth * devicePixelRatio
      canvas.height = canvas.offsetHeight * devicePixelRatio
      ctx.scale(devicePixelRatio, devicePixelRatio)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    let t = 0
    const draw = () => {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      ctx.clearRect(0, 0, W, H)

      // Sky gradient
      const sky = ctx.createLinearGradient(0, 0, 0, H)
      sky.addColorStop(0, '#1A0F0A')
      sky.addColorStop(0.6, '#2D1A10')
      sky.addColorStop(1, '#8B5A3A')
      ctx.fillStyle = sky
      ctx.fillRect(0, 0, W, H)

      // Stars
      ctx.fillStyle = 'rgba(255,248,235,0.6)'
      const starSeed = [0.15, 0.32, 0.48, 0.62, 0.78, 0.22, 0.55, 0.88, 0.11, 0.73]
      starSeed.forEach((s, i) => {
        ctx.beginPath()
        ctx.arc(s * W, (i / starSeed.length) * H * 0.55, 0.8 + s * 0.6, 0, Math.PI * 2)
        ctx.fill()
      })

      // Ground
      const groundY = H * 0.78
      const ground = ctx.createLinearGradient(0, groundY, 0, H)
      ground.addColorStop(0, '#A0633C')
      ground.addColorStop(0.3, '#8B5230')
      ground.addColorStop(1, '#5C3018')
      ctx.fillStyle = ground
      ctx.fillRect(0, groundY, W, H - groundY)

      // Terrain features
      ctx.fillStyle = 'rgba(90,50,25,0.6)'
      ctx.beginPath()
      ctx.ellipse(W * 0.15, groundY, 40, 12, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.ellipse(W * 0.75, groundY + 4, 55, 16, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.ellipse(W * 0.55, groundY, 28, 9, 0, 0, Math.PI * 2)
      ctx.fill()

      // Hazard zones
      ctx.strokeStyle = 'rgba(199,108,100,0.5)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.ellipse(W * 0.22, groundY - 2, 38, 10, 0, 0, Math.PI * 2)
      ctx.stroke()
      ctx.beginPath()
      ctx.ellipse(W * 0.68, groundY - 4, 45, 12, 0, 0, Math.PI * 2)
      ctx.stroke()

      // Safe landing zone
      ctx.strokeStyle = 'rgba(100,140,101,0.8)'
      ctx.setLineDash([])
      ctx.lineWidth = 1.5
      const lzX = W * 0.48
      ctx.beginPath()
      ctx.arc(lzX, groundY - 2, 28, 0, Math.PI * 2)
      ctx.stroke()
      ctx.beginPath()
      ctx.arc(lzX, groundY - 2, 12, 0, Math.PI * 2)
      ctx.stroke()
      ctx.beginPath()
      ctx.arc(lzX, groundY - 2, 4, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(100,140,101,0.7)'
      ctx.fill()

      // Landing zone label
      ctx.fillStyle = 'rgba(100,140,101,0.9)'
      ctx.font = `${9 / devicePixelRatio}px Space Mono, monospace`
      ctx.textAlign = 'center'
      ctx.fillText('LZ-ALPHA', lzX, groundY + 16)

      // Trajectory line
      if (trajectoryPoints.length > 1) {
        ctx.strokeStyle = 'rgba(214,155,77,0.65)'
        ctx.lineWidth = 1.5
        ctx.setLineDash([6, 4])
        ctx.beginPath()
        trajectoryPoints.forEach((p, i) => {
          const px = p.x * W
          const py = p.y * H
          if (i === 0) ctx.moveTo(px, py)
          else ctx.lineTo(px, py)
        })
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Lander position
      const landFraction = Math.max(0, Math.min(1, 1 - altitude / 2000))
      const landerX = W * 0.48 + Math.sin(t * 0.8) * W * 0.02 * (1 - landFraction)
      const landerY = groundY - 30 - (H * 0.55) * (1 - landFraction)

      if (simState !== 'idle') {
        // Thruster flame
        if (simState === 'running' || simState === 'paused') {
          const flameH = 20 + Math.sin(t * 8) * 4
          const flame = ctx.createRadialGradient(landerX, landerY + 18, 0, landerX, landerY + 18, flameH)
          flame.addColorStop(0, 'rgba(255,220,140,0.9)')
          flame.addColorStop(0.4, 'rgba(214,155,77,0.7)')
          flame.addColorStop(1, 'rgba(199,108,100,0)')
          ctx.beginPath()
          ctx.ellipse(landerX, landerY + 18, 8, flameH, 0, 0, Math.PI * 2)
          ctx.fillStyle = flame
          ctx.fill()
        }

        // Lander body
        ctx.fillStyle = '#536F59'
        ctx.beginPath()
        ctx.roundRect(landerX - 16, landerY - 18, 32, 24, 4)
        ctx.fill()
        ctx.fillStyle = '#648C65'
        ctx.beginPath()
        ctx.roundRect(landerX - 12, landerY - 14, 24, 16, 3)
        ctx.fill()

        // Sensor dome
        ctx.fillStyle = '#779477'
        ctx.beginPath()
        ctx.ellipse(landerX, landerY - 18, 10, 6, 0, 0, Math.PI * 2)
        ctx.fill()

        // Solar panels
        ctx.fillStyle = 'rgba(119,152,163,0.85)'
        ctx.fillRect(landerX - 42, landerY - 12, 24, 8)
        ctx.fillRect(landerX + 18, landerY - 12, 24, 8)

        // Legs
        ctx.strokeStyle = '#AFC3A7'
        ctx.lineWidth = 2
        ctx.setLineDash([])
        ctx.beginPath()
        ctx.moveTo(landerX, landerY + 6)
        ctx.lineTo(landerX - 20, landerY + 22)
        ctx.moveTo(landerX, landerY + 6)
        ctx.lineTo(landerX + 20, landerY + 22)
        ctx.stroke()

        // Altitude indicator
        ctx.strokeStyle = 'rgba(214,155,77,0.5)'
        ctx.lineWidth = 1
        ctx.setLineDash([3, 3])
        ctx.beginPath()
        ctx.moveTo(landerX + 28, landerY)
        ctx.lineTo(landerX + 28, groundY)
        ctx.stroke()
        ctx.setLineDash([])

        ctx.fillStyle = 'rgba(214,155,77,0.9)'
        ctx.font = `${9 / devicePixelRatio}px Space Mono, monospace`
        ctx.textAlign = 'left'
        ctx.fillText(`${Math.round(altitude)}m`, landerX + 32, landerY + 4)

        // Landed indicator
        if (simState === 'landed') {
          ctx.fillStyle = 'rgba(100,140,101,0.9)'
          ctx.font = `${11 / devicePixelRatio}px Inter, sans-serif`
          ctx.textAlign = 'center'
          ctx.fillText('✓ LANDED SAFELY', W / 2, H * 0.25)
        }
      }

      // EKF uncertainty ellipse
      if (simState === 'running') {
        const unc = 12 + Math.sin(t * 0.5) * 3
        ctx.strokeStyle = 'rgba(119,152,163,0.4)'
        ctx.lineWidth = 1
        ctx.setLineDash([2, 4])
        ctx.beginPath()
        ctx.ellipse(landerX, landerY, unc, unc * 0.7, 0, 0, Math.PI * 2)
        ctx.stroke()
        ctx.setLineDash([])
      }

      // HUD overlay
      ctx.fillStyle = 'rgba(8,8,16,0.72)'
      ctx.beginPath()
      ctx.roundRect(12, 12, 130, 60, 8)
      ctx.fill()
      ctx.fillStyle = 'rgba(175,195,167,0.85)'
      ctx.font = `${10 / devicePixelRatio}px Space Mono, monospace`
      ctx.textAlign = 'left'
      ctx.fillText(`MODE: ${controller}`, 20, 30)
      ctx.fillText(`STATE: ${simState.toUpperCase()}`, 20, 46)
      ctx.fillText(`t = ${Math.round(t * 10) / 10}s`, 20, 62)

      t += 0.016
      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(animRef.current)
      ro.disconnect()
    }
  }, [simState, altitude, trajectoryPoints, controller])

  return <canvas ref={canvasRef} className="sim-canvas" />
}

/* ─── Telemetry Chart ─── */
const TelemetryChart: React.FC<{ data: TelemetryPoint[]; dataKey: keyof TelemetryPoint; label: string; color: string; unit: string }> = ({
  data, dataKey, label, color, unit
}) => (
  <div className="telem-chart">
    <div className="telem-chart-header">
      <span className="telem-chart-label">{label}</span>
      <span className="telem-chart-unit" style={{ color }}>{unit}</span>
    </div>
    <ResponsiveContainer width="100%" height={80}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 4 }}>
        <CartesianGrid strokeDasharray="2 2" stroke="var(--border)" />
        <XAxis dataKey="t" hide tick={{ fontSize: 9 }} />
        <YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} />
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '10px', fontSize: '11px' }}
          labelStyle={{ color: 'var(--muted)' }}
          itemStyle={{ color }}
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  </div>
)

/* ─── Main Component ─── */
const TouchdownModule: React.FC = () => {
  const [controller, setController] = useState<Controller>('MPC')
  const [simState, setSimState] = useState<SimState>('idle')
  const [altitude, setAltitude] = useState(2000)
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([])
  const [environment, setEnvironment] = useState(ENVIRONMENTS[0])
  const [elapsed, setElapsed] = useState(0)
  const [fuel, setFuel] = useState(100)
  const [throttle, setThrottle] = useState(0)
  const [velocityV, setVelocityV] = useState(0)
  const [velocityH, setVelocityH] = useState(0)
  const simInterval = useRef<ReturnType<typeof setInterval> | null>(null)
  const trajectoryPoints = useRef<{ x: number; y: number }[]>([{ x: 0.48, y: 0.15 }])

  const startSim = () => {
    if (simState === 'idle' || simState === 'landed' || simState === 'failed') {
      setAltitude(2000)
      setFuel(100)
      setThrottle(0)
      setVelocityV(0)
      setVelocityH(0)
      setTelemetry([])
      setElapsed(0)
      trajectoryPoints.current = [{ x: 0.48, y: 0.15 }]
    }
    setSimState('running')
  }

  const pauseSim = () => setSimState(s => s === 'running' ? 'paused' : 'running')
  const stopSim = () => {
    setSimState('idle')
    setAltitude(2000)
    setFuel(100)
    if (simInterval.current) clearInterval(simInterval.current)
  }
  const resetSim = () => {
    stopSim()
    setTelemetry([])
    setElapsed(0)
    trajectoryPoints.current = [{ x: 0.48, y: 0.15 }]
  }

  useEffect(() => {
    if (simState === 'running') {
      simInterval.current = setInterval(() => {
        setElapsed(e => e + 0.2)
        setAltitude(prev => {
          if (prev <= 0) {
            setSimState('landed')
            return 0
          }
          const descent = controller === 'PID' ? 12 : controller === 'MPC' ? 9 : 7
          return Math.max(0, prev - descent)
        })
        setFuel(prev => Math.max(0, prev - 0.15))
        setThrottle(40 + Math.sin(Date.now() / 600) * 20)
        setVelocityV(prev => {
          const target = controller === 'PPO' ? 3.5 : controller === 'MPC' ? 4.5 : 6
          return parseFloat((prev * 0.9 + target * 0.1 + Math.random() * 0.5).toFixed(2))
        })
        setVelocityH(prev => parseFloat((prev * 0.92 + Math.random() * 0.3).toFixed(2)))
        setTelemetry(prev => {
          const newPoint: TelemetryPoint = {
            t: parseFloat((prev.length * 0.2).toFixed(1)),
            altitude: Math.max(0, 2000 - prev.length * 12),
            velocityV: 3 + Math.random() * 2,
            velocityH: Math.random() * 1.5,
            fuel: Math.max(0, 100 - prev.length * 0.15),
            throttle: 40 + Math.sin(prev.length * 0.5) * 20,
          }
          return [...prev.slice(-80), newPoint]
        })
      }, 200)
    } else {
      if (simInterval.current) clearInterval(simInterval.current)
    }
    return () => { if (simInterval.current) clearInterval(simInterval.current) }
  }, [simState, controller])

  const telemetryGauges = [
    { label: 'Altitude', value: `${Math.round(altitude)}`, unit: 'm', color: 'var(--info)' },
    { label: 'Vert. Velocity', value: velocityV.toFixed(1), unit: 'm/s', color: 'var(--warning)' },
    { label: 'Horiz. Velocity', value: velocityH.toFixed(2), unit: 'm/s', color: 'var(--primary-light)' },
    { label: 'Fuel', value: fuel.toFixed(1), unit: '%', color: fuel < 20 ? 'var(--danger)' : 'var(--success)' },
    { label: 'Throttle', value: throttle.toFixed(0), unit: '%', color: 'var(--primary)' },
    { label: 'Elapsed', value: elapsed.toFixed(1), unit: 's', color: 'var(--muted)' },
  ]

  return (
    <div className="touchdown-root">

      {/* ── Left panel — Config ── */}
      <aside className="td-config-panel">
        <div className="config-section">
          <div className="config-section-title">Mission Setup</div>
          <div className="config-field">
            <label>Environment</label>
            <div className="config-select-wrap">
              <select value={environment} onChange={e => setEnvironment(e.target.value)} className="config-select">
                {ENVIRONMENTS.map(e => <option key={e}>{e}</option>)}
              </select>
              <ChevronDown size={13} className="select-icon" />
            </div>
          </div>
          <div className="config-field">
            <label>Initial Altitude</label>
            <div className="config-input-group">
              <input type="number" defaultValue={2000} className="config-input" />
              <span className="config-input-unit">m</span>
            </div>
          </div>
          <div className="config-field">
            <label>Initial Velocity</label>
            <div className="config-input-group">
              <input type="number" defaultValue={180} className="config-input" />
              <span className="config-input-unit">m/s</span>
            </div>
          </div>
          <div className="config-field">
            <label>Fuel Mass</label>
            <div className="config-input-group">
              <input type="number" defaultValue={500} className="config-input" />
              <span className="config-input-unit">kg</span>
            </div>
          </div>
        </div>

        <div className="config-section">
          <div className="config-section-title">Controller Selection</div>
          <div className="controller-cards">
            {CONTROLLERS.map(ctrl => (
              <button
                key={ctrl.id}
                className={`controller-card ${controller === ctrl.id ? 'controller-card--active' : ''}`}
                onClick={() => setController(ctrl.id)}
                style={controller === ctrl.id ? { borderColor: ctrl.color } : {}}
              >
                <div className="controller-card-header">
                  <span
                    className="controller-id"
                    style={{ color: controller === ctrl.id ? ctrl.color : 'var(--muted)' }}
                  >{ctrl.id}</span>
                  {controller === ctrl.id && (
                    <CheckCircle2 size={13} style={{ color: ctrl.color }} />
                  )}
                </div>
                <div className="controller-label">{ctrl.label}</div>
                <div className="controller-desc">{ctrl.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="config-section">
          <div className="config-section-title">Landing Intelligence</div>
          <div className="landing-sites">
            {[
              { id: 'LZ-A', status: 'safe', score: 0.94 },
              { id: 'LZ-B', status: 'hazard', score: 0.31 },
              { id: 'LZ-C', status: 'alternate', score: 0.71 },
            ].map(site => (
              <div key={site.id} className={`landing-site landing-site--${site.status}`}>
                <div className="site-id">{site.id}</div>
                <div className="site-bar-wrap">
                  <div className="site-bar" style={{ width: `${site.score * 100}%` }} />
                </div>
                <div className="site-score">{(site.score * 100).toFixed(0)}%</div>
                <div className={`site-badge site-badge--${site.status}`}>
                  {site.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Center — Viewport ── */}
      <div className="td-viewport-area">
        <div className="viewport-header">
          <div className="viewport-title">
            <Target size={15} />
            Entry, Descent &amp; Landing — Simulation View
          </div>
          <div className="sim-state-indicator">
            <span className={`sim-state-dot ${simState}`} />
            {simState === 'idle' ? 'Standby' : simState === 'running' ? 'Simulating' : simState === 'paused' ? 'Paused' : simState === 'landed' ? 'Landed ✓' : 'Mission Failed'}
          </div>
        </div>

        <div className="viewport-canvas-wrap">
          <SimViewport
            simState={simState}
            altitude={altitude}
            trajectoryPoints={trajectoryPoints.current}
            controller={controller}
          />
        </div>

        {/* Timeline / Controls */}
        <div className="sim-control-bar">
          <div className="sim-ctrl-left">
            <button className={`sim-ctrl-btn ${simState === 'running' ? 'sim-ctrl-btn--active' : ''}`} onClick={startSim} disabled={simState === 'running'} title="Run simulation">
              <Play size={14} />
            </button>
            <button className="sim-ctrl-btn" onClick={pauseSim} disabled={simState === 'idle'} title="Pause / Resume">
              <Pause size={14} />
            </button>
            <button className="sim-ctrl-btn sim-ctrl-btn--stop" onClick={stopSim} title="Stop">
              <Square size={13} />
            </button>
            <button className="sim-ctrl-btn" onClick={resetSim} title="Reset">
              <RefreshCw size={13} />
            </button>
          </div>

          <div className="sim-timeline">
            <div className="timeline-track">
              <div
                className="timeline-fill"
                style={{ width: `${Math.min(100, (1 - altitude / 2000) * 100)}%` }}
              />
            </div>
            <span className="timeline-label">T+{elapsed.toFixed(1)}s</span>
          </div>

          <div className="sim-ctrl-right">
            <Settings2 size={14} />
            <span>Controller: <strong>{controller}</strong></span>
          </div>
        </div>

        {/* Event log */}
        <div className="event-log">
          <div className="event-log-title">Event Log</div>
          {simState === 'idle' && <div className="event-entry event-entry--info">System ready. Configure mission and press Run to begin.</div>}
          {simState === 'running' && <div className="event-entry event-entry--active">EDL sequence active — {controller} controller engaged.</div>}
          {altitude < 500 && altitude > 0 && simState === 'running' && <div className="event-entry event-entry--warn">⚠ Terminal descent phase — altitude below 500m.</div>}
          {simState === 'landed' && <div className="event-entry event-entry--success">✓ Soft landing achieved. Mission complete.</div>}
        </div>
      </div>

      {/* ── Right panel — Telemetry ── */}
      <aside className="td-telemetry-panel">
        <div className="telem-section-title">Live Telemetry</div>

        <div className="telem-gauges">
          {telemetryGauges.map(g => (
            <div key={g.label} className="telem-gauge">
              <div className="telem-gauge-label">{g.label}</div>
              <div className="telem-gauge-value" style={{ color: g.color }}>
                {g.value}
                <span className="telem-gauge-unit">{g.unit}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="telem-charts-area">
          <TelemetryChart data={telemetry} dataKey="altitude" label="Altitude" color="#590907" unit="m" />
          <TelemetryChart data={telemetry} dataKey="velocityV" label="Vertical Velocity" color="#A5A79B" unit="m/s" />
          <TelemetryChart data={telemetry} dataKey="fuel" label="Fuel Remaining" color="#4E7850" unit="%" />
          <TelemetryChart data={telemetry} dataKey="throttle" label="Throttle" color="#BF802B" unit="%" />
        </div>

        <div className="telem-section-title" style={{ marginTop: '16px' }}>Controller State</div>
        <div className="controller-state-panel">
          {[
            { label: 'Mode', value: controller },
            { label: 'State', value: simState === 'idle' ? 'STANDBY' : simState.toUpperCase() },
            { label: 'EKF Cov.', value: simState === 'running' ? '0.42' : '—' },
            { label: 'Residual', value: simState === 'running' ? '0.08' : '—' },
            { label: 'Iterations', value: simState === 'running' ? String(Math.floor(elapsed / 0.2)) : '0' },
          ].map(item => (
            <div key={item.label} className="ctrl-state-row">
              <span className="ctrl-state-label">{item.label}</span>
              <span className="ctrl-state-value" style={{ fontFamily: 'var(--font-mono)' }}>{item.value}</span>
            </div>
          ))}
        </div>

        {fuel < 20 && simState === 'running' && (
          <div className="telem-alert">
            <AlertTriangle size={13} />
            Low fuel — {fuel.toFixed(0)}% remaining
          </div>
        )}
      </aside>
    </div>
  )
}

export default TouchdownModule

