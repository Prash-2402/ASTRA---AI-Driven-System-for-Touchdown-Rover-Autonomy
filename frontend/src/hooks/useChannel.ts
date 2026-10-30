import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../services/api";

/** Subscribe to a backend websocket channel with automatic reconnection. */
export function useChannel<T = any>(channel: string, onMessage: (msg: T) => void, enabled = true) {
  const [connected, setConnected] = useState(false);
  const cb = useRef(onMessage);
  cb.current = onMessage;
  useEffect(() => {
    if (!enabled) return;
    let ws: WebSocket | null = null;
    let stop = false;
    let retry: number | undefined;
    const open = () => {
      ws = new WebSocket(wsUrl(channel));
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (!stop) retry = window.setTimeout(open, 1500); };
      ws.onerror = () => ws?.close();
      ws.onmessage = (e) => { try { cb.current(JSON.parse(e.data)); } catch { /* ignore malformed */ } };
    };
    open();
    return () => { stop = true; window.clearTimeout(retry); ws?.close(); };
  }, [channel, enabled]);
  return connected;
}

export function usePoll<T>(fn: () => Promise<T>, ms: number, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const run = () => fn().then((d) => { if (alive) { setData(d); setError(null); } }).catch((e) => alive && setError(String(e.message || e)));
    run();
    const id = ms > 0 ? window.setInterval(run, ms) : undefined;
    return () => { alive = false; window.clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, refresh: () => setTick((t) => t + 1) };
}
