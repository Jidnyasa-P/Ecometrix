import { useMemo, useRef, useState } from "react";
import type { ForecastPoint } from "../lib/types";
import { fmtIndianShort, fmtInt } from "../lib/format";

const W = 920, H = 430, M = { t: 24, r: 28, b: 52, l: 92 };

/** Line chart for the city series: solid history, dashed projection, shaded backtest-error envelope. Pure SVG, no chart library. */
export default function PopChart({ series, lastObserved }: { series: ForecastPoint[]; lastObserved: number }) {
  const [hover, setHover] = useState<ForecastPoint | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const g = useMemo(() => {
    const years = series.map(p => p.year);
    const x0 = Math.min(...years), x1 = Math.max(...years);
    const lows = series.map(p => p.low ?? p.total), highs = series.map(p => p.high ?? p.total);
    const y0 = Math.min(...lows) * 0.94, y1 = Math.max(...highs) * 1.04;
    const x = (v: number) => M.l + ((v - x0) / (x1 - x0 || 1)) * (W - M.l - M.r);
    const y = (v: number) => H - M.b - ((v - y0) / (y1 - y0 || 1)) * (H - M.t - M.b);
    const hist = series.filter(p => p.kind === "history");
    const fut = [series.find(p => p.year === lastObserved) ?? hist[hist.length - 1], ...series.filter(p => p.kind === "forecast")];
    const line = (pts: ForecastPoint[]) => pts.map((p, i) => `${i ? "L" : "M"}${x(p.year).toFixed(1)},${y(p.total).toFixed(1)}`).join(" ");
    const fp = series.filter(p => p.kind === "forecast");
    const bandTop = fp.map(p => `${x(p.year).toFixed(1)},${y(p.high ?? p.total).toFixed(1)}`);
    const bandBot = [...fp].reverse().map(p => `${x(p.year).toFixed(1)},${y(p.low ?? p.total).toFixed(1)}`);
    const anchor = hist[hist.length - 1];
    const band = fp.length ? `M${x(anchor.year).toFixed(1)},${y(anchor.total).toFixed(1)} L${bandTop.join(" L")} L${bandBot.join(" L")} Z` : "";
    const yt = Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4);
    const xt = years.filter(v => v % 5 === 0);
    return { x, y, hist, fut, line, band, yt, xt, x0, x1 };
  }, [series, lastObserved]);

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = series[0], d = Infinity;
    for (const p of series) { const dd = Math.abs(g.x(p.year) - px); if (dd < d) { d = dd; best = p; } }
    setHover(best);
  };

  return (
    <figure className="chart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="City population: history to 2020 and projection to 2035 with an error envelope"
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {g.yt.map(v => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={g.y(v)} y2={g.y(v)} className="chart__grid" />
            <text x={M.l - 12} y={g.y(v) + 5} textAnchor="end" className="chart__tick">{fmtIndianShort(v)}</text>
          </g>
        ))}
        {g.xt.map(v => <text key={v} x={g.x(v)} y={H - M.b + 28} textAnchor="middle" className="chart__tick">{v}</text>)}
        <line x1={g.x(lastObserved)} x2={g.x(lastObserved)} y1={M.t} y2={H - M.b} className="chart__divider" />
        <text x={g.x(lastObserved) - 8} y={M.t + 16} textAnchor="end" className="chart__note">history</text>
        <text x={g.x(lastObserved) + 8} y={M.t + 16} className="chart__note">projection</text>
        {g.band && <path d={g.band} className="chart__band" />}
        <path d={g.line(g.hist)} className="chart__hist" />
        <path d={g.line(g.fut)} className="chart__fut" />
        {hover && <><line x1={g.x(hover.year)} x2={g.x(hover.year)} y1={M.t} y2={H - M.b} className="chart__cursor" /><circle cx={g.x(hover.year)} cy={g.y(hover.total)} r="6" className="chart__dot" /></>}
      </svg>
      <div className="chart__tip" aria-live="polite">
        {hover ? (
          <><strong>{hover.year}</strong> · {fmtInt(hover.total)} people ({hover.kind === "history" ? "WorldPop modelled series" : "projection"})
            {hover.kind === "forecast" && hover.low != null && hover.high != null && <> · envelope {fmtInt(hover.low)} to {fmtInt(hover.high)}</>}</>
        ) : <span className="muted">Move over the chart to read values.</span>}
      </div>
      <figcaption className="chart__cap">Sum of the study-area hexagons. Shaded band: range of errors the same method made when tested on past years (see the test below). It is not a statistical interval.</figcaption>
    </figure>
  );
}
