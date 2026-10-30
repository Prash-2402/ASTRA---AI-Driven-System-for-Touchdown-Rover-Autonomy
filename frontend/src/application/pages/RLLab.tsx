import { useState } from "react";
import { Empty, ErrorNote, Field, fmt, PageHeader, Panel, Stat, StatusPill } from "../../components/ui";
import { Series } from "../../charts/Series";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";

export default function RLLab() {
  const runs = usePoll(() => api.get("/api/touchdown/training"), 5000);
  const [sel, setSel] = useState<string | null>(null);
  const [form, setForm] = useState({ timesteps: 100000, envs: 2, seed: 0 });
  const [err, setErr] = useState<string | null>(null);
  const list: any[] = runs.data?.runs || [];
  const current = sel ?? list[list.length - 1]?.run_id ?? null;
  const detail = usePoll(() => (current ? api.get(`/api/touchdown/training/${current}`) : Promise.resolve(null)), 5000, [current]);
  const train = (detail.data?.metrics || []).filter((m: any) => m.type === "train");
  const evals = (detail.data?.metrics || []).filter((m: any) => m.type === "eval");
  const meta = detail.data?.metadata;
  const start = async () => { setErr(null); try { const r = await api.post("/api/touchdown/training", form); setSel(r.run_id); runs.refresh(); } catch (e: any) { setErr(e.message); } };
  return (
    <div>
      <PageHeader eyebrow="Proximal Policy Optimization · Stable-Baselines3" title="Reinforcement Learning Lab" />
      <ErrorNote error={err || runs.error} />
      <div className="grid lg:grid-cols-[340px_1fr] gap-5">
        <div className="space-y-5">
          <Panel eyebrow="New run" title="Train a touchdown policy">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Timesteps"><input className="input num" type="number" value={form.timesteps} onChange={(e) => setForm({ ...form, timesteps: +e.target.value })} /></Field>
              <Field label="Parallel envs"><input className="input num" type="number" value={form.envs} onChange={(e) => setForm({ ...form, envs: +e.target.value })} /></Field>
              <Field label="Seed"><input className="input num" type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: +e.target.value })} /></Field>
            </div>
            <button className="btn btn-primary mt-4 w-full justify-center" onClick={start}>Start training</button>
            <p className="text-[11px] text-muted mt-3">Policy acts at 10 Hz on EKF estimates; full physics + sensors run inside the environment. A model is only offered to Mission Control after training <b>completes</b>.</p>
          </Panel>
          <Panel eyebrow="Registry" title="Training runs">
            {list.length ? <div className="space-y-1.5">{[...list].reverse().map((r) => (
              <button key={r.run_id} onClick={() => setSel(r.run_id)} className={`w-full text-left rounded-[12px] px-3 py-2 border ${current === r.run_id ? "bg-sage" : "hover:bg-sage-soft"}`}>
                <div className="num text-[11.5px]">{r.run_id}</div>
                <div className="flex gap-2 items-center mt-1"><StatusPill status={r.status} />{r.final_evaluation && <span className="chip">success {fmt(r.final_evaluation.success_rate * 100, 0)}%</span>}</div>
              </button>))}</div> : <Empty title="No training runs" />}
          </Panel>
        </div>
        <div className="space-y-5 min-w-0">
          {meta ? <>
            <Panel eyebrow={current ?? ""} title="Run summary">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <Stat label="Status" value={meta.status} tone={meta.status === "failed" ? "bad" : undefined} />
                <Stat label="Timesteps" value={train.length ? train[train.length - 1].timesteps.toLocaleString() : 0} sub={`target ${meta.timesteps_target?.toLocaleString()}`} />
                <Stat label="Episodes" value={train.length ? train[train.length - 1].episodes : 0} />
                <Stat label="Last eval success" value={evals.length ? `${fmt(evals[evals.length - 1].success_rate * 100, 0)}%` : "—"} />
                <Stat label="Env version" value={meta.environment_version ? "v2" : "v1"} />
              </div>
              {meta.error && <ErrorNote error={meta.error} />}
            </Panel>
            <div className="grid md:grid-cols-2 gap-5">
              <Panel eyebrow="Rollouts" title="Episode reward"><Series data={train} x="timesteps" lines={[{ key: "episode_reward", name: "mean reward (20 ep)" }]} /></Panel>
              <Panel eyebrow="Rollouts" title="Success rate & episode length"><Series data={train} x="timesteps" lines={[{ key: "success_rate", name: "success" }]} height={110} /><Series data={train} x="timesteps" lines={[{ key: "episode_length", name: "length [steps]", color: "#7798A3" }]} height={110} /></Panel>
              <Panel eyebrow="Optimisation" title="Policy & value loss"><Series data={train} x="timesteps" lines={[{ key: "policy_loss", name: "policy loss" }]} height={110} /><Series data={train} x="timesteps" lines={[{ key: "value_loss", name: "value loss", color: "#D69B4D" }]} height={110} /></Panel>
              <Panel eyebrow="Optimisation" title="Entropy & approx. KL"><Series data={train} x="timesteps" lines={[{ key: "entropy", name: "entropy" }, { key: "approx_kl", name: "approx KL", color: "#C76C64" }]} /></Panel>
            </div>
            <Panel eyebrow="Deterministic evaluation episodes" title="Evaluation performance">
              {evals.length ? <table className="table"><thead><tr><th>timesteps</th><th>episodes</th><th>success</th><th>mean return</th><th>landing error [m]</th><th>|vz| [m/s]</th><th>fuel [kg]</th></tr></thead><tbody>
                {evals.map((e: any, i: number) => <tr key={i}><td className="num">{e.timesteps}{e.final ? " (final)" : ""}</td><td className="num">{e.episodes}</td><td className="num">{fmt(e.success_rate * 100, 0)}%</td><td className="num">{fmt(e.mean_return, 1)}</td><td className="num">{fmt(e.mean_landing_error_m, 1)}</td><td className="num">{fmt(e.mean_touchdown_speed, 2)}</td><td className="num">{fmt(e.mean_fuel_kg, 0)}</td></tr>)}</tbody></table>
                : <div className="text-[12px] text-muted">No evaluation checkpoints yet.</div>}
            </Panel>
          </> : <Empty title="Select or start a training run" />}
        </div>
      </div>
    </div>
  );
}
