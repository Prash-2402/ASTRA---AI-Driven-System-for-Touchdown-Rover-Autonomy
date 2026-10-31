import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { CamSwitch, PhaseTimeline, Toggle } from "../../components/SimViewport";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import type { CamMode } from "../../visualization/lib/scene";
import type { Overlay } from "../../visualization/RoverScene";

const RoverScene = lazy(() => import("../../visualization/RoverScene"));
export const FAULTS: [string, string, string][] = [
  ["actuator_degradation", "Wheel damage", "Front-left wheel limited to 30 % torque"],
  ["sensor_dropout", "Sensor dropout", "LiDAR + camera stop reporting for 45 s"],
  ["terrain_misclassification", "Terrain misclassification", "Invert 15 % of traversability cells"],
  ["power_drain", "Power-drain spike", "3× consumption + 60 W parasitic load"],
];
const WHEELS = ["FL", "ML", "RL", "FR", "MR", "RR"];
const TASK_KINDS: [string, string, string][] = [["collect_sample", "Collect rock sample", "#c084fc"], ["collect_sand", "Collect sand", "#f2b35b"], ["capture_image", "Capture images", "#38bdf8"]];
const MODES = ["DEPLOYED", "TRANSIT", "WORKING", "RETURNING", "SHELTERING", "COMPLETE"];
const MODE_TEXT: Record<string, string> = {
  DEPLOYED: "The rover stands beside the landed lander. It plans every leg itself from its own lidar and camera map — the ground only observes.",
  TRANSIT: "Driving to the next task site: A* over the perceived cost map, Pure Pursuit wheel control. A newly perceived obstacle that blocks the route triggers an immediate re-plan.",
  WORKING: "At the site: the arm collects the sample / the mast camera images the target. The rover holds still for the task duration.",
  RETURNING: "Returning to the lander — either because the task list is done, or because the onboard decision layer judged it necessary (dust storm, damage, energy).",
  SHELTERING: "Parked beside the lander and staying there until the hazard clears (dust optical depth below 2.0), then it resumes the remaining tasks on its own.",
  COMPLETE: "All tasks finished and the rover is parked beside the lander.",
};

export default function RoverPage() {
  const live = useSim((s) => s.rover);
  const hist = useSim((s) => s.roverHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [cam, setCam] = useState<CamMode>("chase");
  const stage = useRef<HTMLDivElement>(null);
  const [fs, setFs] = useState(false);
  useEffect(() => { const h = () => setFs(document.fullscreenElement === stage.current); document.addEventListener("fullscreenchange", h); return () => document.removeEventListener("fullscreenchange", h); }, []);
  const toggleFs = () => { if (document.fullscreenElement) document.exitFullscreen(); else stage.current?.requestFullscreen?.(); };
  const [labels, setLabels] = useState(false);
  const [lidar, setLidar] = useState(true);
  const [overlay, setOverlay] = useState<Overlay>("none");
  const [placing, setPlacing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cfg, setCfg] = useState({ seed: 7, terrain: 1, controller: "astra", battery: 0.8, speed: 0.6, kinds: TASK_KINDS.map((k) => k[0]) });
  const [envp, setEnvp] = useState({ sandstorm: 0, wind_speed: 4, comms: true });
  const terrains = usePoll(() => api.get("/api/rover/terrain"), 0);
  const decisions = usePoll(() => api.get("/api/rover/decisions"), 2500, [live?.run_uid]);
  const costmap = usePoll(() => (overlay !== "none" ? api.get("/api/rover/costmap") : Promise.resolve(null)), 2500, [overlay, live?.run_uid]);
  const ops = (live as any)?.ops;

  const configure = async (c = cfg) => {
    setErr(null);
    try {
      await api.post("/api/rover/config", { seed: c.seed, terrain: c.terrain, controller: c.controller, initial_battery: c.battery, max_speed: c.speed,
        ground_ops: true, task_kinds: c.kinds });
      if (envp.sandstorm > 0 || !envp.comms || envp.wind_speed !== 4) await api.post("/api/rover/environment", envp);
      ingest(await api.get("/api/rover/telemetry")); setScene(await api.get("/api/rover/scene"));
    } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { api.get("/api/rover/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  // this page always runs surface operations; switch the backend session over if it holds a plain traverse
  useEffect(() => { api.get("/api/rover/config").then((c) => { const a = c.active;
    if (a) setCfg((x) => ({ ...x, seed: a.seed ?? x.seed, terrain: a.terrain ?? x.terrain, controller: a.controller ?? x.controller, battery: a.initial_battery ?? x.battery, speed: a.max_speed ?? x.speed, kinds: a.task_kinds?.length ? a.task_kinds : x.kinds }));
    if (!a?.ground_ops) configure(); }).catch(() => {}); }, []); // eslint-disable-line
  useEffect(() => { if (live?.run_uid) api.get("/api/rover/scene").then(setScene).catch((e) => setErr(e.message)); }, [live?.run_uid]);
  useEffect(() => { const e = (live as any)?.environment; if (e) setEnvp(e); }, [live?.run_uid]); // eslint-disable-line

  const inject = async (ft: string) => { try { await api.post("/api/rover/faults", { fault_type: ft, duration: ft === "sensor_dropout" ? 45 : null }); } catch (e: any) { setErr(e.message); } };
  const pushEnv = async (p: Partial<typeof envp>) => { const n = { ...envp, ...p }; setEnvp(n); try { await api.post("/api/rover/environment", n); } catch (e: any) { setErr(e.message); } };
  const place = async (x: number, y: number) => {
    try { const r = await api.post("/api/rover/obstacle", { x, y, radius: 0.6 }); setScene(await api.get("/api/rover/scene"));
      setNote(r.on_route ? "Obstacle placed ON the planned route — watch the rover perceive it with lidar and re-plan." : "Obstacle placed off the current route.");
    } catch (e: any) { setNote(`Not placed: ${e.message}`); }
    setTimeout(() => setNote(null), 6000);
  };
  const dropOnRoute = () => {
    const p = live?.planned_path, pos = live?.frame?.estimate.position;
    if (!p?.length || !pos) { setNote("No planned route yet — press Start first."); return; }
    let k = 0, best = 1e9; p.forEach((q, i) => { const d = Math.hypot(q[0] - pos[0], q[1] - pos[1]); if (d < best) { best = d; k = i; } });
    const q = p[Math.min(p.length - 1, k + 7)]; place(q[0], q[1]);
  };

  const f = live?.frame;
  const held = terrains.data?.find((t: any) => t.variant === cfg.terrain)?.split === "held_out";
  const n_lidar = (live as any)?.lidar?.length ?? 0;
  const mode = ops ? (live?.status === "idle" && (live?.t ?? 0) === 0 ? "DEPLOYED" : ops.mode) : "DEPLOYED";
  const env = (live as any)?.environment || envp;
  return (
    <div>
      <PageHeader eyebrow="Mars surface · after landing · fully autonomous" title={<>Rover <em>Ground</em> Operations</>}>
        <SimControls module="rover" status={live?.status} speed={live?.speed} />
      </PageHeader>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="panel px-5 py-3 mb-5"><PhaseTimeline phases={mode === "SHELTERING" ? MODES : MODES.filter((m) => m !== "SHELTERING")} current={mode} failed={!!live?.result && !live.result.success} /></div>
      <div className="grid xl:grid-cols-[1fr_350px] gap-5">
        <div className="space-y-5 min-w-0">
          <div ref={stage} className="panel overflow-hidden relative" style={{ height: fs ? "100vh" : "66vh", minHeight: 460, borderRadius: fs ? 0 : undefined }}>
            {scene ? <Suspense fallback={<div className="p-6 eyebrow">Loading Mars terrain…</div>}>
              <RoverScene snap={live} scene={scene} cam={cam} labels={labels} lidar={lidar} overlay={overlay} costmap={costmap.data} placing={placing} onPlace={place} /></Suspense>
              : <div className="h-full grid place-items-center eyebrow">Loading Mars terrain…</div>}
            {/* overlay laid out in flow: toolbar, notices below it, HUD row at the bottom - nothing covers a button */}
            <div className="absolute inset-3 flex flex-col gap-2 pointer-events-none">
              <div className="flex flex-wrap justify-between gap-2 pointer-events-auto">
                <CamSwitch value={cam} onChange={setCam} modes={[["chase", "Chase"], ["cinematic", "Orbit"], ["observer", "Lander view"], ["overhead", "Overhead"], ["free", "Free"]]} />
                <div className="flex flex-wrap gap-2">
                  <button className="hud px-3 py-1.5 text-[11.5px] text-[var(--danger)]" onClick={dropOnRoute}>⚠ Drop obstacle on route</button>
                  <button className={`hud px-3 py-1.5 text-[11.5px] ${placing ? "!bg-[var(--danger)] !text-white" : "text-[var(--ink-secondary)]"}`} onClick={() => setPlacing(!placing)}>{placing ? "● Click the ground · done" : "＋ Place obstacles by clicking"}</button>
                  <button className="hud px-3 py-1.5 text-[11.5px] text-[var(--ink-secondary)]" onClick={toggleFs}>{fs ? "⤡ Exit fullscreen" : "⛶ Fullscreen"}</button>
                  <Toggle on={labels} onClick={() => setLabels(!labels)}>Components</Toggle>
                  <Toggle on={lidar} onClick={() => setLidar(!lidar)}>LiDAR</Toggle>
                  <div className="seg hud !p-[3px]">{(["none", "cost", "slope"] as Overlay[]).map((o) => <button key={o} className={overlay === o ? "on" : ""} onClick={() => setOverlay(o)}>{o === "none" ? "No overlay" : o === "cost" ? "Cost" : "Slope"}</button>)}</div>
                </div>
              </div>
              {fs && <div className="self-end hud px-2 py-1 pointer-events-auto"><SimControls module="rover" status={live?.status} speed={live?.speed} /></div>}
              <div className="flex flex-col gap-2 max-w-[440px] min-h-0 overflow-hidden">
                {!env.comms && <div className="rounded-[10px] px-3 py-2 text-[11px]" style={{ background: "rgba(30,41,59,.88)", color: "#fff", border: "1px solid rgba(148,163,184,.6)" }}>
                  <b>✕ COMMS LOST</b> — the rover continues autonomously; this view is the simulator's, the ground would only see buffered telemetry later.</div>}
                {env.sandstorm > 0.05 && <div className="rounded-[10px] px-3 py-2 text-[11px]" style={{ background: "rgba(120,53,15,.85)", color: "#fff" }}>
                  DUST STORM {fmt(env.sandstorm, 2)} · rover-measured optical depth τ = {fmt(ops?.dust_optical_depth, 1)} (returns to the lander above 3.5)</div>}
                {ops?.mode === "SHELTERING" && <div className="hud px-3 py-2 text-[11px] text-[var(--warning)]">Sheltering at the lander ({ops.shelter_reason})</div>}
{note && <div className="hud px-3 py-2 text-[11px] text-ink">{note}</div>}
              </div>
              <div className="mt-auto flex items-end justify-between gap-2">
                {overlay !== "none" ? <div className="hud px-3 py-2 text-[11px] text-[var(--ink-secondary)] shrink-0">
                  <div className="h-2 w-48 rounded" style={{ background: overlay === "cost" ? "linear-gradient(90deg,#2a9d8f,#f2b35b)" : "linear-gradient(90deg,#2a9d8f,#f2b35b,#e63946)" }} />
                  <div className="flex justify-between w-48 mt-1"><span>{overlay === "cost" ? "easy" : "0°"}</span><span>{overlay === "cost" ? "costly, still drivable" : "25°+"}</span></div>
                  {overlay === "cost" && <div className="flex items-center gap-1.5 mt-1"><span className="inline-block w-3 h-2 rounded-sm" style={{ background: "#e63946" }} />blocked (rock + safety margin, too steep)</div>}
                  <div className="mt-1 text-[10.5px]">The planner's own perceived map — not ground truth.</div></div>
                : <div className="hud px-3 py-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-[var(--ink-secondary)] min-w-0">
                  <span className="flex items-center gap-1.5"><span className="inline-block w-4 h-[3px] rounded bg-[#6FD3A8]" />Planned route</span>
                  <span className="flex items-center gap-1.5"><span className="inline-block w-4 h-[3px] rounded bg-white border" />Driven path</span>
                  <span className="flex items-center gap-1.5"><span className="inline-block w-4 h-[3px] rounded bg-[#6FD3A8] opacity-40" />Earlier routes (re-plans)</span>
                  {TASK_KINDS.map(([k, l, c]) => <span key={k} className="flex items-center gap-1.5"><span className="inline-block w-2 h-2 rotate-45" style={{ background: c }} />{l}</span>)}</div>}
                {mode && <div className="hud p-3 max-w-[340px] shrink text-[12px] leading-relaxed text-[var(--ink-secondary)] hidden md:block">
                  <div className="eyebrow !text-[9.5px] mb-1 text-[var(--primary)]">Rover is · {mode}</div>{MODE_TEXT[mode]}</div>}
              </div>
            </div>
          </div>
          {f && <Panel eyebrow="How the components interact (live)" title="Sense → Estimate → Plan → Decide → Act">
            <div className="grid sm:grid-cols-5 gap-2">
              {[["Sense", `${n_lidar} lidar returns · camera ${f.evidence?.camera_stale < 1 ? "live" : "stale"} · τ ${fmt(ops?.dust_optical_depth, 1)}`, f.faults_active.includes("sensor_dropout") || env.sandstorm > 0.5 ? "bad" : ""],
                ["Estimate", `EKF σ ${fmt(f.estimate.pos_sigma, 2)} m · error ${fmt(f.error.position, 2)} m · slip ${fmt(f.slip, 2)}`, ""],
                ["Plan", `A* route ${fmt(live?.planned_path?.length, 0)} cells · ${live?.path_history?.length ?? 0} recent re-plans`, ""],
                ["Decide", `mode ${ops?.mode ?? "—"} · ${ops?.tasks?.filter((t: any) => t.status === "done").length ?? 0}/${ops?.tasks?.length ?? 0} tasks · comms ${env.comms ? "up" : "LOST"}`, ops?.mode === "RETURNING" || ops?.mode === "SHELTERING" ? "warn" : ""],
                ["Act", `v ${fmt(f.controller?.v, 2)} m/s · safety: ${f.safety.action}${f.safety.reasons[0] ? " — " + f.safety.reasons[0] : ""}`, f.safety.action !== "continue" ? "warn" : ""]].map(([k, v, tone], i) => (
                <div key={k} className="relative rounded-[12px] border p-3" style={{ borderColor: tone === "bad" ? "var(--danger)" : tone === "warn" ? "var(--warning)" : "var(--border)", background: "var(--ivory)" }}>
                  <div className="eyebrow !text-[9.5px] text-[var(--primary)]">0{i + 1} · {k}</div>
                  <div className="text-[11.5px] text-[var(--ink-secondary)] mt-1.5 leading-snug break-words">{v}</div>
                </div>))}
            </div>
          </Panel>}
          {f ? <div className="grid md:grid-cols-2 gap-5">
            <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ"><ErrorVsSigma data={hist} err="err" sig="sig" /></Panel>
            <Panel eyebrow="Energy" title="State of charge & power"><Series data={hist} lines={[{ key: "soc", name: "SoC" }]} height={140} /><Series data={hist} lines={[{ key: "power", name: "power [W]", color: "#C77D12" }]} height={140} /></Panel>
            <Panel eyebrow="Mobility" title="Speed & wheel slip"><Series data={hist} lines={[{ key: "speed", name: "speed [m/s]" }, { key: "slip", name: "slip est.", color: "#C0392B" }]} /></Panel>
            <Panel eyebrow="Estimator" title="Heading error vs ±2σ"><ErrorVsSigma data={hist} err="herr" sig="hsig" title="|heading error| [rad]" /></Panel>
          </div> : <Empty title="Rover deployed beside the lander">Press Start — the rover will plan and drive to its tasks on its own.</Empty>}
          <Panel eyebrow="Explainability" title="Autonomous decision log"><DecisionLog decisions={decisions.data || []} /></Panel>
        </div>
        <div className="space-y-5">
          <Panel eyebrow="Mission" title="Surface tasks">
            {ops?.tasks?.length ? <ol className="space-y-2">{ops.tasks.map((k: any) => (
              <li key={k.id} className="flex items-center gap-3 rounded-[12px] border px-3 py-2" style={{ borderColor: k.status === "active" || k.status === "working" ? "var(--primary)" : "var(--border)" }}>
                <span className="inline-block w-2.5 h-2.5 rotate-45 shrink-0" style={{ background: TASK_KINDS.find((t) => t[0] === k.kind)?.[2] }} />
                <div className="flex-1 min-w-0"><div className="text-[13px] text-ink">{k.label}</div><div className="text-[10.5px] text-muted num">({fmt(k.x, 1)}, {fmt(k.y, 1)}) · {fmt(k.duration, 0)} s</div></div>
                <span className={`chip ${k.status === "done" ? "!text-white !bg-[var(--success)]" : k.status === "skipped" ? "opacity-60" : ""}`}>{k.status}</span>
              </li>))}
              <li className="flex items-center gap-3 rounded-[12px] border px-3 py-2" style={{ borderColor: ops.mode === "RETURNING" ? "var(--primary)" : "var(--border)" }}>
                <span className="inline-block w-2.5 h-2.5 rounded-full shrink-0 bg-[#e5e7eb] border" /><div className="flex-1 text-[13px] text-ink">Return to the lander</div>
                <span className="chip">{ops.mode === "COMPLETE" ? "done" : ops.mode === "RETURNING" || ops.mode === "SHELTERING" ? ops.mode.toLowerCase() : "last"}</span></li>
            </ol> : <div className="text-[12px] text-muted">Configuring surface operations…</div>}
            <p className="text-[11px] text-muted mt-3">Sites were chosen from orbital data before the sol (sand patch, bedrock outcrop, far vista). Order, re-plans, skips and returns are decided onboard.</p>
          </Panel>
          <Panel eyebrow="Environment · live" title="Storms, wind & comms">
            {([["sandstorm", "Dust storm intensity", 0, 1, 0.05, ""], ["wind_speed", "Wind speed", 0, 35, 1, "m/s"]] as const).map(([k, l, lo, hi, st, u]) => (
              <label key={k} className="block mb-3">
                <div className="flex justify-between text-[11.5px] text-ink2"><span>{l}</span><span className="num text-ink">{fmt((envp as any)[k], k === "sandstorm" ? 2 : 0)} {u}</span></div>
                <input type="range" className="w-full accent-[var(--primary)]" min={lo} max={hi} step={st} value={(envp as any)[k]}
                  onChange={(e) => setEnvp({ ...envp, [k]: +e.target.value })} onPointerUp={(e) => pushEnv({ [k]: +(e.target as HTMLInputElement).value })} onKeyUp={(e) => pushEnv({ [k]: +(e.target as HTMLInputElement).value })} />
              </label>))}
            <label className="flex items-center gap-2 text-[12.5px]"><input type="checkbox" checked={!envp.comms} onChange={(e) => pushEnv({ comms: !e.target.checked })} /> Loss of communication signal</label>
            <p className="text-[11px] text-muted mt-3">The storm degrades lidar range/noise, camera classification and visual localisation; the rover infers it from its own sky-brightness (optical-depth) measurement. Martian wind (ρ ≈ 0.02 kg/m³) pushes only a few newtons even in a storm.</p>
          </Panel>
          <Panel eyebrow="Damage & faults" title="Inject onboard problems">
            <div className="grid gap-2">
              {FAULTS.map(([id, name, desc]) => (
                <button key={id} className="text-left rounded-[12px] border px-3 py-2.5 hover:bg-[var(--sage-soft)] disabled:opacity-40" style={{ borderColor: "var(--border)" }} disabled={live?.status !== "running"} onClick={() => inject(id)}>
                  <div className="text-[13px] font-medium">{name}</div><div className="text-[11px] text-muted">{desc}</div>
                </button>))}
            </div>
            <p className="text-[11px] text-muted mt-3">The rover is not told about faults. Wheel damage below 50 % estimated capability makes it abandon the remaining tasks and return to the lander.</p>
          </Panel>
          <Panel eyebrow="Telemetry" title="Rover state">
            {f ? <>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Position" value={`${fmt(f.truth.position[0], 1)}, ${fmt(f.truth.position[1], 1)}`} unit="m" sub={`EKF ${fmt(f.estimate.position[0], 1)}, ${fmt(f.estimate.position[1], 1)}`} />
                <Stat label="Speed" value={fmt(f.truth.speed, 2)} unit="m/s" />
                <Stat label="Battery" value={fmt(f.battery.soc * 100, 1)} unit="%" tone={f.battery.soc < 0.22 ? "warn" : undefined} sub={`${fmt(f.battery.energy_used_wh, 1)} Wh used`} />
                <Stat label="Power" value={fmt(f.battery.power, 0)} unit="W" />
              </div>
              <div className="mt-4 grid grid-cols-6 gap-1 text-center">
                {WHEELS.map((w, i) => <div key={w} className="rounded-[8px] py-1.5" style={{ background: "var(--ivory)" }}>
                  <div className="text-[10px] text-muted">{w}</div><div className="num text-[12px]">{fmt(f.wheels.torque[i], 1)}</div>
                  <div className={`num text-[10px] ${f.wheels.health_est[i] < 0.9 ? "text-danger" : "text-muted"}`}>{fmt(f.wheels.health_est[i], 2)}</div></div>)}
              </div>
              {f.classification.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{f.classification.map((c) => <span key={c} className="chip">{c}</span>)}</div>}
            </> : <div className="text-[12px] text-muted">Not started.</div>}
          </Panel>
          <Panel eyebrow="Mission configuration" title="Site, rover & tasks">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Terrain"><select className="select" value={cfg.terrain} onChange={(e) => setCfg({ ...cfg, terrain: +e.target.value })}>
                {(terrains.data || []).map((t: any) => <option key={t.variant} value={t.variant}>T{t.variant} · {t.name}</option>)}</select></Field>
              <Field label="Autonomy"><select className="select" value={cfg.controller} onChange={(e) => setCfg({ ...cfg, controller: e.target.value })}>
                <option value="astra">ASTRA adaptive</option><option value="fsm">FSM baseline</option></select></Field>
              <Field label="Seed"><input className="input num" type="number" value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
              <Field label="Initial battery"><input className="input num" type="number" step="0.05" value={cfg.battery} onChange={(e) => setCfg({ ...cfg, battery: +e.target.value })} /></Field>
              <Field label="Max speed [m/s]"><input className="input num" type="number" step="0.05" value={cfg.speed} onChange={(e) => setCfg({ ...cfg, speed: +e.target.value })} /></Field>
            </div>
            <div className="mt-3 space-y-1">{TASK_KINDS.map(([k, l]) => <label key={k} className="flex items-center gap-2 text-[12.5px]">
              <input type="checkbox" checked={cfg.kinds.includes(k)} onChange={(e) => setCfg({ ...cfg, kinds: e.target.checked ? [...cfg.kinds, k] : cfg.kinds.filter((x) => x !== k) })} />{l}</label>)}</div>
            {held && <p className="text-[11px] text-warning mt-2">Held-out terrain: use for evaluation only, never for tuning.</p>}
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={() => configure()}>Apply & reset mission</button>
          </Panel>
          {live?.result && <Panel eyebrow="Mission result" title={live.result.success ? "Surface mission complete" : `Outcome: ${live.result.outcome}`}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Tasks" value={`${live.result.ground_ops?.tasks_completed ?? 0}/${live.result.ground_ops?.tasks_total ?? 0}`} sub={`${live.result.ground_ops?.tasks_skipped ?? 0} skipped`} />
              <Stat label="Time" value={fmt(live.result.mission_time_s, 0)} unit="s" />
              <Stat label="Energy" value={fmt(live.result.energy_used_wh, 1)} unit="Wh" /><Stat label="Route" value={fmt(live.result.route_length_m, 1)} unit="m" />
              <Stat label="Re-plans" value={live.result.replans} /><Stat label="Collisions" value={live.result.collisions} tone={live.result.collisions ? "bad" : undefined} />
            </div>
            <a className="btn btn-ghost mt-4" href={api.url(`/api/runs/${live.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">Download PDF debrief</a>
          </Panel>}
          <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={live?.events || []} /></Panel>
        </div>
      </div>
    </div>
  );
}
