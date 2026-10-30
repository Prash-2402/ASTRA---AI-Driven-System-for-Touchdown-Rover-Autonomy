import React from 'react'
import { BookOpen, Layers, Cpu, Terminal, Compass, ShieldCheck } from 'lucide-react'

export const DocumentationPage: React.FC = () => {
  return (
    <div style={{ padding: '28px 36px', maxWidth: '1000px', margin: '0 auto', color: 'var(--ink)' }}>
      <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '24px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--muted)' }}>
          ASTRA TECHNICAL SPECIFICATION &amp; API MANUAL
        </span>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '32px', fontWeight: 800, marginTop: '4px' }}>
          Platform Architecture &amp; Autonomy Engine
        </h1>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', lineHeight: 1.7 }}>
        <div style={{ background: 'var(--surface)', padding: '20px 24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary-dark)', marginBottom: '8px' }}>
            <Layers size={18} />
            1. Dual-Module Autonomy Architecture
          </h2>
          <p style={{ color: 'var(--ink-secondary)', fontSize: '14px' }}>
            ASTRA coordinates two mission-critical planetary robotics domains under a unified scientific simulation core:
          </p>
          <ul style={{ paddingLeft: '20px', marginTop: '8px', fontSize: '13.5px', color: 'var(--ink-secondary)' }}>
            <li><strong>ASTRA Touchdown:</strong> High-fidelity 6-DOF Entry, Descent and Landing (EDL) simulator integrating atmospheric deceleration, radar altimetry fusion, terrain elevation hazards, and closed-loop divert guidance.</li>
            <li><strong>ASTRA Rover:</strong> 6-wheel rocker-bogie kinematic vehicle platform featuring terramechanics slip models, real-time Extended Kalman Filter (EKF) localization, and autonomous replanning under fault injections.</li>
          </ul>
        </div>

        <div style={{ background: 'var(--surface)', padding: '20px 24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary-dark)', marginBottom: '8px' }}>
            <Cpu size={18} />
            2. Controller Formulations &amp; RL Benchmarks
          </h2>
          <p style={{ color: 'var(--ink-secondary)', fontSize: '14px' }}>
            The platform provides plug-and-play evaluation across three distinct flight controller architectures:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '12px' }}>
            <div style={{ background: 'var(--background)', padding: '12px', borderRadius: '10px', border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--ink)' }}>Cascaded PID</div>
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Classical attitude quaternion inner loop + velocity outer loop.</div>
            </div>
            <div style={{ background: 'var(--background)', padding: '12px', borderRadius: '10px', border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--ink)' }}>Nonlinear MPC</div>
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Convex quadratic optimization over 15-step horizon with thruster throttling.</div>
            </div>
            <div style={{ background: 'var(--background)', padding: '12px', borderRadius: '10px', border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--ink)' }}>PPO RL Policy</div>
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Deep neural policy trained with generalized advantage estimation across noisy wind shear.</div>
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--surface)', padding: '20px 24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary-dark)', marginBottom: '8px' }}>
            <ShieldCheck size={18} />
            3. Fault Injection Framework
          </h2>
          <p style={{ color: 'var(--ink-secondary)', fontSize: '14px' }}>
            To validate true operational autonomy, four standard fault modes can be introduced dynamically during live simulations:
          </p>
          <ol style={{ paddingLeft: '20px', marginTop: '8px', fontSize: '13.5px', color: 'var(--ink-secondary)' }}>
            <li><strong>Sensor Dropout:</strong> Simulates optical or IMU packet losses, stressing the EKF dead-reckoning buffer.</li>
            <li><strong>Terrain Misclassification:</strong> Injects false safe/hazard labels into the terrain cost map to trigger diversion logic.</li>
            <li><strong>Power Drain Spike:</strong> Forces power budget degradation, compelling the planner to prune non-critical waypoints.</li>
            <li><strong>Actuator Degradation:</strong> Simulates wheel motor slip or thruster canting to test adaptive torque re-allocation.</li>
          </ol>
        </div>
      </div>
    </div>
  )
}

export default DocumentationPage

