import { useState } from "react";
import { api } from "../services/api";
import type { ModuleId } from "../services/types";
import { ErrorNote, StatusPill } from "./ui";

/** Lifecycle controls bound directly to the backend session endpoints. */
export default function SimControls({ module, status, speed, onChange }: { module: ModuleId; status?: string; speed?: number; onChange?: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [spd, setSpd] = useState<number>(speed ?? (module === "rover" ? 4 : 2));
  const call = async (action: string, body: any = {}) => {
    setBusy(true); setErr(null);
    try { await api.post(`/api/${module}/${action}`, body); onChange?.(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const running = status === "running", paused = status === "paused";
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={status} />
        <button className="btn btn-primary" disabled={busy || running || paused} onClick={() => call("start", { speed: spd })}>▶ Start</button>
        <button className="btn btn-ghost" disabled={busy || !running} onClick={() => call("pause")}>❚❚ Pause</button>
        <button className="btn btn-ghost" disabled={busy || !paused} onClick={() => call("resume")}>↻ Resume</button>
        <button className="btn btn-ghost" disabled={busy || !(running || paused)} onClick={() => call("stop")}>■ Stop</button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => call("reset")}>⟲ Reset</button>
        <label className="flex items-center gap-2 text-[12px] text-ink2 ml-1">
          Speed
          <select className="select !w-auto !py-1.5" value={spd} onChange={(e) => { const v = Number(e.target.value); setSpd(v); call("speed", { speed: v }); }}>
            {[0.5, 1, 2, 4, 8, 16, 0].map((v) => <option key={v} value={v}>{v === 0 ? "max" : `${v}×`}</option>)}
          </select>
        </label>
      </div>
      <ErrorNote error={err} />
    </div>
  );
}
