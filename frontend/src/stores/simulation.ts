import { create } from "zustand";
import type { RoverSnapshot, TouchdownSnapshot, MissionEvent } from "../services/types";

const HISTORY = 900; // ~90 s of 10 Hz publication for live charts

interface SimState {
  touchdown: TouchdownSnapshot | null;
  rover: RoverSnapshot | null;
  moon: any | null;
  moonHistory: any[];
  tdHistory: any[];
  roverHistory: any[];
  events: (MissionEvent & { module?: string })[];
  wsConnected: boolean;
  ingest: (snap: any) => void;
  pushEvent: (e: any) => void;
  setConnected: (b: boolean) => void;
  clear: (m: "touchdown" | "rover") => void;
}

export const useSim = create<SimState>((set) => ({
  touchdown: null, rover: null, moon: null, moonHistory: [], tdHistory: [], roverHistory: [], events: [], wsConnected: false,
  ingest: (snap) => set((s) => {
    if (snap.module === "touchdown") {
      const f = snap.frame;
      const sameRun = s.touchdown?.run_uid === snap.run_uid;
      const hist = sameRun ? s.tdHistory : [];
      const last = hist[hist.length - 1];
      const next = f && (!last || last.t !== f.t) ? [...hist, {
        t: f.t, agl: f.truth.agl, agl_est: f.estimate.agl, vz: f.truth.velocity[2], vz_est: f.estimate.velocity[2],
        fuel: f.truth.fuel, throttle: f.actuators.throttle, tilt: f.truth.tilt_deg,
        err: Math.hypot(...f.error.position), sig: Math.hypot(...f.estimate.sigma.slice(0, 3)),
        err_x: f.error.position[0], sig_x: f.estimate.sigma[0],
      }].slice(-HISTORY) : hist;
      return { touchdown: snap, tdHistory: next };
    }
    if (snap.module === "rover") {
      const f = snap.frame;
      const sameRun = s.rover?.run_uid === snap.run_uid;
      const hist = sameRun ? s.roverHistory : [];
      const last = hist[hist.length - 1];
      const next = f && (!last || last.t !== f.t) ? [...hist, {
        t: f.t, soc: f.battery.soc, power: f.battery.power, speed: f.truth.speed, err: f.error.position,
        sig: f.estimate.pos_sigma, herr: f.error.heading, hsig: f.estimate.sigma?.[4] ?? 0, slip: f.slip,
        nis: f.nis?.visloc ?? null,
      }].slice(-HISTORY) : hist;
      return { rover: snap, roverHistory: next };
    }
    if (snap.module === "moon") {
      const f = snap.frame;
      const same = s.moon?.run_uid === snap.run_uid;
      const hist = same ? s.moonHistory : [];
      const last = hist[hist.length - 1];
      const next = f && (!last || last.t !== f.t) ? [...hist, { t: f.t, agl: f.truth.agl, vz: f.truth.velocity[2], vx: f.truth.velocity[0],
        throttle: f.engine.throttle, prop: f.truth.propellant, dust: f.dust_rate, nav: f.error.position, pitch: (f.truth.pitch * 180) / Math.PI }].slice(-HISTORY) : hist;
      return { moon: snap, moonHistory: next };
    }
    return {};
  }),
  pushEvent: (e) => set((s) => (e.kind === "status" ? {} : { events: [...s.events, e].slice(-300) })),
  setConnected: (b) => set({ wsConnected: b }),
  clear: (m) => set(m === "touchdown" ? { touchdown: null, tdHistory: [] } : { rover: null, roverHistory: [] }),
}));
