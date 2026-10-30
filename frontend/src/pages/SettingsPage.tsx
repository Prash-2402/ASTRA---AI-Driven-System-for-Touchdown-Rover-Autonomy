import React, { useState } from 'react'
import { Settings, Shield, Bell, Database, Monitor, Cpu } from 'lucide-react'

export const SettingsPage: React.FC = () => {
  const [telemetryFrequency, setTelemetryFrequency] = useState('10 Hz')
  const [themeMode, setThemeMode] = useState('Sage & Cream (Light)')
  const [physicsStep, setPhysicsStep] = useState('5 ms (200 Hz)')
  const [hardwareAcc, setHardwareAcc] = useState(true)
  const [streamAudio, setStreamAudio] = useState(false)

  return (
    <div style={{ padding: '28px 36px', maxWidth: '800px', margin: '0 auto', color: 'var(--ink)' }}>
      <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '16px', marginBottom: '24px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--muted)' }}>
          ASTRA WORKSPACE PREFERENCES
        </span>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '30px', fontWeight: 800, marginTop: '4px' }}>
          System &amp; Simulation Settings
        </h1>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Simulation Engine */}
        <div style={{ background: 'var(--surface)', padding: '20px 24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '15px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ink)', marginBottom: '16px' }}>
            <Cpu size={16} className="text-primary-dark" />
            Physics &amp; Simulation Engine
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Numerical Integration Step</div>
                <div style={{ fontSize: '11.5px', color: 'var(--muted)' }}>Runge-Kutta 4th order (RK4) ODE solver delta time.</div>
              </div>
              <select
                value={physicsStep}
                onChange={e => setPhysicsStep(e.target.value)}
                style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--background)', fontSize: '12px' }}
              >
                <option>1 ms (1000 Hz Ultra)</option>
                <option>5 ms (200 Hz)</option>
                <option>10 ms (100 Hz)</option>
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Telemetry Stream Frequency</div>
                <div style={{ fontSize: '11.5px', color: 'var(--muted)' }}>Downlink refresh rate to telemetry dashboard.</div>
              </div>
              <select
                value={telemetryFrequency}
                onChange={e => setTelemetryFrequency(e.target.value)}
                style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--background)', fontSize: '12px' }}
              >
                <option>20 Hz</option>
                <option>10 Hz</option>
                <option>5 Hz</option>
                <option>1 Hz</option>
              </select>
            </div>
          </div>
        </div>

        {/* Display & Interface */}
        <div style={{ background: 'var(--surface)', padding: '20px 24px', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '15px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ink)', marginBottom: '16px' }}>
            <Monitor size={16} className="text-primary-dark" />
            Display &amp; Theme System
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Interface Theme</div>
                <div style={{ fontSize: '11.5px', color: 'var(--muted)' }}>Active palette token specification.</div>
              </div>
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--primary-dark)', background: 'var(--sage)', padding: '4px 10px', borderRadius: '6px' }}>
                Sage Green &amp; Cream (Light)
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Hardware Acceleration (WebGL)</div>
                <div style={{ fontSize: '11.5px', color: 'var(--muted)' }}>Enable GPU acceleration for 3D trajectory viewports.</div>
              </div>
              <input
                type="checkbox"
                checked={hardwareAcc}
                onChange={e => setHardwareAcc(e.target.checked)}
                style={{ accentColor: 'var(--primary-dark)', width: '16px', height: '16px', cursor: 'pointer' }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsPage

