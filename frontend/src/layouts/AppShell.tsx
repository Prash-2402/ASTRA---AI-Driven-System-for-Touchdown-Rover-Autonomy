import { Suspense, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useChannel } from "../hooks/useChannel";
import { useSim } from "../stores/simulation";

const NAV: [string, string, string][] = [
  ["Overview", "/app", "◎"], ["Mission Control", "/app/mission-control", "◉"], ["Touchdown", "/app/touchdown", "▾"],
  ["Rover", "/app/rover", "◫"], ["Scenario Builder", "/app/scenarios", "✎"], ["Fault Injection", "/app/faults", "⚡"],
  ["Controller Comparison", "/app/comparison", "⇄"], ["Reinforcement Learning Lab", "/app/rl-lab", "∿"],
  ["Experiment Lab", "/app/experiments", "⚗"], ["Results & Analytics", "/app/results", "▤"], ["Telemetry", "/app/telemetry", "≋"],
  ["Architecture", "/app/architecture", "⌗"], ["Documentation", "/app/documentation", "❡"], ["Settings", "/app/settings", "⚙"],
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
  const rv = useSim((s) => s.rover?.status);
  return (
    <div className="app-root flex min-h-screen">
      <LiveBridge />
      <aside className={`fixed md:sticky top-0 z-40 h-screen w-[248px] shrink-0 border-r bg-[var(--cream)]/95 backdrop-blur md:translate-x-0 transition-transform ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="px-6 pt-7 pb-5">
          <Link to="/" className="h-display text-[30px] leading-none text-ink">ASTRA</Link>
          <div className="eyebrow mt-1.5 !text-[9.5px]">Planetary autonomy lab</div>
        </div>
        <nav className="px-3 space-y-0.5 overflow-y-auto scroll-thin" style={{ maxHeight: "calc(100vh - 190px)" }}>
          {NAV.map(([label, to, icon]) => (
            <NavLink key={to} to={to} end={to === "/app"} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-[12px] px-3 py-2 text-[13px] transition-colors ${isActive ? "bg-sage text-ink font-medium" : "text-ink2 hover:bg-sage-soft"}`}>
              <span className="w-4 text-center text-primary-dark">{icon}</span>{label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute bottom-0 inset-x-0 px-6 py-4 border-t text-[11px] space-y-1.5">
          <div className="flex items-center gap-2"><span className="dot" style={{ background: connected ? "var(--success)" : "var(--danger)" }} />Telemetry link {connected ? "live" : "offline"}</div>
          <div className="flex items-center gap-2 text-ink2"><span className="num">TD</span> {td ?? "—"} <span className="num ml-2">RV</span> {rv ?? "—"}</div>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/20 md:hidden" onClick={() => setOpen(false)} />}
      <div className="flex-1 min-w-0">
        <div className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3 border-b bg-[var(--cream)]/95 backdrop-blur">
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
