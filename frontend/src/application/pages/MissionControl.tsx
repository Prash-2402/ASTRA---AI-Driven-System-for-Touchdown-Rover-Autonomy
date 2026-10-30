import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SimControls from "../../components/SimControls";
import { ErrorNote, EventTimeline, Field, fmt, PageHeader, Panel, Stat } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";
import { FAULTS } from "../../modules/rover/RoverPage";

export default function MissionControl() {
  const [mod, setMod] = useState<"touchdown" | "rover" | "moon">("touchdown");
  const live = useSim((s) => (mod === "touchdown" ? s.touchdown : mod === "rover" ? s.rover : s.moon)) as any;
  const ingest = useSim((s) => s.ingest);
  const [err, setErr] = useState<string | null>(null);
  const [seed, setSeed] = useState(42);
  const [ctrl, setCtrl] = useState("pid");
  const [scenario, setScenario] = useState("nominal");
  const [terrain, setTerrain] = useState(1);
  const terrains = usePoll(() => api.get("/api/rover/terrain"), 0);
  const avail = usePoll(() => api.get("/api/touchdown/controllers"), 0);
  useEffect(() => { setCtrl(mod === "touchdown" ? "pid" : mod === "rover" ? "astra" : "apollo"); api.get(`/api/${mod}/telemetry`).then(ingest).catch((e) => setErr(e.message)); }, [mod, ingest]);

  const apply = async () => {
    setErr(null);
    try {
      if (mod === "moon") await api.post("/api/moon/config", { seed });
      else if (mod === "touchdown") await api.post("/api/touchdown/config", { seed, controller: ctrl, terrain: { hazard_at_target: scenario === "hazard" } });
      else await api.post("/api/rover/config", { seed, controller: ctrl, terrain, faults: scenario === "nominal" ? [] : [{ fault_type: scenario, start: 20, duration: scenario === "sensor_dropout" ? 45 : null }] });
      ingest(await api.get(`/api/${mod}/telemetry`));
    } catch (e: any) { setErr(e.message); }
  };
  const injectNow = async (body: any, path: string) => { try { await api.post(path, body); } catch (e: any) { setErr(e.message); } };
  const f = live?.frame;
  return (
    <div>
      <PageHeader eyebrow="Operations" title="Mission Control">
        <div className="flex rounded-full bg-sage p-1">{(["rover", "moon", "touchdown"] as const).map((m) => (
          <button key={m} onClick={() => setMod(m)} className={`px-4 py-1.5 rounded-full text-[13px] ${mod === m ? "bg-surface shadow-soft" : "text-ink2"}`}>{m === "touchdown" ? "Touchdown" : m === "rover" ? "Rover" : "Moon"}</button>))}</div>
      </PageHeader>
      <ErrorNote error={err} />
      <div className="grid lg:grid-cols-[380px_1fr] gap-5">
        <div className="space-y-5">
          <Panel eyebrow="1 · Configure" title="Mission">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Controller"><select className="select" value={ctrl} onChange={(e) => setCtrl(e.target.value)}>
                {mod === "moon" ? <option value="apollo">Apollo-style guidance (P64/P66)</option> : mod === "touchdown" ? <><option value="pid">PID</option><option value="mpc">MPC</option><option value="ppo" disabled={!avail.data?.ppo}>PPO{avail.data?.ppo ? "" : " (untrained)"}</option></>
                  : <><option value="astra">ASTRA adaptive</option><option value="fsm">FSM baseline</option></>}</select></Field>
              <Field label="Random seed"><input className="input num" type="number" value={seed} onChange={(e) => setSeed(+e.target.value)} /></Field>
              {mod === "rover" && <Field label="Terrain"><select className="select" value={terrain} onChange={(e) => setTerrain(+e.target.value)}>
                {(terrains.data || []).map((t: any) => <option key={t.variant} value={t.variant}>T{t.variant} ({t.split === "held_out" ? "held-out" : "dev"})</option>)}</select></Field>}
              <Field label="Scenario"><select className="select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                <option value="nominal">Nominal</option>
                {mod === "moon" ? null : mod === "touchdown" ? <option value="hazard">Hidden hazard at target</option> : FAULTS.map(([id, n]) => <option key={id} value={id}>{n} @ 20 s</option>)}</select></Field>
            </div>
            <button className="btn btn-sage mt-4 w-full justify-center" onClick={apply}>Apply configuration</button>
          </Panel>
          <Panel eyebrow="2 · Run" title="Lifecycle"><SimControls module={mod} status={live?.status} speed={live?.speed} /></Panel>
          <Panel eyebrow="3 · Intervene" title="Live injection">
            {mod === "moon" ? <p className="text-[12.5px] text-ink2">The lunar landing has no fault injection: change high-gate conditions on the Moon page.</p> : mod === "touchdown" ? <div className="grid gap-2">
              <button className="btn btn-ghost justify-center" onClick={() => injectNow({ radius: 25 }, "/api/touchdown/inject/hazard")}>Boulder field at target</button>
              <button className="btn btn-ghost justify-center" onClick={() => injectNow({ force: [2500, -1500, 0], duration: 4 }, "/api/touchdown/inject/disturbance")}>Lateral gust</button>
            </div> : <div className="grid grid-cols-2 gap-2">{FAULTS.map(([id, n]) => <button key={id} className="btn btn-ghost !text-[12px] justify-center" disabled={live?.status !== "running"} onClick={() => injectNow({ fault_type: id, duration: id === "sensor_dropout" ? 45 : null }, "/api/rover/faults")}>{n}</button>)}</div>}
          </Panel>
        </div>
        <div className="space-y-5 min-w-0">
          <Panel eyebrow="Live telemetry" title={`${mod === "touchdown" ? "Lander" : mod === "rover" ? "Rover" : "Lunar Module"} · ${live?.run_uid ?? "no session"}`} right={<Link className="btn btn-ghost" to={`/app/${mod}`}>Open 3D view →</Link>}>
            {f ? (mod === "moon" ? <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              <Stat label="Phase" value={<span className="text-[14px]">{live.phase}</span>} /><Stat label="t" value={fmt(live.t, 1)} unit="s" />
              <Stat label="AGL" value={fmt(f.truth.agl, 1)} unit="m" /><Stat label="vz" value={fmt(f.truth.velocity[2], 2)} unit="m/s" />
              <Stat label="Throttle" value={fmt(f.engine.throttle * 100, 0)} unit="%" /><Stat label="Propellant" value={fmt(f.truth.propellant, 0)} unit="kg" />
              <Stat label="Dust" value={fmt(f.dust_rate, 2)} unit="kg/s" /><Stat label="Nav error" value={fmt(f.error.position, 1)} unit="m" />
            </div> : mod === "touchdown" ? <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              <Stat label="Phase" value={live.phase} /><Stat label="t" value={fmt(live.t, 1)} unit="s" />
              <Stat label="AGL" value={fmt(f.truth.agl, 1)} unit="m" /><Stat label="vz" value={fmt(f.truth.velocity[2], 2)} unit="m/s" />
              <Stat label="Fuel" value={fmt(f.truth.fuel, 1)} unit="kg" /><Stat label="Throttle" value={fmt(f.actuators.throttle * 100, 0)} unit="%" />
              <Stat label="EKF pos error" value={fmt(Math.hypot(...f.error.position), 2)} unit="m" /><Stat label="Diversions" value={live.diversions} />
            </div> : <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              <Stat label="t" value={fmt(live.t, 1)} unit="s" /><Stat label="Speed" value={fmt(f.truth.speed, 2)} unit="m/s" />
              <Stat label="SoC" value={fmt(f.battery.soc * 100, 1)} unit="%" /><Stat label="Power" value={fmt(f.battery.power, 0)} unit="W" />
              <Stat label="Safety" value={f.safety.action} /><Stat label="EKF error" value={fmt(f.error.position, 2)} unit="m" />
              <Stat label="Faults" value={f.faults_active.length ? f.faults_active.join(", ") : "none"} /><Stat label="Classified" value={f.classification.join(", ") || "nominal"} />
            </div>) : <div className="text-[12px] text-muted">Apply a configuration to create a session.</div>}
            {live?.result && <div className="mt-5 panel-soft p-4 text-[13px]"><b>Result:</b> {live.result.outcome} · success = {String(live.result.success)}</div>}
          </Panel>
          <Panel eyebrow="Inspection" title="Event stream"><EventTimeline events={live?.events || []} max={80} /></Panel>
          {f && <Panel eyebrow="Raw frame" title="Latest telemetry frame (backend)"><pre className="num text-[10.5px] max-h-72 overflow-auto scroll-thin text-ink2">{JSON.stringify(f, null, 1)}</pre></Panel>}
        </div>
      </div>
    </div>
  );
}
