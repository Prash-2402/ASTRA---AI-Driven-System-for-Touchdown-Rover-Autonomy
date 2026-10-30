import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import AppShell from './components/AppShell'
import OverviewDashboard from './pages/OverviewDashboard'
import TouchdownModule from './pages/TouchdownModule'
import RoverModule from './pages/RoverModule'
import ExperimentLab from './pages/ExperimentLab'
import TelemetryPage from './pages/TelemetryPage'
import ScenarioBuilder from './pages/ScenarioBuilder'
import ControllerComparison from './pages/ControllerComparison'
import DocumentationPage from './pages/DocumentationPage'
import SettingsPage from './pages/SettingsPage'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<OverviewDashboard />} />
          <Route path="overview" element={<OverviewDashboard />} />
          <Route path="touchdown" element={<TouchdownModule />} />
          <Route path="rover" element={<RoverModule />} />
          <Route path="experiment-lab" element={<ExperimentLab />} />
          <Route path="scenario-builder" element={<ScenarioBuilder />} />
          <Route path="controller-comparison" element={<ControllerComparison />} />
          <Route path="results" element={<ExperimentLab />} />
          <Route path="telemetry" element={<TelemetryPage />} />
          <Route path="documentation" element={<DocumentationPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
