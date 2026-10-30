import { useState } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { fmt } from "./ui";

const axis = { stroke: "#8A94A6", fontSize: 10, fontFamily: "JetBrains Mono" };
const tip = { background: "#FFFFFF", border: "1px solid rgba(17,24,39,.1)", borderRadius: 12, fontSize: 11, color: "#111827" };
const CH: Record<string, { label: string; unit: string; rates: number[]; what: string }> = {
  altimeter: { label: "Radar altimeter", unit: "m", rates: [0.5, 1.0, 2.0], what: "height above terrain" },
  position: { label: "TRN position (vertical)", unit: "m", rates: [0.6, 1.2], what: "altitude from terrain-relative navigation" },
  velocimeter: { label: "Doppler velocimeter (vertical)", unit: "m/s", rates: [0.05, 0.1], what: "vertical velocity" },
};
const STATUS_COLOR: Record<string, string> = { OK: "#16a34a", SUSPECT: "#f59e0b", ISOLATED: "#dc2626" };

/** "The Sensor That Lies": inject a slow drift, watch the monitor's evidence build up side by side. */
export default function SensorHealthPanel({ snap, hist, onError }: { snap: any; hist: any[]; onError: (e: string) => void }) {
  const [channel, setChannel] = useState("altimeter");
  const [rate, setRate] = useState(0.5);
  const sh = snap?.sensor_health;
  const drift = snap?.drift || {};
  const driftCh = Object.keys(drift)[0];
  const ch = driftCh || channel;
  const meta = CH[ch];
  const series: any[] = (sh?.series?.[ch] || []).map((r: number[]) => ({ t: r[0], meas: r[1], truth: r[2], e: r[3], g: r[4] }));
  // running mean of the normalised innovation (honest -> ~0; lying -> leans one way)
  let acc = 0; series.forEach((r, i) => { acc = i === 0 ? r.e : acc * 0.94 + r.e * 0.06; r.mean = acc; });
  const st = sh?.channels?.[ch];
  const onset = drift[ch]?.t0;
  const susT = st?.first?.suspect, isoT = st?.first?.isolated;
  const isolatedEv = (sh?.events || []).filter((e: any) => e.status === "ISOLATED").slice(-1)[0];
  const nav = hist.slice(-400).map((r) => ({ t: r.t, err: r.agl_est - r.agl }));
  const inject = async () => { try { await api.post("/api/touchdown/inject/drift", { channel, rate }); } catch (e: any) { onError(e.message); } };
  const marks = (labelled = false) => (<>
    {onset != null && <ReferenceLine x={onset} stroke="#f59e0b" strokeDasharray="4 3" label={labelled ? { value: "drift", fill: "#b45309", fontSize: 10, position: "insideTopLeft" } : undefined} />}
    {susT != null && <ReferenceLine x={susT} stroke="#a855f7" strokeDasharray="4 3" label={labelled ? { value: "suspect", fill: "#7e22ce", fontSize: 10, position: "insideBottomRight" } : undefined} />}
    {isoT != null && <ReferenceLine x={isoT} stroke="#16a34a" strokeWidth={2} label={labelled ? { value: "ISOLATED", fill: "#15803d", fontSize: 10, position: "insideTopRight" } : undefined} />}
  </>);
  const chart = (title: string, sub: string, body: JSX.Element) => (
    <div className="rounded-[14px] border p-3 min-w-0" style={{ background: "var(--ivory)" }}>
      <div className="text-[12.5px] font-medium text-ink">{title}</div><div className="text-[10.5px] text-muted mb-1">{sub}</div>
      <div style={{ height: 190 }}><ResponsiveContainer>{body}</ResponsiveContainer></div>
    </div>);
  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div><div className="eyebrow">Hurdle · The Sensor That Lies</div>
          <h3 className="text-[15px] font-semibold text-ink mt-0.5">Sensor-health monitor — catching a sensor that keeps talking but is slowly wrong</h3></div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-[11px] text-ink2">Sensor<select className="select !py-1.5 block" value={channel} disabled={!!driftCh} onChange={(e) => { setChannel(e.target.value); setRate(CH[e.target.value].rates[0]); }}>
            {Object.entries(CH).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
          <label className="text-[11px] text-ink2">Drift rate<select className="select !py-1.5 block" value={rate} disabled={!!driftCh} onChange={(e) => setRate(+e.target.value)}>
            {CH[channel].rates.map((r) => <option key={r} value={r}>{r} {CH[channel].unit}/s</option>)}</select></label>
          <button className="btn btn-primary !py-2" disabled={!!driftCh || snap?.status !== "running"} onClick={inject}>Inject slow drift</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mb-3">
        {Object.entries(sh?.channels || {}).map(([k, v]: any) => (
          <span key={k} className="chip" style={{ borderColor: STATUS_COLOR[v.status], color: STATUS_COLOR[v.status] }}>
            <span className="dot" style={{ background: STATUS_COLOR[v.status] }} />{CH[k]?.label ?? k}: {v.status} · CUSUM {fmt(v.cusum, 1)}/{v.threshold}</span>))}
        <span className="chip">cross-check altimeter↔TRN {fmt(sh?.cross?.cusum, 1)}/{sh?.cross?.threshold}</span>
        {!snap?.status || snap.status !== "running" ? <span className="text-[11px] text-muted self-center">Start the landing, then inject a drift (monitoring begins after the 15 s filter warm-up).</span> : null}
      </div>
      {isolatedEv && <div className="rounded-[12px] px-4 py-2.5 mb-3 text-[12.5px]" style={{ background: "rgba(220,38,38,.08)", border: "1px solid rgba(220,38,38,.4)" }}>
        <b className="text-danger">⚠ {String(isolatedEv.channel).toUpperCase()} DRIFT DETECTED at t = {fmt(isolatedEv.t, 1)} s</b>
        {drift[isolatedEv.channel] && <> · <b>{fmt(isolatedEv.t - drift[isolatedEv.channel].t0, 1)} s after onset</b> (true bias then {fmt(drift[isolatedEv.channel].rate * (isolatedEv.t - drift[isolatedEv.channel].t0), 2)} {CH[isolatedEv.channel]?.unit})</>}
        {" "}· sensor isolated from the navigation filter · evidence: {isolatedEv.confirmed_by}, innovations leaning {isolatedEv.direction}</div>}
      <div className="grid lg:grid-cols-3 gap-3">
        {chart(`1 · ${meta.label}: readings vs truth`, `every dot is a real reading of ${meta.what}; the line is the truth only the simulator knows`,
          <ComposedChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} /><XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={axis} tickFormatter={(v) => v.toFixed(0)} />
            <YAxis tick={axis} domain={["auto", "auto"]} /><Tooltip contentStyle={tip} formatter={(v: any) => Number(v).toFixed(2)} /><Legend wrapperStyle={{ fontSize: 10 }} />
            <Scatter dataKey="meas" name="sensor reading" fill="#ef4444" shape={(p: any) => <circle cx={p.cx} cy={p.cy} r={1.6} fill="#ef4444" fillOpacity={0.55} />} isAnimationActive={false} />
            <Line dataKey="truth" name="truth" stroke="#111827" dot={false} strokeWidth={1.4} isAnimationActive={false} />{marks()}
          </ComposedChart>)}
        {chart("2 · Normalised innovation y/√S", "honest noise scatters on both sides of 0 — a lying sensor keeps leaning one way",
          <ComposedChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} /><XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={axis} tickFormatter={(v) => v.toFixed(0)} />
            <YAxis tick={axis} domain={[-6, 6]} allowDataOverflow /><Tooltip contentStyle={tip} formatter={(v: any) => Number(v).toFixed(2)} /><Legend wrapperStyle={{ fontSize: 10 }} />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <Scatter dataKey="e" name="innovation sample" fill="#2563eb" shape={(p: any) => <circle cx={p.cx} cy={p.cy} r={1.6} fill="#2563eb" fillOpacity={0.5} />} isAnimationActive={false} />
            <Line dataKey="mean" name="running mean" stroke="#111827" dot={false} strokeWidth={1.8} isAnimationActive={false} />{marks()}
          </ComposedChart>)}
        {chart("3 · CUSUM vs threshold — the exact moment", `adds up the one-sided lean; crossing h = ${st?.threshold ?? 14} raises SUSPECT, confirmation ISOLATES`,
          <ComposedChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} /><XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={axis} tickFormatter={(v) => v.toFixed(0)} />
            <YAxis tick={axis} domain={[0, Math.max(30, (st?.threshold ?? 14) * 3)]} allowDataOverflow /><Tooltip contentStyle={tip} formatter={(v: any) => Number(v).toFixed(2)} /><Legend wrapperStyle={{ fontSize: 10 }} />
            <ReferenceLine y={st?.threshold ?? 14} stroke="#dc2626" strokeDasharray="5 4" label={{ value: "threshold h", fill: "#dc2626", fontSize: 10, position: "insideTopLeft" }} />
            <Line dataKey="g" name="CUSUM" stroke="#7c3aed" dot={false} strokeWidth={2} isAnimationActive={false} />{marks(true)}
          </ComposedChart>)}
      </div>
      <div className="grid lg:grid-cols-[1fr_320px] gap-3 mt-3">
        {chart("4 · What the lie does to navigation", "EKF altitude estimate − truth. After isolation the remaining sensors pull it back.",
          <ComposedChart data={nav} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} /><XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={axis} tickFormatter={(v) => v.toFixed(0)} />
            <YAxis tick={axis} /><Tooltip contentStyle={tip} formatter={(v: any) => Number(v).toFixed(2)} /><ReferenceLine y={0} stroke="#9ca3af" />
            <Line dataKey="err" name="altitude estimate error [m]" stroke="#e03131" dot={false} strokeWidth={1.6} isAnimationActive={false} />{marks()}
          </ComposedChart>)}
        <div className="rounded-[14px] border p-3 text-[11.5px] text-ink2 leading-relaxed" style={{ background: "var(--sage-soft)" }}>
          <div className="eyebrow !text-[9.5px] mb-1">How it decides</div>
          <b>CUSUM</b> per sensor axis adds up how far each normalised innovation leans beyond ±{sh?.k ?? 0.5}σ; honest noise cancels out, a drift accumulates.
          <b> Blame</b>: the altimeter and TRN measure the same height independently — the cross-check (or the liar's opposite pull on its twin) names which one lies.
          If both disagree with the estimate <i>the same way</i> while agreeing with each other, the estimate itself was dragged: the <b>velocimeter</b> is blamed.
          Thresholds were calibrated on fault-free missions: 0 false alarms in the dataset.
        </div>
      </div>
    </section>
  );
}
