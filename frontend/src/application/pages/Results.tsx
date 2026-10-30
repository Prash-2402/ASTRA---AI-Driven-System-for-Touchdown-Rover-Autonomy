import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ErrorBar, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorNote, fmt, PageHeader, Panel } from "../../components/ui";
import { ErrorVsSigma, Series } from "../../charts/Series";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { PairedTable, ResultsTable } from "./ExperimentLab";

const ax = { fontSize: 10, fontFamily: "JetBrains Mono", fill: "#8A94A6" };
const C = { astra: "#4C6EF5", fsm: "#F08C00", pid: "#4C6EF5", mpc: "#12B886", ppo: "#E03131" } as Record<string, string>;

function Grouped({ rows, metric, label, ci }: { rows: any[]; metric: string; label: string; ci?: boolean }) {
  const ctrls = Array.from(new Set(rows.map((r) => r.controller)));
  const by: Record<string, any> = {};
  rows.forEach((r) => {
    const short: Record<string, string> = { nominal: "nominal", sensor_dropout: "dropout", terrain_misclassification: "misclass", power_drain: "power", actuator_degradation: "actuator",
      "paired:dropout+actuator": "dropout+act", "paired:misclass+power": "misclass+pwr", hazard: "hazard", disturbance: "gust" };
    const k = `${r.terrain === "-" ? "" : "T" + r.terrain + " · "}${short[r.condition] ?? r.condition}`;
    by[k] = by[k] || { name: k };
    if (metric === "completion_rate") { by[k][r.controller] = r.completion_rate; by[k][r.controller + "_e"] = [r.completion_rate - r.ci_low, r.ci_high - r.completion_rate]; }
    else by[k][r.controller] = r.metrics[metric]?.mean ?? null;
  });
  return <div style={{ height: 260 }}><ResponsiveContainer><BarChart data={Object.values(by)} margin={{ left: -10 }}><CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} />
    <XAxis dataKey="name" tick={{ ...ax, fontSize: 9.5 }} interval={0} angle={-30} textAnchor="end" height={64} /><YAxis tick={ax} label={{ value: label, angle: -90, position: "insideLeft", offset: 20, style: ax }} />
    <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid rgba(17,24,39,.1)", borderRadius: 12, fontSize: 11 }} formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)} /><Legend wrapperStyle={{ fontSize: 11 }} />
    {ctrls.map((c) => <Bar key={c} dataKey={c} fill={C[c] || "#AFC3A7"} radius={[6, 6, 0, 0]}>{ci && <ErrorBar dataKey={c + "_e"} stroke="#111827" width={4} />}</Bar>)}</BarChart></ResponsiveContainer></div>;
}

export default function Results() {
  const [split, setSplit] = useState<"held" | "dev">("held");
  const rover = usePoll(() => api.get(`/api/results/statistics?module=rover&held_out=${split === "held"}`), 8000, [split]);
  const td = usePoll(() => api.get("/api/results/statistics?module=touchdown"), 10000);
  const runs = usePoll(() => api.get("/api/runs?limit=40"), 10000);
  const training = usePoll(() => api.get("/api/touchdown/training"), 15000);
  const [runSel, setRunSel] = useState<string | null>(null);
  const tel = usePoll(() => (runSel ? api.get(`/api/runs/${runSel}/telemetry?every=2`) : Promise.resolve(null)), 0, [runSel]);
  const lastTrain = (training.data?.runs || []).filter((r: any) => r.status !== "failed").slice(-1)[0];
  const trainDetail = usePoll(() => (lastTrain ? api.get(`/api/touchdown/training/${lastTrain.run_id}`) : Promise.resolve(null)), 15000, [lastTrain?.run_id]);
  const rows = rover.data?.table || [];
  const single = rows.filter((r: any) => !r.condition.startsWith("paired")), paired = rows.filter((r: any) => r.condition.startsWith("paired"));
  const runMod = (runs.data || []).find((r: any) => r.run_uid === runSel)?.module;
  const series = (tel.data || []).map((fr: any) => runMod === "rover"
    ? { t: fr.t, err: fr.error.position, sig: fr.estimate.pos_sigma, herr: fr.error.heading, hsig: fr.estimate.sigma[4] }
    : { t: fr.t, err: Math.hypot(...fr.error.position), sig: Math.hypot(...fr.estimate.sigma.slice(0, 3)), herr: fr.error.position[2], hsig: fr.estimate.sigma[2] });
  return (
    <div>
      <PageHeader eyebrow="Generated from stored trials only" title="Results & Analytics">
        <div className="flex rounded-full bg-sage p-1">{(["held", "dev"] as const).map((s) => <button key={s} onClick={() => setSplit(s)} className={`px-4 py-1.5 rounded-full text-[13px] ${split === s ? "bg-surface shadow-soft" : "text-ink2"}`}>{s === "held" ? "Held-out terrains" : "Development terrains"}</button>)}</div>
      </PageHeader>
      <ErrorNote error={rover.error} />
      {rover.data && rover.data.trials_completed < rover.data.trials_total && <div className="panel-soft p-3 text-[12.5px] mb-5">INCOMPLETE: {rover.data.trials_completed} of {rover.data.trials_total} rover trials in this split have finished. Charts use completed trials only.</div>}
      {!rows.length ? <Empty title="No rover experiment results in this split">Create and run an experiment in the Experiment Lab.</Empty> : <>
        <div className="grid xl:grid-cols-2 gap-5">
          <Panel eyebrow="Primary metric" title="Mission completion rate (95 % Wilson CI) — single faults"><Grouped rows={single} metric="completion_rate" label="completion" ci /></Panel>
          <Panel eyebrow="Primary metric" title="Time to completion [s] (successful missions)"><Grouped rows={single} metric="time_to_completion_s" label="seconds" /></Panel>
          <Panel eyebrow="Secondary" title="Energy consumed [Wh]"><Grouped rows={single} metric="energy_used_wh" label="Wh" /></Panel>
          <Panel eyebrow="Secondary" title="Safety violations per mission"><Grouped rows={single} metric="safety_violations" label="count" /></Panel>
          <Panel eyebrow="Fault autonomy" title="Fault-detection delay [s]"><Grouped rows={single.filter((r: any) => r.condition !== "nominal")} metric="detection_delay_s" label="s" /></Panel>
          <Panel eyebrow="Fault autonomy" title="Classification accuracy (ASTRA) & recovery rate"><Grouped rows={single.filter((r: any) => r.condition !== "nominal")} metric="classification_accuracy" label="accuracy" /></Panel>
          {paired.length > 0 && <Panel eyebrow="Harder tier (reported separately)" title="Paired-fault completion (95 % CI)" className="xl:col-span-2"><Grouped rows={paired} metric="completion_rate" label="completion" ci /></Panel>}
        </div>
        <Panel eyebrow="Full table" title="Rover statistics" className="mt-5"><ResultsTable rows={rows} /></Panel>
        <Panel eyebrow="Matched seeds" title="Paired tests" className="mt-5"><PairedTable rows={rover.data.paired} /></Panel>
      </>}
      <div className="grid xl:grid-cols-2 gap-5 mt-5">
        <Panel eyebrow="Touchdown" title="Landing performance by controller">
          {td.data?.table?.length ? <><Grouped rows={td.data.table} metric="completion_rate" label="success" ci /><ResultsTable rows={td.data.table} /></> : <Empty title="No touchdown experiments yet" />}
        </Panel>
        <Panel eyebrow="Reinforcement learning" title={`Training performance ${lastTrain ? "· " + lastTrain.run_id : ""}`}>
          {trainDetail.data?.metrics?.length ? <Series data={trainDetail.data.metrics.filter((m: any) => m.type === "train")} x="timesteps" lines={[{ key: "episode_reward", name: "episode reward" }]} /> : <Empty title="No training metrics" />}
        </Panel>
      </div>
      <Panel eyebrow="State estimation" title="Estimation error vs covariance for a stored run" className="mt-5"
        right={<select className="select !w-auto" value={runSel ?? ""} onChange={(e) => setRunSel(e.target.value || null)}><option value="">select run…</option>{(runs.data || []).map((r: any) => <option key={r.run_uid} value={r.run_uid}>{r.module} · {r.controller} · {r.outcome} · {r.run_uid.slice(-10)}</option>)}</select>}>
        {series.length ? <div className="grid md:grid-cols-2 gap-5"><ErrorVsSigma data={series} err="err" sig="sig" title="|position error| [m]" /><ErrorVsSigma data={series} err="herr" sig="hsig" title={runMod === "rover" ? "|heading error| [rad]" : "vertical error [m]"} /></div>
          : <div className="text-[12px] text-muted">Pick a run with a telemetry archive.</div>}
        <p className="text-[11px] text-muted mt-2">The shaded band is the filter's own ±2σ. A filter can be confidently wrong — compare the band with the actual error, never the band alone.</p>
      </Panel>
    </div>
  );
}
