import { Suspense, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useChannel } from "../hooks/useChannel";
import { useSim } from "../stores/simulation";

const NAV: { group: string; items: [string, string, string][] }[] = [
  { group: "Mission", items: [["Dashboard", "/app", "◎"]] },
  { group: "Simulations", items: [["Landing Simulation", "/app/landing", "▾"], ["Rover Ground Operations", "/app/rover", "⬡"]] },
  { group: "Operations", items: [["Mission Control", "/app/mission-control", "◉"], ["Scenario Builder", "/app/scenarios", "✎"],
    ["Fault Injection", "/app/faults", "⚡"]] },
  { group: "Research", items: [["Hurdle Evidence", "/app/evidence", "◆"],["Controller Comparison", "/app/comparison", "⇄"], ["Reinforcement Learning Lab", "/app/rl-lab", "∿"],
    ["Experiment Lab", "/app/experiments", "⚗"], ["Results & Analytics", "/app/results", "▤"], ["Telemetry", "/app/telemetry", "≋"]] },
];

/** Single live connection for the whole application: telemetry + events feed the store. */
function LiveBridge() {
  const ingest = useSim((s) => s.ingest);
  const pushEvent = useSim((s) => s.pushEvent);
  const setConnected = useSim((s) => s.setConnected);
  const c1 = useChannel("telemetry", ingest);
  useChannel("events", pushEvent);
  setTimeout(() => setConnected(c1), 0);
  return null;
}

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const connected = useSim((s) => s.wsConnected);
  const td = useSim((s) => s.touchdown?.status);
  const mn = useSim((s) => s.moon?.status);
  const rv = useSim((s) => s.rover?.status);
  return (
    <div className="app-root flex min-h-screen">
      <LiveBridge />
      <aside className={`fixed md:sticky top-0 z-40 h-screen w-[256px] shrink-0 border-r bg-white md:translate-x-0 transition-transform ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="px-6 pt-7 pb-5">
          <Link to="/" className="flex items-center gap-2.5"><svg width="26" height="26" viewBox="0 0 64 64" aria-hidden><circle cx="32" cy="32" r="20" fill="#C1683F"/><ellipse cx="32" cy="32" rx="30" ry="9" fill="none" stroke="#4C6EF5" strokeWidth="3" transform="rotate(-20 32 32)"/></svg><span className="text-[22px] font-extrabold tracking-[-0.03em] leading-none text-ink" style={{ fontFamily: "Manrope, Inter, sans-serif" }}>ASTRA</span></Link>
          <div className="eyebrow mt-2 !text-[9.5px]">Planetary autonomy lab</div>
        </div>
        <nav className="px-3 space-y-0.5 overflow-y-auto scroll-thin" style={{ maxHeight: "calc(100vh - 175px)" }}>
          {NAV.map((g) => (
            <div key={g.group} className="mb-3">
              <div className="eyebrow !text-[9.5px] px-3 mb-1.5 mt-2">{g.group}</div>
              {g.items.map(([label, to, icon]) => (
                <NavLink key={to} to={to} end={to === "/app"} onClick={() => setOpen(false)}
                  className={({ isActive }) => `relative flex items-center gap-3 rounded-[10px] px-3 py-[7px] text-[13px] transition-colors ${isActive ? "bg-sage text-ink font-medium before:absolute before:left-0 before:top-2 before:bottom-2 before:w-[3px] before:rounded-full before:bg-[var(--primary)]" : "text-ink2 hover:bg-sage-soft hover:text-ink"}`}>
                  <span className="w-4 text-center text-primary">{icon}</span>{label}
                </NavLink>))}
            </div>
          ))}
        </nav>
        <div className="absolute bottom-0 inset-x-0 px-6 py-4 border-t text-[11px] space-y-1.5">
          <div className="flex items-center gap-2"><span className="dot" style={{ background: connected ? "var(--success)" : "var(--danger)" }} />Telemetry link {connected ? "live" : "offline"}</div>
          <div className="flex items-center gap-2 text-ink2"><span className="num">RV</span> {rv ?? "—"} <span className="num ml-2">MN</span> {mn ?? "—"} <span className="num ml-2">TD</span> {td ?? "—"}</div>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/20 md:hidden" onClick={() => setOpen(false)} />}
      <div className="flex-1 min-w-0">
        <div className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3 border-b bg-white">
          <button className="btn btn-ghost !px-3" onClick={() => setOpen(true)} aria-label="Open navigation">☰</button>
          <span className="h-display text-2xl">ASTRA</span><span className="w-10" />
        </div>
        <main key={loc.pathname} className="px-4 md:px-9 py-7 max-w-[1680px] mx-auto">
          <Suspense fallback={<div className="eyebrow">Loading…</div>}><Outlet /></Suspense>
        </main>
      </div>
    </div>
  );
}
