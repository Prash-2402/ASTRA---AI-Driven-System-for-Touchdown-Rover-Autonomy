import React, { useState } from 'react'
import { Sliders, Plus, Save, Play, Layers, MapPin, Wind, Mountain, AlertTriangle, ShieldCheck } from 'lucide-react'
import './ScenarioBuilder.css'

export const ScenarioBuilder: React.FC = () => {
  const [scenarioName, setScenarioName] = useState('SCEN-082_Martian_Crater_High_Turbulence')
  const [environment, setEnvironment] = useState('Mars — Jezero Crater')
  const [gravity, setGravity] = useState(3.72)
  const [surfacePressure, setSurfacePressure] = useState(0.636)
  const [windGusts, setWindGusts] = useState(24.5)
  const [slopeAngle, setSlopeAngle] = useState(14.0)
  const [boulderDensity, setBoulderDensity] = useState('High (18 boulders / 100m²)')
  const [opticalDust, setOpticalDust] = useState(0.85)

  return (
    <div className="scen-root">
      <div className="scen-header">
        <div>
          <div className="scen-eyebrow">PHYSICS &amp; TERRAIN SPECIFICATION</div>
          <h1 className="scen-title">Custom Scenario Builder</h1>
        </div>
        <div className="scen-header-actions">
          <button className="scen-btn-save">
            <Save size={14} />
            <span>Save Configuration</span>
          </button>
          <button className="scen-btn-run">
            <Play size={14} />
            <span>Launch in Simulation</span>
          </button>
        </div>
      </div>

      <div className="scen-grid">
        {/* Environment Parameters */}
        <div className="scen-card">
          <div className="scen-card-title">
            <Mountain size={15} className="text-primary-dark" />
            <span>PLANETARY ENVIRONMENTAL PARAMETERS</span>
          </div>

          <div className="scen-field">
            <label>Scenario Identifier</label>
            <input
              type="text"
              value={scenarioName}
              onChange={e => setScenarioName(e.target.value)}
              className="scen-input font-mono"
            />
          </div>

          <div className="scen-field">
            <label>Planetary Body</label>
            <select
              value={environment}
              onChange={e => setEnvironment(e.target.value)}
              className="scen-select"
            >
              <option>Mars — Jezero Crater</option>
              <option>Mars — Olympus Rupes</option>
              <option>Moon — Shackleton South Pole</option>
              <option>Titan — Shangri-La Dune Field</option>
            </select>
          </div>

          <div className="scen-dual-fields">
            <div className="scen-field">
              <label>Surface Gravity (g)</label>
              <div className="scen-input-unit">
                <input
                  type="number"
                  step="0.01"
                  value={gravity}
                  onChange={e => setGravity(+e.target.value)}
                />
                <span>m/s²</span>
              </div>
            </div>
            <div className="scen-field">
              <label>Atmospheric Pressure</label>
              <div className="scen-input-unit">
                <input
                  type="number"
                  step="0.01"
                  value={surfacePressure}
                  onChange={e => setSurfacePressure(+e.target.value)}
                />
                <span>kPa</span>
              </div>
            </div>
          </div>
        </div>

        {/* Dynamic Hazards & Wind */}
        <div className="scen-card">
          <div className="scen-card-title">
            <Wind size={15} className="text-warning" />
            <span>DYNAMIC ATMOSPHERIC &amp; WIND PROFILE</span>
          </div>

          <div className="scen-field">
            <div className="scen-slider-label">
              <span>Peak Crosswind Gust Velocity</span>
              <span className="font-mono">{windGusts} m/s</span>
            </div>
            <input
              type="range"
              min="0"
              max="60"
              step="0.5"
              value={windGusts}
              onChange={e => setWindGusts(+e.target.value)}
              className="scen-slider"
            />
          </div>

          <div className="scen-field">
            <div className="scen-slider-label">
              <span>Atmospheric Dust Optical Depth (τ)</span>
              <span className="font-mono">{opticalDust}</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="3.0"
              step="0.05"
              value={opticalDust}
              onChange={e => setOpticalDust(+e.target.value)}
              className="scen-slider"
            />
          </div>

          <div className="scen-field">
            <div className="scen-slider-label">
              <span>Terrain Slope Inclination</span>
              <span className="font-mono">{slopeAngle}°</span>
            </div>
            <input
              type="range"
              min="0"
              max="35"
              step="0.5"
              value={slopeAngle}
              onChange={e => setSlopeAngle(+e.target.value)}
              className="scen-slider"
            />
          </div>

          <div className="scen-field">
            <label>Hazard Boulder Density Distribution</label>
            <select
              value={boulderDensity}
              onChange={e => setBoulderDensity(e.target.value)}
              className="scen-select"
            >
              <option>Low (2 boulders / 100m²)</option>
              <option>Moderate (8 boulders / 100m²)</option>
              <option>High (18 boulders / 100m²)</option>
              <option>Dense Field (35 boulders / 100m²)</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ScenarioBuilder

