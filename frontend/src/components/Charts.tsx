import { fmtInr, fmtNum } from "../lib/format";
import type { PortfolioResult, SensitivityRow } from "../lib/types";

const W = 760, H = 300, M = { t: 20, r: 20, b: 56, l: 84 };

/** Benefit (normalised objective) against budget: the exact optimum and the simple "top need first" list. */
export function FrontierChart({ results, budgets, current }: { results: PortfolioResult[]; budgets: number[]; current: number }) {
  if (!results.length) return null;
  const ys = results.flatMap(r => [r.objective_norm, r.baseline_top_need.objective_norm]);
  const ymax = Math.max(...ys, 1e-9) * 1.08;
  const x = (i: number) => M.l + (budgets.length > 1 ? (i / (budgets.length - 1)) * (W - M.l - M.r) : (W - M.l - M.r) / 2);
  const y = (v: number) => H - M.b - (v / ymax) * (H - M.t - M.b);
  const line = (f: (r: PortfolioResult) => number) => results.map((r, k) => `${k ? "L" : "M"}${x(budgets.indexOf(r.budget_inr)).toFixed(1)},${y(f(r)).toFixed(1)}`).join(" ");
  return (
    <figure className="chart chart--small">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Benefit against budget for the optimised portfolio and the simple top-need list">
        {[0, 0.5, 1].map(k => <g key={k}><line x1={M.l} x2={W - M.r} y1={y(ymax * k / 1.08)} y2={y(ymax * k / 1.08)} className="chart__grid" />
          <text x={M.l - 10} y={y(ymax * k / 1.08) + 5} textAnchor="end" className="chart__tick">{fmtNum(ymax * k / 1.08, 2)}</text></g>)}
        {budgets.map((b, i) => <text key={b} x={x(i)} y={H - M.b + 26} textAnchor="middle" className="chart__tick">{fmtInr(b)}</text>)}
        <text x={(M.l + W - M.r) / 2} y={H - 8} textAnchor="middle" className="chart__note">Budget (selected city currency, present value)</text>
        <path d={line(r => r.baseline_top_need.objective_norm)} className="chart__fut" />
        <path d={line(r => r.objective_norm)} className="chart__hist" />
        {results.map(r => { const i = budgets.indexOf(r.budget_inr); return <circle key={r.budget_inr} cx={x(i)} cy={y(r.objective_norm)} r={r.budget_inr === current ? 8 : 5} className={r.budget_inr === current ? "chart__dot" : "chart__pt"} />; })}
      </svg>
      <figcaption className="chart__cap"><span className="key key--solid" /> Optimised portfolio &nbsp; <span className="key key--dash" /> Simple list: fund the highest-need sites first. Benefit is the weighted, normalised score (higher is better).</figcaption>
    </figure>
  );
}

const METRIC_LABEL: Record<string, string> = { cost_pv_inr: "Present-value cost", carbon_t_co2e: "Carbon stored", inr_per_t_co2e: "Cost per tonne CO₂e", inr_per_person_newly_served: "Cost per person newly served" };

/** Tornado: how far one metric moves when each assumption goes to its low and high value. */
export function Tornado({ rows, metric, base }: { rows: SensitivityRow[]; metric: string; base: number | null | undefined }) {
  const items = rows.map(r => ({ r, a: r.effects[metric]?.at_low, b: r.effects[metric]?.at_high })).filter(x => x.a != null && x.b != null && base)
    .map(x => ({ ...x, lo: Math.min(x.a as number, x.b as number), hi: Math.max(x.a as number, x.b as number) })).filter(x => x.hi - x.lo > 1e-9 * (base ?? 1))
    .sort((p, q) => (q.hi - q.lo) - (p.hi - p.lo)).slice(0, 8);
  if (!items.length || !base) return <p className="muted">No assumption moves {METRIC_LABEL[metric] ?? metric} for this site type.</p>;
  const all = items.flatMap(i => [i.lo, i.hi, base]);
  const lo = Math.min(...all), hi = Math.max(...all);
  const px = (v: number) => ((v - lo) / (hi - lo || 1)) * 100;
  return (
    <div className="tornado" role="list" aria-label={`Sensitivity of ${METRIC_LABEL[metric] ?? metric}`}>
      {items.map(({ r, lo: a, hi: b }) => (
        <div className="tornado__row" role="listitem" key={r.parameter}>
          <div className="tornado__name">{r.parameter.replace(/_/g, " ")}</div>
          <div className="tornado__track"><span className="tornado__base" style={{ left: `${px(base)}%` }} />
            <span className="tornado__bar" style={{ left: `${px(a)}%`, width: `${Math.max(1.5, px(b) - px(a))}%` }} /></div>
          <div className="tornado__val">{fmtNum(a, 0)} to {fmtNum(b, 0)}</div>
        </div>
      ))}
      <p className="muted">Line = base case ({fmtNum(base, 0)}). Each bar is one assumption moved to its low and high value with everything else at base.</p>
    </div>
  );
}
export { METRIC_LABEL };
