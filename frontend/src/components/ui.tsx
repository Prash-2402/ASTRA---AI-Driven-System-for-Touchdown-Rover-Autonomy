import { ReactNode, useState } from "react";
import type { DecisionEvent, MissionEvent } from "../services/types";

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-4 mb-6">
      <div className="min-w-0"><div className="eyebrow">{eyebrow}</div><h1 className="h-display text-[clamp(28px,2.7vw,40px)] text-ink mt-1">{title}</h1></div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export function Panel({ title, eyebrow, children, className = "", right }: { title?: ReactNode; eyebrow?: string; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={`panel p-5 ${className}`}>
      {(title || eyebrow) && (
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}{title && <h3 className="text-[15px] font-semibold text-ink mt-0.5">{title}</h3>}</div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, unit, sub, tone }: { label: string; value: ReactNode; unit?: string; sub?: ReactNode; tone?: "ok" | "warn" | "bad" }) {
  const c = tone === "bad" ? "text-danger" : tone === "warn" ? "text-warning" : "text-ink";
  return (
    <div className="min-w-0">
      <div className="eyebrow !text-[10px] truncate">{label}</div>
      <div className={`num text-[20px] mt-1 ${c} truncate`}>{value}{unit && <span className="text-[12px] text-muted ml-1">{unit}</span>}</div>
      {sub && <div className="text-[11px] text-muted mt-0.5 truncate">{sub}</div>}
    </div>
  );
}

export function StatusPill({ status }: { status?: string | null }) {
  const map: Record<string, string> = { running: "var(--success)", paused: "var(--warning)", completed: "var(--info)", error: "var(--danger)",
    failed: "var(--danger)", stopped: "var(--muted)", idle: "var(--muted)", created: "var(--muted)", cancelled: "var(--muted)",
    completed_with_errors: "var(--warning)", interrupted: "var(--warning)" };
  const s = status || "—";
  return <span className="chip"><span className="dot" style={{ background: map[s] || "var(--muted)" }} />{s}</span>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="panel-soft p-8 text-center">
      <div className="h-display text-2xl text-ink">{title}</div>
      {children && <div className="text-[13px] text-ink2 mt-2 max-w-md mx-auto">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error?: string | null }) {
  if (!error) return null;
  return <div className="rounded-[12px] border border-[rgba(199,108,100,.35)] bg-[rgba(199,108,100,.08)] text-danger text-[12.5px] px-4 py-2.5 my-3 whitespace-pre-wrap">{error}</div>;
}

export const fmt = (v: any, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "—" : typeof v === "number" ? v.toFixed(d) : String(v));

export function EventTimeline({ events, max = 60 }: { events: MissionEvent[]; max?: number }) {
  if (!events?.length) return <div className="text-[12px] text-muted">No events yet.</div>;
  const colors: Record<string, string> = { fault: "var(--danger)", injection: "var(--warning)", detection: "var(--warning)", classification: "var(--info)",
    diversion: "var(--info)", abort: "var(--danger)", touchdown: "var(--success)", safety: "var(--danger)", recovery: "var(--success)", halt: "var(--danger)" };
  return (
    <ol className="space-y-1.5 max-h-[340px] overflow-y-auto scroll-thin pr-2">
      {[...events].slice(-max).reverse().map((e, i) => (
        <li key={i} className="flex gap-3 text-[12px]">
          <span className="num text-muted w-[52px] shrink-0 text-right">{fmt(e.t, 1)}s</span>
          <span className="dot mt-1.5 shrink-0" style={{ background: colors[e.kind] || "var(--primary-light)" }} />
          <span className="text-ink2"><span className="font-medium text-ink">{e.kind}</span> · {e.message}</span>
        </li>
      ))}
    </ol>
  );
}

export function DecisionLog({ decisions }: { decisions: DecisionEvent[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!decisions?.length) return <div className="text-[12px] text-muted">No autonomous decisions recorded for this run yet.</div>;
  return (
    <div className="space-y-2 max-h-[520px] overflow-y-auto scroll-thin pr-1">
      {[...decisions].reverse().map((d) => (
        <div key={d.event_id} className="rounded-[14px] border bg-ivory">
          <button className="w-full text-left px-4 py-3 flex items-start gap-3" onClick={() => setOpen(open === d.event_id ? null : d.event_id)}>
            <span className="num text-[11px] text-muted mt-0.5 w-[54px] shrink-0">{fmt(d.t, 1)}s</span>
            <div className="min-w-0 flex-1">
              <div className="text-[12px] text-muted truncate">{d.trigger}</div>
              <div className="text-[13px] text-ink font-medium">{d.decision}</div>
            </div>
            <span className="chip">{d.actual_outcome ? (d.actual_outcome.landed_safely ?? d.actual_outcome.recovered) ? "outcome ✓" : "outcome ✗" : "pending"}</span>
          </button>
          {open === d.event_id && (
            <div className="px-4 pb-4 grid md:grid-cols-2 gap-3 text-[11.5px]">
              <KV title="Evidence" obj={d.evidence} />
              <KV title="Estimated state & uncertainty" obj={{ ...d.estimated_state, ...d.uncertainty }} />
              {d.fault_classification && <KV title="Fault classification" obj={d.fault_classification} />}
              <KV title="Expected outcome" obj={d.expected_outcome} />
              <KV title="Actual outcome (observed later)" obj={d.actual_outcome ?? { status: "not yet observed" }} />
              <KV title="Details" obj={Object.fromEntries(Object.entries(d.details || {}).filter(([k]) => !["route_before", "route_after", "alternatives"].includes(k)))} />
              {d.details?.alternatives && <KV title={`Alternatives evaluated (${d.details.alternatives.length})`} obj={d.details.alternatives.slice(0, 8)} />}
              {d.details?.route_after && <div className="text-muted">Route before: {d.details.route_before?.length ?? 0} pts · after: {d.details.route_after.length} pts · replan {fmt(d.details.replan_ms, 0)} ms</div>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function KV({ title, obj }: { title: string; obj: any }) {
  return (
    <div className="rounded-[10px] bg-sage-soft p-3 min-w-0">
      <div className="eyebrow !text-[9.5px] mb-1.5">{title}</div>
      <pre className="num text-[10.5px] whitespace-pre-wrap break-words text-ink2 max-h-56 overflow-auto scroll-thin">{JSON.stringify(round(obj), null, 1)}</pre>
    </div>
  );
}

function round(o: any): any {
  if (typeof o === "number") return Math.abs(o) < 1e-3 && o !== 0 ? Number(o.toExponential(2)) : Number(o.toFixed(3));
  if (Array.isArray(o)) return o.map(round);
  if (o && typeof o === "object") return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, round(v)]));
  return o;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="label">{label}</span>{children}</label>;
}
