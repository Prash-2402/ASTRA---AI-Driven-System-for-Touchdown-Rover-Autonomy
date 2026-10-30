import React from 'react'

const Placeholder: React.FC<{ title: string }> = ({ title }) => (
  <div style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>
    <h2 style={{ color: 'var(--ink)', marginBottom: '8px' }}>{title}</h2>
    <p>This module is being built...</p>
  </div>
)

export const RoverModule = () => <Placeholder title="ASTRA Rover" />
export const ExperimentLab = () => <Placeholder title="Experiment Lab" />
export const TelemetryPage = () => <Placeholder title="Telemetry" />

