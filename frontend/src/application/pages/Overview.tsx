import { Link } from "react-router-dom";
import { Empty, ErrorNote, fmt, PageHeader, Panel, Stat, StatusPill } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

export default function Overview() {
  const { data, error } = usePoll(() => api.get("/api/platform/status"), 3000);
  const events = useSim((s) => s.events);
  const sess = data?.sessions || {};
  return (
    <div>
      <PageHeader eyebrow="Research laboratory" title={<>Good to see you in <em>ASTRA</em>.</>}>
        <Link to="/app/mission-control" className="btn btn-primary">Open Mission Control</Link>
      </PageHeader>
      <ErrorNote error={error && `Backend unreachable: ${error}. Start it with: uvicorn backend.api.main:app`} />
      <div className="grid lg:grid-cols-[1.35fr_1fr] gap-5 items-start">
        <div className="grid sm:grid-cols-2 gap-5 content-start">
          {(["touchdown", "rover"] as const).map((m) => (
            <Link key={m} to={`/app/${m}`} className="panel p-6 hover:shadow-card transition-shadow block">
              <div className="flex justify-between items-start">
                <div className="eyebrow">Module {m === "touchdown" ? "1" : "2"}</div><StatusPill status={sess[m]?.status ?? "idle"} />
              </div>
              <div className="h-display text-4xl mt-3">{m === "touchdown" ? "Touchdown" : "Rover"}</div>
              <p className="text-[13px] text-ink2 mt-2">{m === "touchdown" ? "6-DOF powered descent, EKF, PID / MPC / PPO, hazard-driven diversion." : "PyBullet rocker-bogie traverse, four injected faults, adaptive A* vs FSM."}</p>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <Stat label="Sim time" value={fmt(sess[m]?.t, 1)} unit="s" />
                <Stat label="Controllers" value={m === "touchdown" ? Object.entries(data?.controllers?.touchdown || {}).filter(([k, v]) => ["pid", "mpc", "ppo"].includes(k) && v).length + "/3" : "2/2"} sub={m === "touchdown" && data && !data.controllers?.touchdown?.ppo ? "PPO: no trained policy yet" : undefined} />
              </div>
            </Link>
          ))}
          <Panel eyebrow="Records" title="Platform activity" className="sm:col-span-2">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              <Stat label="Interactive + trial runs" value={data?.counts?.runs ?? "—"} />
              <Stat label="Experiments" value={data?.counts?.experiments ?? "—"} />
              <Stat label="Completed exps." value={data?.counts?.experiments_completed ?? "—"} />
              <Stat label="Decisions logged" value={data?.counts?.decisions ?? "—"} />
              <Stat label="Training runs" value={data?.counts?.training_runs ?? "—"} />
            </div>
          </Panel>
        </div>
        <div className="space-y-5">
          <Panel eyebrow="System health" title="Services">
            <div className="space-y-2 text-[13px]">
              <Row k="API" v={data ? `v${data.version}` : "offline"} ok={!!data} />
              <Row k="PostgreSQL" v={data?.database?.connected ? `migration ${data.database.migration}` : data?.database?.error ?? "—"} ok={!!data?.database?.connected} />
              <Row k="PyBullet" v={data?.software?.pybullet_api ? `API ${data.software.pybullet_api}` : "unavailable"} ok={!!data?.software?.pybullet_api} />
              <Row k="Build" v={data?.software?.git_commit ?? "—"} ok={!!data} />
            </div>
          </Panel>
          <Panel eyebrow="Recent runs" title="Latest completed missions">
            {data?.recent_runs?.length ? (
              <table className="table"><tbody>{data.recent_runs.map((r: any) => (
                <tr key={r.run_uid}><td className="num text-[11px]">{r.run_uid.slice(0, 22)}</td><td>{r.module}</td><td>{r.controller}</td>
                  <td><span className="chip" style={{ color: r.success ? "var(--success)" : "var(--danger)" }}>{r.outcome ?? r.status}</span></td></tr>))}</tbody></table>
            ) : <Empty title="No runs yet">Completed missions and experiment trials will appear here.</Empty>}
          </Panel>
          <Panel eyebrow="Live" title="Recent activity">
            {events.length ? <ul className="space-y-1 text-[12px] max-h-56 overflow-auto scroll-thin">{[...events].reverse().slice(0, 30).map((e, i) => <li key={i}><span className="num text-muted">{e.module} {fmt(e.t, 1)}s</span> · {e.message}</li>)}</ul>
              : <div className="text-[12px] text-muted">No live events in this session.</div>}
          </Panel>
        </div>
      </div>
    </div>
  );
}
const Row = ({ k, v, ok }: { k: string; v: string; ok: boolean }) => (
  <div className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="dot" style={{ background: ok ? "var(--success)" : "var(--danger)" }} />{k}</span><span className="num text-[11.5px] text-ink2 truncate max-w-[60%]">{v}</span></div>);
