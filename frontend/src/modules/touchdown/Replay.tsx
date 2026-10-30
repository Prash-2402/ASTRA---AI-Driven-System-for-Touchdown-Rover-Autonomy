import { useEffect, useMemo, useRef, useState } from "react";
import { fmt } from "../../components/ui";
import { api } from "../../services/api";

/** Loads a finished landing's archived telemetry and turns playback time into a snapshot the live 3D scene
 *  understands (flown trail grows, lander pose and phase follow the recording). */
export function useReplay(uid: string | null) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(4);
  useEffect(() => {
    setData(null); setErr(null); setI(0); setPlaying(false);
    if (!uid) return;
    api.get(`/api/touchdown/replay/${uid}`).then((d) => { setData(d); setPlaying(true); }).catch((e) => setErr(e.message));
  }, [uid]);
  const raf = useRef(0);
  useEffect(() => {
    if (!playing || !data) return;
    let last = performance.now(), acc = 0;
    const fr = data.frames, dtF = fr.length > 1 ? fr[1].t - fr[0].t : 0.2;
    const tick = (now: number) => {
      acc += ((now - last) / 1000) * rate; last = now;
      const steps = Math.floor(acc / dtF);
      if (steps > 0) { acc -= steps * dtF; setI((k) => { const n = Math.min(fr.length - 1, k + steps); if (n === fr.length - 1) setPlaying(false); return n; }); }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, data, rate]);
  const snap = useMemo(() => {
    if (!data) return null;
    const fr = data.frames, f = fr[Math.min(i, fr.length - 1)];
    const trail = fr.slice(0, i + 1).filter((_: any, k: number) => k % 3 === 0 || k === i).map((x: any) => x.truth.position);
    const r = data.result || {};
    const diverted = Math.hypot(f.target[0] - (r.original_target?.[0] ?? f.target[0]), f.target[1] - (r.original_target?.[1] ?? f.target[1])) > 1;
    return { module: "touchdown", run_uid: `replay-${data.run_uid}`, t: f.t, phase: f.phase, frame: f, actual_trajectory: trail, events: [],
      diversions: diverted ? r.diversions ?? 1 : 0, result: i === fr.length - 1 ? r : null, original_target: r.original_target,
      obstacles: r.obstacles || [], environment: { name: data.environment }, status: "replay" } as any;
  }, [data, i]);
  return { data, err, i, setI, playing, setPlaying, rate, setRate, snap };
}

export function ReplayBar({ r, onExit }: { r: ReturnType<typeof useReplay>; onExit: () => void }) {
  const fr = r.data?.frames || [];
  const f = fr[r.i];
  const end = fr.length - 1;
  return (
    <div className="hud p-3 w-full">
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip !text-white !bg-[#7c3aed]">REPLAY</span>
        <span className="num text-[11px] text-ink2 truncate max-w-[220px]">{r.data?.run_uid ?? "loading…"}</span>
        <button className="btn btn-primary !py-1.5" disabled={!fr.length} onClick={() => { if (r.i >= end) r.setI(0); r.setPlaying(!r.playing); }}>{r.playing ? "❚❚ Pause" : r.i >= end && end > 0 ? "↺ Replay" : "▶ Play"}</button>
        <select className="select !w-auto !py-1" value={r.rate} onChange={(e) => r.setRate(+e.target.value)}>{[1, 2, 4, 8, 16].map((x) => <option key={x} value={x}>{x}×</option>)}</select>
        <span className="num text-[11.5px] text-ink">t = {fmt(f?.t, 1)} s · {f?.phase ?? ""} · AGL {fmt(f?.truth?.agl, 0)} m</span>
        <button className="btn btn-ghost !py-1.5 ml-auto" onClick={onExit}>✕ Exit replay</button>
      </div>
      <input type="range" className="w-full accent-[#7c3aed] mt-2" min={0} max={Math.max(end, 0)} value={r.i} onChange={(e) => { r.setPlaying(false); r.setI(+e.target.value); }} />
      {r.err && <div className="text-[11.5px] text-danger mt-1">{r.err}</div>}
    </div>
  );
}
