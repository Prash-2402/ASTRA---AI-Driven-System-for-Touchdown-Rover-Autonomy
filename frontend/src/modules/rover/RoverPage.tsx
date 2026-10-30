import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { CamSwitch, Gauge, PhaseTimeline, Toggle } from "../../components/SimViewport";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import type { CamMode } from "../../visualization/lib/scene";
import type { Overlay } from "../../visualization/RoverScene";

const RoverScene = lazy(() => import("../../visualization/RoverScene"));
export const FAULTS: [string, string, string][] = [
  ["sensor_dropout", "Sensor dropout", "LiDAR + camera stop reporting for 45 s"],
  ["terrain_misclassification", "Terrain misclassification", "Invert 15 % of traversability cells"],
  ["power_drain", "Power-drain spike", "3× consumption + 60 W parasitic load"],
  ["actuator_degradation", "Actuator degradation", "Front-left wheel limited to 30 % torque"],
];
const WHEELS = ["FL", "ML", "RL", "FR", "MR", "RR"];
const EDL = ["POWERED DESCENT", "SKY CRANE", "TOUCHDOWN", "BRIDLE CUT", "FLYAWAY"];
const EDL_TEXT: Record<string, string> = {
  "POWERED DESCENT": "Eight throttleable engines decelerate the descent stage with the rover still bolted underneath. A velocity-profile controller tracks the commanded descent rate while nulling horizontal drift over the landing point on the crater floor.",
  "SKY CRANE": "At ~21 m the rover is lowered on three bridles and an umbilical (orange) while the stage descends at a constant 0.75 m/s. The rover hangs as a variable-length pendulum; its swing is computed from the stage's accelerations.",
  TOUCHDOWN: "The wheels touch the crater floor at 0.75 m/s. The stage senses the loss of bridle tension (its effective mass halves) and holds position for 0.7 s.",
  "BRIDLE CUT": "Pyrotechnic cutters sever the bridles and umbilical; the rover is now free and resting on its rocker-bogie suspension.",
  FLYAWAY: "The descent stage pitches 45° and departs at full throttle so it crashes far away from the rover.",
};

export default function RoverPage() {
  const live = useSim((s) => s.rover);
  const hist = useSim((s) => s.roverHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [landing, setLanding] = useState<any>(null);
  const [mode, setMode] = useState<"landing" | "traverse">("landing");
  const [lt, setLt] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [cam, setCam] = useState<CamMode>("cinematic");
  const [labels, setLabels] = useState(false);
  const [lidar, setLidar] = useState(true);
  const [overlay, setOverlay] = useState<Overlay>("none");
  const [err, setErr] = useState<string | null>(null);
  const [cfg, setCfg] = useState({ seed: 7, terrain: 1, controller: "astra", battery: 0.8, speed: 0.4 });
  const terrains = usePoll(() => api.get("/api/rover/terrain"), 0);
  const decisions = usePoll(() => api.get("/api/rover/decisions"), 2500, [live?.run_uid]);
  const costmap = usePoll(() => (overlay !== "none" && mode === "traverse" ? api.get("/api/rover/costmap") : Promise.resolve(null)), 2500, [overlay, mode, live?.run_uid]);

  useEffect(() => { api.get("/api/rover/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  useEffect(() => { api.get("/api/rover/config").then((c) => { const a = c.active; if (a) setCfg((x) => ({ ...x, seed: a.seed ?? x.seed, terrain: a.terrain ?? x.terrain, controller: a.controller ?? x.controller, battery: a.initial_battery ?? x.battery, speed: a.max_speed ?? x.speed })); }).catch(() => {}); }, [live?.run_uid]);
  useEffect(() => {
    if (!live?.run_uid) return;
    api.get("/api/rover/scene").then(setScene).catch((e) => setErr(e.message));
    api.get("/api/rover/landing").then((l) => { setLanding(l); setLt(0); }).catch((e) => setErr(e.message));
  }, [live?.run_uid]);
  useEffect(() => { if (live?.status === "running" || (live?.t ?? 0) > 0) { setMode("traverse"); setCam((c) => (c === "cinematic" ? "chase" : c)); } }, [live?.status]);
  // landing playback clock (render-side; the trajectory itself is precomputed physics)
  const raf = useRef(0);
  useEffect(() => {
    if (!playing || !landing) return;
    let last = performance.now();
    const tick = (now: number) => { const dt = (now - last) / 1000; last = now;
      setLt((t) => { const end = landing.frames[landing.frames.length - 1].t; const n = t + dt * rate; if (n >= end) { setPlaying(false); return end; } return n; });
      raf.current = requestAnimationFrame(tick); };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, landing, rate]);

  const configure = async () => {
    setErr(null);
    try { await api.post("/api/rover/config", { seed: cfg.seed, terrain: cfg.terrain, controller: cfg.controller, initial_battery: cfg.battery, max_speed: cfg.speed });
      ingest(await api.get("/api/rover/telemetry")); setMode("landing"); setCam("cinematic"); setPlaying(false); setLt(0); } catch (e: any) { setErr(e.message); }
  };
  const beginTraverse = async () => { try { await api.post("/api/rover/start", { speed: 4 }); setMode("traverse"); setCam("chase"); } catch (e: any) { setErr(e.message); } };
  const inject = async (ft: string) => { try { await api.post("/api/rover/faults", { fault_type: ft, duration: ft === "sensor_dropout" ? 45 : null }); } catch (e: any) { setErr(e.message); } };

  const f = live?.frame;
  const lf = landing ? landing.frames[Math.min(landing.frames.length - 1, Math.floor(lt / 0.05))] : null;
  const landed = lf && landing && lt >= landing.frames[landing.frames.length - 1].t - 0.01;
  const held = terrains.data?.find((t: any) => t.variant === cfg.terrain)?.split === "held_out";
  const n_lidar = (live as any)?.lidar?.length ?? 0;
  return (
    <div>
      <PageHeader eyebrow="Mars · crater-floor landing and autonomous traverse" title={<>Rover <em>Movement</em> Simulation</>}>
        <SimControls module="rover" status={live?.status} speed={live?.speed} />
      </PageHeader>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="panel px-5 py-3 mb-5 flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="seg">
          <button className={mode === "landing" ? "on" : ""} onClick={() => { setMode("landing"); setCam("cinematic"); }}>1 · Crater landing</button>
          <button className={mode === "traverse" ? "on" : ""} onClick={() => { setMode("traverse"); setCam("chase"); }}>2 · Traverse</button>
        </div>
        {mode === "landing" ? <PhaseTimeline phases={EDL} current={lf?.phase} /> :
          <PhaseTimeline phases={["LANDED", "NAVIGATING", live?.frame?.faults_active?.length ? "FAULT RESPONSE" : "NOMINAL OPS", "SCIENCE TARGET"]}
            current={live?.result ? "SCIENCE TARGET" : live?.frame?.faults_active?.length ? "FAULT RESPONSE" : live?.status === "running" ? "NAVIGATING" : "LANDED"}
            failed={!!live?.result && !live.result.success} />}
      </div>
      <div className="grid xl:grid-cols-[1fr_350px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="panel overflow-hidden relative" style={{ height: "66vh", minHeight: 460 }}>
            {scene ? <Suspense fallback={<div className="p-6 eyebrow">Loading Mars terrain…</div>}>
              <RoverScene snap={live} scene={scene} cam={cam} labels={labels} lidar={lidar} overlay={overlay} costmap={costmap.data} landing={landing} landingTime={lt} mode={mode} /></Suspense>
              : <div className="h-full grid place-items-center eyebrow">Loading Mars terrain…</div>}
            <div className="absolute top-3 left-3 right-3 flex flex-wrap justify-between gap-2">
              <CamSwitch value={cam} onChange={setCam} modes={[["chase", "Chase"], ["cinematic", "Orbit"], ["observer", "Ground observer"], ["overhead", "Overhead"], ["free", "Free"]]} />
              <div className="flex flex-wrap gap-2">
                <Toggle on={labels} onClick={() => setLabels(!labels)}>Components</Toggle>
                {mode === "traverse" && <Toggle on={lidar} onClick={() => setLidar(!lidar)}>LiDAR returns</Toggle>}
                {mode === "traverse" && <div className="seg hud !p-[3px]">{(["none", "cost", "slope"] as Overlay[]).map((o) => <button key={o} className={overlay === o ? "on" : ""} onClick={() => setOverlay(o)}>{o === "none" ? "No overlay" : o === "cost" ? "Cost gradient" : "Slope gradient"}</button>)}</div>}
              </div>
            </div>
            {mode === "landing" && landing && <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-end gap-3">
              <div className="hud p-3 w-[240px] space-y-2.5">
                <Gauge label="Descent-stage altitude" value={lf?.altitude ?? 0} max={130} unit="m" tone="var(--info)" />
                <Gauge label="Descent rate" value={-(lf?.ds_velocity?.[2] ?? 0)} max={20} unit="m/s" fmt={(v) => v.toFixed(2)} />
                <Gauge label="Throttle" value={(lf?.throttle ?? 0) * 100} max={100} unit="%" fmt={(v) => v.toFixed(0)} tone="var(--warning)" />
                <Gauge label="Bridle length" value={lf?.bridle ?? 0} max={7.5} unit="m" fmt={(v) => v.toFixed(2)} tone="#F2B35B" />
                <div className="num text-[10.5px] text-[var(--ink-secondary)]">swing {fmt(((lf?.swing?.[0] ?? 0) * 180) / Math.PI, 2)}° / {fmt(((lf?.swing?.[1] ?? 0) * 180) / Math.PI, 2)}°</div>
              </div>
              <div className="hud p-3 flex-1 min-w-[260px]">
                <div className="flex items-center gap-2 mb-2">
                  <button className="btn btn-primary !py-1.5" onClick={() => { if (landed) setLt(0); setPlaying(!playing); }}>{playing ? "❚❚ Pause" : landed ? "↺ Replay" : "▶ Play landing"}</button>
                  <button className="btn btn-ghost !py-1.5" onClick={() => { setLt(0); setPlaying(false); }}>⟲ Restart</button>
                  <select className="select !w-auto !py-1" value={rate} onChange={(e) => setRate(+e.target.value)}>{[0.5, 1, 2, 4].map((r) => <option key={r} value={r}>{r}×</option>)}</select>
                  {landed && <button className="btn btn-sage !py-1.5 ml-auto" onClick={beginTraverse}>Begin traverse →</button>}
                </div>
                <input type="range" className="w-full accent-[var(--primary)]" min={0} max={landing.frames[landing.frames.length - 1].t} step={0.05} value={lt} onChange={(e) => { setLt(+e.target.value); setPlaying(false); }} />
                <div className="text-[11.5px] text-[var(--ink-secondary)] mt-1.5 leading-relaxed"><span className="text-[var(--primary)] font-medium">{lf?.phase}</span> · t = {fmt(lt, 1)} s — {EDL_TEXT[lf?.phase ?? "POWERED DESCENT"]}</div>
              </div>
            </div>}
            {mode === "traverse" && overlay !== "none" && <div className="absolute bottom-3 left-3 hud px-3 py-2 text-[11px] text-[var(--ink-secondary)]">
              <div className="h-2 w-48 rounded" style={{ background: "linear-gradient(90deg,#2a9d8f,#f2b35b,#e63946)" }} />
              <div className="flex justify-between w-48 mt-1"><span>{overlay === "cost" ? "low cost" : "0°"}</span><span>{overlay === "cost" ? "high · red = hard constraint" : "25°+"}</span></div>
              <div className="mt-1 text-[10.5px]">The planner's own perceived map — not ground truth.</div></div>}
            <div className="absolute bottom-3 right-3 text-[10px] text-[var(--muted)] hud px-2 py-1 hidden md:block">Crater walls beyond the 60 m arena are context terrain (visual only).</div>
          </div>
          {mode === "traverse" && f && <Panel eyebrow="How the components interact (live)" title="Sense → Estimate → Plan → Act → Verify">
            <div className="grid sm:grid-cols-5 gap-2">
              {[["Sense", `${n_lidar} lidar returns · camera ${f.evidence?.camera_stale < 1 ? "live" : "stale"} · IMU · odometry`, f.faults_active.includes("sensor_dropout") ? "bad" : ""],
                ["Estimate", `EKF σ ${fmt(f.estimate.pos_sigma, 2)} m · error ${fmt(f.error.position, 2)} m · slip ${fmt(f.slip, 2)}`, ""],
                ["Plan", `A* route ${fmt(live?.planned_path?.length, 0)} cells · ${live?.path_history?.length ?? 0} recent replans`, ""],
                ["Act", `v ${fmt(f.controller?.v, 2)} m/s · ω ${fmt(f.controller?.w, 2)} rad/s · τ ${f.wheels.torque.map((x: number) => x.toFixed(1)).join(" ")}`, ""],
                ["Verify", `safety: ${f.safety.action}${f.safety.reasons[0] ? " — " + f.safety.reasons[0] : ""} · policy: ${f.policy}`, f.safety.action !== "continue" ? "warn" : ""]].map(([k, v, tone], i) => (
                <div key={k} className="relative rounded-[12px] border p-3" style={{ borderColor: tone === "bad" ? "var(--danger)" : tone === "warn" ? "var(--warning)" : "var(--border)", background: "var(--ivory)" }}>
                  <div className="eyebrow !text-[9.5px] text-[var(--primary)]">0{i + 1} · {k}</div>
                  <div className="text-[11.5px] text-[var(--ink-secondary)] mt-1.5 leading-snug break-words">{v}</div>
                </div>))}
            </div>
          </Panel>}
          {mode === "traverse" && (f ? <div className="grid md:grid-cols-2 gap-5">
            <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ"><ErrorVsSigma data={hist} err="err" sig="sig" /></Panel>
            <Panel eyebrow="Estimator" title="Heading error vs ±2σ"><ErrorVsSigma data={hist} err="herr" sig="hsig" title="|heading error| [rad]" /></Panel>
            <Panel eyebrow="Energy" title="State of charge & power"><Series data={hist} lines={[{ key: "soc", name: "SoC" }]} height={140} /><Series data={hist} lines={[{ key: "power", name: "power [W]", color: "#F08C00" }]} height={140} /></Panel>
            <Panel eyebrow="Mobility" title="Speed & wheel slip"><Series data={hist} lines={[{ key: "speed", name: "speed [m/s]" }, { key: "slip", name: "slip est.", color: "#E03131" }]} /></Panel>
          </div> : <Empty title="Rover on the crater floor">Play the landing, then begin the traverse.</Empty>)}
          <Panel eyebrow="Explainability" title="Decision audit log"><DecisionLog decisions={decisions.data || []} /></Panel>
        </div>
        <div className="space-y-5">
          {mode === "landing" && landing?.touchdown && <Panel eyebrow="Landing dynamics" title="Sky-crane result">
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Touchdown speed" value={fmt(Math.abs(landing.touchdown.vertical_speed), 2)} unit="m/s" />
              <Stat label="Landing error" value={fmt(landing.touchdown.error_m * 100, 1)} unit="cm" />
              <Stat label="Swing at contact" value={landing.touchdown.swing_deg.map((v: number) => v.toFixed(2)).join(" / ")} unit="°" />
              <Stat label="Touchdown at" value={fmt(landing.touchdown.t, 1)} unit="s" />
              <Stat label="Rover mass" value={landing.parameters.rover_mass} unit="kg" />
              <Stat label="Bridle" value={landing.parameters.bridle_max} unit="m" />
            </div>
            <p className="text-[11px] text-muted mt-3">Pendulum with moving pivot and varying length, integrated at 200 Hz (simulation/rover/skycrane.py).</p>
          </Panel>}
          <Panel eyebrow="Telemetry" title="Rover state">
            {f ? <>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Position (truth)" value={`${fmt(f.truth.position[0], 1)}, ${fmt(f.truth.position[1], 1)}`} unit="m" sub={`EKF ${fmt(f.estimate.position[0], 1)}, ${fmt(f.estimate.position[1], 1)}`} />
                <Stat label="Speed" value={fmt(f.truth.speed, 2)} unit="m/s" sub={`EKF v ${fmt(f.estimate.v, 2)}`} />
                <Stat label="Heading" value={fmt((f.truth.rpy[2] * 180) / Math.PI, 0)} unit="°" sub={`EKF ${fmt((f.estimate.heading * 180) / Math.PI, 0)}°`} />
                <Stat label="Roll / pitch" value={`${fmt((f.truth.rpy[0] * 180) / Math.PI, 1)} / ${fmt((f.truth.rpy[1] * 180) / Math.PI, 1)}`} unit="°" />
                <Stat label="Battery" value={fmt(f.battery.soc * 100, 1)} unit="%" tone={f.battery.soc < 0.22 ? "warn" : undefined} sub={`${fmt(f.battery.voltage, 1)} V · ${fmt(f.battery.current, 2)} A`} />
                <Stat label="Power" value={fmt(f.battery.power, 0)} unit="W" sub={`${fmt(f.battery.energy_used_wh, 2)} Wh used`} />
              </div>
              <div className="mt-4">
                <div className="eyebrow !text-[10px] mb-1.5">Wheels — torque [N m] · health estimate</div>
                <div className="grid grid-cols-6 gap-1 text-center">
                  {WHEELS.map((w, i) => <div key={w} className="rounded-[8px] py-1.5" style={{ background: "var(--ivory)" }}>
                    <div className="text-[10px] text-muted">{w}</div><div className="num text-[12px]">{fmt(f.wheels.torque[i], 1)}</div>
                    <div className={`num text-[10px] ${f.wheels.health_est[i] < 0.9 ? "text-danger" : "text-muted"}`}>{fmt(f.wheels.health_est[i], 2)}</div></div>)}
                </div>
                <div className="mt-3 text-[10.5px] text-muted">Rocker L/R {fmt(f.wheels.joints.rocker_L_joint, 3)} / {fmt(f.wheels.joints.rocker_R_joint, 3)} rad · bogie L/R {fmt(f.wheels.joints.bogie_L_joint, 3)} / {fmt(f.wheels.joints.bogie_R_joint, 3)} rad</div>
              </div>
              {f.classification.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{f.classification.map((c) => <span key={c} className="chip">{c}</span>)}</div>}
            </> : <div className="text-[12px] text-muted">Traverse not started.</div>}
          </Panel>
          <Panel eyebrow="Live fault injection" title="Four primary faults">
            <div className="grid gap-2">
              {FAULTS.map(([id, name, desc]) => (
                <button key={id} className="text-left rounded-[12px] border px-3 py-2.5 hover:bg-[var(--sage-soft)] disabled:opacity-40" style={{ borderColor: "var(--border)" }} disabled={live?.status !== "running"} onClick={() => inject(id)}>
                  <div className="text-[13px] font-medium">{name}</div><div className="text-[11px] text-muted">{desc}</div>
                </button>))}
            </div>
            <p className="text-[11px] text-muted mt-3">Faults change the simulated sensors, battery or wheel physics. The autonomy stack is not told a fault exists.</p>
          </Panel>
          <Panel eyebrow="Mission configuration" title="Landing site & traverse">
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
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={configure}>Apply & reset mission</button>
          </Panel>
          {live?.result && <Panel eyebrow="Mission result" title={live.result.success ? "Science target reached" : `Outcome: ${live.result.outcome}`}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Time" value={fmt(live.result.mission_time_s, 0)} unit="s" /><Stat label="Energy" value={fmt(live.result.energy_used_wh, 2)} unit="Wh" />
              <Stat label="Route" value={fmt(live.result.route_length_m, 1)} unit="m" /><Stat label="Collisions" value={live.result.collisions} />
            </div>
            <a className="btn btn-ghost mt-4" href={api.url(`/api/runs/${live.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">Download PDF debrief</a>
          </Panel>}
          <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={mode === "landing" ? (landing?.events || []).filter((e: any) => e.t <= lt) : live?.events || []} /></Panel>
        </div>
      </div>
    </div>
  );
}
