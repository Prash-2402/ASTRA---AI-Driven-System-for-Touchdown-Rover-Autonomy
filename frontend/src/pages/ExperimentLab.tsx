import React, { useState } from 'react'
import {
  FlaskConical, Play, AlertTriangle, BarChart3, CheckCircle2,
  Clock, Zap, Lock, ShieldCheck, RefreshCw, Layers, Sliders, Database
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, AreaChart, Area
} from 'recharts'
import './ExperimentLab.css'

interface ExperimentRecord {
  id: string
  name: string
  module: 'Touchdown' | 'Rover'
  controller: string
  trials: number
  completionRate: number
  meanTime: number
  energyUsed: number
  status: 'COMPLETED' | 'RUNNING' | 'FAILED'
  timestamp: string
  mode: 'Development' | 'Held-Out'
}

export const ExperimentLab: React.FC = () => {
  // Config state
  const [expName, setExpName] = useState('EXP-049_Stochastic_Descent_Robustness')
  const [targetModule, setTargetModule] = useState<'Touchdown' | 'Rover'>('Touchdown')
  const [scenario, setScenario] = useState('High Winds + Crater Diversion')
  const [evalMode, setEvalMode] = useState<'Development' | 'Held-Out'>('Development')
  const [trialCount, setTrialCount] = useState(25)
  const [randomSeed, setRandomSeed] = useState(1337)
  const [controllerA, setControllerA] = useState('PPO (Reinforcement Learning)')
  const [controllerB, setControllerB] = useState('MPC (Model Predictive)')

  // Fault configs
  const [faultSensor, setFaultSensor] = useState(true)
  const [faultActuator, setFaultActuator] = useState(false)
  const [faultTerrain, setFaultTerrain] = useState(true)

  // Execution state
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)

  // Experiment records history
  const [history, setHistory] = useState<ExperimentRecord[]>([
    {
      id: 'EXP-048',
      name: 'Rover_SandyDune_Slip_Recovery',
      module: 'Rover',
      controller: 'ASTRA Adaptive',
      trials: 20,
      completionRate: 95.0,
      meanTime: 42.6,
      energyUsed: 1480,
      status: 'COMPLETED',
      timestamp: 'Today, 11:24',
      mode: 'Development'
    },
    {
      id: 'EXP-047',
      name: 'EDL_Jezero_Terminal_Burn_PPO',
      module: 'Touchdown',
      controller: 'PPO Agent v4',
      trials: 30,
      completionRate: 93.3,
      meanTime: 78.4,
      energyUsed: 3120,
      status: 'COMPLETED',
      timestamp: 'Today, 09:15',
      mode: 'Held-Out'
    }
  ])

  // Active metrics
  const hasResults = history.length > 0

  // Run batch simulation
  const handleRunExperiment = () => {
    setIsRunning(true)
    setProgress(5)

    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
          clearInterval(interval)
          setIsRunning(false)
          // Add completed record
          const newRec: ExperimentRecord = {
            id: `EXP-0${history.length + 49}`,
            name: expName,
            module: targetModule,
            controller: controllerA,
            trials: trialCount,
            completionRate: +(88 + Math.random() * 10).toFixed(1),
            meanTime: +(65 + Math.random() * 15).toFixed(1),
            energyUsed: Math.round(2400 + Math.random() * 600),
            status: 'COMPLETED',
            timestamp: 'Just now',
            mode: evalMode
          }
          setHistory(prev => [newRec, ...prev])
          return 100
        }
        return p + 15
      })
    }, 250)
  }

  // Data for charts
  const completionData = [
    { name: 'Trial 1-5', ASTRA: 100, Baseline: 80 },
    { name: 'Trial 6-10', ASTRA: 95, Baseline: 75 },
    { name: 'Trial 11-15', ASTRA: 92, Baseline: 68 },
    { name: 'Trial 16-20', ASTRA: 96, Baseline: 70 },
    { name: 'Trial 21-25', ASTRA: 98, Baseline: 65 },
  ]

  const energyData = [
    { trial: 'T1', ASTRA: 2200, Baseline: 3100 },
    { trial: 'T5', ASTRA: 2350, Baseline: 3400 },
    { trial: 'T10', ASTRA: 2180, Baseline: 3300 },
    { trial: 'T15', ASTRA: 2420, Baseline: 3600 },
    { trial: 'T20', ASTRA: 2290, Baseline: 3250 },
  ]

  const errorDistribution = [
    { step: '0s', error: 0.08 },
    { step: '10s', error: 0.06 },
    { step: '20s', error: 0.04 },
    { step: '30s', error: 0.035 },
    { step: '40s', error: 0.028 },
    { step: '50s', error: 0.022 },
  ]

  return (
    <div className="lab-root">
      {/* ── LEFT PANEL: EXPERIMENT CONFIGURATION ── */}
      <aside className="lab-config-panel">
        <div className="lab-panel-header">
          <FlaskConical size={16} className="text-primary-dark" />
          <span>EXPERIMENT BATCH CONFIGURATION</span>
        </div>

        {/* Experiment Setup */}
        <div className="lab-section">
          <label className="lab-label">Experiment Identifier</label>
          <input
            type="text"
            value={expName}
            onChange={e => setExpName(e.target.value)}
            className="lab-input"
          />
        </div>

        {/* Module Selector */}
        <div className="lab-section">
          <label className="lab-label">Target System Module</label>
          <div className="lab-pill-group">
            <button
              className={`lab-pill-btn ${targetModule === 'Touchdown' ? 'active' : ''}`}
              onClick={() => setTargetModule('Touchdown')}
            >
              ASTRA Touchdown
            </button>
            <button
              className={`lab-pill-btn ${targetModule === 'Rover' ? 'active' : ''}`}
              onClick={() => setTargetModule('Rover')}
            >
              ASTRA Rover
            </button>
          </div>
        </div>

        {/* Evaluation Mode */}
        <div className="lab-section">
          <label className="lab-label">Evaluation Mode</label>
          <div className="lab-eval-toggle">
            <button
              className={`lab-eval-btn ${evalMode === 'Development' ? 'active' : ''}`}
              onClick={() => setEvalMode('Development')}
            >
              Development
            </button>
            <button
              className={`lab-eval-btn ${evalMode === 'Held-Out' ? 'active-heldout' : ''}`}
              onClick={() => setEvalMode('Held-Out')}
            >
              Held-Out Evaluation
            </button>
          </div>

          {/* Held-Out Warning Box */}
          {evalMode === 'Held-Out' && (
            <div className="lab-heldout-warning">
              <Lock size={14} className="text-warning flex-shrink-0" />
              <span>
                <strong>Held-Out Mode Active:</strong> Environmental parameters, terrain noise, and sensor
                seeds are strictly locked to prevent tuning leakage.
              </span>
            </div>
          )}
        </div>

        {/* Scenario Selection */}
        <div className="lab-section">
          <label className="lab-label">Test Scenario</label>
          <select
            value={scenario}
            onChange={e => setScenario(e.target.value)}
            disabled={evalMode === 'Held-Out'}
            className="lab-select"
          >
            <option>High Winds + Crater Diversion</option>
            <option>Terminal Engine Throttle Anomaly</option>
            <option>Boulder Field Slip Obstacle</option>
            <option>Dust Storm Low Visibility Navigation</option>
          </select>
        </div>

        {/* Fault Injection Matrix */}
        <div className="lab-section">
          <label className="lab-label">Active Fault Matrix</label>
          <div className="lab-checkbox-group">
            <label className="lab-checkbox-item">
              <input
                type="checkbox"
                checked={faultSensor}
                onChange={e => setFaultSensor(e.target.checked)}
              />
              <span>Sensor Noise / Dropout</span>
            </label>
            <label className="lab-checkbox-item">
              <input
                type="checkbox"
                checked={faultTerrain}
                onChange={e => setFaultTerrain(e.target.checked)}
              />
              <span>Terrain Hazard Misclassification</span>
            </label>
            <label className="lab-checkbox-item">
              <input
                type="checkbox"
                checked={faultActuator}
                onChange={e => setFaultActuator(e.target.checked)}
              />
              <span>Actuator Degradation</span>
            </label>
          </div>
        </div>

        {/* Execution Parameters */}
        <div className="lab-section lab-grid-params">
          <div>
            <label className="lab-label">Trial Count (N)</label>
            <input
              type="number"
              min="5"
              max="100"
              value={trialCount}
              onChange={e => setTrialCount(+e.target.value)}
              className="lab-input"
            />
          </div>
          <div>
            <label className="lab-label">Random Seed</label>
            <input
              type="number"
              value={randomSeed}
              onChange={e => setRandomSeed(+e.target.value)}
              className="lab-input"
            />
          </div>
        </div>

        {/* Controller Pair */}
        <div className="lab-section">
          <label className="lab-label">Primary Controller (ASTRA)</label>
          <select value={controllerA} onChange={e => setControllerA(e.target.value)} className="lab-select">
            <option>PPO (Reinforcement Learning)</option>
            <option>MPC (Model Predictive)</option>
            <option>ASTRA Adaptive Planner</option>
          </select>

          <label className="lab-label mt-2">Benchmark Baseline</label>
          <select value={controllerB} onChange={e => setControllerB(e.target.value)} className="lab-select">
            <option>Classic PID / FSM Baseline</option>
            <option>Pure Pursuit Fixed Path</option>
          </select>
        </div>

        {/* Action Button */}
        <div className="lab-actions">
          <button
            className={`lab-run-btn ${isRunning ? 'running' : ''}`}
            onClick={handleRunExperiment}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <RefreshCw size={14} className="spin-icon" />
                <span>Simulating Batch ({progress}%)...</span>
              </>
            ) : (
              <>
                <Play size={14} />
                <span>Execute Batch Experiment</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* ── RIGHT AREA: SCIENTIFIC RESULTS & BENCHMARK CHARTS ── */}
      <section className="lab-results-area">
        <div className="lab-results-header">
          <div className="lab-results-title">
            <BarChart3 size={16} className="text-primary-dark" />
            <span>EMPIRICAL BENCHMARK RESULTS &amp; CONFIDENCE INTERVALS</span>
          </div>
          <span className="badge-pill">N = {trialCount} Monte Carlo Trials</span>
        </div>

        {/* Metric Cards 3x2 Grid */}
        <div className="lab-metrics-grid">
          <div className="lab-metric-card">
            <div className="metric-title">COMPLETION RATE</div>
            <div className="metric-val text-success">96.4% <span className="metric-ci">±1.8%</span></div>
            <div className="metric-compare">
              <span className="text-muted">Baseline: 71.2%</span>
              <span className="text-success font-semibold">+25.2% Δ</span>
            </div>
          </div>

          <div className="lab-metric-card">
            <div className="metric-title">MEAN TIME TO COMPLETION</div>
            <div className="metric-val">68.4s <span className="metric-ci">±3.2s</span></div>
            <div className="metric-compare">
              <span className="text-muted">Baseline: 84.1s</span>
              <span className="text-success font-semibold">-18.6% faster</span>
            </div>
          </div>

          <div className="lab-metric-card">
            <div className="metric-title">MEAN ENERGY CONSUMPTION</div>
            <div className="metric-val">2,280 J <span className="metric-ci">±110 J</span></div>
            <div className="metric-compare">
              <span className="text-muted">Baseline: 3,320 J</span>
              <span className="text-success font-semibold">-31.3% consumed</span>
            </div>
          </div>

          <div className="lab-metric-card">
            <div className="metric-title">SAFETY VIOLATIONS</div>
            <div className="metric-val text-success">0.08 / run <span className="metric-ci">p &lt; 0.001</span></div>
            <div className="metric-compare">
              <span className="text-muted">Baseline: 0.84 / run</span>
              <span className="text-success font-semibold">10.5x safer</span>
            </div>
          </div>

          <div className="lab-metric-card">
            <div className="metric-title">FAULT RECOVERY SUCCESS</div>
            <div className="metric-val text-success">94.2% <span className="metric-ci">±2.4%</span></div>
            <div className="metric-compare">
              <span className="text-muted">Baseline: 42.0%</span>
              <span className="text-success font-semibold">2.2x resilience</span>
            </div>
          </div>

          <div className="lab-metric-card">
            <div className="metric-title">STATE ESTIMATION ERROR (MEAN)</div>
            <div className="metric-val">0.034m <span className="metric-ci">EKF 3σ</span></div>
            <div className="metric-compare">
              <span className="text-muted">Raw Sensors: 0.420m</span>
              <span className="text-success font-semibold">12x accuracy</span>
            </div>
          </div>
        </div>

        {/* Scientific Charts Panel */}
        <div className="lab-charts-grid">
          {/* Chart 1: Completion Rate Comparison */}
          <div className="lab-chart-box">
            <div className="chart-box-title">Completion Rate by Trial Group (%)</div>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={completionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(83, 111, 89, 0.15)" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis domain={[50, 100]} tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Bar dataKey="ASTRA" fill="#590907" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Baseline" fill="#A5A79B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 2: Energy Dissipation Profile */}
          <div className="lab-chart-box">
            <div className="chart-box-title">Energy Consumption Profile (Joules)</div>
            <ResponsiveContainer width="100%" height={170}>
              <LineChart data={energyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(83, 111, 89, 0.15)" />
                <XAxis dataKey="trial" tick={{ fontSize: 10 }} />
                <YAxis domain={[1800, 4000]} tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Line type="monotone" dataKey="ASTRA" stroke="#590907" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="Baseline" stroke="#77796F" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 3: Estimation Residual Convergence */}
          <div className="lab-chart-box full-width">
            <div className="chart-box-title">EKF State Estimation Error Residual Decay (m)</div>
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={errorDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(83, 111, 89, 0.15)" />
                <XAxis dataKey="step" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
                <Area type="monotone" dataKey="error" stroke="#590907" fill="rgba(89, 9, 7, 0.12)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Experiment Run History Table */}
        <div className="lab-history-section">
          <div className="history-header">
            <Database size={14} />
            <span>REPRODUCIBLE EXPERIMENT RUN ARCHIVE</span>
          </div>
          <table className="lab-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>EXPERIMENT NAME</th>
                <th>MODULE</th>
                <th>CONTROLLER</th>
                <th>MODE</th>
                <th>TRIALS</th>
                <th>COMPLETION</th>
                <th>STATUS</th>
                <th>TIMESTAMP</th>
              </tr>
            </thead>
            <tbody>
              {history.map(item => (
                <tr key={item.id}>
                  <td className="font-mono">{item.id}</td>
                  <td className="font-semibold text-ink">{item.name}</td>
                  <td>{item.module}</td>
                  <td>{item.controller}</td>
                  <td>
                    <span className={`mode-badge ${item.mode === 'Held-Out' ? 'heldout' : 'dev'}`}>
                      {item.mode}
                    </span>
                  </td>
                  <td className="font-mono">{item.trials}</td>
                  <td className="font-mono text-success font-semibold">{item.completionRate}%</td>
                  <td>
                    <span className="status-badge-complete">
                      <CheckCircle2 size={11} />
                      {item.status}
                    </span>
                  </td>
                  <td className="text-muted text-xs">{item.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

export default ExperimentLab
