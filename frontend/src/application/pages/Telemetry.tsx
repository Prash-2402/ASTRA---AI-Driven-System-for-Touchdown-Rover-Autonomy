import { useState } from "react";
import { ErrorNote, fmt, PageHeader, Panel } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";
import { useSim } from "../../stores/simulation";

export default function Telemetry() {
  const [mod, setMod] = useState<"touchdown" | "rover" | "moon">("rover");
  const live = useSim((s) => (mod === "touchdown" ? s.touchdown : mod === "rover" ? s.rover : s.moon)) as any;
  const connected = useSim((s) => s.wsConnected);
  const runs = usePoll(() => api.get(`/api/runs?module=${mod}&limit=100&include_trials=true`), 8000, [mod]);
  const [sel, setSel] = useState<string | null>(null);
  const detail = usePoll(() => (sel ? api.get(`/api/runs/${sel}`) : Promise.resolve(null)), 0, [sel]);
  return (
    <div>
      <PageHeader eyebrow={`WebSocket ${connected ? "connected" : "disconnected"} · 10 Hz publication`} title="Telemetry">
        <div className="flex rounded-full bg-sage p-1">{(["rover", "moon", "touchdown"] as const).map((m) => <button key={m} onClick={() => setMod(m)} className={`px-4 py-1.5 rounded-full text-[13px] ${mod === m ? "bg-surface shadow-soft" : "text-ink2"}`}>{m}</button>)}</div>
      </PageHeader>
      <ErrorNote error={runs.error} />
      <div className="grid xl:grid-cols-2 gap-5">
        <Panel eyebrow="Live frame" title={live ? `${live.run_uid} · t=${fmt(live.t, 2)} s` : "No live session"}>
          <pre className="num text-[10.5px] max-h-[620px] overflow-auto scroll-thin text-ink2">{live ? JSON.stringify(live.frame, null, 1) : "—"}</pre>
        </Panel>
        <div className="space-y-5 min-w-0">
          <Panel eyebrow="Archive" title="Stored runs (full-rate archives + 1 Hz database rows)">
            <div className="max-h-[330px] overflow-auto scroll-thin"><table className="table nowrap"><thead><tr><th>run</th><th>ctrl</th><th>outcome</th><th>sim s</th><th>export</th></tr></thead><tbody>
              {(runs.data || []).map((r: any) => <tr key={r.run_uid} className={sel === r.run_uid ? "bg-sage" : ""} onClick={() => setSel(r.run_uid)} style={{ cursor: "pointer" }}>
                <td className="num text-[11px]">{r.run_uid}{r.trial_id ? " (trial)" : ""}</td><td>{r.controller}</td><td>{r.outcome}</td><td className="num">{fmt(r.sim_time_s, 0)}</td>
                <td className="whitespace-nowrap"><a className="text-primary-dark underline mr-2" href={api.url(`/api/runs/${r.run_uid}/telemetry?format=csv`)}>CSV</a>
                  <a className="text-primary-dark underline mr-2" href={api.url(`/api/runs/${r.run_uid}/telemetry`)} target="_blank" rel="noreferrer">JSON</a>
                  <a className="text-primary-dark underline" href={api.url(`/api/runs/${r.run_uid}/report.pdf`)} target="_blank" rel="noreferrer">PDF</a></td></tr>)}</tbody></table></div>
          </Panel>
          {detail.data && <Panel eyebrow="Run record" title={detail.data.run_uid}>
            <pre className="num text-[10.5px] max-h-[300px] overflow-auto scroll-thin text-ink2">{JSON.stringify({ result: detail.data.result, software_versions: detail.data.software_versions, decisions: detail.data.decisions?.length, faults: detail.data.faults }, null, 1)}</pre>
          </Panel>}
        </div>
      </div>
    </div>
  );
}
