import { useState } from "react";
import { ErrorNote, Field, fmt, PageHeader, Panel, StatusPill } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import { FAULTS } from "../../modules/rover/RoverPage";

const EVIDENCE: Record<string, string> = {
  sensor_dropout: "Sensor staleness (lidar/camera/visloc), ground-ring range inconsistency for corrupted returns.",
  terrain_misclassification: "Camera-vs-lidar disagreement: isolated 'untraversable' labels on lidar-flat ground.",
  power_drain: "Measured electrical power vs motor-model prediction (ratio), online fixed-load estimate.",
  actuator_degradation: "Isolated wheel speed-tracking residual + torque ceiling below commanded limit.",
};

export default function FaultInjection() {
  const live = useSim((s) => s.rover);
  const faults = usePoll(() => api.get("/api/rover/faults"), 2000);
  const [err, setErr] = useState<string | null>(null);
  const [params, setParams] = useState<Record<string, any>>({});
  const [dur, setDur] = useState<Record<string, number | null>>({ sensor_dropout: 45 });
  const inject = async (id: string) => {
    setErr(null);
    try { await api.post("/api/rover/faults", { fault_type: id, duration: dur[id] ?? null, params: params[id] || {} }); faults.refresh(); } catch (e: any) { setErr(e.message); }
  };
  const defs = faults.data?.defaults || {};
  return (
    <div>
      <PageHeader eyebrow="Rover fault taxonomy (closed: four classes)" title="Fault Injection"><StatusPill status={live?.status} /></PageHeader>
      <ErrorNote error={err} />
      {live?.status !== "running" && <div className="panel-soft p-4 text-[13px] mb-5">Live injection requires a running rover session (Rover page or Mission Control). For reproducible schedules use the Scenario Builder or Experiment Lab.</div>}
      <div className="grid md:grid-cols-2 gap-5">
        {FAULTS.map(([id, name, desc], k) => (
          <Panel key={id} eyebrow={`Fault 0${k + 1}`} title={name}>
            <p className="text-[12.5px] text-ink2">{desc}</p>
            <div className="text-[11.5px] text-muted mt-2"><b>Detection evidence:</b> {EVIDENCE[id]}</div>
            <div className="grid grid-cols-2 gap-2 mt-4">
              {Object.entries(defs[id] || {}).map(([p, v]) => (
                <Field key={p} label={p}>{Array.isArray(v) ? <input className="input num" defaultValue={(v as any[]).join(",")} onChange={(e) => setParams({ ...params, [id]: { ...(params[id] || {}), [p]: e.target.value.split(",").map((s) => s.trim()) } })} />
                  : typeof v === "string" ? <select className="select" defaultValue={v} onChange={(e) => setParams({ ...params, [id]: { ...(params[id] || {}), [p]: e.target.value } })}><option>missing</option><option>corrupted</option></select>
                  : <input className="input num" type="number" step="any" defaultValue={v as number} onChange={(e) => setParams({ ...params, [id]: { ...(params[id] || {}), [p]: +e.target.value } })} />}</Field>))}
              <Field label="duration [s] (blank = until end)"><input className="input num" type="number" value={dur[id] ?? ""} onChange={(e) => setDur({ ...dur, [id]: e.target.value ? +e.target.value : null })} /></Field>
            </div>
            <button className="btn btn-primary mt-4" disabled={live?.status !== "running"} onClick={() => inject(id)}>Inject now</button>
          </Panel>))}
      </div>
      <Panel eyebrow="Injected in current session" title="Fault log" className="mt-5">
        {faults.data?.log?.length ? <table className="table"><thead><tr><th>t [s]</th><th>fault</th><th>phase</th><th>params</th></tr></thead><tbody>
          {faults.data.log.map((l: any, i: number) => <tr key={i}><td className="num">{fmt(l.t, 1)}</td><td>{l.fault_type}</td><td>{l.phase}</td><td className="num text-[11px]">{JSON.stringify(l.params ?? {})}</td></tr>)}</tbody></table>
          : <div className="text-[12px] text-muted">No faults injected in this session.</div>}
      </Panel>
    </div>
  );
}
