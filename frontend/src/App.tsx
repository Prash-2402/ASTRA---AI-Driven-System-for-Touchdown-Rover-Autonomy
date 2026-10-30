import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layouts/AppShell";

const Landing = lazy(() => import("./public-site/Landing"));
const Overview = lazy(() => import("./application/pages/Overview"));
const MissionControl = lazy(() => import("./application/pages/MissionControl"));
const LandingSim = lazy(() => import("./modules/landing/LandingSimPage"));
const Rover = lazy(() => import("./modules/rover/RoverPage"));
const ScenarioBuilder = lazy(() => import("./application/pages/ScenarioBuilder"));
const FaultInjection = lazy(() => import("./application/pages/FaultInjection"));
const ControllerComparison = lazy(() => import("./application/pages/ControllerComparison"));
const RLLab = lazy(() => import("./application/pages/RLLab"));
const ExperimentLab = lazy(() => import("./application/pages/ExperimentLab"));
const Results = lazy(() => import("./application/pages/Results"));
const Telemetry = lazy(() => import("./application/pages/Telemetry"));
const Evidence = lazy(() => import("./application/pages/Evidence"));

const Loading = () => <div className="p-10 eyebrow">Loading…</div>;

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="mission-control" element={<MissionControl />} />
          <Route path="landing" element={<LandingSim />} />
          <Route path="touchdown" element={<Navigate to="/app/landing?env=mars" replace />} />
          <Route path="moon" element={<Navigate to="/app/landing?env=moon&type=apollo" replace />} />
          <Route path="rover" element={<Rover />} />
          <Route path="scenarios" element={<ScenarioBuilder />} />
          <Route path="faults" element={<FaultInjection />} />
          <Route path="comparison" element={<ControllerComparison />} />
          <Route path="rl-lab" element={<RLLab />} />
          <Route path="experiments" element={<ExperimentLab />} />
          <Route path="results" element={<Results />} />
          <Route path="telemetry" element={<Telemetry />} />
          <Route path="evidence" element={<Evidence />} />
        </Route>
        <Route path="/app/*" element={<Navigate to="/app" />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Suspense>
  );
}
