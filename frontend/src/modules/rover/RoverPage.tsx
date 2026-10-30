import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

const RoverScene = lazy(() => import("../../visualization/RoverScene"));
export const FAULTS: [string, string, string][] = [
  ["sensor_dropout", "Sensor dropout", "LiDAR + camera stop reporting"],
  ["terrain_misclassification", "Terrain misclassification", "Invert 15 % of traversability cells"],
  ["power_drain", "Power-drain spike", "3× consumption + 60 W parasitic"],
  ["actuator_degradation", "Actuator degradation", "Front-left wheel at 30 % torque"],
];
const WHEELS = ["FL", "ML", "RL", "FR", "MR", "RR"];

export default function RoverPage() {
  const live = useSim((s) => s.rover);
  const hist = useSim((s) => s.roverHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [follow, setFollow] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [cfg, setCfg] = useState({ seed: 7, terrain: 1, controller: "astra", battery: 0.8, speed: 0.4 });
  const terrains = usePoll(() => api.get("/api/rover/terrain"), 0);
  const decisions = usePoll(() => api.get("/api/rover/decisions"), 2000, [live?.run_uid]);

  useEffect(() => { api.get("/api/rover/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  useEffect(() => { api.get("/api/rover/config").then((c) => { const a = c.active; if (a) setCfg((x) => ({ ...x, seed: a.seed ?? x.seed, terrain: a.terrain ?? x.terrain,
    controller: a.controller ?? x.controller, battery: a.initial_battery ?? x.battery, speed: a.max_speed ?? x.speed })); }).catch(() => {}); }, [live?.run_uid]);
  useEffect(() => { if (live?.run_uid) api.get("/api/rover/scene").then(setScene).catch(() => {}); }, [live?.run_uid]);

  const configure = async () => {
    setErr(null);
    try {
      await api.post("/api/rover/config", { seed: cfg.seed, terrain: cfg.terrain, controller: cfg.controller, initial_battery: cfg.battery, max_speed: cfg.speed });
      ingest(await api.get("/api/rover/telemetry"));
    } catch (e: any) { setErr(e.message); }
  };
  const inject = async (ft: string) => { try { await api.post("/api/rover/faults", { fault_type: ft, duration: ft === "sensor_dropout" ? 45 : null }); } catch (e: any) { setErr(e.message); } };

  const f = live?.frame;
  const held = terrains.data?.find((t: any) => t.variant === cfg.terrain)?.split === "held_out";
  return (
    <div>
      <PageHeader eyebrow="Module 2 · Adaptive autonomy under injected hazards" title={<>ASTRA <em>Rover</em></>}>
        <SimControls module="rover" status={live?.status} speed={live?.speed} />
      </PageHeader>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="grid xl:grid-cols-[1fr_350px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="panel overflow-hidden relative" style={{ height: "62vh", minHeight: 420 }}>
            <Suspense fallback={<div className="p-6 eyebrow">Loading 3D…</div>}><RoverScene snap={live} scene={scene} follow={follow} /></Suspense>
            <div className="absolute top-4 left-4 flex flex-wrap gap-2">
              <span className="chip !bg-[rgba(255,253,244,.92)]">{live?.controller?.toUpperCase() ?? "—"}</span>
              <span className="chip !bg-[rgba(255,253,244,.92)]">t = {fmt(live?.t, 1)} s</span>
              {f?.faults_active.map((x) => <span key={x} className="chip !bg-[rgba(199,108,100,.15)] !text-danger">⚠ {x}</span>)}
              <button className="chip !bg-[rgba(255,253,244,.92)] hover:!bg-sage" onClick={() => setFollow(!follow)}>{follow ? "following rover" : "free camera"}</button>
            </div>
            <div className="absolute bottom-3 left-4 right-4 flex flex-wrap gap-3 text-[10.5px] text-ink2 rounded-[12px] px-3 py-2" style={{ background: "rgba(255,253,244,.9)" }}>
              <L c="#536F59" t="planned route" /><L c="#AFC3A7" t="previous routes" /><L c="#26372D" t="executed (truth)" /><L c="#7798A3" t="EKF estimate" />
              <L c="#C76C64" t="perceived obstacle" /><L c="#D69B4D" t="perceived untraversable" />
            </div>
          </div>
          {f ? <div className="grid md:grid-cols-2 gap-5">
            <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ"><ErrorVsSigma data={hist} err="err" sig="sig" /></Panel>
            <Panel eyebrow="Estimator" title="Heading error vs ±2σ & visloc NIS"><ErrorVsSigma data={hist} err="herr" sig="hsig" title="|heading error| [rad]" /></Panel>
            <Panel eyebrow="Energy" title="State of charge & power"><Series data={hist} lines={[{ key: "soc", name: "SoC" }]} height={150} /><Series data={hist} lines={[{ key: "power", name: "power [W]", color: "#D69B4D" }]} height={150} /></Panel>
            <Panel eyebrow="Mobility" title="Speed & wheel slip"><Series data={hist} lines={[{ key: "speed", name: "speed [m/s]" }, { key: "slip", name: "slip est.", color: "#C76C64" }]} /></Panel>
          </div> : <Empty title="No traverse configured">Pick a terrain and controller, apply, then start.</Empty>}
          <Panel eyebrow="Explainability" title="Decision audit log"><DecisionLog decisions={decisions.data || []} /></Panel>
        </div>
        <div className="space-y-5">
          <Panel eyebrow="Telemetry" title="Rover state">
            {f ? <>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Position (truth)" value={`${fmt(f.truth.position[0], 1)}, ${fmt(f.truth.position[1], 1)}`} unit="m" sub={`EKF ${fmt(f.estimate.position[0], 1)}, ${fmt(f.estimate.position[1], 1)}`} />
                <Stat label="Speed" value={fmt(f.truth.speed, 2)} unit="m/s" sub={`EKF v ${fmt(f.estimate.v, 2)}`} />
                <Stat label="Heading" value={fmt((f.truth.rpy[2] * 180) / Math.PI, 0)} unit="°" sub={`EKF ${fmt((f.estimate.heading * 180) / Math.PI, 0)}°`} />
                <Stat label="Pos σ / error" value={`${fmt(f.estimate.pos_sigma, 2)} / ${fmt(f.error.position, 2)}`} unit="m" />
                <Stat label="Battery" value={fmt(f.battery.soc * 100, 1)} unit="%" tone={f.battery.soc < 0.22 ? "warn" : undefined} sub={`${fmt(f.battery.voltage, 1)} V · ${fmt(f.battery.current, 2)} A`} />
                <Stat label="Power" value={fmt(f.battery.power, 0)} unit="W" sub={`${fmt(f.battery.energy_used_wh, 2)} Wh used`} />
                <Stat label="Slip" value={fmt(f.slip, 2)} />
                <Stat label="Safety" value={f.safety.action} tone={f.safety.action === "safe_halt" ? "bad" : f.safety.action === "continue" ? "ok" : "warn"} sub={f.safety.reasons[0]} />
              </div>
              <div className="mt-4">
                <div className="eyebrow !text-[10px] mb-1.5">Wheels — torque [N m] · health estimate</div>
                <div className="grid grid-cols-6 gap-1 text-center">
                  {WHEELS.map((w, i) => <div key={w} className="rounded-[8px] bg-sage-soft py-1.5">
                    <div className="text-[10px] text-muted">{w}</div><div className="num text-[12px]">{fmt(f.wheels.torque[i], 1)}</div>
                    <div className={`num text-[10px] ${f.wheels.health_est[i] < 0.9 ? "text-danger" : "text-muted"}`}>{fmt(f.wheels.health_est[i], 2)}</div></div>)}
                </div>
              </div>
              <div className="mt-4 text-[11.5px] text-ink2"><span className="eyebrow !text-[10px]">Policy</span><div className="mt-1">{f.policy}</div></div>
              {f.classification.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{f.classification.map((c) => <span key={c} className="chip">{c}</span>)}</div>}
            </> : <div className="text-[12px] text-muted">No telemetry.</div>}
          </Panel>
          <Panel eyebrow="Live fault injection" title="Four primary faults">
            <div className="grid gap-2">
              {FAULTS.map(([id, name, desc]) => (
                <button key={id} className="text-left rounded-[12px] border px-3 py-2.5 hover:bg-sage-soft disabled:opacity-40" disabled={live?.status !== "running"} onClick={() => inject(id)}>
                  <div className="text-[13px] font-medium">{name}</div><div className="text-[11px] text-muted">{desc}</div>
                </button>))}
            </div>
            <p className="text-[11px] text-muted mt-3">Faults change the simulated sensors, battery or wheel physics. The autonomy stack is not told a fault exists.</p>
          </Panel>
          <Panel eyebrow="Mission configuration" title="Traverse">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Terrain"><select className="select" value={cfg.terrain} onChange={(e) => setCfg({ ...cfg, terrain: +e.target.value })}>
                {(terrains.data || []).map((t: any) => <option key={t.variant} value={t.variant}>T{t.variant} · {t.name}</option>)}</select></Field>
              <Field label="Controller"><select className="select" value={cfg.controller} onChange={(e) => setCfg({ ...cfg, controller: e.target.value })}>
                <option value="astra">ASTRA adaptive</option><option value="fsm">FSM baseline</option></select></Field>
              <Field label="Seed"><input className="input num" type="number" value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
              <Field label="Initial battery"><input className="input num" type="number" step="0.05" value={cfg.battery} onChange={(e) => setCfg({ ...cfg, battery: +e.target.value })} /></Field>
              <Field label="Max speed [m/s]"><input className="input num" type="number" step="0.05" value={cfg.speed} onChange={(e) => setCfg({ ...cfg, speed: +e.target.value })} /></Field>
            </div>
            {held && <p className="text-[11px] text-warning mt-2">Held-out terrain: use for evaluation only, never for tuning.</p>}
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={configure}>Apply configuration</button>
          </Panel>
          {live?.result && <Panel eyebrow="Mission result" title={live.result.success ? "Science target reached" : `Outcome: ${live.result.outcome}`}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Time" value={fmt(live.result.mission_time_s, 0)} unit="s" /><Stat label="Energy" value={fmt(live.result.energy_used_wh, 2)} unit="Wh" />
              <Stat label="Route" value={fmt(live.result.route_length_m, 1)} unit="m" /><Stat label="Collisions" value={live.result.collisions} />
              <Stat label="Final dist." value={fmt(live.result.final_distance_to_target_m, 2)} unit="m" /><Stat label="Replans" value={live.result.replans} />
            </div>
            <a className="btn btn-ghost mt-4" href={api.url(`/api/runs/${live.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">Download PDF debrief</a>
          </Panel>}
          <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={live?.events || []} /></Panel>
        </div>
      </div>
    </div>
  );
}
const L = ({ c, t }: { c: string; t: string }) => <span className="inline-flex items-center gap-1.5"><span className="inline-block w-3 h-[3px] rounded" style={{ background: c }} />{t}</span>;
