import { lazy, Suspense, useEffect, useState } from "react";
import { Series } from "../../charts/Series";
import SimControls from "../../components/SimControls";
import { CamSwitch, Gauge, PhaseTimeline } from "../../components/SimViewport";
import { DecisionLog, Empty, ErrorNote, EventTimeline, Field, fmt, Panel, Stat } from "../../components/ui";
import type { LandingFeatures } from "../landing/LandingSimPage";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import type { CamMode } from "../../visualization/lib/scene";

const MoonScene = lazy(() => import("../../visualization/MoonScene"));
const PHASES = ["APPROACH (P64)", "TERMINAL DESCENT (P66)", "CONTACT", "TOUCHDOWN", "LANDED"];
const EXPLAIN: Record<string, string> = {
  "APPROACH (P64)": "Guidance re-solves a quadratic acceleration profile 10× per second so position, velocity and acceleration all meet the low-gate targets at a fixed final time. The lander pitches back to brake its forward speed; the dashed curve is the guidance's own predicted path.",
  "TERMINAL DESCENT (P66)": "Rate-of-descent mode: the lander is almost upright and descends at a commanded ~1 m/s while nulling horizontal drift. RCS thrusters (white puffs) make small attitude corrections. Below ~40 m the exhaust starts eroding regolith — the dust sheet you see.",
  CONTACT: "A 1.73 m probe under the footpads touched the surface: the contact light is on. The descent engine is shut down after a short delay so the exhaust doesn't reflect off the ground into the engine bell.",
  TOUCHDOWN: "Footpads on the surface. The final drop happens with the engine off, in lunar gravity (1.625 m/s²).",
  LANDED: "All touchdown limits met: vertical speed ≤ 3 m/s, horizontal ≤ 1.2 m/s, tilt ≤ 12°, slope ≤ 12°, no boulder > 0.6 m under the footprint.",
  FAILED: "At least one touchdown limit was violated — see the debrief for which one.",
};

export default function MoonPage({ features }: { features: LandingFeatures }) {
  const live = useSim((s) => s.moon);
  const hist = useSim((s) => s.moonHistory);
  const ingest = useSim((s) => s.ingest);
  const [scene, setScene] = useState<any>(null);
  const [cam, setCam] = useState<CamMode>("front");
  const labels = features.labels, plan = features.paths;
  const [err, setErr] = useState<string | null>(null);
  const [cfg, setCfg] = useState({ seed: 11, high_gate_altitude: 2000, high_gate_downrange: 4200, crossrange_offset: 60, terminal_descent_rate: 1.0, propellant: 1900 });
  const decisions = usePoll(() => api.get("/api/moon/decisions"), 3000, [live?.run_uid]);

  useEffect(() => { api.get("/api/moon/telemetry").then(ingest).catch((e) => setErr(e.message)); }, [ingest]);
  useEffect(() => { if (live?.run_uid) api.get("/api/moon/scene").then(setScene).catch((e) => setErr(e.message)); }, [live?.run_uid]);
  const apply = async () => { setErr(null); try { await api.post("/api/moon/config", cfg); ingest(await api.get("/api/moon/telemetry")); } catch (e: any) { setErr(e.message); } };

  const f = live?.frame;
  const vh = f ? Math.hypot(f.truth.velocity[0], f.truth.velocity[1]) : 0;
  const failed = live?.phase === "FAILED";
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4"><SimControls module="moon" status={live?.status} speed={live?.speed} />
        <span className="text-[11.5px] text-muted">Independent lunar simulation · g = 1.625 m/s² · no atmosphere</span></div>
      <ErrorNote error={err || (live as any)?.error} />
      <div className="panel px-5 py-3.5 mb-5"><PhaseTimeline phases={failed ? [...PHASES.slice(0, 4), "FAILED"] : PHASES} current={live?.phase} failed={failed} /></div>
      <div className="grid xl:grid-cols-[1fr_340px] gap-5">
        <div className="space-y-5 min-w-0">
          <div className="panel overflow-hidden relative" style={{ height: "66vh", minHeight: 460 }}>
            {scene && live ? <Suspense fallback={<div className="p-6 eyebrow">Loading lunar terrain…</div>}><MoonScene snap={live} scene={scene} cam={cam} labels={labels} showPlan={plan} /></Suspense>
              : <div className="h-full grid place-items-center eyebrow">Loading lunar terrain…</div>}
            <div className="absolute top-3 left-3 right-3 flex flex-wrap justify-between gap-2">
              <CamSwitch value={cam} onChange={setCam} modes={[["front", "Front view"], ["frontWide", "Front · wide"], ["free", "Free view"]]} />
            </div>
            {f && <div className="absolute bottom-3 left-3 hud p-3 w-[250px] space-y-2.5">
              <Gauge label="Altitude AGL" value={f.truth.agl} max={2000} unit="m" fmt={(v) => v.toFixed(v < 100 ? 1 : 0)} tone="var(--info)" />
              <Gauge label="Descent rate" value={-f.truth.velocity[2]} max={30} unit="m/s" fmt={(v) => v.toFixed(2)} tone={-f.truth.velocity[2] > 3 && f.truth.agl < 30 ? "var(--danger)" : "var(--primary)"} />
              <Gauge label="Horizontal speed" value={vh} max={80} unit="m/s" fmt={(v) => v.toFixed(2)} />
              <Gauge label="Throttle" value={f.engine.throttle * 100} max={100} unit="%" fmt={(v) => v.toFixed(0)} tone="var(--warning)" />
              <Gauge label="Propellant" value={f.truth.propellant} max={cfg.propellant} unit="kg" fmt={(v) => v.toFixed(0)} tone={f.truth.propellant < 300 ? "var(--danger)" : "var(--primary)"} />
              <div className="flex justify-between items-center pt-1">
                <span className={`chip ${["CONTACT", "TOUCHDOWN", "LANDED"].includes(live.phase) ? "!text-white !bg-[var(--success)]" : ""}`}>CONTACT LIGHT</span>
                <span className="num text-[11px] text-[var(--ink-secondary)]">dust {fmt(f.dust_rate, 2)} kg/s</span>
              </div>
            </div>}
            {live?.phase && <div className="absolute bottom-3 right-3 hud p-3 max-w-[340px] text-[12px] leading-relaxed text-[var(--ink-secondary)] hidden md:block">
              <div className="eyebrow !text-[9.5px] mb-1 text-[var(--primary)]">What is happening · {live.phase}</div>{EXPLAIN[live.phase]}</div>}
          </div>
          {!features.telemetry ? null : hist.length > 1 ? <div className="grid md:grid-cols-2 gap-5">
            <Panel eyebrow="Trajectory" title="Altitude & descent rate"><Series data={hist} lines={[{ key: "agl", name: "AGL [m]" }]} height={140} /><Series data={hist} lines={[{ key: "vz", name: "vertical speed [m/s]", color: "#1C7ED6" }, { key: "vx", name: "downrange speed [m/s]", color: "#F08C00" }]} height={140} /></Panel>
            <Panel eyebrow="Propulsion" title="Throttle, pitch & propellant"><Series data={hist} lines={[{ key: "throttle", name: "throttle [0-1]", color: "#F08C00" }]} height={140} /><Series data={hist} lines={[{ key: "pitch", name: "pitch [deg]", color: "#7950F2" }]} height={140} /></Panel>
            <Panel eyebrow="Plume-surface interaction" title="Regolith erosion rate"><Series data={hist} lines={[{ key: "dust", name: "dust [kg/s]", color: "#1F2937" }]} /></Panel>
            <Panel eyebrow="Navigation" title="Navigation error (IMU + landing radar)"><Series data={hist} lines={[{ key: "nav", name: "|estimate − truth| [m]", color: "#E03131" }]} /></Panel>
          </div> : <Empty title="Ready at high gate">Press Start to begin powered descent from high gate.</Empty>}
          <Panel eyebrow="Explainability" title="Decision audit"><DecisionLog decisions={decisions.data || []} /></Panel>
        </div>
        <div className="space-y-5">
          <Panel eyebrow="Telemetry" title="Lunar Module state">
            {f ? <div className="grid grid-cols-2 gap-4">
              <Stat label="Phase" value={<span className="text-[14px]">{live.phase}</span>} />
              <Stat label="Mission time" value={fmt(live.t, 1)} unit="s" />
              <Stat label="Altitude AGL" value={fmt(f.truth.agl, 1)} unit="m" />
              <Stat label="Vertical speed" value={fmt(f.truth.velocity[2], 2)} unit="m/s" />
              <Stat label="Thrust" value={fmt(f.engine.thrust_n / 1000, 1)} unit="kN" sub={f.engine.on ? "DPS firing" : "engine off"} />
              <Stat label="Pitch / roll" value={`${fmt((f.truth.pitch * 180) / Math.PI, 1)} / ${fmt((f.truth.roll * 180) / Math.PI, 1)}`} unit="°" />
              <Stat label="Mass" value={fmt(f.truth.mass, 0)} unit="kg" />
              <Stat label="Range to site" value={fmt(Math.hypot(f.target[0] - f.truth.position[0], f.target[1] - f.truth.position[1]), 0)} unit="m" />
            </div> : <div className="text-[12px] text-muted">No telemetry.</div>}
          </Panel>
          <Panel eyebrow="Configuration" title="High-gate conditions">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Seed (terrain + noise)"><input className="input num" type="number" value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
              <Field label="High-gate altitude [m]"><input className="input num" type="number" value={cfg.high_gate_altitude} onChange={(e) => setCfg({ ...cfg, high_gate_altitude: +e.target.value })} /></Field>
              <Field label="Downrange [m]"><input className="input num" type="number" value={cfg.high_gate_downrange} onChange={(e) => setCfg({ ...cfg, high_gate_downrange: +e.target.value })} /></Field>
              <Field label="Crossrange offset [m]"><input className="input num" type="number" value={cfg.crossrange_offset} onChange={(e) => setCfg({ ...cfg, crossrange_offset: +e.target.value })} /></Field>
              <Field label="P66 descent rate [m/s]"><input className="input num" type="number" step="0.1" value={cfg.terminal_descent_rate} onChange={(e) => setCfg({ ...cfg, terminal_descent_rate: +e.target.value })} /></Field>
              <Field label="Propellant [kg]"><input className="input num" type="number" value={cfg.propellant} onChange={(e) => setCfg({ ...cfg, propellant: +e.target.value })} /></Field>
            </div>
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={apply}>Apply & reset landing</button>
            <p className="text-[11px] text-muted mt-3">Separate engine from the Mars modules: own terrain generator, LM-class vehicle, guidance and dust model. See docs/MOON_LANDING.md.</p>
          </Panel>
          {live?.result && <Panel eyebrow="Debrief" title={live.result.success ? "The Eagle has landed" : `Outcome: ${live.result.outcome}`}>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Touchdown vz" value={fmt(live.result.touchdown?.vertical_speed, 2)} unit="m/s" />
              <Stat label="Horizontal" value={fmt(live.result.touchdown?.horizontal_speed, 2)} unit="m/s" />
              <Stat label="Tilt" value={fmt(live.result.touchdown?.tilt_deg, 1)} unit="°" />
              <Stat label="Site slope" value={fmt(live.result.touchdown?.site_slope_deg, 1)} unit="°" />
              <Stat label="Propellant left" value={fmt(live.result.propellant_remaining_kg, 0)} unit="kg" />
              <Stat label="Miss distance" value={fmt(live.result.landing_error_m, 1)} unit="m" />
              <Stat label="Dust eroded" value={fmt(live.result.dust_eroded_kg, 1)} unit="kg" />
              <Stat label="Boulder under pads" value={fmt(live.result.touchdown?.max_boulder_under_footprint_m, 2)} unit="m" />
            </div>
          </Panel>}
          <Panel eyebrow="Timeline" title="Mission events"><EventTimeline events={live?.events || []} /></Panel>
        </div>
      </div>
    </div>
  );
}
