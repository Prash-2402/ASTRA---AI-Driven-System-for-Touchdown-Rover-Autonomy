import React, { useState, useEffect } from 'react'
import {
  Radio, Activity, Gauge, Download, Filter,
  Maximize2, Zap, AlertCircle, Compass, Layers, CheckCircle2
} from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import './TelemetryPage.css'

interface TelemetrySample {
  timestamp: string
  altitude: number
  velocityV: number
  velocityH: number
  acceleration: number
  roll: number
  pitch: number
  yaw: number
  battery: number
  power: number
  torque: number
  wheelSlip: number
  ekfCov: number
  faultResidual: number
}

export const TelemetryPage: React.FC = () => {
  const [selectedSubsystem, setSelectedSubsystem] = useState<'All' | 'Touchdown' | 'Rover'>('All')
  const [timeWindow, setTimeWindow] = useState<'30s' | '1m' | '5m'>('1m')
  const [isStreaming, setIsStreaming] = useState(true)

  // Live telemetry stream buffer
  const [data, setData] = useState<TelemetrySample[]>(() => {
    // Generate initial realistic sample stream
    const points: TelemetrySample[] = []
    const now = Date.now()
    for (let i = 30; i >= 0; i--) {
      const t = new Date(now - i * 1000).toLocaleTimeString()
      points.push({
        timestamp: t,
        altitude: Math.max(0, 1850 - (30 - i) * 35),
        velocityV: +(12.4 + Math.sin(i * 0.4) * 2.1).toFixed(2),
        velocityH: +(2.8 + Math.cos(i * 0.3) * 0.9).toFixed(2),
        acceleration: +(-1.62 + Math.sin(i * 0.5) * 0.4).toFixed(2),
        roll: +(1.2 + Math.sin(i * 0.2) * 1.8).toFixed(2),
        pitch: +(-2.4 + Math.cos(i * 0.25) * 2.1).toFixed(2),
        yaw: +(45.0 + Math.sin(i * 0.1) * 3.5).toFixed(2),
        battery: +(94.5 - (30 - i) * 0.15).toFixed(1),
        power: Math.round(480 + Math.sin(i * 0.6) * 60),
        torque: +(18.4 + Math.sin(i * 0.7) * 4.2).toFixed(1),
        wheelSlip: +(3.2 + Math.abs(Math.sin(i * 0.3)) * 2.8).toFixed(1),
        ekfCov: +(0.032 + Math.random() * 0.008).toFixed(4),
        faultResidual: +(0.015 + Math.random() * 0.005).toFixed(4),
      })
    }
    return points
  })

  // Live streaming clock
  useEffect(() => {
    if (!isStreaming) return
    const timer = setInterval(() => {
      setData(prev => {
        const last = prev[prev.length - 1]
        const tStr = new Date().toLocaleTimeString()
        const nextAltitude = Math.max(0, +(last.altitude - 8 - Math.random() * 4).toFixed(1))
        const nextSample: TelemetrySample = {
          timestamp: tStr,
          altitude: nextAltitude,
          velocityV: +(8.5 + Math.sin(Date.now() / 800) * 1.5).toFixed(2),
          velocityH: +(1.9 + Math.cos(Date.now() / 1200) * 0.6).toFixed(2),
          acceleration: +(-1.62 + Math.sin(Date.now() / 900) * 0.3).toFixed(2),
          roll: +(0.8 + Math.sin(Date.now() / 1500) * 1.4).toFixed(2),
          pitch: +(-1.2 + Math.cos(Date.now() / 1400) * 1.6).toFixed(2),
          yaw: +(48.2 + Math.sin(Date.now() / 3000) * 2.0).toFixed(2),
          battery: Math.max(0, +(last.battery - 0.04).toFixed(1)),
          power: Math.round(490 + Math.sin(Date.now() / 600) * 40),
          torque: +(19.1 + Math.sin(Date.now() / 700) * 3.0).toFixed(1),
          wheelSlip: +(3.6 + Math.abs(Math.sin(Date.now() / 1000)) * 2.2).toFixed(1),
          ekfCov: +(0.031 + Math.random() * 0.006).toFixed(4),
          faultResidual: +(0.018 + Math.random() * 0.004).toFixed(4),
        }
        return [...prev.slice(1), nextSample]
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [isStreaming])

  const latest = data[data.length - 1] || ({} as TelemetrySample)

  return (
    <div className="telem-page-root">
      {/* ── TOP CONTROL & FILTER STRIP ── */}
      <header className="telem-header">
        <div className="telem-header-left">
          <div className="telem-title">
            <Radio size={16} className="text-primary-dark" />
            <span>REAL-TIME TELEMETRY MATRIX &amp; SENSOR FUSION BUS</span>
          </div>
          <div className="telem-stream-indicator">
            <span className={`telem-dot ${isStreaming ? 'pulse' : ''}`} />
            <span>{isStreaming ? 'STREAMING ACTIVE @ 10 Hz' : 'STREAM PAUSED'}</span>
          </div>
        </div>

        <div className="telem-header-right">
          {/* Subsystem filter */}
          <div className="telem-filter-group">
            <Filter size={13} className="text-muted" />
            {(['All', 'Touchdown', 'Rover'] as const).map(sys => (
              <button
                key={sys}
                className={`telem-filter-btn ${selectedSubsystem === sys ? 'active' : ''}`}
                onClick={() => setSelectedSubsystem(sys)}
              >
                {sys}
              </button>
            ))}
          </div>

          {/* Time window */}
          <div className="telem-window-group">
            {(['30s', '1m', '5m'] as const).map(tw => (
              <button
                key={tw}
                className={`telem-win-btn ${timeWindow === tw ? 'active' : ''}`}
                onClick={() => setTimeWindow(tw)}
              >
                {tw}
              </button>
            ))}
          </div>

          {/* Toggle stream */}
          <button
            className={`telem-toggle-stream ${isStreaming ? 'active' : ''}`}
            onClick={() => setIsStreaming(!isStreaming)}
          >
            {isStreaming ? 'Pause Stream' : 'Resume Stream'}
          </button>
        </div>
      </header>

      {/* ── REAL-TIME STATS STRIP ── */}
      <div className="telem-stats-strip">
        <div className="telem-stat-pill">
          <span className="stat-label">ALTITUDE</span>
          <span className="stat-value font-mono">{latest.altitude?.toFixed(1)} m</span>
        </div>
        <div className="telem-stat-pill">
          <span className="stat-label">DESCENT VELOCITY</span>
          <span className="stat-value font-mono">{latest.velocityV?.toFixed(2)} m/s</span>
        </div>
        <div className="telem-stat-pill">
          <span className="stat-label">POWER BUS</span>
          <span className="stat-value font-mono">{latest.power} W</span>
        </div>
        <div className="telem-stat-pill">
          <span className="stat-label">STATE UNCERTAINTY (EKF)</span>
          <span className="stat-value font-mono text-success">±{(latest.ekfCov * 100)?.toFixed(2)} cm</span>
        </div>
        <div className="telem-stat-pill">
          <span className="stat-label">RESIDUAL DRIFT</span>
          <span className="stat-value font-mono">{latest.faultResidual?.toFixed(4)}</span>
        </div>
      </div>

      {/* ── SCIENTIFIC MULTI-CHART MATRIX ── */}
      <div className="telem-charts-grid">
        {/* 1. Altitude & Vertical Descent Profile */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">DESCENT PROFILE</span>
            <span className="card-title">Altitude (m) vs Ground Reference</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Area type="monotone" dataKey="altitude" stroke="#590907" fill="rgba(89, 9, 7, 0.12)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. Velocity Dual Axis: Vertical vs Horizontal */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">KINEMATICS</span>
            <span className="card-title">Vertical Velocity &amp; Horizontal Drift (m/s)</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Line type="monotone" dataKey="velocityV" name="Vertical Vel" stroke="#590907" strokeWidth={1.8} dot={false} />
                <Line type="monotone" dataKey="velocityH" name="Horizontal Vel" stroke="#BF802B" strokeWidth={1.8} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 3. 3-Axis Attitude: Roll, Pitch, Yaw */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">ORIENTATION</span>
            <span className="card-title">Attitude Dynamics: Roll, Pitch, Yaw (deg)</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Line type="monotone" dataKey="roll" name="Roll" stroke="#590907" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="pitch" name="Pitch" stroke="#A5A79B" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="yaw" name="Yaw" stroke="#B79B79" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 4. Power & Battery Bus Reserve */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">POWER SUBSYSTEM</span>
            <span className="card-title">Battery Reserve (%) with 20% Threshold</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <ReferenceLine y={20} stroke="#B84A39" strokeDasharray="3 3" label={{ value: 'LOW BATTERY', fill: '#B84A39', fontSize: 9 }} />
                <Area type="monotone" dataKey="battery" stroke="#4E7850" fill="rgba(78, 120, 80, 0.2)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 5. 6-Wheel Slip & Drivetrain Torque */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">TERRAIN INTERACTION</span>
            <span className="card-title">Wheel Slip (%) &amp; Torque (N·m)</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Line type="monotone" dataKey="wheelSlip" name="Wheel Slip %" stroke="#BF802B" strokeWidth={1.8} dot={false} />
                <Line type="monotone" dataKey="torque" name="Torque N·m" stroke="#590907" strokeWidth={1.8} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 6. EKF Covariance & Fault Residuals */}
        <div className="telem-card">
          <div className="telem-card-header">
            <span className="card-tag">STATE ESTIMATOR</span>
            <span className="card-title">EKF Covariance Trace &amp; Innovation Residual</span>
          </div>
          <div className="telem-chart-body">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(165, 167, 155, 0.2)" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Line type="monotone" dataKey="ekfCov" name="EKF Covariance" stroke="#590907" strokeWidth={1.8} dot={false} />
                <Line type="monotone" dataKey="faultResidual" name="Fault Residual" stroke="#A5A79B" strokeWidth={1.8} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TelemetryPage
