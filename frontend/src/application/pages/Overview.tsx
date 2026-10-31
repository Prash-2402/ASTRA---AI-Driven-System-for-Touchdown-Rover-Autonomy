import { Link } from "react-router-dom";
import { Empty, ErrorNote, fmt, PageHeader, Panel, Stat, StatusPill } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

/** Small inline illustrations for the three simulation cards (pure SVG, theme-aware). */
const ART: Record<string, JSX.Element> = {
  rover: (<svg viewBox="0 0 220 110" className="w-full h-full" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="gr" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#FCE9DC" /><stop offset="1" stopColor="#F6D3BC" /></linearGradient></defs>
    <rect width="220" height="110" fill="url(#gr)" /><path d="M0 82 Q55 70 110 80 T220 76 V110 H0Z" fill="#E7B494" /><path d="M0 92 Q70 84 140 92 T220 90 V110 H0Z" fill="#D99C78" />
    <g transform="translate(78 48)"><rect x="0" y="12" width="56" height="14" rx="3" fill="#fff" stroke="#9AA3B5" /><rect x="40" y="-8" width="4" height="22" fill="#9AA3B5" /><rect x="34" y="-14" width="16" height="8" rx="2" fill="#fff" stroke="#9AA3B5" />
      <path d="M6 26 L16 34 L30 26 L44 34 L52 26" stroke="#6B7280" strokeWidth="2.5" fill="none" />{[8, 30, 52].map((x) => <circle key={x} cx={x} cy="36" r="6" fill="#4B5563" />)}</g></svg>),
  moon: (<svg viewBox="0 0 220 110" className="w-full h-full" preserveAspectRatio="xMidYMid slice"><rect width="220" height="110" fill="#26221F" />{[[20, 15], [60, 30], [150, 12], [190, 40], [100, 20], [170, 25]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1" fill="#fff" />)}
    <circle cx="185" cy="22" r="9" fill="#7A1F35" /><path d="M0 84 Q60 76 120 82 T220 80 V110 H0Z" fill="#9CA3AF" /><ellipse cx="60" cy="94" rx="18" ry="4" fill="#6B7280" />
    <g transform="translate(96 40)"><rect x="6" y="0" width="20" height="14" fill="#D1D5DB" /><rect x="2" y="14" width="28" height="12" fill="#E0A82E" /><path d="M2 26 L-6 40 M30 26 L38 40" stroke="#E0A82E" strokeWidth="2" /><path d="M10 26 L16 40 L22 26Z" fill="#E5E7EB" opacity=".8" /></g></svg>),
  touchdown: (<svg viewBox="0 0 220 110" className="w-full h-full" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="gt" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#E8EDFF" /><stop offset="1" stopColor="#FBE3D3" /></linearGradient></defs>
    <rect width="220" height="110" fill="url(#gt)" /><path d="M0 86 Q80 78 150 86 T220 84 V110 H0Z" fill="#E2A47F" /><path d="M110 8 C108 30 100 50 104 66" stroke="#7A1F35" strokeDasharray="4 4" fill="none" />
    <g transform="translate(92 54)"><polygon points="4,0 24,0 28,10 0,10" fill="#E0A82E" /><path d="M2 10 L-6 22 M26 10 L34 22" stroke="#6B7280" strokeWidth="2" /><path d="M10 10 L14 24 L18 10Z" fill="#F59F00" opacity=".8" /></g>
    <g transform="translate(26 14)"><rect x="0" y="4" width="10" height="8" fill="#E0A82E" /><rect x="-16" y="6" width="14" height="4" fill="#5C1527" /><rect x="12" y="6" width="14" height="4" fill="#5C1527" /></g></svg>),
};

export default function Overview() {
  const { data, error } = usePoll(() => api.get("/api/platform/status"), 3000);
  const events = useSim((s) => s.events);
  const sess = data?.sessions || {};
  const sims: [string, string, string, string][] = [
    ["touchdown", "Landing · Mars & Moon", "Autonomous powered descent: lidar scans the pad and surroundings, detects obstacles and re-plans to a safe site.", "/app/landing?env=mars"],
    ["moon", "Landing · Apollo LM", "Lunar Module P64 approach and P66 terminal descent in 1.625 m/s² gravity, with regolith dust.", "/app/landing?env=moon&type=apollo"],
    ["rover", "Rover Ground Operations", "After landing: autonomous sample collection and imaging, obstacle avoidance, dust storms, comms loss and return to the lander.", "/app/rover"],
  ];
  return (
    <div>
      <PageHeader eyebrow="Overview of the platform" title={<>Mission <em>Dashboard</em></>}>
        <Link to="/app/mission-control" className="btn btn-primary">Open Mission Control</Link>
      </PageHeader>
      <ErrorNote error={error && `Backend unreachable: ${error}. Start it with: uvicorn backend.api.main:app`} />
      <div className="panel p-5 mb-5 grid grid-cols-2 md:grid-cols-5 gap-5">
        <Stat label="Runs recorded" value={data?.counts?.runs ?? "—"} />
        <Stat label="Experiments" value={data?.counts?.experiments ?? "—"} sub={`${data?.counts?.experiments_completed ?? 0} completed`} />
        <Stat label="Decisions audited" value={data?.counts?.decisions ?? "—"} />
        <Stat label="Training runs" value={data?.counts?.training_runs ?? "—"} />
        <Stat label="Database" value={data?.database?.connected ? "online" : "offline"} tone={data?.database?.connected ? "ok" : "bad"} sub={data?.database?.migration ? `migration ${data.database.migration}` : undefined} />
      </div>
      <div className="grid md:grid-cols-3 gap-5 mb-5">
        {sims.map(([id, name, desc, to]) => (
          <Link key={id} to={to} className="panel sim-card">
            <div className="h-[120px] border-b" style={{ borderColor: "var(--border)" }}>{ART[id]}</div>
            <div className="p-5">
              <div className="flex justify-between items-center"><div className="eyebrow">Simulation</div><StatusPill status={sess[id]?.status ?? "idle"} /></div>
              <div className="h-display text-[24px] mt-2">{name}</div>
              <p className="text-[13px] text-ink2 mt-1.5 leading-relaxed min-h-[60px]">{desc}</p>
              <div className="mt-3 flex items-center justify-between text-[12px]">
                <span className="num text-muted">t = {fmt(sess[id]?.t, 1)} s</span>
                <span className="text-[var(--primary)] font-semibold">Open →</span>
              </div>
            </div>
          </Link>))}
      </div>
      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-5 items-start">
        <Panel eyebrow="Recent runs" title="Latest completed missions">
          {data?.recent_runs?.length ? (
            <table className="table nowrap"><thead><tr><th>run</th><th>module</th><th>controller</th><th>outcome</th></tr></thead><tbody>{data.recent_runs.map((r: any) => (
              <tr key={r.run_uid}><td className="num text-[11.5px]">{r.run_uid}</td><td>{r.module}</td><td>{r.controller}</td>
                <td><span className="chip" style={{ color: r.success ? "var(--success)" : "var(--danger)" }}>{r.outcome ?? r.status}</span></td></tr>))}</tbody></table>
          ) : <Empty title="No runs yet">Completed missions and experiment trials will appear here.</Empty>}
        </Panel>
        <div className="space-y-5">
          <Panel eyebrow="System health" title="Services">
            <div className="space-y-2.5 text-[13px]">
              <Row k="API" v={data ? `v${data.version}` : "offline"} ok={!!data} />
              <Row k="PostgreSQL" v={data?.database?.connected ? `migration ${data.database.migration}` : data?.database?.error ?? "—"} ok={!!data?.database?.connected} />
              <Row k="PyBullet" v={data?.software?.pybullet_api ? `API ${data.software.pybullet_api}` : "unavailable"} ok={!!data?.software?.pybullet_api} />
              <Row k="Touchdown controllers" v={data ? `PID · MPC · PPO ${data.controllers?.touchdown?.ppo ? "✓" : "(untrained)"}` : "—"} ok={!!data} />
            </div>
          </Panel>
          <Panel eyebrow="Live" title="Recent activity">
            {events.length ? <ul className="space-y-1.5 text-[12px] max-h-56 overflow-auto scroll-thin">{[...events].reverse().slice(0, 30).map((e, i) => <li key={i}><span className="num text-muted">{e.module} {fmt(e.t, 1)}s</span> · {e.message}</li>)}</ul>
              : <div className="text-[12px] text-muted">No live events in this session.</div>}
          </Panel>
        </div>
      </div>
    </div>
  );
}
const Row = ({ k, v, ok }: { k: string; v: string; ok: boolean }) => (
  <div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2"><span className="dot" style={{ background: ok ? "var(--success)" : "var(--danger)" }} />{k}</span><span className="num text-[11.5px] text-ink2 truncate max-w-[60%]">{v}</span></div>);
