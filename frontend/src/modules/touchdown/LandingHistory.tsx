import { useState } from "react";
import { ErrorNote, fmt } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

/** Aggregate quality of past landings. Accuracy = mean distance from the pad; precision = spread of that distance. */
export function StatCards({ s, compact = false }: { s: any; compact?: boolean }) {
  const cards: [string, string, string][] = [
    ["Success rate", pct(s?.success_rate), `${s?.landed_safely ?? 0} of ${s?.completed ?? 0} landings within all touchdown limits`],
    ["Accuracy", s?.accuracy_m == null ? "—" : `${fmt(s.accuracy_m, 2)} m`, "mean distance from the pad (safe landings)"],
    ["Precision", s?.precision_m == null ? "—" : `± ${fmt(s.precision_m, 2)} m`, "spread of that distance — how repeatable"],
    ["Within 2 m", pct(s?.within_2m), `touchdown speed ${s?.touchdown_speed == null ? "—" : fmt(s.touchdown_speed, 2) + " m/s"}`],
  ];
  return (
    <div className={`grid ${compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-4"} gap-3`}>
      {cards.map(([l, v, sub]) => (
        <div key={l} className="rounded-[14px] border p-3" style={{ background: "var(--ivory)" }}>
          <div className="eyebrow !text-[9.5px]">{l}</div><div className="num text-[22px] text-ink mt-0.5">{v}</div>
          <div className="text-[10.5px] text-muted mt-0.5 leading-snug">{sub}</div></div>))}
    </div>
  );
}

export default function LandingHistory({ onReplay, refreshKey }: { onReplay: (uid: string) => void; refreshKey?: any }) {
  const [ctrl, setCtrl] = useState("");
  const h = usePoll(() => api.get(`/api/touchdown/history?limit=200${ctrl ? `&controller=${ctrl}` : ""}`), 0, [ctrl, refreshKey]);
  const d = h.data;
  return (
    <div className="space-y-4">
      <ErrorNote error={h.error} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[12.5px] text-ink2">{d ? `${d.stats.runs} recorded landings` : "Loading…"} · every finished landing is stored with its full telemetry.</div>
        <div className="seg">{[["", "All"], ["pid", "PID"], ["mpc", "MPC"], ["ppo", "PPO"]].map(([k, l]) => <button key={k} className={ctrl === k ? "on" : ""} onClick={() => setCtrl(k)}>{l}</button>)}</div>
      </div>
      {d && <StatCards s={d.stats} />}
      {d && !ctrl && Object.keys(d.by_controller).length > 1 && <div className="overflow-x-auto"><table className="w-full text-[12px]">
        <thead><tr className="text-left text-muted text-[11px]">{["Controller", "Landings", "Success", "Accuracy", "Precision", "Within 2 m", "Touchdown"].map((x) => <th key={x} className="py-1.5 pr-3 font-medium">{x}</th>)}</tr></thead>
        <tbody>{Object.entries(d.by_controller).map(([c, s]: any) => <tr key={c} className="border-t">
          <td className="py-1.5 pr-3 font-medium uppercase">{c}</td><td className="pr-3">{s.completed}</td><td className="pr-3">{pct(s.success_rate)}</td>
          <td className="pr-3 num">{fmt(s.accuracy_m, 2)} m</td><td className="pr-3 num">± {fmt(s.precision_m, 2)} m</td><td className="pr-3">{pct(s.within_2m)}</td>
          <td className="num">{fmt(s.touchdown_speed, 2)} m/s</td></tr>)}</tbody></table></div>}
      {d && <div className="overflow-x-auto max-h-[460px] scroll-thin"><table className="w-full text-[12px]">
        <thead className="sticky top-0 bg-white"><tr className="text-left text-muted text-[11px]">{["When", "Controller", "World", "Outcome", "Miss", "Touchdown", "Diversions", "Fuel", "Notes", ""].map((x) => <th key={x} className="py-1.5 pr-3 font-medium">{x}</th>)}</tr></thead>
        <tbody>{d.runs.map((r: any) => <tr key={r.run_uid} className="border-t align-middle">
          <td className="py-1.5 pr-3 num text-[11px] text-muted">{r.finished_at ? new Date(r.finished_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
          <td className="pr-3 uppercase">{r.controller}</td><td className="pr-3 capitalize">{r.environment}</td>
          <td className="pr-3"><span className={`chip ${r.success ? "!text-white !bg-[var(--success)]" : r.outcome === "crash" ? "!text-white !bg-[var(--danger)]" : ""}`}>{r.outcome ?? r.status ?? "—"}</span></td>
          <td className="pr-3 num">{fmt(r.landing_error_m, 2)} m</td><td className="pr-3 num">{fmt(r.touchdown_vz == null ? null : Math.abs(r.touchdown_vz), 2)} m/s</td>
          <td className="pr-3">{r.diversions ?? 0}</td><td className="pr-3 num">{fmt(r.fuel_used_kg, 0)} kg</td>
          <td className="pr-3 text-[11px] text-ink2">{[r.hover_scans ? "hover-scan" : "", r.sensor_faults?.length ? `drift: ${r.sensor_faults.join(", ")}` : "", r.guard ? "guard flag" : ""].filter(Boolean).join(" · ")}</td>
          <td className="whitespace-nowrap"><button className="btn btn-ghost !py-1 !px-2 text-[11px]" onClick={() => onReplay(r.run_uid)}>▶ Replay</button>
            <a className="btn btn-ghost !py-1 !px-2 text-[11px] ml-1" href={api.url(`/api/runs/${r.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">Report</a></td></tr>)}</tbody></table></div>}
    </div>
  );
}
