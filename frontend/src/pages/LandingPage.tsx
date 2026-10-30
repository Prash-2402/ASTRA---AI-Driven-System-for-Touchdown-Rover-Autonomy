import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MarsScrollSection from '../components/MarsScrollSection'
import './LandingPage.css'

/* ── Starfield Canvas ── */
const StarfieldCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const starsRef = useRef<{ x: number; y: number; r: number; opacity: number; twinkle: number }[]>([])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      starsRef.current = Array.from({ length: 180 }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.2 + 0.3,
        opacity: Math.random() * 0.6 + 0.25,
        twinkle: Math.random() * Math.PI * 2,
      }))
    }
    resize()
    window.addEventListener('resize', resize)

    let t = 0
    const draw = () => {
      t += 0.008
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      starsRef.current.forEach(s => {
        const alpha = s.opacity * (0.7 + 0.3 * Math.sin(t + s.twinkle))
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(245, 243, 237, ${alpha})`
        ctx.fill()
      })
      animRef.current = requestAnimationFrame(draw)
    }
    animRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(animRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={canvasRef} className="starfield-canvas" />
}

/* ── Intelligence Flow Diagram ── */
const IntelligenceFlow: React.FC = () => {
  const steps = [
    { label: 'Sense', icon: '◉', desc: 'Multi-modal sensors' },
    { label: 'Estimate', icon: '◈', desc: 'EKF state fusion' },
    { label: 'Predict', icon: '◆', desc: 'Model-based prediction' },
    { label: 'Decide', icon: '◉', desc: 'RL policy inference' },
    { label: 'Act', icon: '◈', desc: 'Motor commands' },
    { label: 'Verify', icon: '◆', desc: 'Residual monitoring' },
    { label: 'Adapt', icon: '◉', desc: 'Online replanning' },
  ]

  return (
    <div className="intelligence-flow">
      {steps.map((step, i) => (
        <React.Fragment key={step.label}>
          <div className="flow-node" style={{ animationDelay: `${i * 0.12}s` }}>
            <div className="flow-icon">{step.icon}</div>
            <div className="flow-label">{step.label}</div>
            <div className="flow-desc">{step.desc}</div>
          </div>
          {i < steps.length - 1 && (
            <div className="flow-connector" style={{ animationDelay: `${i * 0.12 + 0.06}s` }}>
              <div className="flow-arrow-track">
                <div className="flow-arrow-pulse" />
              </div>
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

/* ── Main Landing Page ── */
const LandingPage: React.FC = () => {
  const navigate = useNavigate()
  const [scrollY, setScrollY] = useState(0)
  const [navVisible, setNavVisible] = useState(true)
  const lastScrollY = useRef(0)

  useEffect(() => {
    const handleScroll = () => {
      const current = window.scrollY
      setNavVisible(current < 80 || current < lastScrollY.current)
      lastScrollY.current = current
      setScrollY(current)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const navLinks = ['Overview', 'Mission', 'Touchdown', 'Rover', 'Technology', 'Research', 'Launch']

  const researchItems = [
    { icon: '⬡', title: 'Physics-Based Simulation', desc: 'High-fidelity 6-DOF dynamics with aerodynamic drag, gravity models, and sensor noise characterization.' },
    { icon: '⬢', title: 'Reinforcement Learning', desc: 'Proximal Policy Optimization agents trained on stochastic planetary environments with curriculum learning.' },
    { icon: '◈', title: 'State Estimation', desc: 'Extended Kalman Filter fusion across IMU, altimeter, optical flow, and terrain-relative navigation.' },
    { icon: '◉', title: 'Fault Injection', desc: 'Controlled injection across sensor dropouts, actuator degradation, and power spikes for resilience benchmarks.' },
    { icon: '⬡', title: 'Adaptive Planning', desc: 'Real-time online route replanning with terrain cost maps, energy constraints, and slip mitigation.' },
    { icon: '⬢', title: 'Reproducible Experiments', desc: 'Seeded random environments, locked held-out configurations, and structured empirical validation.' },
  ]

  return (
    <div className="landing-root">
      {/* ── Fixed background starfield & nebula ── */}
      <div className="landing-bg">
        <div className="bg-void" />
        <StarfieldCanvas />
        <div className="bg-nebula" />
        <div className="bg-atmosphere-veil" style={{ opacity: Math.min(scrollY / 600, 0.75) }} />
      </div>

      {/* ── Top Navigation ── */}
      <nav className={`landing-nav ${navVisible ? 'nav-visible' : 'nav-hidden'}`}>
        <div className="nav-logo">
          <span className="nav-logo-mark">✦</span>
          <span className="nav-logo-text">ASTRA</span>
        </div>
        <div className="nav-links">
          {navLinks.map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(' ', '-')}`} className="nav-link">{l}</a>
          ))}
        </div>
        <button className="nav-cta" onClick={() => navigate('/app')}>
          Enter ASTRA
        </button>
      </nav>

      {/* ════════════════════════════════════════════
          SECTION 1 — Pinned Cinematic Mars Scroll Hero (Dark Space)
      ════════════════════════════════════════════ */}
      <MarsScrollSection onEnterApp={() => navigate('/app')} />

      {/* ════════════════════════════════════════════
          SECTION 2 — Mission Introduction (Light Editorial Contrast)
      ════════════════════════════════════════════ */}
      <section className="mission-intro-section" id="mission">
        <div className="container">
          <div className="mission-intro-header">
            <span className="section-label-burgundy">RESEARCH SPECIFICATION</span>
            <h2 className="editorial-headline">Engineering Planetary Autonomy</h2>
            <div className="editorial-rule" />
            <p className="editorial-lead">
              Interplanetary surface operations operate under severe light-time communication delays, unmapped geologic hazards,
              and unpredictable atmospheric dynamics. ASTRA synthesizes 6-DOF physics-based simulation with verifiable cognitive autonomy.
            </p>
          </div>

          <div className="mission-pillars-grid">
            <div className="mission-pillar-card">
              <span className="pillar-num font-mono">01</span>
              <h3 className="pillar-title">Physical Realism</h3>
              <p className="pillar-text">
                Every actuator, thruster plume, terramechanics wheel interaction, and atmospheric density gradient is computed using verified physics models.
              </p>
            </div>
            <div className="mission-pillar-card">
              <span className="pillar-num font-mono">02</span>
              <h3 className="pillar-title">Closed-Loop Autonomy</h3>
              <p className="pillar-text">
                Continuous state estimation through Extended Kalman Filters enables real-time hazard detection, safe diversion, and adaptive trajectory replanning.
              </p>
            </div>
            <div className="mission-pillar-card">
              <span className="pillar-num font-mono">03</span>
              <h3 className="pillar-title">Empirical Evidence</h3>
              <p className="pillar-text">
                Rigorous Monte Carlo batches with randomized wind shears, sensor dropouts, and locked held-out evaluation datasets produce reproducible scientific proof.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 3 — Touchdown Module (Dark Cinematic EDL)
      ════════════════════════════════════════════ */}
      <section className="touchdown-showcase-section" id="touchdown">
        <div className="container">
          <div className="showcase-header">
            <span className="section-label-cream">EDL DYNAMICS &amp; LANDING SITE DIVERSION</span>
            <h2 className="showcase-headline">ASTRA Touchdown</h2>
            <p className="showcase-subhead">
              Physics-based Entry, Descent and Landing with multi-sensor fusion, optimal thruster control,
              and autonomous landing-site diversion.
            </p>
          </div>

          <div className="touchdown-split-layout">
            {/* Visualizer Frame */}
            <div className="showcase-visual-frame">
              <svg viewBox="0 0 320 230" className="lander-svg">
                <defs>
                  <radialGradient id="td-burn" cx="50%" cy="0%" r="80%">
                    <stop offset="0%" stopColor="#E8D2B5" stopOpacity="0.95" />
                    <stop offset="40%" stopColor="#590907" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#300605" stopOpacity="0" />
                  </radialGradient>
                  <radialGradient id="td-ground-glow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="rgba(232, 210, 181, 0.25)" />
                    <stop offset="100%" stopColor="transparent" />
                  </radialGradient>
                </defs>

                {/* Ground glow */}
                <ellipse cx="160" cy="202" rx="90" ry="12" fill="url(#td-ground-glow)" />

                {/* Descent trajectory */}
                <path d="M 230 15 Q 210 80 160 160" stroke="#E8D2B5" strokeWidth="1.5" strokeDasharray="5,4" fill="none" opacity="0.75" />

                {/* Thruster flame */}
                <ellipse cx="160" cy="178" rx="14" ry="22" fill="url(#td-burn)">
                  <animate attributeName="ry" values="22;18;24;20;22" dur="0.6s" repeatCount="indefinite" />
                </ellipse>

                {/* Landing legs */}
                <line x1="160" y1="145" x2="115" y2="192" stroke="#A5A79B" strokeWidth="2.5" strokeLinecap="round" />
                <line x1="160" y1="145" x2="205" y2="192" stroke="#A5A79B" strokeWidth="2.5" strokeLinecap="round" />
                <line x1="115" y1="192" x2="102" y2="192" stroke="#A5A79B" strokeWidth="2" strokeLinecap="round" />
                <line x1="205" y1="192" x2="218" y2="192" stroke="#A5A79B" strokeWidth="2" strokeLinecap="round" />

                {/* Lander chassis */}
                <rect x="138" y="102" width="44" height="46" rx="5" fill="#41443D" stroke="#A5A79B" strokeWidth="1.5" />
                <rect x="144" y="108" width="32" height="34" rx="4" fill="#171814" />

                {/* Solar panels */}
                <rect x="76" y="112" width="54" height="14" rx="2" fill="#5E7B88" opacity="0.9" />
                <rect x="190" y="112" width="54" height="14" rx="2" fill="#5E7B88" opacity="0.9" />
                <line x1="130" y1="119" x2="76" y2="119" stroke="#676A60" strokeWidth="1.5" />
                <line x1="190" y1="119" x2="244" y2="119" stroke="#676A60" strokeWidth="1.5" />

                {/* Sensor dome */}
                <ellipse cx="160" cy="102" rx="16" ry="8" fill="#A5A79B" />

                {/* Landing target reticle — Burgundy accent */}
                <circle cx="160" cy="202" r="22" stroke="#590907" strokeWidth="2" fill="none" opacity="0.85" />
                <circle cx="160" cy="202" r="10" stroke="#590907" strokeWidth="1.5" fill="none" opacity="0.9" />
                <circle cx="160" cy="202" r="3" fill="#590907" />

                {/* Technical annotations */}
                <text x="32" y="96" fill="#A5A79B" fontSize="9" fontFamily="Space Mono">ALT: 1,842m</text>
                <text x="210" y="96" fill="#A5A79B" fontSize="9" fontFamily="Space Mono">v: 48.3 m/s</text>
                <text x="120" y="215" fill="#E8D2B5" fontSize="9" fontFamily="Space Mono">TARGET: LZ-ALPHA</text>
              </svg>
            </div>

            {/* Spec & Action Card */}
            <div className="showcase-info-card dark-card">
              <h3 className="showcase-title text-cream">Precision Landing Autonomy</h3>
              <p className="showcase-desc text-muted-dark">
                Combines 6-DOF rocket landing equations of motion with terrain-relative optical navigation.
                If boulders or steep crater walls are detected in the primary target ellipse, the lander diverts autonomously to an alternate safe landing site.
              </p>

              <div className="capability-tag-list">
                <span className="showcase-tag">6-DOF EDL Dynamics</span>
                <span className="showcase-tag">EKF Navigation</span>
                <span className="showcase-tag">PID / MPC / PPO</span>
                <span className="showcase-tag">Crater Diversion</span>
              </div>

              <div className="showcase-actions">
                <button className="btn-primary" onClick={() => navigate('/app/touchdown')}>
                  Launch Touchdown Simulation →
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 4 — Rover Module (Warm Editorial Light Section)
      ════════════════════════════════════════════ */}
      <section className="rover-showcase-section" id="rover">
        <div className="container">
          <div className="showcase-header light-header">
            <span className="section-label-burgundy">FAULT-AWARE ROBOTICS</span>
            <h2 className="editorial-headline">ASTRA Rover</h2>
            <p className="editorial-lead">
              Planetary surface mobility with terramechanics wheel-ground physical interaction,
              slip risk heuristics, and active fault injection recovery.
            </p>
          </div>

          <div className="rover-split-layout">
            {/* Spec & Action Card */}
            <div className="showcase-info-card light-card">
              <h3 className="showcase-title text-ink">Adaptive Path Replanning</h3>
              <p className="showcase-desc text-secondary">
                Unlike rigid finite-state machine baselines, ASTRA Rover evaluates real-time wheel slip,
                slope tilt, and power budget constraints. When actuator or sensor anomalies are introduced,
                the planner dynamically routes around high-risk terrain.
              </p>

              <div className="capability-tag-list">
                <span className="showcase-tag light-tag">6-Wheel Rocker-Bogie</span>
                <span className="showcase-tag light-tag">Terramechanics Slip</span>
                <span className="showcase-tag light-tag">Fault Recovery</span>
                <span className="showcase-tag light-tag">A* Slip Heuristics</span>
              </div>

              <div className="showcase-actions">
                <button className="btn-primary" onClick={() => navigate('/app/rover')}>
                  Launch Rover Autonomy →
                </button>
              </div>
            </div>

            {/* Visualizer Frame */}
            <div className="showcase-visual-frame light-visual-frame">
              <svg viewBox="0 0 320 210" className="rover-svg">
                {/* Ground */}
                <ellipse cx="160" cy="180" rx="120" ry="14" fill="#D7D8D0" />

                {/* Path lines */}
                <path d="M 40 172 Q 90 166 140 170 Q 190 174 250 168" stroke="#590907" strokeWidth="2" strokeDasharray="5,4" fill="none" />

                {/* Wheels */}
                {[90, 160, 230].map(x => (
                  <React.Fragment key={x}>
                    <circle cx={x} cy={168} r={12} fill="#272922" stroke="#676A60" strokeWidth="2" />
                    <circle cx={x} cy={168} r={6} fill="#A5A79B" />
                  </React.Fragment>
                ))}

                {/* Chassis */}
                <rect x="85" y="132" width="150" height="26" rx="4" fill="#57594F" />
                <rect x="90" y="136" width="140" height="18" rx="3" fill="#272922" />

                {/* Solar deck */}
                <rect x="105" y="108" width="80" height="24" rx="3" fill="#5E7B88" opacity="0.85" />

                {/* Mast camera */}
                <rect x="175" y="90" width="4" height="24" rx="2" fill="#A5A79B" />
                <circle cx="177" cy="86" r="5" fill="#590907" />

                <text x="35" y="160" fill="#77796F" fontSize="9" fontFamily="Space Mono">START</text>
                <text x="255" y="156" fill="#590907" fontSize="9" fontFamily="Space Mono" fontWeight="bold">WAYPOINT</text>
              </svg>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 5 — Cognitive Architecture Flow (Dark Cinematic)
      ════════════════════════════════════════════ */}
      <section className="intelligence-section" id="technology">
        <div className="container">
          <div className="section-eyebrow-cream">COGNITIVE ARCHITECTURE</div>
          <h2 className="section-headline-dark">From sensing to autonomous action.</h2>
          <p className="section-subhead-dark">
            Every planetary decision follows a closed-loop autonomy cycle — from raw sensor telemetry
            to verified physical actuation, with continuous online adaptation.
          </p>
          <IntelligenceFlow />
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 6 — Research Foundation (Warm Light Surface)
      ════════════════════════════════════════════ */}
      <section className="research-section" id="research">
        <div className="container">
          <div className="research-inner">
            <div className="research-header">
              <span className="section-label-burgundy">RESEARCH WORKSTATION</span>
              <h2 className="editorial-headline">Engineering Autonomy Through Measurable Evidence</h2>
              <div className="editorial-rule" />
              <p className="editorial-lead">
                Every simulation run is reproducible. Every controller benchmark is validated against held-out terrain profiles.
              </p>
            </div>
            <div className="research-grid">
              {researchItems.map((item, i) => (
                <div key={i} className="research-card">
                  <div className="research-icon">{item.icon}</div>
                  <h3 className="research-card-title">{item.title}</h3>
                  <p className="research-card-desc">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          SECTION 7 — Final CTA (Deep Space Darkness)
      ════════════════════════════════════════════ */}
      <section className="cta-section" id="launch">
        <div className="container">
          <div className="cta-inner">
            <span className="section-label-cream">READY FOR DEPLOYMENT</span>
            <h2 className="cta-headline">
              Explore the next frontier of<br />autonomous systems.
            </h2>
            <p className="cta-desc">
              Launch ASTRA Mission Control and evaluate autonomous planetary landers and rovers
              under rigorous physics-based simulation.
            </p>
            <button className="btn-cta-launch" onClick={() => navigate('/app')}>
              <span>Launch ASTRA Mission Control</span>
              <span className="btn-arrow">→</span>
            </button>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════
          Footer
      ════════════════════════════════════════════ */}
      <footer className="landing-footer">
        <div className="container">
          <div className="footer-top">
            <div className="footer-brand">
              <div className="footer-logo">
                <span className="nav-logo-mark">✦</span>
                <span>ASTRA</span>
              </div>
              <p className="footer-tagline">
                AI-Driven System for Touchdown &amp; Rover Autonomy.
              </p>
            </div>
            <div className="footer-links">
              {[
                { heading: 'Platform', links: ['Overview', 'Mission', 'Technology'] },
                { heading: 'Modules', links: ['Touchdown', 'Rover', 'Experiment Lab'] },
                { heading: 'Resources', links: ['Documentation', 'Telemetry', 'Settings'] },
              ].map(group => (
                <div key={group.heading} className="footer-link-group">
                  <h4>{group.heading}</h4>
                  {group.links.map(l => (
                    <a key={l} href={l === 'Touchdown' ? '/app/touchdown' : l === 'Rover' ? '/app/rover' : l === 'Experiment Lab' ? '/app/experiment-lab' : '#'}>
                      {l}
                    </a>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="footer-bottom">
            <span>© {new Date().getFullYear()} ASTRA Planetary Autonomy Platform</span>
            <span>Aerospace Engineering &amp; Autonomous Systems</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
