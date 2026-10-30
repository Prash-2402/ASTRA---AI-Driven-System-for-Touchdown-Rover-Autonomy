import { useState } from "react";
import { Empty, ErrorNote, Field, fmt, PageHeader, Panel, StatusPill } from "../../components/ui";
import { useChannel, usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";

export function ResultsTable({ rows }: { rows: any[] }) {
  return (
    <div className="overflow-x-auto scroll-thin"><table className="table"><thead><tr><th>terrain</th><th>condition</th><th>controller</th><th>n</th><th>completion</th><th>95 % Wilson CI</th><th>time to completion [s]</th><th>energy [Wh]</th><th>violations</th><th>detect delay [s]</th><th>class. acc.</th></tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}><td className="num">{r.terrain}</td><td>{r.condition}</td><td className="font-medium">{r.controller}</td><td className="num">{r.n}</td>
        <td className="num">{r.successes}/{r.n} = {fmt(r.completion_rate, 2)}</td><td className="num">[{fmt(r.ci_low, 2)}, {fmt(r.ci_high, 2)}]</td>
        <td className="num">{r.metrics.time_to_completion_s?.n ? `${fmt(r.metrics.time_to_completion_s.mean, 0)} ± ${fmt(r.metrics.time_to_completion_s.sd, 0)} (n=${r.metrics.time_to_completion_s.n})` : r.metrics.mission_time_s ? fmt(r.metrics.mission_time_s.mean, 0) : "—"}</td>
        <td className="num">{r.metrics.energy_used_wh ? `${fmt(r.metrics.energy_used_wh.mean)} ± ${fmt(r.metrics.energy_used_wh.sd)}` : r.metrics.fuel_used_kg ? `${fmt(r.metrics.fuel_used_kg.mean, 0)} kg` : "—"}</td>
        <td className="num">{fmt(r.metrics.safety_violations?.mean)}</td><td className="num">{fmt(r.metrics.detection_delay_s?.mean, 1)}</td><td className="num">{fmt(r.metrics.classification_accuracy?.mean)}</td></tr>)}</tbody></table></div>
  );
}

export function PairedTable({ rows }: { rows: any[] }) {
  if (!rows?.length) return null;
  return (
    <div className="overflow-x-auto scroll-thin"><table className="table"><thead><tr><th>terrain</th><th>condition</th><th>metric</th><th>pairs</th><th>mean diff (ASTRA − FSM)</th><th>test</th><th>p</th></tr></thead>
      <tbody>{rows.map((p, i) => <tr key={i}><td className="num">{p.terrain}</td><td>{p.condition}</td><td>{p.metric}</td><td className="num">{p.n}</td><td className="num">{fmt(p.mean_diff, 3)}</td><td>{p.test}</td><td className="num">{fmt(p.p_value, 3)}</td></tr>)}</tbody></table></div>
  );
}

export default function ExperimentLab() {
  const list = usePoll(() => api.get("/api/experiments"), 4000);
  const conds = usePoll(() => api.get("/api/experiments/conditions"), 0);
  const [sel, setSel] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState<any>({ name: "Rover fault-response evaluation", module: "rover", held_out: false, terrains: [1], conditions: ["nominal", "actuator_degradation"], controllers: ["astra", "fsm"], trials: 5, base_seed: 1000 });
  const [prog, setProg] = useState<Record<number, any>>({});
  useChannel("experiments", (m: any) => setProg((p) => ({ ...p, [m.id]: m })));
  const exps: any[] = list.data || [];
  const cur = sel ?? exps[0]?.id ?? null;
  const res = usePoll(() => (cur ? api.get(`/api/experiments/${cur}/results`) : Promise.resolve(null)), 6000, [cur]);
  const toggle = (k: string, v: any) => setF({ ...f, [k]: f[k].includes(v) ? f[k].filter((x: any) => x !== v) : [...f[k], v] });
  const create = async (run: boolean) => {
    setErr(null);
    try { const e = await api.post("/api/experiments", f); if (run) await api.post(`/api/experiments/${e.id}/run`); setSel(e.id); list.refresh(); } catch (e: any) { setErr(e.message); }
  };
  const allConds: string[] = f.module === "rover" ? conds.data?.rover?.all || [] : conds.data?.touchdown || [];
  const terrOpts = f.held_out ? [4, 5] : [1, 2, 3];
  const n = f.trials * f.conditions.length * f.controllers.length * (f.module === "rover" ? f.terrains.length : 1);
  return (
    <div>
      <PageHeader eyebrow="Matched, reproducible batches" title="Experiment Lab" />
      <ErrorNote error={err || list.error} />
      <div className="grid xl:grid-cols-[380px_1fr] gap-5">
        <div className="space-y-5">
          <Panel eyebrow="Design" title="New experiment">
            <div className="space-y-3">
              <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Module"><select className="select" value={f.module} onChange={(e) => setF({ ...f, module: e.target.value, controllers: e.target.value === "rover" ? ["astra", "fsm"] : ["pid", "mpc"], conditions: ["nominal"] })}><option value="rover">Rover</option><option value="touchdown">Touchdown</option></select></Field>
                <Field label="Trials per cell (matched seeds)"><input className="input num" type="number" value={f.trials} onChange={(e) => setF({ ...f, trials: +e.target.value })} /></Field>
                <Field label="Base seed"><input className="input num" type="number" value={f.base_seed} onChange={(e) => setF({ ...f, base_seed: +e.target.value })} /></Field>
              </div>
              {f.module === "rover" && <>
                <label className="flex items-center gap-2 text-[12.5px]"><input type="checkbox" checked={f.held_out} onChange={(e) => setF({ ...f, held_out: e.target.checked, terrains: e.target.checked ? [4, 5] : [1] })} /> Held-out evaluation mode (terrains 4–5 only)</label>
                <div><span className="label">Terrains</span><div className="flex gap-2">{terrOpts.map((t) => <button key={t} className={`chip ${f.terrains.includes(t) ? "!bg-sage !text-ink" : ""}`} onClick={() => toggle("terrains", t)}>T{t}</button>)}</div></div>
              </>}
              <div><span className="label">Conditions</span><div className="flex flex-wrap gap-1.5">{allConds.map((c) => <button key={c} className={`chip ${f.conditions.includes(c) ? "!bg-sage !text-ink" : ""}`} onClick={() => toggle("conditions", c)}>{c}</button>)}</div></div>
              <div><span className="label">Controllers</span><div className="flex gap-1.5">{(f.module === "rover" ? ["astra", "fsm"] : ["pid", "mpc", "ppo"]).map((c) => <button key={c} className={`chip ${f.controllers.includes(c) ? "!bg-sage !text-ink" : ""}`} onClick={() => toggle("controllers", c)}>{c}</button>)}</div></div>
              <div className="text-[12px] text-ink2">{n} trials will be created.</div>
              <div className="flex gap-2"><button className="btn btn-ghost" onClick={() => create(false)}>Create</button><button className="btn btn-primary" onClick={() => create(true)}>Create & run</button></div>
            </div>
          </Panel>
          <Panel eyebrow="History" title="Experiments">
            {exps.length ? <div className="space-y-1.5 max-h-[420px] overflow-auto scroll-thin">{exps.map((e) => {
              const p = prog[e.id]?.progress || e.progress;
              return <button key={e.id} onClick={() => setSel(e.id)} className={`w-full text-left rounded-[12px] px-3 py-2 border ${cur === e.id ? "bg-sage" : "hover:bg-sage-soft"}`}>
                <div className="text-[12.5px] font-medium">#{e.id} {e.name}</div>
                <div className="flex items-center gap-2 mt-1"><StatusPill status={prog[e.id]?.status || e.status} /><span className="num text-[11px] text-muted">{p?.done}/{p?.total}</span>{e.held_out && <span className="chip">held-out</span>}</div>
                {p?.total > 0 && <div className="h-1 bg-sage-soft rounded mt-2"><div className="h-1 bg-primary rounded" style={{ width: `${(100 * p.done) / p.total}%` }} /></div>}
              </button>; })}</div> : <Empty title="No experiments yet" />}
          </Panel>
        </div>
        <div className="space-y-5 min-w-0">
          {res.data ? <>
            <Panel eyebrow={`Experiment #${cur}`} title={res.data.complete ? "Results (complete)" : `Results — INCOMPLETE (${res.data.trials_completed}/${res.data.trials_total} trials)`}
              right={<div className="flex gap-2">{["csv", "json", "pdf"].map((x) => <a key={x} className="btn btn-ghost !py-1.5" href={api.url(`/api/experiments/${cur}/export?format=${x}`)} target="_blank" rel="noreferrer">{x.toUpperCase()}</a>)}
                {exps.find((e) => e.id === cur)?.status !== "running" && !res.data.complete && <button className="btn btn-sage !py-1.5" onClick={() => api.post(`/api/experiments/${cur}/run`).then(list.refresh).catch((e) => setErr(e.message))}>Run / resume</button>}
                {exps.find((e) => e.id === cur)?.status === "running" && <button className="btn btn-danger !py-1.5" onClick={() => api.post(`/api/experiments/${cur}/cancel`).then(list.refresh)}>Cancel</button>}</div>}>
              {!res.data.complete && <div className="panel-soft p-3 text-[12px] mb-3">Statistics below use only completed trials and will change as the batch progresses.</div>}
              {res.data.table?.length ? <ResultsTable rows={res.data.table} /> : <Empty title="No completed trials yet" />}
            </Panel>
            {res.data.paired?.length > 0 && <Panel eyebrow="Matched seeds" title="Paired ASTRA vs FSM tests"><PairedTable rows={res.data.paired} />
              <p className="text-[11px] text-muted mt-2">McNemar exact on discordant success pairs; Wilcoxon signed-rank on pairs where both values exist. With small n, p-values are descriptive only.</p></Panel>}
          </> : <Empty title="Select an experiment" />}
        </div>
      </div>
    </div>
  );
}
