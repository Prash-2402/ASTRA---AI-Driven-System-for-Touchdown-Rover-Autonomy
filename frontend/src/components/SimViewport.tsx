import { ReactNode } from "react";
import type { CamMode } from "../visualization/lib/scene";

/** Shared chrome for 3D simulation viewports: camera-mode switch, toggles, phase timeline, HUD slots. */
export function CamSwitch({ modes, value, onChange }: { modes: [CamMode, string][]; value: CamMode; onChange: (m: CamMode) => void }) {
  return (
    <div className="seg hud !p-[3px]">{modes.map(([m, l]) => <button key={m} className={value === m ? "on" : ""} onClick={() => onChange(m)}>{l}</button>)}</div>
  );
}

export function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return <button onClick={onClick} className={`hud px-3 py-1.5 text-[11.5px] ${on ? "text-[var(--primary)]" : "text-[var(--ink-secondary)]"}`}>{on ? "● " : "○ "}{children}</button>;
}

export function PhaseTimeline({ phases, current, failed }: { phases: string[]; current?: string; failed?: boolean }) {
  const idx = phases.indexOf(current ?? "");
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      {phases.map((p, i) => (
        <div key={p} className={`stage ${i < idx ? "done" : ""} ${i === idx ? (failed ? "now bad" : "now") : ""}`}>
          <span className="pip" />{p}{i < phases.length - 1 && <span className="ml-3 w-6 h-px bg-[var(--border-strong)]" />}
        </div>))}
    </div>
  );
}

export function Gauge({ label, value, max, unit, tone = "var(--primary)", fmt = (v: number) => v.toFixed(1) }:
  { label: string; value: number; max: number; unit?: string; tone?: string; fmt?: (v: number) => string }) {
  const f = Math.max(0, Math.min(1, value / max));
  return (
    <div>
      <div className="flex justify-between text-[10.5px] text-[var(--ink-secondary)]"><span className="eyebrow !text-[9.5px]">{label}</span><span className="num text-[var(--ink)]">{fmt(value)}{unit && <span className="text-[var(--muted)] ml-1">{unit}</span>}</span></div>
      <div className="h-1.5 rounded-full bg-[rgba(17,24,39,.08)] mt-1 overflow-hidden"><div className="h-full rounded-full transition-[width] duration-300" style={{ width: `${f * 100}%`, background: tone }} /></div>
    </div>
  );
}
