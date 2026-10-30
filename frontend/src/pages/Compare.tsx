import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { useData } from "../lib/data";
import { find, PRESET_LABEL, usePortfolios } from "../lib/portfolio";
import { fmtInr, fmtInt, fmtNum, fmtPct } from "../lib/format";
import type { PortfolioResult, Portfolios } from "../lib/types";

interface Pick { preset: string; b: number; eq: number }
const COLS = ["A", "B", "C"];

function Picker({ label, p, P, set }: { label: string; p: Pick; P: Portfolios; set: (x: Pick) => void }) {
  return (
    <fieldset className="pick"><legend>Plan {label}</legend>
      <label className="field">Priority<select value={p.preset} onChange={e => set({ ...p, preset: e.target.value })}>{Object.keys(P.presets).map(k => <option key={k} value={k}>{PRESET_LABEL[k] ?? k}</option>)}</select></label>
      <label className="field">Budget<select value={p.b} onChange={e => set({ ...p, b: Number(e.target.value) })}>{P.budgets_inr.map((b, i) => <option key={b} value={i}>{fmtInr(b)}</option>)}</select></label>
      <label className="field">Equity rule<select value={p.eq} onChange={e => set({ ...p, eq: Number(e.target.value) })}>{P.equity_shares_pct.map(x => <option key={x} value={x}>{x === 0 ? "None" : `At least ${x}% of spend in top-third need`}</option>)}</select></label>
    </fieldset>
  );
}

const METRICS: { key: string; label: string; badge: "ASSUMED" | "MODELLED"; get: (r: PortfolioResult) => number; fmt: (n: number) => string; range?: (r: PortfolioResult) => [number, number]; better: "high" | "low" }[] = [
  { key: "cost", label: "Cost, present value (median)", badge: "ASSUMED", get: r => r.cost_pv_inr.p50, fmt: fmtInr, range: r => [r.cost_pv_inr.p10, r.cost_pv_inr.p90], better: "low" },
  { key: "people", label: "People newly within 300 m of a park (counted once)", badge: "MODELLED", get: r => r.people_newly_served, fmt: fmtInt, better: "high" },
  { key: "cool", label: "Cooling, person-degrees", badge: "MODELLED", get: r => r.cooling_person_degrees.p50, fmt: fmtInt, range: r => [r.cooling_person_degrees.p10, r.cooling_person_degrees.p90], better: "high" },
  { key: "carbon", label: "Carbon stored, t CO₂e (mini-forests only)", badge: "ASSUMED", get: r => r.carbon_t_co2e.p50, fmt: fmtInt, range: r => [r.carbon_t_co2e.p10, r.carbon_t_co2e.p90], better: "high" }
];

export default function Compare() {
  const d = useData();
  const pf = usePortfolios(d.status === "ready");
  const [picks, setPicks] = useState<Pick[] | null>(null);

  const P = pf.status === "ready" ? pf.data : null;
  const initial = useMemo<Pick[] | null>(() => {
    if (!P) return null;
    const keys = Object.keys(P.presets); const mid = Math.floor((P.budgets_inr.length - 1) / 2);
    const second = keys.find(k => k !== "balanced") ?? keys[0];
    return [{ preset: keys.includes("balanced") ? "balanced" : keys[0], b: mid, eq: 0 }, { preset: second, b: mid, eq: 0 }, { preset: keys.includes("balanced") ? "balanced" : keys[0], b: mid, eq: P.equity_shares_pct.includes(50) ? 50 : 0 }];
  }, [P]);
  const cur = picks ?? initial;

  if (d.status === "loading") return <div className="fullstate"><Notice title="Loading…" /></div>;
  if (d.status !== "ready") return <div className="fullstate"><Notice tone="warn" title="The baseline is not available.">Build the data first.</Notice></div>;
  if (pf.status === "missing") return <div className="fullstate"><Notice tone="warn" title="No portfolio results yet.">{pf.reason}</Notice></div>;
  if (!P || !cur) return <div className="fullstate"><Notice title="Loading the pre-solved plans…" /></div>;

  const results = cur.map(p => find(P, p.preset, p.b, p.eq));
  const set = (i: number) => (x: Pick) => setPicks(cur.map((c, k) => (k === i ? x : c)));
  const a = results[0];
  const diffs: string[] = [];
  results.slice(1).forEach((r, i) => {
    if (!a || !r) return;
    const dp = r.people_newly_served - a.people_newly_served, dc = r.cost_pv_inr.p50 - a.cost_pv_inr.p50;
    diffs.push(`Plan ${COLS[i + 1]} versus A: ${fmtInt(Math.abs(dp))} ${dp >= 0 ? "more" : "fewer"} people newly within 300 m of a park, ` +
      `${fmtInt(Math.abs(r.cooling_person_degrees.p50 - a.cooling_person_degrees.p50))} ${r.cooling_person_degrees.p50 >= a.cooling_person_degrees.p50 ? "more" : "fewer"} person-degrees of cooling, ` +
      `${fmtInt(Math.abs(r.carbon_t_co2e.p50 - a.carbon_t_co2e.p50))} t ${r.carbon_t_co2e.p50 >= a.carbon_t_co2e.p50 ? "more" : "less"} carbon, at ${fmtInr(Math.abs(dc))} ${dc >= 0 ? "more" : "less"} cost.`);
  });

  return (
    <>
      <PageHead kicker="Milestone M7 · Screen 5" title="Compare plans, against doing nothing.">
        <p>Pick up to three plans from the pre-solved grid. Every column is a simulation: nothing is built, and the last column is what happens if the city does nothing.</p>
      </PageHead>
      <Section>
        <div className="picks">{cur.map((p, i) => <Picker key={i} label={COLS[i]} p={p} P={P} set={set(i)} />)}</div>
      </Section>
      <Section>
        <div className="tablewrap"><table className="table table--compare">
          <caption className="sr">Comparison of three simulated plans and doing nothing</caption>
          <thead><tr><th>Indicator</th>{cur.map((_, i) => <th key={i}>Plan {COLS[i]}</th>)}<th>Do nothing</th></tr></thead>
          <tbody>
            <tr><td><strong>Sites funded</strong></td>{results.map((r, i) => <td key={i}>{r ? `${r.n_sites} (${Object.entries(r.by_type).map(([t, n]) => `${n} ${t === "pocket_park" ? "park" : "forest"}`).join(", ")})` : "n/a"}</td>)}<td>0</td></tr>
            {METRICS.map(m => {
              const vals = results.map(r => (r ? m.get(r) : NaN)); const finite = vals.filter(Number.isFinite);
              const best = finite.length ? (m.better === "high" ? Math.max(...finite) : Math.min(...finite)) : NaN;
              return (
                <tr key={m.key}><td><strong>{m.label}</strong> <EvidenceBadge kind={m.badge} /></td>
                  {results.map((r, i) => <td key={i} className={r && vals[i] === best && finite.length > 1 ? "best" : ""}>{r ? <><strong>{m.fmt(m.get(r))}</strong>{m.range && <span className="muted"><br />range {m.fmt(m.range(r)[0])} to {m.fmt(m.range(r)[1])}</span>}</> : "n/a"}</td>)}
                  <td>{m.key === "cost" ? "₹ 0" : "0"}</td></tr>);
            })}
            <tr><td><strong>Chance the cost fits the budget</strong></td>{results.map((r, i) => <td key={i}>{r ? fmtPct(r.prob_within_budget * 100, 0) : "n/a"}</td>)}<td>n/a</td></tr>
            <tr><td><strong>Share of spend in the top third of need</strong></td>{results.map((r, i) => <td key={i}>{r ? fmtPct(r.high_need_share_of_spend * 100, 0) : "n/a"}</td>)}<td>n/a</td></tr>
            <tr><td><strong>Whole-plan cost per person newly served</strong></td>{results.map((r, i) => <td key={i}>{r && r.people_newly_served > 0 ? fmtInr(r.cost_pv_inr.p50 / r.people_newly_served) : "n/a"}</td>)}<td>n/a</td></tr>
          </tbody>
        </table></div>
        <p className="muted">Best value in each row is shaded. The cost-per-person row divides the whole plan&rsquo;s cost by one benefit, so it overstates the price of that benefit when the plan also buys cooling and carbon. Each benefit is kept separate on purpose.</p>
      </Section>
      {diffs.length > 0 && <Section><h2 className="display display--sm">What differs.</h2><ul className="limits limits--plain">{diffs.map(t => <li key={t}>{t}</li>)}</ul></Section>}
      <Section>
        <p className="lede">Weights, budgets and the equity share are policy choices, listed on the <Link to="/method">Method</Link> page. Open a plan&rsquo;s <Link to={`/report?preset=${cur[0].preset}&budget=${cur[0].b}&equity=${cur[0].eq}`}>printable report</Link>.
          Average ratio across the grid versus funding highest-need first: {fmtNum(P.results.filter(r => r.gain_vs_top_need_pct != null && r.equity_pct === 0).reduce((s, r) => s + (r.gain_vs_top_need_pct ?? 0), 0) / Math.max(1, P.results.filter(r => r.gain_vs_top_need_pct != null && r.equity_pct === 0).length), 0)}% more weighted benefit.</p>
      </Section>
    </>
  );
}
