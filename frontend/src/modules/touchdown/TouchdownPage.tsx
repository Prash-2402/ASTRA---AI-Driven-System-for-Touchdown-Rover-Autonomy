import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

const TouchdownScene = lazy(() => import("../../visualization/TouchdownScene"));
const deg = (r: number) => (r * 180) / Math.PI;

export default function TouchdownPage() {
  const live = useSim((s) => s.touchdown);
  const hist = useSim((s) => s.tdHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [follow, setFollow] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [cfg, setCfg] = useState({ seed: 42, controller: "pid", hazard: false, alt: 2900, wind: 4 });
  const avail = usePoll(() => api.get("/api/touchdown/controllers"), 0);
  const decisions = usePoll(() => api.get("/api/touchdown/decisions"), 2000, [live?.run_uid]);
  const debrief = usePoll(() => (live?.result ? api.get("/api/touchdown/debrief") : Promise.resolve(null)), 0, [live?.run_uid, !!live?.result]);

  useEffect(() => { api.get("/api/touchdown/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  // keep the form in sync with the configuration the backend session is actually running
  useEffect(() => { api.get("/api/touchdown/config").then((c) => { const a = c.active; if (a) setCfg((x) => ({ ...x, seed: a.seed ?? x.seed, controller: a.controller ?? x.controller,
    hazard: !!a.terrain?.hazard_at_target, alt: a.initial_position?.[2] ?? x.alt })); }).catch(() => {}); }, [live?.run_uid]);
  useEffect(() => { if (live?.run_uid) api.get("/api/touchdown/scene").then(setScene).catch(() => {}); }, [live?.run_uid]);
  useEffect(() => { if (live?.diversions) api.get("/api/touchdown/scene").then(setScene).catch(() => {}); }, [live?.diversions]);

  const configure = async () => {
    setErr(null);
    try {
      await api.post("/api/touchdown/config", { seed: cfg.seed, controller: cfg.controller, initial_position: [-650, 320, cfg.alt],
        terrain: { hazard_at_target: cfg.hazard }, planet: { wind: [cfg.wind, -cfg.wind / 2, 0] } });
      ingest(await api.get("/api/touchdown/telemetry")); setScene(await api.get("/api/touchdown/scene"));
    } catch (e: any) { setErr(e.message); }
  };
  const inject = async (kind: string, body: any) => { try { await api.post(`/api/touchdown/inject/${kind}`, body); } catch (e: any) { setErr(e.message); } };

  const f = live?.frame;
  return (
    <div>
      <PageHeader eyebrow="Module 1 · Entry, descent & landing" title={<>ASTRA <em>Touchdown</em></>}>
        <SimControls module="touchdown" status={live?.status} speed={live?.speed} />
      </PageHeader>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="grid xl:grid-cols-[1fr_340px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="panel overflow-hidden relative" style={{ height: "62vh", minHeight: 420 }}>
            <Suspense fallback={<div className="p-6 eyebrow">Loading 3D…</div>}>
              <TouchdownScene snap={live} scene={scene} decisions={decisions.data || []} follow={follow} />
            </Suspense>
            <div className="absolute top-4 left-4 flex flex-wrap gap-2">
              <span className="chip !bg-[rgba(255,253,244,.92)]">{live?.phase ?? "—"}</span>
              <span className="chip !bg-[rgba(255,253,244,.92)]">t = {fmt(live?.t, 1)} s</span>
              <button className="chip !bg-[rgba(255,253,244,.92)] hover:!bg-sage" onClick={() => setFollow(!follow)}>{follow ? "following lander" : "free camera"}</button>
            </div>
            <div className="absolute bottom-3 left-4 right-4 flex flex-wrap gap-3 text-[10.5px] text-ink2 rounded-[12px] px-3 py-2" style={{ background: "rgba(255,253,244,.9)" }}>
              <Legend c="#26372D" t="actual (truth)" /><Legend c="#7798A3" t="estimated / MPC horizon" /><Legend c="#779477" t="desired profile" />
              <Legend c="#D69B4D" t="predicted → touchdown" /><Legend c="#648C65" t="feasible alt. site" /><Legend c="#C76C64" t="infeasible site" />
              <span className="text-muted">Lander drawn 4× scale for visibility.</span>
            </div>
          </div>
          {!f ? <Empty title="No descent configured">Configure a mission on the right and press Start.</Empty> : (
            <div className="grid md:grid-cols-2 gap-5">
              <Panel eyebrow="Truth vs estimate" title="Altitude & vertical speed"><Series data={hist} lines={[{ key: "agl", name: "AGL truth [m]" }, { key: "agl_est", name: "AGL EKF [m]", dashed: true }]} /></Panel>
              <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ (east axis)"><ErrorVsSigma data={hist} err="err_x" sig="sig_x" /></Panel>
              <Panel eyebrow="Propulsion" title="Throttle & tilt"><Series data={hist} lines={[{ key: "throttle", name: "throttle [0-1]" }, { key: "tilt", name: "tilt [deg]", color: "#D69B4D" }]} /></Panel>
              <Panel eyebrow="Resources" title="Fuel & vertical velocity"><Series data={hist} lines={[{ key: "fuel", name: "fuel [kg]" }, { key: "vz", name: "vz truth [m/s]", color: "#7798A3" }, { key: "vz_est", name: "vz EKF", dashed: true, color: "#C76C64" }]} /></Panel>
            </div>
          )}
          <Panel eyebrow="Explainability" title="Decision audit log"><DecisionLog decisions={decisions.data || []} /></Panel>
        </div>
        <div className="space-y-5">
          <Panel eyebrow="Telemetry" title="Vehicle state">
            {f ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-4">
                <Stat label="Altitude AGL" value={fmt(f.truth.agl, 1)} unit="m" sub={`EKF ${fmt(f.estimate.agl, 1)} m`} />
                <Stat label="Vertical speed" value={fmt(f.truth.velocity[2], 2)} unit="m/s" sub={`EKF ${fmt(f.estimate.velocity[2], 2)}`} />
                <Stat label="Horizontal speed" value={fmt(Math.hypot(f.truth.velocity[0], f.truth.velocity[1]), 2)} unit="m/s" />
                <Stat label="Fuel" value={fmt(f.truth.fuel, 1)} unit="kg" tone={f.truth.fuel < 40 ? "warn" : undefined} />
                <Stat label="Throttle" value={fmt(f.actuators.throttle * 100, 0)} unit="%" sub={`cmd ${fmt(f.command.throttle * 100, 0)}%`} />
                <Stat label="Tilt" value={fmt(f.truth.tilt_deg, 1)} unit="°" />
                <Stat label="Roll / pitch" value={`${fmt(deg(f.truth.euler[0]), 1)} / ${fmt(deg(f.truth.euler[1]), 1)}`} unit="°" />
                <Stat label="Pos. error" value={fmt(Math.hypot(...f.error.position), 2)} unit="m" sub={`σ ${fmt(Math.hypot(...f.estimate.sigma.slice(0, 3)), 2)} m`} />
                <Stat label="Target" value={`${fmt(f.target[0], 0)}, ${fmt(f.target[1], 0)}`} sub={`diversions: ${live?.diversions ?? 0}`} />
                <Stat label="Pred. touchdown" value={f.predicted_touchdown ? `${fmt(f.predicted_touchdown[0], 0)}, ${fmt(f.predicted_touchdown[1], 0)}` : "—"} />
              </div>
            ) : <div className="text-[12px] text-muted">No telemetry.</div>}
            {f?.controller?.mpc && <div className="mt-4 text-[11px] text-ink2 num">MPC: {f.controller.mpc.success ? "converged" : "not converged"} · {fmt(f.controller.mpc.solve_ms, 1)} ms · it {f.controller.mpc.iterations} · N={f.controller.mpc.horizon}/Nc={f.controller.mpc.control_horizon}</div>}
            {f?.controller?.ppo && <div className="mt-4 text-[11px] text-ink2 num">PPO checkpoint {f.controller.ppo.checkpoint}</div>}
          </Panel>
          <Panel eyebrow="Mission configuration" title="Initial conditions">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Controller"><select className="select" value={cfg.controller} onChange={(e) => setCfg({ ...cfg, controller: e.target.value })}>
                <option value="pid">Cascade PID</option><option value="mpc">MPC</option><option value="ppo" disabled={!avail.data?.ppo}>PPO {avail.data?.ppo ? "" : "(no trained policy)"}</option></select></Field>
              <Field label="Random seed"><input className="input num" type="number" value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
              <Field label="Initial altitude [m]"><input className="input num" type="number" value={cfg.alt} onChange={(e) => setCfg({ ...cfg, alt: +e.target.value })} /></Field>
              <Field label="Mean wind [m/s]"><input className="input num" type="number" value={cfg.wind} onChange={(e) => setCfg({ ...cfg, wind: +e.target.value })} /></Field>
            </div>
            <label className="flex items-center gap-2 text-[12.5px] mt-3"><input type="checkbox" checked={cfg.hazard} onChange={(e) => setCfg({ ...cfg, hazard: e.target.checked })} /> Hidden boulder field at target (discoverable only by lidar)</label>
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={configure}>Apply configuration</button>
          </Panel>
          <Panel eyebrow="Live intervention" title="Hazards & disturbances">
            <div className="grid gap-2">
              <button className="btn btn-ghost justify-center" onClick={() => inject("hazard", { radius: 25 })}>Inject boulder field at current target</button>
              <button className="btn btn-ghost justify-center" onClick={() => inject("disturbance", { force: [2500, -1500, 0], duration: 4 })}>Lateral gust: 2.9 kN for 4 s</button>
              <button className="btn btn-ghost justify-center" onClick={() => inject("sensor", { channel: "position", degradation: 8 })}>Degrade TRN position sensor ×8</button>
              <button className="btn btn-ghost justify-center" onClick={() => inject("sensor", { channel: "velocimeter", dropout: true })}>Velocimeter dropout</button>
            </div>
            <p className="text-[11px] text-muted mt-3">Hazards are written into the true terrain only; the lander must discover them through its sensors.</p>
          </Panel>
          {live?.site_status && <Panel eyebrow="Perception" title="Current site assessment">
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <Stat label="Safe" value={live.site_status.safe ? "yes" : live.site_status.covered ? "no" : "unsensed"} tone={live.site_status.safe ? "ok" : "bad"} />
              <Stat label="Score" value={fmt(live.site_status.score, 2)} />
              <Stat label="Slope" value={fmt(live.site_status.slope_deg, 1)} unit="°" />
              <Stat label="Max rock" value={fmt(live.site_status.max_rock_h, 2)} unit="m" />
            </div>
            {live.site_status.reasons?.length > 0 && <div className="text-[11.5px] text-danger mt-2">{live.site_status.reasons.join("; ")}</div>}
          </Panel>}
          {debrief.data?.result && <Panel eyebrow="Mission debrief" title={debrief.data.result.success ? "Landed safely" : `Outcome: ${debrief.data.result.outcome}`}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Landing error" value={fmt(debrief.data.result.landing_error_m, 2)} unit="m" />
              <Stat label="From original" value={fmt(debrief.data.result.distance_from_original_target_m, 1)} unit="m" />
              <Stat label="Touchdown vz" value={fmt(debrief.data.result.touchdown?.vertical_speed, 2)} unit="m/s" />
              <Stat label="Fuel used" value={fmt(debrief.data.result.fuel_used_kg, 1)} unit="kg" />
              <Stat label="Diversions" value={debrief.data.result.diversions} />
              <Stat label="Max est. error" value={fmt(debrief.data.result.max_position_estimation_error_m, 1)} unit="m" />
            </div>
            <a className="btn btn-ghost mt-4" href={api.url(`/api/runs/${debrief.data.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">Download PDF debrief</a>
          </Panel>}
          <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={live?.events || []} /></Panel>
        </div>
      </div>
    </div>
  );
}

const Legend = ({ c, t }: { c: string; t: string }) => <span className="inline-flex items-center gap-1.5"><span className="inline-block w-3 h-[3px] rounded" style={{ background: c }} />{t}</span>;
