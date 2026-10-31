import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ErrorVsSigma, Series } from "../../charts/Series";
import SensorHealthPanel from "../../components/SensorHealthPanel";
import SimControls from "../../components/SimControls";
import { CamSwitch, Gauge, PhaseTimeline } from "../../components/SimViewport";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import type { CamMode } from "../../visualization/lib/scene";
import type { LandingFeatures } from "../landing/LandingSimPage";
import LandingHistory from "./LandingHistory";
import LandingResultCard from "./LandingResultCard";
import { ReplayBar, useReplay } from "./Replay";

const TouchdownScene = lazy(() => import("../../visualization/TouchdownScene"));
const deg = (r: number) => (r * 180) / Math.PI;
const PHASES = ["ENTRY", "DESCENT", "LANDING APPROACH", "SITE ASSESSMENT", "DIVERSION", "TOUCHDOWN", "MISSION COMPLETE"];
const EXPLAIN: Record<string, string> = {
  ENTRY: "Unpowered coast: the main engine is off; RCS thrusters hold the lander vertical. The relay orbiter overhead receives telemetry.",
  DESCENT: "Powered descent: the main engine fires and the guidance law (PID, MPC or PPO) commands an acceleration. The cyan line is the target path; purple dashes are the guidance forecast.",
  "LANDING APPROACH": "Approach toward the pad. Below the assessment altitude the lidar keeps re-scanning the pad every second.",
  "HOVER & SCAN": "The lander arrests its descent above the pad and holds a stable hover while the lidar scans the pad and its surroundings at 2 Hz. Only then does it commit to the final descent.",
  "SITE ASSESSMENT": "Close-range lidar scans the pad and its surroundings (cyan ring + sweep). Perceived rocks are dotted (red = above the 0.35 m hazard limit).",
  DIVERSION: "The pad was found unsafe. Candidate sites were scored (green rings = feasible) and the lander re-planned its path (amber) to a safe site. The abandoned path is dashed red.",
  TOUCHDOWN: "Footpad contact. Vertical and horizontal speed, tilt, slope and rock clearance at the real contact point decide success.",
  "MISSION COMPLETE": "Landed within all limits. Open the result card for accuracy, precision, playback and the report.",
  FAILED: "A touchdown limit was violated — see the result card.",
  ABORT: "A late hazard left no planned diversion feasible: emergency side-step to the least-hazardous reachable point.",
};
const LEGEND: [string, string, boolean?][] = [["#34d399", "Flown trail"], ["#22d3ee", "Target path"], ["#fbbf24", "Replanned path"],
  ["#f87171", "Abandoned path", true], ["#a78bfa", "Guidance forecast", true], ["#67e8f9", "Lidar scan"]];
type Tab = "mission" | "sensors" | "telemetry" | "decisions" | "events" | "history";

export default function TouchdownPage({ env, diversion, features }: { env: "mars" | "moon"; diversion: boolean; features: LandingFeatures }) {
  const live = useSim((s) => s.touchdown);
  const hist = useSim((s) => s.tdHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [cam, setCam] = useState<CamMode>("front");
  const [overlay, setOverlay] = useState<"none" | "slope" | "hazard">("none");
  const [placing, setPlacing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hud, setHud] = useState(true);
  const [details, setDetails] = useState(true);
  const [tab, setTab] = useState<Tab>("mission");
  const [fs, setFs] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [replayUid, setReplayUid] = useState<string | null>(null);
  const replay = useReplay(replayUid);
  const stage = useRef<HTMLDivElement>(null);
  const [cfg, setCfg] = useState({ seed: 42, controller: "pid", hazard: false, alt: 2900, guard: "monitor" });
  const [envp, setEnvp] = useState({ wind_speed: 4.5, wind_dir_deg: -27, gust_std: 1.5, dust: 0 });
  const avail = usePoll(() => api.get("/api/touchdown/controllers"), 0);
  const decisions = usePoll(() => api.get("/api/touchdown/decisions"), 2000, [live?.run_uid]);
  const airless = env === "moon";

  useEffect(() => { api.get("/api/touchdown/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  useEffect(() => { if (live?.run_uid) api.get("/api/touchdown/scene").then(setScene).catch(() => {}); }, [live?.run_uid]);
  useEffect(() => { if (live?.diversions || overlay === "hazard") api.get("/api/touchdown/scene").then(setScene).catch(() => {}); }, [live?.diversions, overlay, live?.phase]);
  useEffect(() => { const e = (live as any)?.environment; if (e && !e.airless) setEnvp((x) => ({ ...x, wind_speed: e.wind_speed, wind_dir_deg: e.wind_dir_deg, gust_std: e.gust_std, dust: e.dust })); }, [live?.run_uid]); // eslint-disable-line
  useEffect(() => { const h = () => setFs(document.fullscreenElement === stage.current); document.addEventListener("fullscreenchange", h); return () => document.removeEventListener("fullscreenchange", h); }, []);
  const toggleFs = () => { if (document.fullscreenElement) document.exitFullscreen(); else stage.current?.requestFullscreen?.(); };

  const configure = async (over: Partial<typeof cfg> = {}) => {
    setErr(null);
    const c = { ...cfg, ...over };
    try {
      const a = envp.wind_dir_deg * Math.PI / 180;
      await api.post("/api/touchdown/config", { seed: c.seed, controller: c.controller, environment: env, enable_diversion: diversion, ppo_guard: c.guard,
        initial_position: [-650, 320, c.alt], terrain: { hazard_at_target: c.hazard },
        planet: airless ? {} : { wind: [envp.wind_speed * Math.cos(a), envp.wind_speed * Math.sin(a), 0], gust_std: envp.gust_std } });
      if (!airless && envp.dust > 0) await api.post("/api/touchdown/environment", { dust: envp.dust });
      ingest(await api.get("/api/touchdown/telemetry")); setScene(await api.get("/api/touchdown/scene"));
    } catch (e: any) { setErr(e.message); }
  };
  // the session must run the environment / landing type chosen in the selectors above
  const synced = useRef("");
  useEffect(() => {
    api.get("/api/touchdown/config").then((c) => {
      const a = c.active || {};
      setCfg((x) => ({ ...x, seed: a.seed ?? x.seed, controller: a.controller ?? x.controller, hazard: !!a.terrain?.hazard_at_target, alt: a.initial_position?.[2] ?? x.alt, guard: a.ppo_guard ?? x.guard }));
      const want = `${env}|${diversion}`;
      if (synced.current !== want && ((a.environment ?? "mars") !== env || (a.enable_diversion ?? true) !== diversion)) configure();
      synced.current = want;
    }).catch(() => {});
  }, [env, diversion]); // eslint-disable-line

  const inject = async (kind: string, body: any) => { try { return await api.post(`/api/touchdown/inject/${kind}`, body); } catch (e: any) { setErr(e.message); } };
  const placeObstacle = async (x?: number, y?: number) => {
    const r = await inject("hazard", x === undefined ? { radius: 22 } : { x, y, radius: 6 });
    if (!r) return;
    setScene(await api.get("/api/touchdown/scene"));
    setNote(r.affects_target
      ? (r.can_still_divert ? (diversion ? "Obstacle on the landing pad — the lidar will detect it and the lander will re-plan (side-steps possible down to ~8 m with PID/MPC)."
        : "Obstacle on the pad — autonomous diversion is OFF for this landing type, so the lander will not re-plan.")
        : "Obstacle on the pad, but the lander is below its last-chance altitude — too late to re-plan.")
      : `Obstacle placed ${fmt(r.distance_to_target_m, 0)} m from the pad — outside the landing footprint, no re-plan needed.`);
    setTimeout(() => setNote(null), 7000);
  };
  const pushEnv = async (p: Partial<typeof envp>) => { const n = { ...envp, ...p }; setEnvp(n); try { await api.post("/api/touchdown/environment", n); } catch (e: any) { setErr(e.message); } };

  const inReplay = !!replayUid;
  const view: any = inReplay ? replay.snap : live;
  const viewScene = inReplay ? replay.data?.scene : scene;
  const viewEnv = inReplay ? (replay.data?.environment ?? env) : env;
  const f = view?.frame;
  const per = (live as any)?.perception;
  const hov = (live as any)?.hover;
  const orig = view?.original_target;
  const divEvent = [...(live?.events || [])].reverse().find((e) => e.kind === "diversion" || e.kind === "abort");
  const pendingObstacle = !inReplay && ((live as any)?.obstacles || []).some((o: any) => o.affects_target) && !live?.diversions && f && f.truth.agl > (per?.assessment_agl ?? 450);
  const phase = !inReplay && hov?.active ? "HOVER & SCAN" : view?.phase;
  const phases = (() => {
    const p = hov?.enabled ? [...PHASES.slice(0, 3), "HOVER & SCAN", ...PHASES.slice(3)] : [...PHASES];
    return view?.phase === "FAILED" || view?.phase === "ABORT" ? [...p.slice(0, -1), view.phase] : p;
  })();
  const showCard = !inReplay && !!live?.result && dismissed !== live?.run_uid;
  const tabs: [Tab, string][] = [["mission", "Mission"], ...(features.sensors ? [["sensors", "Sensor health"]] as [Tab, string][] : []),
    ["telemetry", "Telemetry"], ["decisions", "Decisions"], ["events", "Events"], ["history", "History"]];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <SimControls module="touchdown" status={live?.status} speed={live?.speed} />
        <div className="flex gap-2">
          <button className="btn btn-ghost !py-1.5" onClick={() => setDetails(!details)}>{details ? "▾ Hide details" : "▸ Show details"}</button>
          <button className="btn btn-ghost !py-1.5" onClick={toggleFs}>⛶ Fullscreen</button>
        </div>
      </div>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="panel px-5 py-3 mb-3"><PhaseTimeline phases={phases} current={phase} failed={view?.phase === "FAILED"} /></div>

      <div ref={stage} className="panel overflow-hidden relative" style={{ height: fs ? "100vh" : "72vh", minHeight: 480, borderRadius: fs ? 0 : undefined, background: viewEnv === "moon" ? "#000" : undefined }}>
        {viewScene && view ? <Suspense fallback={<div className="p-6 eyebrow">Loading terrain…</div>}>
          <TouchdownScene snap={view} scene={viewScene} decisions={inReplay ? [] : decisions.data || []} cam={cam} labels={features.labels} overlay={inReplay ? "none" : overlay}
            showPaths={features.paths} showScan={features.scan && !inReplay} env={viewEnv} placing={placing && features.obstacles && !inReplay} onPlace={(x, y) => placeObstacle(x, y)} /></Suspense>
          : <div className="h-full grid place-items-center eyebrow">{inReplay ? (replay.err ?? "Loading the recorded landing…") : "Loading terrain…"}</div>}

        {/* one overlay layer laid out in flow: toolbar, then notices, then the bottom HUD row -
            notices can never sit on top of a button, and they never take clicks */}
        <div className="absolute inset-3 flex flex-col gap-2 pointer-events-none">
          <div className="flex flex-wrap justify-between gap-2 pointer-events-auto">
            <div className="flex flex-wrap gap-2 items-start">
              <CamSwitch value={cam} onChange={setCam} modes={[["front", "Front view"], ["frontWide", "Front · wide"], ["free", "Free view"]]} />
              {features.obstacles && !inReplay && <>
                <button className="hud px-3 py-1.5 text-[11.5px] text-[var(--danger)]" onClick={() => placeObstacle()}>⚠ Spawn obstacle at pad</button>
                <button className={`hud px-3 py-1.5 text-[11.5px] ${placing ? "!bg-[var(--danger)] !text-white" : "text-[var(--ink-secondary)]"}`} onClick={() => setPlacing(!placing)}>
                  {placing ? "● Click the surface · done" : "＋ Place obstacles"}</button></>}
            </div>
            <div className="flex flex-wrap gap-2 items-start">
              {!inReplay && <div className="seg hud !p-[3px]">{([["none", "No overlay"], ["slope", "Slope"], ["hazard", "Hazard map"]] as const).map(([o, l]) =>
                <button key={o} className={overlay === o ? "on" : ""} onClick={() => setOverlay(o)}>{l}</button>)}</div>}
              <button className="hud px-3 py-1.5 text-[11.5px] text-[var(--ink-secondary)]" onClick={() => setHud(!hud)}>{hud ? "◐ Hide HUD" : "◑ Show HUD"}</button>
              <button className="hud px-3 py-1.5 text-[11.5px] text-[var(--ink-secondary)]" onClick={toggleFs}>{fs ? "⤡ Exit fullscreen" : "⛶ Fullscreen"}</button>
            </div>
          </div>
          {fs && !inReplay && <div className="self-end hud px-2 py-1 pointer-events-auto"><SimControls module="touchdown" status={live?.status} speed={live?.speed} /></div>}

          {!inReplay && <div className="flex flex-col gap-2 max-w-[460px] min-h-0 overflow-hidden">
            {hov?.active && <div className="rounded-[10px] px-3 py-2 text-[11.5px]" style={{ background: "rgba(14,116,144,.88)", color: "#fff" }}>
              <b>◎ HOVER & SCAN</b> · {hov.stable_for > 0 ? `holding ${fmt(hov.stable_for, 1)} / ${fmt(hov.duration, 0)} s` : "arresting the descent"} · lidar scanning the pad at 2 Hz</div>}
            {live && live.diversions > 0 && <div className="rounded-[10px] px-3 py-2 text-[11px] leading-snug" style={{ background: "rgba(127,29,29,.82)", color: "#fff", border: "1px solid rgba(248,113,113,.7)" }}>
              <div className="font-semibold tracking-wide">⚠ HAZARD DETECTED AT PLANNED PAD ({fmt(orig?.[0], 0)}, {fmt(orig?.[1], 0)})</div>
              <div className="text-[#bbf7d0] mt-0.5">AUTONOMOUS DIVERT → SAFE SITE ({fmt(f?.target[0], 0)}, {fmt(f?.target[1], 0)}) · {fmt(Math.hypot((f?.target[0] ?? 0) - (orig?.[0] ?? 0), (f?.target[1] ?? 0) - (orig?.[1] ?? 0)), 0)} m away</div>
              {divEvent && <div className="opacity-80 mt-0.5">t = {fmt(divEvent.t, 1)} s · {divEvent.message}</div>}</div>}
            {live?.phase === "ABORT" && divEvent?.kind === "abort" && <div className="rounded-[10px] px-3 py-2 text-[11px]" style={{ background: "rgba(146,64,14,.88)", color: "#fff" }}><b>⚠ LATE HAZARD</b> · {divEvent.message}</div>}
            {(live as any)?.events?.some((e: any) => e.kind === "guard") && <div className="rounded-[10px] px-3 py-2 text-[11px] leading-snug" style={{ background: "rgba(146,64,14,.88)", color: "#fff" }}>
              <b>⚠ LEARNED CONTROLLER OUTSIDE ITS EXPERIENCE</b><div className="opacity-90">{[...(live?.events || [])].reverse().find((e: any) => e.kind === "guard")?.message}</div></div>}
            {pendingObstacle && <div className="hud px-3 py-2 text-[11px] text-[var(--warning)]">Obstacle on the pad — lidar not yet in range (AGL {fmt(f?.truth.agl, 0)} m)</div>}
            {hud && features.scan && per?.scans > 0 && <div className="hud px-3 py-1.5 text-[11px] text-[var(--ink-secondary)]"><span className="text-[#0e7490] font-medium">LIDAR SCAN #{per.scans}</span> · radius {fmt(per.region?.[2], 0)} m · {per.rocks?.length ?? 0} rocks · {per.rocks?.filter((r: number[]) => r[2] > per.hazard_limit_m).length ?? 0} above limit</div>}
            {note && <div className="hud px-3 py-2 text-[11px] text-ink">{note}</div>}
          </div>}

          {!inReplay && hud && <div className="mt-auto flex items-end justify-between gap-2">
            {f ? <div className="hud p-3 w-[230px] shrink-0 space-y-2.5">
              <Gauge label="Altitude AGL" value={f.truth.agl} max={3000} unit="m" fmt={(v) => v.toFixed(v < 100 ? 1 : 0)} tone="var(--info)" />
              <Gauge label="Vertical speed" value={-f.truth.velocity[2]} max={100} unit="m/s" fmt={(v) => v.toFixed(2)} />
              <Gauge label="Throttle" value={f.actuators.throttle * 100} max={100} unit="%" fmt={(v) => v.toFixed(0)} tone="var(--warning)" />
              <Gauge label="Fuel" value={f.truth.fuel} max={450} unit="kg" fmt={(v) => v.toFixed(0)} tone={f.truth.fuel < 60 ? "var(--danger)" : "var(--success)"} />
            </div> : <span />}
            {features.paths && <div className="hidden lg:flex flex-wrap gap-x-3 gap-y-1 hud px-3 py-1.5 text-[10.5px] text-[var(--ink-secondary)] min-w-0">
              {LEGEND.map(([c, l, dashed]) => <span key={l} className="flex items-center gap-1.5"><span className="inline-block w-4 h-[3px] rounded" style={{ background: dashed ? `repeating-linear-gradient(90deg, ${c} 0 4px, transparent 4px 7px)` : c }} />{l}</span>)}
            </div>}
            {phase ? <div className="hud p-3 max-w-[350px] shrink text-[12px] leading-relaxed text-[var(--ink-secondary)] hidden md:block">
              <div className="eyebrow !text-[9.5px] mb-1 text-[var(--primary)]">What is happening · {phase}</div>{EXPLAIN[phase] ?? ""}</div> : <span />}
          </div>}
        </div>
        {inReplay && <div className="absolute bottom-3 left-3 right-3"><ReplayBar r={replay} onExit={() => setReplayUid(null)} /></div>}
        {showCard && <LandingResultCard live={live} onClose={() => setDismissed(live!.run_uid!)}
          onReplay={() => { setDismissed(live!.run_uid!); setReplayUid(live!.run_uid!); }}
          onHistory={() => { setDismissed(live!.run_uid!); setDetails(true); setTab("history"); if (document.fullscreenElement) document.exitFullscreen(); }} />}
      </div>

      {details && <div className="mt-4">
        <div className="seg mb-4 flex-wrap">{tabs.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>

        {tab === "mission" && <div className="grid lg:grid-cols-3 gap-4">
          <Panel eyebrow="Telemetry" title="Vehicle state">
            {f && !inReplay ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-4">
                <Stat label="Altitude AGL" value={fmt(f.truth.agl, 1)} unit="m" sub={`EKF ${fmt(f.estimate.agl, 1)} m`} />
                <Stat label="Vertical speed" value={fmt(f.truth.velocity[2], 2)} unit="m/s" />
                <Stat label="Horizontal speed" value={fmt(Math.hypot(f.truth.velocity[0], f.truth.velocity[1]), 2)} unit="m/s" />
                <Stat label="Fuel" value={fmt(f.truth.fuel, 1)} unit="kg" tone={f.truth.fuel < 40 ? "warn" : undefined} />
                <Stat label="Tilt" value={fmt(f.truth.tilt_deg, 1)} unit="°" sub={`roll ${fmt(deg(f.truth.euler[0]), 1)} / pitch ${fmt(deg(f.truth.euler[1]), 1)}`} />
                <Stat label="Pos. error" value={fmt(Math.hypot(...f.error.position), 2)} unit="m" sub={`σ ${fmt(Math.hypot(...f.estimate.sigma.slice(0, 3)), 2)} m`} />
                <Stat label="Target pad" value={`${fmt(f.target[0], 0)}, ${fmt(f.target[1], 0)}`} sub={`diversions: ${live?.diversions ?? 0}`} />
                <Stat label="Pred. touchdown" value={f.predicted_touchdown ? `${fmt(f.predicted_touchdown[0], 0)}, ${fmt(f.predicted_touchdown[1], 0)}` : "—"} />
              </div>) : <div className="text-[12px] text-muted">{inReplay ? "Replaying a recorded landing." : "No telemetry."}</div>}
            {f?.controller?.mpc && <div className="mt-4 text-[11px] text-ink2 num">MPC: {f.controller.mpc.success ? "converged" : "not converged"} · {fmt(f.controller.mpc.solve_ms, 1)} ms · N={f.controller.mpc.horizon}</div>}
            {f?.controller?.ppo && <div className="mt-4 text-[11px] text-ink2 num space-y-0.5">
              <div>PPO {f.controller.ppo.checkpoint} · in control: <b className={f.controller.ppo.in_control === "pid" ? "text-warning" : "text-ink"}>{String(f.controller.ppo.in_control).toUpperCase()}</b></div>
              {f.controller.ppo.guard && <div>guard ({f.controller.ppo.guard.mode}): z {fmt(f.controller.ppo.guard.z_max, 1)}σ · vs PID {fmt(f.controller.ppo.guard.disagreement, 2)} · residual {fmt(f.controller.ppo.guard.dynamics_residual, 2)} m/s²</div>}</div>}
          </Panel>
          <Panel eyebrow="Mission configuration" title="Initial conditions">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Controller"><select className="select" value={cfg.controller} onChange={(e) => setCfg({ ...cfg, controller: e.target.value })}>
                <option value="pid">Cascade PID</option><option value="mpc">MPC</option><option value="ppo" disabled={!avail.data?.ppo}>PPO {avail.data?.ppo ? "" : "(no trained policy)"}</option></select></Field>
              {cfg.controller === "ppo" && <Field label="PPO guard"><select className="select" value={cfg.guard} onChange={(e) => setCfg({ ...cfg, guard: e.target.value })}>
                <option value="monitor">Flag only</option><option value="fallback">Flag + hand over to PID</option><option value="off">Off</option></select></Field>}
              <Field label="Random seed"><input className="input num" type="number" value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
              <Field label="Initial altitude [m]"><input className="input num" type="number" value={cfg.alt} onChange={(e) => setCfg({ ...cfg, alt: +e.target.value })} /></Field>
            </div>
            <label className="flex items-center gap-2 text-[12.5px] mt-3"><input type="checkbox" checked={cfg.hazard} onChange={(e) => setCfg({ ...cfg, hazard: e.target.checked })} /> Hidden boulder field at the pad</label>
            <p className="text-[11px] text-muted mt-2">PID and MPC hover-and-scan at ~80 m and descend gently so late obstacles can still be side-stepped. PPO flies its trained profile.</p>
            <button className="btn btn-sage mt-3 w-full justify-center" onClick={() => configure()}>Apply configuration</button>
          </Panel>
          <div className="space-y-4">
            <Panel eyebrow={airless ? "Environment · airless body" : "Environment · live"} title="Wind, gusts & dust">
              {airless ? <p className="text-[12px] text-ink2">The Moon has no atmosphere: no wind, gusts or dust storms. Gravity 1.625 m/s².</p> : <>
                {([["wind_speed", "Mean wind", 0, 30, 0.5, "m/s"], ["wind_dir_deg", "Wind direction", -180, 180, 5, "°"], ["gust_std", "Gust σ", 0, 8, 0.25, "m/s"], ["dust", "Dust opacity (lidar)", 0, 1, 0.05, ""]] as const).map(([k, l, lo, hi, st, u]) => (
                  <label key={k} className="block mb-2.5">
                    <div className="flex justify-between text-[11.5px] text-ink2"><span>{l}</span><span className="num text-ink">{fmt((envp as any)[k], k === "dust" ? 2 : 1)} {u}</span></div>
                    <input type="range" className="w-full accent-[var(--primary)]" min={lo} max={hi} step={st} value={(envp as any)[k]}
                      onChange={(e) => setEnvp({ ...envp, [k]: +e.target.value })} onPointerUp={(e) => pushEnv({ [k]: +(e.target as HTMLInputElement).value })} onKeyUp={(e) => pushEnv({ [k]: +(e.target as HTMLInputElement).value })} />
                  </label>))}</>}
            </Panel>
            <Panel eyebrow="Live intervention" title="Hazards & disturbances">
              <div className="grid gap-2">
                <button className="btn btn-ghost justify-center" onClick={() => placeObstacle()}>Boulder field at current pad</button>
                {!airless && <button className="btn btn-ghost justify-center" onClick={() => inject("disturbance", { force: [2500, -1500, 0], duration: 4 })}>Lateral gust 2.9 kN · 4 s</button>}
                <button className="btn btn-ghost justify-center" onClick={() => inject("sensor", { channel: "velocimeter", dropout: true })}>Velocimeter dropout</button>
              </div>
            </Panel>
            {live?.site_status && <Panel eyebrow="Perception" title="Current pad assessment">
              <div className="grid grid-cols-2 gap-3 text-[12px]">
                <Stat label="Safe" value={live.site_status.safe ? "yes" : live.site_status.covered ? "no" : "unsensed"} tone={live.site_status.safe ? "ok" : "bad"} />
                <Stat label="Max rock" value={fmt(live.site_status.max_rock_h, 2)} unit="m" />
              </div>
              {live.site_status.reasons?.length > 0 && <div className="text-[11.5px] text-danger mt-2">{live.site_status.reasons.join("; ")}</div>}
            </Panel>}
          </div>
        </div>}

        {tab === "sensors" && features.sensors && <SensorHealthPanel snap={live} hist={hist} onError={setErr} />}
        {tab === "telemetry" && (!live?.frame ? <Empty title="No descent yet">Press Start to see live charts.</Empty> :
          <div className="grid md:grid-cols-2 gap-4">
            <Panel eyebrow="Truth vs estimate" title="Altitude"><Series data={hist} lines={[{ key: "agl", name: "AGL truth [m]" }, { key: "agl_est", name: "AGL EKF [m]", dashed: true }]} /></Panel>
            <Panel eyebrow="Estimator" title="Position error vs EKF ±2σ (east axis)"><ErrorVsSigma data={hist} err="err_x" sig="sig_x" /></Panel>
            <Panel eyebrow="Propulsion" title="Throttle & tilt"><Series data={hist} lines={[{ key: "throttle", name: "throttle [0-1]" }, { key: "tilt", name: "tilt [deg]", color: "#C77D12" }]} /></Panel>
            <Panel eyebrow="Resources" title="Fuel & vertical velocity"><Series data={hist} lines={[{ key: "fuel", name: "fuel [kg]" }, { key: "vz", name: "vz truth [m/s]", color: "#2F8F6A" }, { key: "vz_est", name: "vz EKF", dashed: true, color: "#C0392B" }]} /></Panel>
          </div>)}
        {tab === "decisions" && <Panel eyebrow="Explainability" title="Decision audit log"><DecisionLog decisions={decisions.data || []} /></Panel>}
        {tab === "events" && <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={live?.events || []} max={120} /></Panel>}
        {tab === "history" && <Panel eyebrow="All recorded landings" title="History · success, accuracy & precision">
          <LandingHistory refreshKey={live?.result ? live?.run_uid : null} onReplay={(uid) => { setReplayUid(uid); window.scrollTo({ top: 0, behavior: "smooth" }); }} /></Panel>}
      </div>}
    </div>
  );
}
