import { fmt } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { StatCards } from "./LandingHistory";

/** Shown over the 3D view the moment a landing finishes: this landing's result, the running success /
 *  accuracy / precision over all recorded landings, and the next actions. */
export default function LandingResultCard({ live, onReplay, onHistory, onClose }: { live: any; onReplay: () => void; onHistory: () => void; onClose: () => void }) {
  const r = live?.result || {};
  const td = r.touchdown || {};
  // the run is persisted a moment after touchdown; poll until the database has it (replay + report need it)
  const info = usePoll(() => api.get("/api/touchdown/telemetry").then((t) => ({ db: t.db_run_id, perr: t.persist_error })), 1500, [live?.run_uid]);
  const stored = !!info.data?.db;
  const hist = usePoll(() => (stored ? api.get(`/api/touchdown/history?limit=500&controller=${r.controller}`) : Promise.resolve(null)), 0, [stored, live?.run_uid]);
  const ok = !!r.success;
  const checks = td.checks ? Object.entries(td.checks) : [];
  const faults = Object.entries(r.sensor_faults || {});
  return (
    <div className="absolute inset-0 z-20 grid place-items-center p-4" style={{ background: "rgba(8,10,16,.45)" }}>
      <div className="panel w-full max-w-[760px] p-5 max-h-full overflow-y-auto scroll-thin">
        <div className="flex items-start justify-between gap-3">
          <div><div className="eyebrow">Landing complete · {String(r.controller ?? "").toUpperCase()} · t = {fmt(r.mission_time_s, 1)} s</div>
            <h3 className={`h-display text-[28px] mt-1 ${ok ? "text-ink" : "text-danger"}`}>{ok ? "Landed safely" : r.outcome === "crash" ? "Touchdown limits violated" : `Outcome: ${r.outcome}`}</h3></div>
          <button className="btn btn-ghost !py-1.5" onClick={onClose}>✕</button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          {[["Accuracy (this landing)", `${fmt(r.landing_error_m, 2)} m`, "distance from the final pad"],
            ["Touchdown speed", `${fmt(Math.abs(td.vertical_speed ?? NaN), 2)} m/s`, `horizontal ${fmt(td.horizontal_speed, 2)} m/s`],
            ["Diversions", String(r.diversions ?? 0), r.diversions ? `${fmt(r.distance_from_original_target_m, 0)} m from the original pad` : "landed on the planned pad"],
            ["Fuel used", `${fmt(r.fuel_used_kg, 0)} kg`, `${fmt(r.fuel_remaining_kg, 0)} kg left`]].map(([l, v, s]) => (
            <div key={l} className="rounded-[14px] border p-3" style={{ background: "var(--ivory)" }}><div className="eyebrow !text-[9.5px]">{l}</div>
              <div className="num text-[20px] text-ink mt-0.5">{v}</div><div className="text-[10.5px] text-muted">{s}</div></div>))}
        </div>
        {checks.length > 0 && <div className="flex flex-wrap gap-1.5 mt-3">{checks.map(([k, v]: any) => <span key={k} className={`chip ${v ? "" : "!text-white !bg-[var(--danger)]"}`}>{v ? "✓" : "✕"} {k.replace(/_ok$/, "").replace(/_/g, " ")}</span>)}
          {(r.hover_scans || []).length > 0 && <span className="chip">hover-scan ×{r.hover_scans.length}</span>}
          {faults.map(([ch, f]: any) => <span key={ch} className="chip">{ch} drift caught {f.detection_delay_s != null ? `+${fmt(f.detection_delay_s, 1)} s` : "—"}</span>)}</div>}
        <div className="mt-5"><div className="eyebrow mb-2">All recorded {String(r.controller ?? "").toUpperCase()} landings</div>
          {hist.data ? <StatCards s={hist.data.stats} /> : <div className="text-[12px] text-muted">{info.data?.perr ? `Not stored: ${info.data.perr}` : "Saving this landing to the database…"}</div>}</div>
        <div className="flex flex-wrap gap-2 mt-5">
          <button className="btn btn-primary" disabled={!stored} onClick={onReplay}>▶ Play back this landing</button>
          <button className="btn btn-ghost" onClick={onHistory}>☰ History</button>
          <a className={`btn btn-ghost ${stored ? "" : "pointer-events-none opacity-40"}`} href={api.url(`/api/runs/${live?.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">⇩ Project report (PDF)</a>
          <button className="btn btn-ghost ml-auto" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
