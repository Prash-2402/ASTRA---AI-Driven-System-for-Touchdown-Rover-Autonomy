import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { CamSwitch, Gauge, PhaseTimeline, Toggle } from "../../components/SimViewport";
import type { CamMode } from "../../visualization/lib/scene";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

const TouchdownScene = lazy(() => import("../../visualization/TouchdownScene"));
const deg = (r: number) => (r * 180) / Math.PI;
const PHASES = ["ENTRY", "DESCENT", "LANDING APPROACH", "SITE ASSESSMENT", "DIVERSION", "TOUCHDOWN", "MISSION COMPLETE"];
const EXPLAIN: Record<string, string> = {
  ENTRY: "Unpowered coast: the main engine is off; RCS thrusters hold the lander vertical while it falls through the thin Martian atmosphere. The relay orbiter overhead receives telemetry.",
  DESCENT: "Powered descent: the main engine fires and the guidance law (PID, MPC or PPO) commands an acceleration. The attitude loop tilts the lander so its thrust points along that command; lateral thrusters trim the remainder.",
  "LANDING APPROACH": "Approach toward the target. The EKF fuses IMU, radar altimeter, Doppler velocimeter and terrain-relative navigation; the dashed amber curve is the predicted touchdown trajectory from the estimated state.",
  "SITE ASSESSMENT": "Close-range lidar (blue cone) maps slopes and boulders the orbital map could not resolve. The target footprint, plus a margin from position uncertainty, is checked against slope, rock and roughness limits.",
  DIVERSION: "The target was assessed unsafe. Candidate sites were scored (colour gradient: green = best) and checked for fuel and control authority; the lander physically flies to the selected site.",
  TOUCHDOWN: "Footpad contact. The vertical and horizontal speeds, tilt, slope and rock clearance at the real contact point decide success.",
  "MISSION COMPLETE": "Landed within all limits. The decision audit records the evidence behind every diversion and its actual outcome.",
  FAILED: "A touchdown limit was violated — see the debrief.", ABORT: "No feasible safe site: the lander set down at the least-hazardous reachable point.",
};

export default function TouchdownPage() {
  const live = useSim((s) => s.touchdown);
  const hist = useSim((s) => s.tdHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [cam, setCam] = useState<CamMode>("chase");
  const [labels, setLabels] = useState(false);
  const [overlay, setOverlay] = useState<"none" | "slope" | "hazard">("none");
  const [paths, setPaths] = useState(true);
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
  useEffect(() => { if (live?.diversions || overlay === "hazard") api.get("/api/touchdown/scene").then(setScene).catch(() => {}); }, [live?.diversions, overlay, live?.phase]);

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
      <PageHeader eyebrow="Mars · entry, descent & autonomous landing" title={<>Touchdown <em>Simulation</em></>}>
        <SimControls module="touchdown" status={live?.status} speed={live?.speed} />
      </PageHeader>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="panel px-5 py-3.5 mb-5"><PhaseTimeline phases={live?.phase === "FAILED" || live?.phase === "ABORT" ? [...PHASES.slice(0, 6), live.phase] : PHASES} current={live?.phase} failed={live?.phase === "FAILED"} /></div>
      <div className="grid xl:grid-cols-[1fr_340px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="panel overflow-hidden relative" style={{ height: "66vh", minHeight: 460 }}>
            {scene ? <Suspense fallback={<div className="p-6 eyebrow">Loading Mars terrain…</div>}>
              <TouchdownScene snap={live} scene={scene} decisions={decisions.data || []} cam={cam} labels={labels} overlay={overlay} showPaths={paths} /></Suspense>
              : <div className="h-full grid place-items-center eyebrow">Loading Mars terrain…</div>}
            <div className="absolute top-3 left-3 right-3 flex flex-wrap justify-between gap-2">
              <CamSwitch value={cam} onChange={setCam} modes={[["chase", "Chase"], ["observer", "Ground observer"], ["orbiter", "From orbit"], ["overhead", "Overhead"], ["cinematic", "Orbit"], ["free", "Free"]]} />
              <div className="flex flex-wrap gap-2">
                <Toggle on={labels} onClick={() => setLabels(!labels)}>Components</Toggle>
                <Toggle on={paths} onClick={() => setPaths(!paths)}>Trajectories</Toggle>
                <div className="seg hud !p-[3px]">{([["none", "No overlay"], ["slope", "Slope gradient"], ["hazard", "Lidar hazard map"]] as const).map(([o, l]) =>
                  <button key={o} className={overlay === o ? "on" : ""} onClick={() => setOverlay(o)}>{l}</button>)}</div>
              </div>
            </div>
            {f && <div className="absolute bottom-3 left-3 hud p-3 w-[240px] space-y-2.5">
              <Gauge label="Altitude AGL" value={f.truth.agl} max={3000} unit="m" fmt={(v) => v.toFixed(v < 100 ? 1 : 0)} tone="var(--info)" />
              <Gauge label="Vertical speed" value={-f.truth.velocity[2]} max={100} unit="m/s" fmt={(v) => v.toFixed(2)} />
              <Gauge label="Throttle" value={f.actuators.throttle * 100} max={100} unit="%" fmt={(v) => v.toFixed(0)} tone="var(--warning)" />
              <Gauge label="Fuel" value={f.truth.fuel} max={450} unit="kg" fmt={(v) => v.toFixed(0)} tone={f.truth.fuel < 60 ? "var(--danger)" : "var(--success)"} />
              <Gauge label="Tilt" value={f.truth.tilt_deg} max={30} unit="°" />
            </div>}
            {live?.phase && <div className="absolute bottom-3 right-3 hud p-3 max-w-[360px] text-[12px] leading-relaxed text-[var(--ink-secondary)] hidden md:block">
              <div className="eyebrow !text-[9.5px] mb-1 text-[var(--primary)]">What is happening · {live.phase}</div>{EXPLAIN[live.phase] ?? ""}
              <div className="mt-2 text-[10.5px] text-[var(--muted)]">Relay orbiter drawn far closer than its ~300 km orbit.</div></div>}
          </div>
          {!f ? <Empty title="No descent configured">Configure a mission on the right and press Start.</Empty> : (
            <div className="grid md:grid-cols-2 gap-5">
              <Panel eyebrow="Truth vs estimate" title="Altitude & vertical speed"><Series data={hist} lines={[{ key: "agl", name: "AGL truth [m]" }, { key: "agl_est", name: "AGL EKF [m]", dashed: true }]} /></Panel>
              <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ (east axis)"><ErrorVsSigma data={hist} err="err_x" sig="sig_x" /></Panel>
              <Panel eyebrow="Propulsion" title="Throttle & tilt"><Series data={hist} lines={[{ key: "throttle", name: "throttle [0-1]" }, { key: "tilt", name: "tilt [deg]", color: "#F08C00" }]} /></Panel>
              <Panel eyebrow="Resources" title="Fuel & vertical velocity"><Series data={hist} lines={[{ key: "fuel", name: "fuel [kg]" }, { key: "vz", name: "vz truth [m/s]", color: "#12B886" }, { key: "vz_est", name: "vz EKF", dashed: true, color: "#E03131" }]} /></Panel>
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


