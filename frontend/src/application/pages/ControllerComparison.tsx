import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorNote, fmt, PageHeader, Panel } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";

const ax = { fontSize: 10, fontFamily: "JetBrains Mono", fill: "#849084" };
function RateChart({ rows }: { rows: any[] }) {
  const d = rows.map((r) => ({ name: r.controller, rate: r.completion_rate, err: [r.completion_rate - r.ci_low, r.ci_high - r.completion_rate] }));
  return <div style={{ height: 220 }}><ResponsiveContainer><BarChart data={d}><CartesianGrid stroke="rgba(83,111,89,.1)" vertical={false} /><XAxis dataKey="name" tick={ax} /><YAxis domain={[0, 1]} tick={ax} />
    <Tooltip formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)} /><Bar dataKey="rate" fill="#779477" radius={[8, 8, 0, 0]}><ErrorBar dataKey="err" stroke="#26372D" width={6} /></Bar></BarChart></ResponsiveContainer></div>;
}

export default function ControllerComparison() {
  const td = usePoll(() => api.get("/api/results/compare?module=touchdown"), 5000);
  const rv = usePoll(() => api.get("/api/results/compare?module=rover"), 5000);
  return (
    <div>
      <PageHeader eyebrow="Like-for-like only" title="Controller Comparison" />
      <ErrorNote error={td.error || rv.error} />
      <div className="panel-soft p-4 text-[12.5px] text-ink2 mb-5">
        Touchdown controllers (PID, MPC, PPO) are compared on landing metrics; rover controllers (ASTRA, FSM) on traverse metrics. The two groups solve
        different problems and are <b>never compared with each other</b>. Pooled numbers below mix scenarios — use the Experiment Lab for matched, condition-specific comparisons.
      </div>
      <div className="grid xl:grid-cols-2 gap-5">
        <Panel eyebrow="Touchdown · all stored runs" title="Landing success (95 % Wilson CI)">
          {td.data?.controllers?.length ? <>
            <RateChart rows={td.data.controllers} />
            <table className="table mt-3"><thead><tr><th>controller</th><th>n</th><th>success</th><th>landing error [m]</th><th>fuel [kg]</th><th>|vz| at contact</th></tr></thead><tbody>
              {td.data.controllers.map((r: any) => <tr key={r.controller}><td>{r.controller.toUpperCase()}</td><td className="num">{r.n}</td><td className="num">{r.successes}/{r.n}</td>
                <td className="num">{fmt(r.landing_error_m.mean)} ± {fmt(r.landing_error_m.sd)}</td><td className="num">{fmt(r.fuel_used_kg.mean, 1)}</td><td className="num">{fmt(r.touchdown_speed.mean)}</td></tr>)}</tbody></table>
          </> : <Empty title="No touchdown runs yet">Run missions or a touchdown experiment to populate this comparison.</Empty>}
        </Panel>
        <Panel eyebrow="Rover · all stored runs" title="Mission completion (95 % Wilson CI)">
          {rv.data?.controllers?.length ? <>
            <RateChart rows={rv.data.controllers} />
            <table className="table mt-3"><thead><tr><th>controller</th><th>n</th><th>success</th><th>time [s] (successes)</th><th>energy [Wh]</th><th>collisions</th></tr></thead><tbody>
              {rv.data.controllers.map((r: any) => <tr key={r.controller}><td>{r.controller.toUpperCase()}</td><td className="num">{r.n}</td><td className="num">{r.successes}/{r.n}</td>
                <td className="num">{fmt(r.time_to_completion_s.mean, 0)} (n={r.time_to_completion_s.n})</td><td className="num">{fmt(r.energy_used_wh.mean)}</td><td className="num">{fmt(r.collisions.mean)}</td></tr>)}</tbody></table>
          </> : <Empty title="No rover runs yet">Run traverses or an experiment batch.</Empty>}
        </Panel>
      </div>
    </div>
  );
}
