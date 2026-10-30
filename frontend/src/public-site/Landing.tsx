import Lenis from "lenis";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { scrollState } from "./PlanetScene";

const PlanetScene = lazy(() => import("./PlanetScene"));

const NAV = [["Overview", "overview"], ["Touchdown", "touchdown"], ["Rover", "rover"], ["Technology", "technology"],
  ["Research", "research"], ["Mission Control", "docs"]] as const;

function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll(".reveal"));
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

const d = (ms: number) => ({ transitionDelay: `${ms}ms` });

function Section({ id, children, align = "left" }: { id: string; children: React.ReactNode; align?: "left" | "right" | "center" }) {
  const j = align === "right" ? "md:ml-auto" : align === "center" ? "mx-auto text-center" : "";
  return (
    <section id={id} className="relative min-h-screen flex items-center px-4 md:px-12 py-24">
      <div className={`w-full max-w-[560px] ${j}`}>{children}</div>
    </section>
  );
}

export default function Landing() {
  const [scrolled, setScrolled] = useState(false);
  const lenisRef = useRef<Lenis | null>(null);
  useReveal();
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const lenis = reduce ? null : new Lenis({ lerp: 0.085 });
    lenisRef.current = lenis;
    let raf = 0;
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      scrollState.progress = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      setScrolled(window.scrollY > 40);
    };
    const loop = (t: number) => { lenis?.raf(t); onScroll(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); lenis?.destroy(); };
  }, []);
  const go = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    lenisRef.current ? lenisRef.current.scrollTo(el, { offset: 0 }) : el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="land relative min-h-screen overflow-x-hidden">
      <div className="fixed inset-0 z-0" aria-hidden><Suspense fallback={null}><PlanetScene /></Suspense></div>
      <div className="fixed inset-0 z-[1] pointer-events-none" style={{ background: "radial-gradient(ellipse at 30% 40%, transparent 30%, rgba(2,4,8,.55) 100%)" }} />

      <header className={`fixed top-0 inset-x-0 z-30 transition-all duration-500 ${scrolled ? "py-3" : "py-6"}`}>
        <div className={`mx-4 md:mx-10 flex items-center justify-between px-4 md:px-6 py-3 ${scrolled ? "glass" : ""}`}>
          <button onClick={() => go("hero")} className="flex items-center gap-3 text-left">
            <span className="h-display text-2xl tracking-wide">ASTRA</span>
            <span className="hidden lg:inline land-eyebrow !text-[10px] !tracking-[.2em] opacity-70">Touchdown &amp; Rover Autonomy</span>
          </button>
          <nav className="hidden md:flex items-center gap-7 text-[13px] text-white/70">
            {NAV.map(([label, id]) => <button key={id} onClick={() => go(id)} className="hover:text-white transition-colors">{label}</button>)}
          </nav>
          <Link to="/app" className="rounded-full bg-[#dfeedd] text-[#16241b] px-4 py-2 text-[13px] font-medium hover:bg-white transition-colors">Enter ASTRA</Link>
        </div>
      </header>

      <main className="relative z-10">
        <section id="hero" className="min-h-screen flex items-center px-4 md:px-12 pt-28 pb-16">
          <div className="max-w-[760px]">
            <div className="land-eyebrow reveal" style={d(0)}>Autonomous Planetary Intelligence</div>
            <h1 className="h-display reveal text-[clamp(44px,8.2vw,112px)] mt-6" style={d(120)}>
              Beyond Simulation.<br /><em className="text-[#c7e0bd]">Toward Autonomous Exploration.</em>
            </h1>
            <p className="reveal mt-7 max-w-[560px] text-[15px] md:text-[17px] leading-relaxed text-white/70" style={d(260)}>
              ASTRA is an integrated planetary autonomy research platform combining physics-based touchdown simulation,
              intelligent rover navigation, reinforcement learning and adaptive decision-making in a unified simulation environment.
            </p>
            <div className="reveal mt-10 flex flex-wrap gap-3" style={d(380)}>
              <button onClick={() => go("overview")} className="rounded-full bg-[#dfeedd] text-[#16241b] px-6 py-3 text-sm font-medium hover:bg-white transition">Explore ASTRA</button>
              <Link to="/app/mission-control" className="rounded-full glass px-6 py-3 text-sm hover:bg-white/10 transition">Enter Mission Control →</Link>
            </div>
          </div>
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 land-eyebrow opacity-60 animate-pulse">Scroll</div>
        </section>

        <Section id="overview">
          <div className="land-eyebrow reveal">01 — Platform</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>One environment. Two autonomous systems.</h2>
          <p className="reveal mt-6 text-white/70 leading-relaxed" style={d(200)}>
            ASTRA studies how planetary robots perceive, estimate their own state, predict outcomes and decide — when the
            terrain is unknown and their own hardware may fail. Every number on screen comes from a computation; every
            autonomous decision is logged with the evidence that produced it.
          </p>
          <div className="reveal grid grid-cols-2 gap-3 mt-8" style={d(300)}>
            {[["6-DOF", "rigid-body lander, RK4"], ["PyBullet", "six-wheel rocker-bogie"], ["EKF", "truth, estimate & covariance kept apart"], ["Matched", "seed-paired experiments"]].map(([a, b]) => (
              <div key={a} className="glass p-4"><div className="h-display text-2xl">{a}</div><div className="text-xs text-white/60 mt-1">{b}</div></div>))}
          </div>
        </Section>

        <Section id="touchdown" align="right">
          <div className="land-eyebrow reveal">02 — ASTRA Touchdown</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>Land where it is safe — not where it was planned.</h2>
          <p className="reveal mt-6 text-white/70 leading-relaxed" style={d(200)}>
            Powered descent on Mars with a 12-state Extended Kalman Filter, cascade PID, constrained Model Predictive Control
            and a PPO policy. Close-range lidar maps boulders the orbital map never saw; if the target turns hazardous, the
            lander evaluates reachable alternatives against fuel and control authority — and diverts physically, never by teleport.
          </p>
          <ul className="reveal mt-6 space-y-2 text-sm text-white/65" style={d(300)}>
            <li>— Variable-mass dynamics, throttle lag, RCS torques</li><li>— Hazard assessment under estimation uncertainty</li><li>— Mission supervisor from entry to touchdown</li>
          </ul>
        </Section>

        <Section id="rover">
          <div className="land-eyebrow reveal">03 — ASTRA Rover</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>When the rover breaks, the plan should bend.</h2>
          <p className="reveal mt-6 text-white/70 leading-relaxed" style={d(200)}>
            A physical six-wheel rover on five deterministic terrains. Four injected faults — sensor dropout, terrain
            misclassification, power-drain spikes and actuator degradation — are detected from evidence, classified with
            confidence, and answered with fault-specific replanning. A fixed-rule baseline faces identical conditions.
          </p>
        </Section>

        <Section id="workflow" align="center">
          <div className="land-eyebrow reveal">04 — Unified autonomy workflow</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>Sense → Estimate → Predict → Decide → Act → Verify → Adapt</h2>
          <div className="reveal mt-10 flex flex-wrap justify-center gap-2" style={d(250)}>
            {["Sense", "Estimate", "Predict", "Decide", "Act", "Verify", "Adapt"].map((s, i) => (
              <span key={s} className="glass px-4 py-2 text-sm" style={{ transitionDelay: `${300 + i * 70}ms` }}>{s}</span>))}
          </div>
          <p className="reveal mt-8 text-white/60 text-sm" style={d(400)}>Implemented as real interfaces — state manager, prediction engine, decision engine, independent safety supervisor and decision audit.</p>
        </Section>

        <Section id="technology" align="right">
          <div className="land-eyebrow reveal">05 — Physics &amp; intelligence</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>Rates that never depend on the renderer.</h2>
          <div className="reveal glass p-6 mt-8 font-mono text-[12px] leading-7 text-white/75" style={d(220)}>
            <div className="flex justify-between"><span>Lander physics (RK4)</span><span>100 Hz</span></div>
            <div className="flex justify-between"><span>Rover physics (PyBullet)</span><span>120 Hz</span></div>
            <div className="flex justify-between"><span>Guidance / control</span><span>20 · 10 Hz</span></div>
            <div className="flex justify-between"><span>Lidar hazard mapping</span><span>1 · 5 Hz</span></div>
            <div className="flex justify-between"><span>Telemetry websocket</span><span>10 Hz</span></div>
            <div className="flex justify-between text-white/45"><span>3D rendering</span><span>display rate, interpolated</span></div>
          </div>
        </Section>

        <Section id="research">
          <div className="land-eyebrow reveal">06 — Experimental research</div>
          <h2 className="h-display reveal text-5xl md:text-6xl mt-4" style={d(100)}>Results you can reproduce — or refute.</h2>
          <p className="reveal mt-6 text-white/70 leading-relaxed" style={d(200)}>
            Held-out terrains never touched during development. Matched seeds and fault schedules for both controllers.
            Completion rates with Wilson intervals, paired McNemar and Wilcoxon tests, and every configuration, software
            version and run identifier stored. Incomplete experiments are shown as incomplete.
          </p>
        </Section>

        <Section id="docs" align="center">
          <div className="land-eyebrow reveal">07 — Mission Control</div>
          <h2 className="h-display reveal text-6xl md:text-7xl mt-4" style={d(100)}>Take the controls.</h2>
          <p className="reveal mt-6 text-white/70" style={d(200)}>Configure a descent, inject a boulder field, break a wheel — and read why the system did what it did.</p>
          <div className="reveal mt-10 flex flex-wrap justify-center gap-3" style={d(300)}>
            <Link to="/app/mission-control" className="rounded-full bg-[#dfeedd] text-[#16241b] px-7 py-3 text-sm font-medium hover:bg-white transition">Enter Mission Control</Link>
            <Link to="/app/moon" className="rounded-full glass px-7 py-3 text-sm hover:bg-white/10 transition">Watch a Moon landing</Link>
          </div>
        </Section>

        <footer className="relative px-4 md:px-12 py-14 border-t border-white/10 bg-black/40 backdrop-blur-md">
          <div className="flex flex-col md:flex-row justify-between gap-6 text-sm text-white/55">
            <div><div className="h-display text-3xl text-white">ASTRA</div><div className="mt-1">AI-Driven System for Touchdown &amp; Rover Autonomy</div></div>
            <div className="flex gap-6 flex-wrap">
              {NAV.map(([label, id]) => <button key={id} onClick={() => go(id)} className="hover:text-white">{label}</button>)}
              <Link to="/app" className="hover:text-white">Application</Link>
            </div>
          </div>
          <div className="mt-8 text-xs text-white/35">Research simulation platform. Results shown in the application are generated by actual simulation runs.</div>
        </footer>
      </main>
    </div>
  );
}
