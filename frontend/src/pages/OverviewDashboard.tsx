import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Target, Navigation2, Activity, Cpu, CheckCircle2,
  Clock, FlaskConical, Zap, TrendingUp, ArrowRight,
  AlertTriangle, Radio, ChevronRight
} from 'lucide-react'
import './OverviewDashboard.css'

const EmptyExperiments: React.FC = () => (
  <div className="empty-state">
    <div className="empty-icon">
      <FlaskConical size={32} />
    </div>
    <h3>No experiments yet</h3>
    <p>Run your first simulation from the Touchdown or Rover modules to see results here.</p>
  </div>
)

const SystemHealthBar: React.FC<{ label: string; value: number; color?: string }> = ({
  label, value, color = 'var(--primary)'
}) => (
  <div className="health-bar-item">
    <div className="health-bar-header">
      <span>{label}</span>
      <span style={{ color }}>{value}%</span>
    </div>
    <div className="health-bar-track">
      <div
        className="health-bar-fill"
        style={{ width: `${value}%`, background: color }}
      />
    </div>
  </div>
)

const OverviewDashboard: React.FC = () => {
  const navigate = useNavigate()
  const [activeModule, setActiveModule] = useState<'touchdown' | 'rover' | null>(null)

  return (
    <div className="overview-root">

      {/* ── Welcome Header ── */}
      <div className="overview-welcome">
        <div className="welcome-text">
          <p className="welcome-eyebrow">Good morning · Mission Control</p>
          <h1 className="welcome-heading">
            Mission Intelligence,<br />
            <span className="heading-accent">Reimagined.</span>
          </h1>
          <p className="welcome-subtext">
            Monitor autonomous systems, explore planetary environments and evaluate
            mission performance from one unified workspace.
          </p>
        </div>
        <div className="welcome-live-indicator">
          <span className="live-dot" />
          <span>All systems nominal</span>
        </div>
      </div>

      {/* ── Module Launch Panels ── */}
      <div className="module-panels">

        {/* Touchdown */}
        <div
          className={`module-panel module-panel--touchdown ${activeModule === 'touchdown' ? 'module-panel--focused' : ''}`}
          onMouseEnter={() => setActiveModule('touchdown')}
          onMouseLeave={() => setActiveModule(null)}
        >
          <div className="module-panel-bg module-panel-bg--touchdown" />

          <div className="module-panel-header">
            <div className="module-badge module-badge--touchdown">
              <Target size={14} />
              TOUCHDOWN
            </div>
            <div className="module-status">
              <span className="module-status-dot module-status-dot--ready" />
              Ready
            </div>
          </div>

          {/* Lander illustration */}
          <div className="module-visual">
            <svg viewBox="0 0 240 180" className="module-svg">
              <defs>
                <radialGradient id="td-planet" cx="50%" cy="100%" r="60%">
                  <stop offset="0%" stopColor="#A0633C" />
                  <stop offset="100%" stopColor="#6B3E24" />
                </radialGradient>
                <radialGradient id="td-atm" cx="50%" cy="80%" r="50%">
                  <stop offset="0%" stopColor="rgba(160,99,60,0.25)" />
                  <stop offset="100%" stopColor="rgba(160,99,60,0)" />
                </radialGradient>
              </defs>

              {/* Planet surface */}
              <ellipse cx="120" cy="168" rx="130" ry="28" fill="url(#td-planet)" />
              <ellipse cx="120" cy="155" rx="160" ry="30" fill="url(#td-atm)" />

              {/* Terrain details */}
              <ellipse cx="60" cy="162" rx="22" ry="6" fill="rgba(90,50,25,0.5)" />
              <ellipse cx="185" cy="165" rx="16" ry="5" fill="rgba(90,50,25,0.4)" />

              {/* Thruster flame */}
              <ellipse cx="120" cy="120" rx="10" ry="16" fill="rgba(214,155,77,0.8)">
                <animate attributeName="ry" values="16;12;18;14;16" dur="0.5s" repeatCount="indefinite" />
              </ellipse>
              <ellipse cx="120" cy="118" rx="5" ry="10" fill="rgba(255,220,150,0.9)">
                <animate attributeName="ry" values="10;7;12;9;10" dur="0.4s" repeatCount="indefinite" />
              </ellipse>

              {/* Lander body */}
              <rect x="104" y="76" width="32" height="32" rx="5" fill="#536F59" />
              <rect x="108" y="80" width="24" height="24" rx="4" fill="#648C65" />

              {/* Sensor dome */}
              <ellipse cx="120" cy="76" rx="12" ry="7" fill="#779477" />

              {/* Legs */}
              <line x1="120" y1="108" x2="88" y2="143" stroke="#AFC3A7" strokeWidth="2" strokeLinecap="round" />
              <line x1="120" y1="108" x2="152" y2="143" stroke="#AFC3A7" strokeWidth="2" strokeLinecap="round" />
              <line x1="88" y1="143" x2="76" y2="143" stroke="#AFC3A7" strokeWidth="2" strokeLinecap="round" />
              <line x1="152" y1="143" x2="164" y2="143" stroke="#AFC3A7" strokeWidth="2" strokeLinecap="round" />

              {/* Solar panels */}
              <rect x="52" y="86" width="46" height="10" rx="2" fill="#7798A3" opacity="0.85" />
              <rect x="142" y="86" width="46" height="10" rx="2" fill="#7798A3" opacity="0.85" />
              <line x1="98" y1="91" x2="104" y2="91" stroke="#526257" strokeWidth="1.5" />
              <line x1="136" y1="91" x2="142" y2="91" stroke="#526257" strokeWidth="1.5" />

              {/* Target reticle */}
              <circle cx="120" cy="155" r="20" stroke="rgba(100,140,101,0.5)" strokeWidth="1.5" fill="none" />
              <circle cx="120" cy="155" r="8" stroke="rgba(100,140,101,0.7)" strokeWidth="1.5" fill="none" />
              <line x1="120" y1="145" x2="120" y2="149" stroke="rgba(100,140,101,0.6)" strokeWidth="1" />
              <line x1="120" y1="161" x2="120" y2="165" stroke="rgba(100,140,101,0.6)" strokeWidth="1" />

              {/* Trajectory */}
              <path d="M 175 25 Q 160 70 120 128" stroke="rgba(214,155,77,0.6)" strokeWidth="1.5" strokeDasharray="5,3" fill="none">
                <animate attributeName="strokeDashoffset" values="0;-16" dur="1.2s" repeatCount="indefinite" />
              </path>
            </svg>
          </div>

          <div className="module-info">
            <h2 className="module-title">ASTRA Touchdown</h2>
            <p className="module-desc">
              Physics-based Entry, Descent &amp; Landing with multi-controller autonomy
              and terrain intelligence.
            </p>
            <div className="module-specs">
              <div className="spec-item">
                <span className="spec-label">Controllers</span>
                <div className="spec-tags">
                  <span className="spec-tag">PID</span>
                  <span className="spec-tag">MPC</span>
                  <span className="spec-tag">PPO</span>
                </div>
              </div>
              <div className="spec-item">
                <span className="spec-label">Status</span>
                <span className="spec-value spec-value--ready">3 scenarios available</span>
              </div>
            </div>
          </div>

          <button className="module-launch-btn module-launch-btn--touchdown" onClick={() => navigate('/app/touchdown')}>
            <span>Launch Touchdown</span>
            <ArrowRight size={16} />
          </button>
        </div>

        {/* Rover */}
        <div
          className={`module-panel module-panel--rover ${activeModule === 'rover' ? 'module-panel--focused' : ''}`}
          onMouseEnter={() => setActiveModule('rover')}
          onMouseLeave={() => setActiveModule(null)}
        >
          <div className="module-panel-bg module-panel-bg--rover" />

          <div className="module-panel-header">
            <div className="module-badge module-badge--rover">
              <Navigation2 size={14} />
              ROVER
            </div>
            <div className="module-status">
              <span className="module-status-dot module-status-dot--ready" />
              Ready
            </div>
          </div>

          {/* Rover illustration */}
          <div className="module-visual">
            <svg viewBox="0 0 240 160" className="module-svg">
              <defs>
                <radialGradient id="rv-surface" cx="50%" cy="100%" r="60%">
                  <stop offset="0%" stopColor="#8C7A6A" />
                  <stop offset="100%" stopColor="#6A5A4A" />
                </radialGradient>
              </defs>

              {/* Ground */}
              <ellipse cx="120" cy="142" rx="120" ry="18" fill="url(#rv-surface)" />

              {/* Path lines */}
              <path d="M 20 138 Q 60 135 100 137 Q 140 139 180 134 Q 205 131 220 132" stroke="rgba(100,140,101,0.5)" strokeWidth="1.5" strokeDasharray="4,3" fill="none" />

              {/* Waypoints */}
              {[{x:40,y:136},{x:100,y:136},{x:165,y:132},{x:218,y:131}].map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={i === 3 ? 4 : 3} fill={i === 3 ? '#648C65' : 'rgba(214,155,77,0.8)'} />
              ))}

              {/* Rover wheels */}
              {[72, 120, 168].map((x, i) => (
                <React.Fragment key={i}>
                  {[116, 132].map(y => (
                    <React.Fragment key={y}>
                      <circle cx={x} cy={y} r={10} fill="#536F59" stroke="#648C65" strokeWidth="1.5" />
                      <circle cx={x} cy={y} r={6} fill="#779477" />
                      <circle cx={x} cy={y} r={2} fill="#26372D" />
                    </React.Fragment>
                  ))}
                  <line x1={x} y1={116} x2={x} y2={132} stroke="#AFC3A7" strokeWidth="2.5" />
                </React.Fragment>
              ))}

              {/* Chassis */}
              <rect x="70" y="100" width="100" height="20" rx="4" fill="#536F59" />
              <rect x="74" y="104" width="92" height="12" rx="3" fill="#648C65" />

              {/* Suspension */}
              <line x1="72" y1="110" x2="72" y2="120" stroke="#AFC3A7" strokeWidth="2" />
              <line x1="120" y1="110" x2="120" y2="120" stroke="#AFC3A7" strokeWidth="2" />
              <line x1="168" y1="110" x2="168" y2="120" stroke="#AFC3A7" strokeWidth="2" />
              <line x1="72" y1="110" x2="120" y2="110" stroke="#779477" strokeWidth="1" />
              <line x1="120" y1="110" x2="168" y2="110" stroke="#779477" strokeWidth="1" />

              {/* Mast + camera */}
              <rect x="130" y="78" width="3" height="24" rx="1.5" fill="#779477" />
              <rect x="127" y="70" width="9" height="8" rx="2" fill="#536F59" />
              <circle cx="131.5" cy="74" r="2.5" fill="#7798A3" />

              {/* Solar panel */}
              <rect x="80" y="82" width="54" height="18" rx="3" fill="#7798A3" opacity="0.8" />
              {[90,100,110,120].map(x => (
                <line key={x} x1={x} y1={82} x2={x} y2={100} stroke="#526257" strokeWidth="0.8" opacity="0.4" />
              ))}

              {/* EKF ellipse around rover */}
              <ellipse cx="120" cy="116" rx="48" ry="20" stroke="rgba(119,152,163,0.3)" strokeWidth="1" fill="rgba(119,152,163,0.05)" strokeDasharray="3,3" />
            </svg>
          </div>

          <div className="module-info">
            <h2 className="module-title">ASTRA Rover</h2>
            <p className="module-desc">
              Fault-aware planetary rover autonomy with adaptive path planning,
              energy management and fault injection.
            </p>
            <div className="module-specs">
              <div className="spec-item">
                <span className="spec-label">Fault Types</span>
                <span className="spec-value">4 injectable fault scenarios</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">EKF</span>
                <span className="spec-value spec-value--ready">State estimation active</span>
              </div>
            </div>
          </div>

          <button className="module-launch-btn module-launch-btn--rover" onClick={() => navigate('/app/rover')}>
            <span>Launch Rover</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {/* ── System Intelligence ── */}
      <div className="intelligence-grid">

        {/* Status cards */}
        <div className="status-cards">
          {[
            { icon: <Activity size={18} />, label: 'Active Simulations', value: '0', sub: 'No simulations running', color: 'var(--muted)' },
            { icon: <CheckCircle2 size={18} />, label: 'Completed Experiments', value: '0', sub: 'Run your first experiment', color: 'var(--success)' },
            { icon: <Cpu size={18} />, label: 'Available Controllers', value: '3', sub: 'PID · MPC · PPO ready', color: 'var(--primary)' },
            { icon: <Clock size={18} />, label: 'Mission Time', value: '—', sub: 'No active mission', color: 'var(--info)' },
          ].map(card => (
            <div key={card.label} className="status-card">
              <div className="status-card-icon" style={{ color: card.color }}>{card.icon}</div>
              <div className="status-card-content">
                <div className="status-card-value">{card.value}</div>
                <div className="status-card-label">{card.label}</div>
                <div className="status-card-sub">{card.sub}</div>
              </div>
            </div>
          ))}
        </div>

        {/* System health */}
        <div className="panel system-health-panel">
          <div className="panel-header">
            <div className="panel-title">
              <Zap size={15} />
              System Health
            </div>
            <span className="panel-badge panel-badge--nominal">All Nominal</span>
          </div>
          <div className="health-bars">
            <SystemHealthBar label="Physics Engine" value={100} color="var(--success)" />
            <SystemHealthBar label="EKF Estimator" value={100} color="var(--success)" />
            <SystemHealthBar label="Controller Bank" value={100} color="var(--success)" />
            <SystemHealthBar label="Telemetry Stream" value={100} color="var(--success)" />
            <SystemHealthBar label="Fault Injector" value={100} color="var(--primary)" />
          </div>
        </div>

        {/* Quick actions */}
        <div className="panel quick-actions-panel">
          <div className="panel-header">
            <div className="panel-title">
              <TrendingUp size={15} />
              Quick Actions
            </div>
          </div>
          <div className="quick-actions">
            {[
              { icon: <Target size={15} />, label: 'New Touchdown Simulation', desc: 'Configure EDL scenario', to: '/app/touchdown', color: 'var(--primary-dark)' },
              { icon: <Navigation2 size={15} />, label: 'New Rover Mission', desc: 'Set terrain and waypoints', to: '/app/rover', color: 'var(--info)' },
              { icon: <FlaskConical size={15} />, label: 'Open Experiment Lab', desc: 'Batch experiment runs', to: '/app/experiment-lab', color: 'var(--warning)' },
              { icon: <Radio size={15} />, label: 'View Telemetry', desc: 'Live data streams', to: '/app/telemetry', color: 'var(--success)' },
            ].map(action => (
              <button key={action.label} className="quick-action-item" onClick={() => navigate(action.to)}>
                <div className="quick-action-icon" style={{ color: action.color }}>{action.icon}</div>
                <div className="quick-action-text">
                  <div className="quick-action-label">{action.label}</div>
                  <div className="quick-action-desc">{action.desc}</div>
                </div>
                <ChevronRight size={14} className="quick-action-arrow" />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Recent Experiments ── */}
      <div className="panel recent-experiments-panel">
        <div className="panel-header">
          <div className="panel-title">
            <FlaskConical size={15} />
            Recent Experiments
          </div>
          <button className="panel-action-btn" onClick={() => navigate('/app/experiment-lab')}>
            View all
          </button>
        </div>
        <EmptyExperiments />
      </div>

      {/* ── Alert banner ── */}
      <div className="system-alert">
        <AlertTriangle size={14} />
        <span>
          <strong>Ready for simulation.</strong> Configure a scenario in Touchdown or Rover to begin your first experiment.
        </span>
      </div>

    </div>
  )
}

export default OverviewDashboard

