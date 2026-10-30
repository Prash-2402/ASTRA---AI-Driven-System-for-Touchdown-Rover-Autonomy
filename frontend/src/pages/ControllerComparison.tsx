import React, { useState } from 'react'
import { BarChart3, CheckCircle2, ShieldAlert, Zap, Cpu, ArrowUpRight } from 'lucide-react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend
} from 'recharts'
import './ControllerComparison.css'

export const ControllerComparison: React.FC = () => {
  const radarData = [
    { metric: 'Fuel / Energy Efficiency', PPO: 94, MPC: 88, PID: 62 },
    { metric: 'Obstacle Diversion', PPO: 96, MPC: 91, PID: 45 },
    { metric: 'Sensor Noise Rejection', PPO: 92, MPC: 85, PID: 58 },
    { metric: 'Real-time Feasibility', PPO: 88, MPC: 72, PID: 99 },
    { metric: 'Fault Recovery Rate', PPO: 95, MPC: 82, PID: 40 },
    { metric: 'Terminal Velocity Precision', PPO: 98, MPC: 94, PID: 74 },
  ]

  const benchmarkBars = [
    { scenario: 'Nominal Descent', PPO: 99.2, MPC: 97.4, PID: 86.0 },
    { scenario: '25 m/s Wind Shear', PPO: 96.5, MPC: 91.0, PID: 62.4 },
    { scenario: 'Crater Hazard Diversion', PPO: 94.8, MPC: 88.2, PID: 41.5 },
    { scenario: 'Sensor Noise 3σ Dropout', PPO: 91.4, MPC: 82.6, PID: 48.0 },
  ]

  return (
    <div className="comp-root">
      <div className="comp-header">
        <div>
          <div className="comp-eyebrow">HEAD-TO-HEAD CONTROLLER BENCHMARK</div>
          <h1 className="comp-title">Autonomous Controller Comparison</h1>
        </div>
        <span className="badge-pill">Evaluated over 500 Monte Carlo Runs</span>
      </div>

      {/* Controller Spec Cards */}
      <div className="comp-cards">
        <div className="ctrl-card ppo">
          <div className="ctrl-badge ppo">REINFORCEMENT LEARNING</div>
          <h3 className="ctrl-name">PPO Deep Policy</h3>
          <p className="ctrl-desc">Actor-Critic neural policy trained with domain randomization &amp; curriculum learning.</p>
          <div className="ctrl-metrics">
            <div className="metric-row"><span>Landing Success:</span> <strong>97.8%</strong></div>
            <div className="metric-row"><span>Energy Index:</span> <strong>0.82x</strong></div>
            <div className="metric-row"><span>Inference Time:</span> <strong>3.2 ms</strong></div>
          </div>
        </div>

        <div className="ctrl-card mpc">
          <div className="ctrl-badge mpc">OPTIMAL CONTROL</div>
          <h3 className="ctrl-name">Nonlinear MPC</h3>
          <p className="ctrl-desc">Receding horizon quadratic program with dynamic thrust vector constraints.</p>
          <div className="ctrl-metrics">
            <div className="metric-row"><span>Landing Success:</span> <strong>92.1%</strong></div>
            <div className="metric-row"><span>Energy Index:</span> <strong>0.91x</strong></div>
            <div className="metric-row"><span>Solve Time:</span> <strong>42.8 ms</strong></div>
          </div>
        </div>

        <div className="ctrl-card pid">
          <div className="ctrl-badge pid">CLASSICAL BASELINE</div>
          <h3 className="ctrl-name">Cascaded PID</h3>
          <p className="ctrl-desc">Traditional proportional-integral-derivative gain-scheduled flight baseline.</p>
          <div className="ctrl-metrics">
            <div className="metric-row"><span>Landing Success:</span> <strong>64.5%</strong></div>
            <div className="metric-row"><span>Energy Index:</span> <strong>1.24x</strong></div>
            <div className="metric-row"><span>Loop Time:</span> <strong>0.4 ms</strong></div>
          </div>
        </div>
      </div>

      {/* Visual Comparative Charts */}
      <div className="comp-charts-grid">
        {/* Radar Evaluation */}
        <div className="comp-chart-card">
          <div className="comp-chart-title">Autonomy Multi-Domain Capability Radar</div>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(165, 167, 155, 0.3)" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: '#272922' }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="rgba(165, 167, 155, 0.3)" />
              <Radar name="PPO" dataKey="PPO" stroke="#590907" fill="rgba(89, 9, 7, 0.25)" />
              <Radar name="MPC" dataKey="MPC" stroke="#BF802B" fill="rgba(191, 128, 43, 0.2)" />
              <Radar name="PID" dataKey="PID" stroke="#77796F" fill="rgba(119, 121, 111, 0.15)" />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar Performance across Challenging Scenarios */}
        <div className="comp-chart-card">
          <div className="comp-chart-title">Mission Success Rate Across Hazardous Scenarios (%)</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={benchmarkBars}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(165, 167, 155, 0.2)" />
              <XAxis dataKey="scenario" tick={{ fontSize: 10 }} />
              <YAxis domain={[30, 100]} tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }} />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
              <Bar dataKey="PPO" fill="#590907" radius={[4, 4, 0, 0]} />
              <Bar dataKey="MPC" fill="#BF802B" radius={[4, 4, 0, 0]} />
              <Bar dataKey="PID" fill="#77796F" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default ControllerComparison

