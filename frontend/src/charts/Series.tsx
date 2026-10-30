import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, ComposedChart } from "recharts";

export const PALETTE = ["#4C6EF5", "#F08C00", "#12B886", "#E03131", "#7950F2", "#1F2937"];
const axis = { stroke: "#8A94A6", fontSize: 10, fontFamily: "JetBrains Mono" };

export function Series({ data, x = "t", lines, height = 180, yLabel, domain }: {
  data: any[]; x?: string; lines: { key: string; name?: string; color?: string; dashed?: boolean }[]; height?: number; yLabel?: string; domain?: [any, any];
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} />
          <XAxis dataKey={x} tick={axis} tickFormatter={(v) => (typeof v === "number" ? v.toFixed(0) : v)} minTickGap={30} />
          <YAxis tick={axis} domain={domain ?? ["auto", "auto"]} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", offset: 22, style: axis } : undefined} />
          <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid rgba(17,24,39,.1)", borderRadius: 12, fontSize: 11, color: "#111827", boxShadow: "0 8px 24px rgba(16,24,40,.12)" }} formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="plainline" />
          {lines.map((l, i) => (
            <Line key={l.key} dataKey={l.key} name={l.name ?? l.key} stroke={l.color ?? PALETTE[i % PALETTE.length]} dot={false}
              strokeWidth={1.8} strokeDasharray={l.dashed ? "5 4" : undefined} isAnimationActive={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Estimation error plotted against its ±k·sigma envelope (covariance is shown, not used as proof of accuracy). */
export function ErrorVsSigma({ data, err, sig, height = 180, k = 2, title }: { data: any[]; err: string; sig: string; height?: number; k?: number; title?: string }) {
  const d = data.map((r) => ({ t: r.t, err: r[err], band: [-(k * r[sig]), k * r[sig]] }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <ComposedChart data={d} margin={{ top: 6, right: 10, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="rgba(17,24,39,.06)" vertical={false} />
          <XAxis dataKey="t" tick={axis} tickFormatter={(v) => v.toFixed(0)} minTickGap={30} />
          <YAxis tick={axis} />
          <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid rgba(17,24,39,.1)", borderRadius: 12, fontSize: 11, color: "#111827", boxShadow: "0 8px 24px rgba(16,24,40,.12)" }} formatter={(v: any) => (Array.isArray(v) ? `±${Number(v[1]).toFixed(3)}` : Number(v).toFixed(3))} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Area dataKey="band" name={`±${k}σ (EKF covariance)`} fill="#4C6EF5" fillOpacity={0.14} stroke="none" isAnimationActive={false} />
          <Line dataKey="err" name={title ?? "actual error (estimate − truth)"} stroke="#E03131" dot={false} strokeWidth={1.6} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
