import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote, Field, PageHeader, Panel } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { FAULTS } from "../../modules/rover/RoverPage";

/** Merge a partial backend config over complete defaults without dropping nested fields. */
function deepMerge(base: any, over: any): any {
  if (Array.isArray(base) || typeof base !== "object" || base === null) return over ?? base;
  const out: any = { ...base };
  for (const [k, v] of Object.entries(over || {})) {
    if (v === null || v === undefined) continue;
    out[k] = typeof v === "object" && !Array.isArray(v) && typeof base[k] === "object" ? deepMerge(base[k], v) : v;
  }
  return out;
}

export default function ScenarioBuilder() {
  const nav = useNavigate();
  const [mod, setMod] = useState<"touchdown" | "rover">("touchdown");
  const [err, setErr] = useState<string | null>(null);
  const td = usePoll(() => api.get("/api/touchdown/config"), 0);
  const terrains = usePoll(() => api.get("/api/rover/terrain"), 0);
  const [t, setT] = useState<any>({ seed: 42, controller: "pid", initial_position: [-650, 320, 2900], initial_velocity: [32, -14, -62], target: [0, 0],
    planet: { gravity: 3.72076, rho0: 0.02, scale_height: 11100, wind: [4, -2, 0], gust_std: 1.5 }, terrain: { rock_density_per_km2: 900, n_craters: 14, roughness_m: 6, hazard_at_target: false },
    lander: { fuel_mass: 450, max_thrust: 10000, isp: 225 }, supervisor: { ignition_agl: 2400, assessment_agl: 450 }, enable_diversion: true });
  const [r, setR] = useState<any>({ seed: 7, terrain: 1, controller: "astra", initial_battery: 0.8, max_speed: 0.4, wheel_torque: 8, rover_mass: 64, duration: 600, faults: [] as any[] });
  useEffect(() => { if (td.data?.active) setT((x: any) => deepMerge(x, td.data.active)); }, [td.data]);
  const tv = terrains.data?.find((x: any) => x.variant === r.terrain);
  const payload = mod === "touchdown" ? t : { ...r, start: tv?.start, target: tv?.target };
  const apply = async () => { setErr(null); try { await api.post(`/api/${mod}/config`, payload); nav(`/app/${mod}`); } catch (e: any) { setErr(e.message); } };
  const num = (obj: any, set: any, path: string[], step = "any") => (
    <input className="input num" type="number" step={step} value={path.reduce((o, k) => o?.[k], obj) ?? ""} onChange={(e) => {
      const v = +e.target.value; const c = structuredClone(obj); let o = c; path.slice(0, -1).forEach((k) => (o = o[k])); o[path[path.length - 1]] = v; set(c); }} />);
  const vec = (obj: any, set: any, key: string, sub?: string) => (
    <div className="grid grid-cols-3 gap-1">{(sub ? obj[sub][key] : obj[key]).map((v: number, i: number) => <input key={i} className="input num" type="number" value={v}
      onChange={(e) => { const c = structuredClone(obj); (sub ? c[sub][key] : c[key])[i] = +e.target.value; set(c); }} />)}</div>);
  return (
    <div>
      <PageHeader eyebrow="Design" title="Scenario Builder">
        <div className="flex rounded-full bg-sage p-1">{(["touchdown", "rover"] as const).map((m) => <button key={m} onClick={() => setMod(m)} className={`px-4 py-1.5 rounded-full text-[13px] ${mod === m ? "bg-surface shadow-soft" : "text-ink2"}`}>{m}</button>)}</div>
      </PageHeader>
      <ErrorNote error={err} />
      <div className="grid lg:grid-cols-[1fr_420px] gap-5">
        {mod === "touchdown" ? <div className="grid md:grid-cols-2 gap-5">
          <Panel eyebrow="Initial state" title="Lander">
            <div className="space-y-3">
              <Field label="Initial position E, N, Up [m]">{vec(t, setT, "initial_position")}</Field>
              <Field label="Initial velocity [m/s]">{vec(t, setT, "initial_velocity")}</Field>
              <div className="grid grid-cols-3 gap-2"><Field label="Fuel [kg]">{num(t, setT, ["lander", "fuel_mass"])}</Field><Field label="Max thrust [N]">{num(t, setT, ["lander", "max_thrust"])}</Field><Field label="Isp [s]">{num(t, setT, ["lander", "isp"])}</Field></div>
              <div className="grid grid-cols-2 gap-2"><Field label="Controller"><select className="select" value={t.controller} onChange={(e) => setT({ ...t, controller: e.target.value })}><option value="pid">PID</option><option value="mpc">MPC</option><option value="ppo">PPO</option></select></Field>
                <Field label="Seed">{num(t, setT, ["seed"], "1")}</Field></div>
            </div>
          </Panel>
          <Panel eyebrow="Environment (Mars)" title="Planet & atmosphere">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Gravity [m/s²]">{num(t, setT, ["planet", "gravity"])}</Field><Field label="ρ₀ [kg/m³]">{num(t, setT, ["planet", "rho0"])}</Field>
              <Field label="Scale height [m]">{num(t, setT, ["planet", "scale_height"])}</Field><Field label="Gust σ [m/s]">{num(t, setT, ["planet", "gust_std"])}</Field>
            </div>
            <Field label="Mean wind [m/s]">{vec(t, setT, "wind", "planet")}</Field>
            <p className="text-[11px] text-muted mt-2">Defaults are documented Mars values (NASA fact sheet). Mixing bodies is not supported.</p>
          </Panel>
          <Panel eyebrow="Landing region" title="Terrain">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Rocks per km²">{num(t, setT, ["terrain", "rock_density_per_km2"])}</Field><Field label="Craters">{num(t, setT, ["terrain", "n_craters"], "1")}</Field>
              <Field label="Relief [m]">{num(t, setT, ["terrain", "roughness_m"])}</Field><Field label="Target E, N [m]"><div className="grid grid-cols-2 gap-1">{t.target.map((v: number, i: number) => <input key={i} className="input num" type="number" value={v} onChange={(e) => { const c = structuredClone(t); c.target[i] = +e.target.value; setT(c); }} />)}</div></Field>
            </div>
            <label className="flex items-center gap-2 text-[12.5px] mt-3"><input type="checkbox" checked={t.terrain.hazard_at_target} onChange={(e) => setT({ ...t, terrain: { ...t.terrain, hazard_at_target: e.target.checked } })} />Hidden boulder field at target</label>
          </Panel>
          <Panel eyebrow="Supervisor" title="Phase thresholds">
            <div className="grid grid-cols-2 gap-2"><Field label="Ignition AGL [m]">{num(t, setT, ["supervisor", "ignition_agl"])}</Field><Field label="Assessment AGL [m]">{num(t, setT, ["supervisor", "assessment_agl"])}</Field></div>
            <label className="flex items-center gap-2 text-[12.5px] mt-3"><input type="checkbox" checked={t.enable_diversion} onChange={(e) => setT({ ...t, enable_diversion: e.target.checked })} />Autonomous diversion enabled</label>
          </Panel>
        </div> : <div className="grid md:grid-cols-2 gap-5">
          <Panel eyebrow="Traverse" title="Terrain & controller">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Terrain"><select className="select" value={r.terrain} onChange={(e) => setR({ ...r, terrain: +e.target.value })}>{(terrains.data || []).map((x: any) => <option key={x.variant} value={x.variant}>T{x.variant} · {x.split}</option>)}</select></Field>
              <Field label="Controller"><select className="select" value={r.controller} onChange={(e) => setR({ ...r, controller: e.target.value })}><option value="astra">ASTRA</option><option value="fsm">FSM</option></select></Field>
              <Field label="Seed">{num(r, setR, ["seed"], "1")}</Field><Field label="Duration [s]">{num(r, setR, ["duration"])}</Field>
            </div>
            <p className="text-[11.5px] text-ink2 mt-3">Start {JSON.stringify(tv?.start)} → science target {JSON.stringify(tv?.target)}</p>
          </Panel>
          <Panel eyebrow="Vehicle" title="Rover">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Total mass [kg]">{num(r, setR, ["rover_mass"])}</Field><Field label="Initial battery [0-1]">{num(r, setR, ["initial_battery"])}</Field>
              <Field label="Wheel torque [N m]">{num(r, setR, ["wheel_torque"])}</Field><Field label="Max speed [m/s]">{num(r, setR, ["max_speed"])}</Field>
            </div>
          </Panel>
          <Panel eyebrow="Fault schedule" title="Scheduled faults" className="md:col-span-2">
            {r.faults.map((fa: any, i: number) => <div key={i} className="grid grid-cols-[1fr_100px_100px_auto] gap-2 mb-2">
              <select className="select" value={fa.fault_type} onChange={(e) => { const c = structuredClone(r); c.faults[i].fault_type = e.target.value; setR(c); }}>{FAULTS.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select>
              <input className="input num" type="number" value={fa.start} onChange={(e) => { const c = structuredClone(r); c.faults[i].start = +e.target.value; setR(c); }} />
              <input className="input num" type="number" placeholder="∞" value={fa.duration ?? ""} onChange={(e) => { const c = structuredClone(r); c.faults[i].duration = e.target.value ? +e.target.value : null; setR(c); }} />
              <button className="btn btn-danger" onClick={() => setR({ ...r, faults: r.faults.filter((_: any, k: number) => k !== i) })}>✕</button></div>)}
            <button className="btn btn-ghost" onClick={() => setR({ ...r, faults: [...r.faults, { fault_type: "sensor_dropout", start: 20, duration: 45 }] })}>+ Add fault (start s, duration s)</button>
          </Panel>
        </div>}
        <Panel eyebrow="Payload" title="Configuration preview">
          <pre className="num text-[10.5px] bg-sage-soft rounded-[12px] p-3 max-h-[520px] overflow-auto scroll-thin">{JSON.stringify(payload, null, 2)}</pre>
          <button className="btn btn-primary mt-4 w-full justify-center" onClick={apply}>Send to {mod} session →</button>
        </Panel>
      </div>
    </div>
  );
}
