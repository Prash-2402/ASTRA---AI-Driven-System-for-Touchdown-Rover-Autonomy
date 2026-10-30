import { PageHeader, Panel } from "../../components/ui";

const STAGES = [
  ["Sense", "simulation/*/sensors.py", "Noisy, biased, delayed, drop-prone channels; truth never leaves the simulator."],
  ["Estimate", "autonomy/estimation/*_ekf.py", "12-state lander EKF, 8-state rover EKF with gating & relocalisation."],
  ["Predict", "autonomy/prediction/", "Touchdown point-mass predictor; rover route-energy model; MPC horizon."],
  ["Decide", "autonomy/planning · decision", "Site assessment & diversion engine; fault classifier & response selector; FSM baseline."],
  ["Act", "autonomy/control/", "PID / MPC / PPO guidance + attitude allocation; Pure Pursuit + skid-steer torque allocation."],
  ["Verify", "autonomy/safety · fault_detection", "Independent safety supervisors; recovery verifier; touchdown checks."],
  ["Adapt", "decision audit → replanning", "Fault-specific cost-map weights, diversion targets, energy-model updates."],
];
const RATES = [["Touchdown physics (RK4)", "100 Hz"], ["Touchdown sensors", "1–100 Hz per channel"], ["Touchdown control", "20 Hz (MPC re-solve 4 Hz)"], ["Lidar hazard mapping", "1 Hz below 450 m"],
  ["Rover physics (PyBullet)", "120 Hz"], ["Rover IMU / odometry", "50 / 20 Hz"], ["Rover lidar / camera / visloc", "5 / 2 / 1 Hz"], ["Rover decision & control", "10 Hz"], ["Telemetry recording", "10 Hz / 5 Hz"], ["WebSocket publication", "10 Hz wall clock"], ["3D rendering", "display rate (interpolated)"]];

export default function Architecture() {
  return (
    <div>
      <PageHeader eyebrow="As implemented" title="Architecture" />
      <Panel eyebrow="Unified mission-intelligence workflow" title="Sense → Estimate → Predict → Decide → Act → Verify → Adapt">
        <div className="grid md:grid-cols-7 gap-2">
          {STAGES.map(([s, where, what], i) => (
            <div key={s} className="relative rounded-[16px] bg-sage-soft border p-3">
              <div className="num text-[10px] text-muted">0{i + 1}</div><div className="h-display text-2xl">{s}</div>
              <div className="num text-[10px] text-primary-dark mt-1 break-words">{where}</div><div className="text-[11.5px] text-ink2 mt-2">{what}</div>
            </div>))}
        </div>
        <p className="text-[12px] text-ink2 mt-4">Shared contracts live in <code className="num">autonomy/framework.py</code>: StateObservationManager, PredictionEngine, DecisionEngine, SafetySupervisorBase and DecisionAudit. The two modules share interfaces — not physics and not controllers.</p>
      </Panel>
      <div className="grid lg:grid-cols-2 gap-5 mt-5">
        <Panel eyebrow="Separation of concerns" title="Source of truth">
          <svg viewBox="0 0 520 300" className="w-full" role="img" aria-label="Backend is the source of truth; frontend reads snapshots">
            {[[20, 30, "React UI (read + command)"], [20, 130, "FastAPI + WebSocket bus"], [20, 230, "PostgreSQL + telemetry archives"], [300, 30, "Simulation sessions (threads)"], [300, 130, "Touchdown engine (RK4)"], [300, 230, "Rover engine (PyBullet)"]].map(([x, y, t]: any) => (
              <g key={t}><rect x={x} y={y} width="200" height="46" rx="14" fill="#EAF0E5" stroke="rgba(83,111,89,.35)" /><text x={x + 100} y={y + 28} textAnchor="middle" fontSize="12" fill="#26372D">{t}</text></g>))}
            <path d="M120 76 V130 M120 176 V230 M220 153 H300 M400 76 V130 M400 176 V230" stroke="#536F59" strokeWidth="1.6" fill="none" markerEnd="url(#a)" />
            <defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#536F59" /></marker></defs>
          </svg>
          <p className="text-[12px] text-ink2">The frontend never owns simulation state. Physics advances on a fixed timestep in backend threads; websocket publication samples snapshots and cannot change the integration step.</p>
        </Panel>
        <Panel eyebrow="Timing" title="Independent loop rates">
          <table className="table"><tbody>{RATES.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num text-right">{v}</td></tr>)}</tbody></table>
        </Panel>
      </div>
    </div>
  );
}
