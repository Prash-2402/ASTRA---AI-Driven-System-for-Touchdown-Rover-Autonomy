import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Field, PageHeader } from "../../components/ui";
import MoonPage from "../moon/MoonPage";
import TouchdownPage from "../touchdown/TouchdownPage";

export type LandingFeatures = { paths: boolean; scan: boolean; obstacles: boolean; labels: boolean; telemetry: boolean };
type Env = "mars" | "moon";
type LandingType = "autonomous" | "fixed" | "apollo";

const ENVS: [Env, string][] = [["mars", "Mars · Jezero-like plains"], ["moon", "Moon · cratered mare"]];
const TYPES: { id: LandingType; label: string; envs: Env[]; blurb: string }[] = [
  { id: "autonomous", label: "Autonomous precision landing (lidar scan & re-plan)", envs: ["mars", "moon"],
    blurb: "ASTRA lander: EKF navigation, PID/MPC/PPO guidance, lidar scanning of the pad and its surroundings, and autonomous diversion to a safe site when an obstacle is found." },
  { id: "fixed", label: "Fixed-target landing (no diversion · baseline)", envs: ["mars", "moon"],
    blurb: "Same vehicle and sensors, but autonomous diversion is disabled: the lander still scans and reports hazards but always lands on the original pad. Use it to compare against autonomous re-planning." },
  { id: "apollo", label: "Apollo-style LM guidance (P64 / P66)", envs: ["moon"],
    blurb: "Lunar Module with Apollo P64 approach guidance and P66 rate-of-descent mode, landing radar and plume–regolith dust. Separate vehicle and physics; no autonomous hazard re-planning." },
];
const FEATURES: [keyof LandingFeatures, string, string, boolean][] = [
  ["paths", "Landing path guidance", "flown trail, target path, replanned path, forecast, pad beacons", true],
  ["scan", "Lidar surroundings scan", "scan footprint, sweep and perceived hazard rocks", false],
  ["obstacles", "Obstacle placement", "spawn at pad or click anywhere on the surface", false],
  ["labels", "Component labels", "annotate the vehicle's actuators and sensors", true],
  ["telemetry", "Telemetry charts", "truth vs estimate, propulsion and resources", true],
];

export default function LandingSimPage() {
  const [sp, setSp] = useSearchParams();
  const env: Env = sp.get("env") === "moon" ? "moon" : "mars";
  const reqType = (sp.get("type") as LandingType) || (sp.get("env") === "moon" && !sp.get("type") ? "autonomous" : "autonomous");
  const type: LandingType = TYPES.find((t) => t.id === reqType && t.envs.includes(env)) ? reqType : "autonomous";
  const [features, setFeatures] = useState<LandingFeatures>({ paths: true, scan: true, obstacles: true, labels: false, telemetry: true });
  const [open, setOpen] = useState(false);
  const pop = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (pop.current && !pop.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h);
  }, []);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); n.set(k, v); setSp(n, { replace: true }); };
  const t = TYPES.find((x) => x.id === type)!;
  const supported = (k: keyof LandingFeatures) => type !== "apollo" || FEATURES.find((f) => f[0] === k)![3];
  const on = FEATURES.filter(([k]) => features[k] && supported(k));
  return (
    <div>
      <PageHeader eyebrow="Unified landing simulation · choose the landing, the world and what to show" title={<>Landing <em>Simulation</em></>} />
      <div className="panel px-5 py-4 mb-5 grid md:grid-cols-3 gap-4 items-end">
        <Field label="Type of landing">
          <select className="select" value={type} onChange={(e) => set("type", e.target.value)}>
            {TYPES.filter((x) => x.envs.includes(env)).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </Field>
        <Field label="Environment">
          <select className="select" value={env} onChange={(e) => { const n = new URLSearchParams(sp); n.set("env", e.target.value);
            if (e.target.value === "mars" && type === "apollo") n.set("type", "autonomous"); setSp(n, { replace: true }); }}>
            {ENVS.map(([id, l]) => <option key={id} value={id}>{l}</option>)}
          </select>
        </Field>
        <div className="relative" ref={pop}>
          <span className="label">Simulation features</span>
          <button className="select text-left w-full truncate" onClick={() => setOpen(!open)}>{on.length ? on.map((f) => f[1]).join(", ") : "None"}</button>
          {open && <div className="absolute z-30 mt-1 w-full min-w-[300px] panel p-2 shadow-lg">
            {FEATURES.map(([k, l, d]) => { const ok = supported(k); return (
              <label key={k} className={`flex gap-2.5 items-start rounded-[10px] px-2.5 py-2 ${ok ? "hover:bg-sage-soft cursor-pointer" : "opacity-45"}`}>
                <input type="checkbox" className="mt-0.5" disabled={!ok} checked={features[k] && ok} onChange={(e) => setFeatures({ ...features, [k]: e.target.checked })} />
                <span><span className="text-[13px] text-ink">{l}</span><span className="block text-[11px] text-muted">{ok ? d : "not available for Apollo-style guidance"}</span></span>
              </label>); })}
          </div>}
        </div>
        <p className="md:col-span-3 text-[12px] text-ink2 -mt-1">{t.blurb}</p>
      </div>
      {type === "apollo"
        ? <MoonPage features={{ ...features, scan: false, obstacles: false }} />
        : <TouchdownPage key={env} env={env} diversion={type === "autonomous"} features={features} />}
    </div>
  );
}
