import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Target, Navigation2, FlaskConical, Activity,
  BarChart3, ChevronLeft, ChevronRight, Settings, BookOpen,
  Sliders, Zap, Bell, ChevronDown, CircuitBoard, Globe2,
  Radio, User, Play, Pause, Square, RefreshCw
} from 'lucide-react'
import './AppShell.css'

interface NavItem {
  to: string
  icon: React.ReactNode
  label: string
  section?: string
}

const navItems: NavItem[] = [
  { to: '/app/overview', icon: <LayoutDashboard size={18} />, label: 'Overview', section: 'Mission' },
  { to: '/app', icon: <CircuitBoard size={18} />, label: 'Mission Control', section: 'Mission' },
  { to: '/app/touchdown', icon: <Target size={18} />, label: 'Touchdown' },
  { to: '/app/rover', icon: <Navigation2 size={18} />, label: 'Rover' },
  { to: '/app/experiment-lab', icon: <FlaskConical size={18} />, label: 'Experiment Lab', section: 'Research' },
  { to: '/app/scenario-builder', icon: <Sliders size={18} />, label: 'Scenario Builder' },
  { to: '/app/controller-comparison', icon: <BarChart3 size={18} />, label: 'Controller Comparison' },
  { to: '/app/results', icon: <Activity size={18} />, label: 'Results' },
  { to: '/app/telemetry', icon: <Radio size={18} />, label: 'Telemetry', section: 'Data' },
  { to: '/app/documentation', icon: <BookOpen size={18} />, label: 'Documentation', section: 'System' },
  { to: '/app/settings', icon: <Settings size={18} />, label: 'Settings' },
]

const AppShell: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false)
  const [simStatus, setSimStatus] = useState<'idle' | 'running' | 'paused'>('idle')
  const navigate = useNavigate()
  const location = useLocation()

  const currentModule = location.pathname.includes('touchdown') ? 'Touchdown' :
    location.pathname.includes('rover') ? 'Rover' :
    location.pathname.includes('experiment') ? 'Experiment Lab' :
    location.pathname.includes('telemetry') ? 'Telemetry' : 'Overview'

  const toggleSim = () => {
    if (simStatus === 'idle' || simStatus === 'paused') setSimStatus('running')
    else setSimStatus('paused')
  }

  const stopSim = () => setSimStatus('idle')

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          {!collapsed && (
            <button className="sidebar-brand" onClick={() => navigate('/')}>
              <span className="brand-mark">✦</span>
              <span className="brand-name">ASTRA</span>
            </button>
          )}
          {collapsed && (
            <button className="sidebar-brand sidebar-brand--collapsed" onClick={() => navigate('/')}>
              <span className="brand-mark">✦</span>
            </button>
          )}
          <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item, i) => {
            const prevItem = navItems[i - 1]
            const showSection = item.section && item.section !== prevItem?.section
            return (
              <React.Fragment key={item.to}>
                {showSection && !collapsed && (
                  <div className="nav-section-label">{item.section}</div>
                )}
                <NavLink
                  to={item.to}
                  end={item.to === '/app'}
                  className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}
                  title={collapsed ? item.label : undefined}
                >
                  <span className="nav-item-icon">{item.icon}</span>
                  {!collapsed && <span className="nav-item-label">{item.label}</span>}
                  {!collapsed && item.to === '/app/touchdown' && (
                    <span className="nav-item-badge nav-item-badge--available">3</span>
                  )}
                </NavLink>
              </React.Fragment>
            )
          })}
        </nav>

        {/* Sim status widget */}
        {!collapsed && (
          <div className="sidebar-sim-widget">
            <div className="sim-widget-header">
              <Zap size={13} />
              <span>Simulation</span>
              <span className={`sim-status-dot ${simStatus}`} />
            </div>
            <div className="sim-controls">
              <button className="sim-btn sim-btn--play" onClick={toggleSim} title={simStatus === 'running' ? 'Pause' : 'Play'}>
                {simStatus === 'running' ? <Pause size={13} /> : <Play size={13} />}
              </button>
              <button className="sim-btn sim-btn--stop" onClick={stopSim} title="Stop">
                <Square size={12} />
              </button>
              <button className="sim-btn" title="Reset">
                <RefreshCw size={12} />
              </button>
            </div>
            <div className="sim-state-label">
              {simStatus === 'idle' ? 'Ready to simulate' :
               simStatus === 'running' ? 'Simulation running...' : 'Simulation paused'}
            </div>
          </div>
        )}
      </aside>

      {/* ── Main area ── */}
      <div className="main-area">

        {/* Top bar */}
        <header className="top-bar">
          <div className="top-bar-left">
            <div className="module-breadcrumb">
              <Globe2 size={14} className="breadcrumb-icon" />
              <span className="breadcrumb-platform">ASTRA</span>
              <span className="breadcrumb-sep">/</span>
              <span className="breadcrumb-module">{currentModule}</span>
            </div>
          </div>

          <div className="top-bar-center">
            <div className="mission-pill">
              <span className="mission-dot" />
              <span className="mission-name">Exploration Mission Alpha</span>
            </div>
          </div>

          <div className="top-bar-right">
            <div className="env-selector">
              <Globe2 size={13} />
              <span>Mars — Jezero Crater</span>
              <ChevronDown size={12} />
            </div>
            <div className={`sim-status-badge ${simStatus}`}>
              <span className="status-pulse" />
              {simStatus === 'idle' ? 'Standby' : simStatus === 'running' ? 'Simulating' : 'Paused'}
            </div>
            <button className="top-bar-icon-btn" title="Notifications">
              <Bell size={16} />
              <span className="notif-dot" />
            </button>
            <button className="top-bar-icon-btn user-btn" title="User profile">
              <User size={16} />
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppShell

