import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { EvidenceBadge, Notice } from "../components/Bits";
import { getJson } from "../lib/api";
import { flattenAssumptions, type AssumptionRow } from "../lib/assumptions";
import { useData } from "../lib/data";
import { find, PRESET_LABEL, usePortfolios } from "../lib/portfolio";
import { fmtDate, fmtInr, fmtInt, fmtNum, fmtPct } from "../lib/format";

export default function Report() {
  const d = useData();
  const pf = usePortfolios(d.status === "ready" && d.meta.city.finance_enabled);
  const [q] = useSearchParams();
  const [assump, setAssump] = useState<AssumptionRow[]>([]);
  useEffect(() => {
    if (d.status !== "ready") return;
    getJson<Record<string, unknown>>("/api/assumptions").then(a => setAssump(flattenAssumptions(a))).catch(() => setAssump([]));
  }, [d.status]);

  if (d.status !== "ready") return <div className="fullstate"><Notice title="Loading…" /></div>;
  if (!d.meta.city.finance_enabled) return <div className="fullstate"><Notice tone="warn" title="A financial report is not available for this city.">{d.meta.city.finance_reason ?? "The local cost and carbon assumptions have not been validated. No financial values are borrowed from Pune."}</Notice></div>;
  if (pf.status === "missing") return <div className="fullstate"><Notice tone="warn" title="No portfolio results yet.">{pf.reason}</Notice></div>;
  if (pf.status !== "ready") return <div className="fullstate"><Notice title="Loading…" /></div>;
  const P = pf.data;
  const preset = q.get("preset") ?? "balanced", b = Number(q.get("budget") ?? Math.floor((P.budgets_inr.length - 1) / 2)), eq = Number(q.get("equity") ?? 0);
  const r = find(P, preset, b, eq);
  if (!r) return <div className="fullstate"><Notice tone="warn" title="That plan is not in the pre-solved grid.">Choose a preset, budget and equity setting on the Plan page.</Notice></div>;
  const nr = new Set(P.no_regret_site_ids);
  const built = d.meta.manifest?.generated_at;

  return (
    <article className="report">
      <div className="report__bar"><button className="btn btn--solid" onClick={() => window.print()}>Print or save as PDF</button></div>
      <header>
        <p className="kicker">EcoMetrix · {d.meta.city.name} · simulated plan</p>
        <h1 className="display display--sm">Greening plan: {PRESET_LABEL[preset] ?? preset}, budget {fmtInr(P.budgets_inr[b])}{eq > 0 ? `, equity rule ${eq}%` : ""}</h1>
        <p className="muted">Data last built {fmtDate(built)}. This is a simulation. Nothing has been built, and every result is compared with doing nothing.</p>
      </header>

      <h2>Summary</h2>
      <table className="table"><tbody>
        <tr><th>Sites funded</th><td>{r.n_sites}</td></tr>
        <tr><th>Cost, present value <EvidenceBadge kind="ASSUMED" /></th><td>{fmtInr(r.cost_pv_inr.p50)} (range {fmtInr(r.cost_pv_inr.p10)} to {fmtInr(r.cost_pv_inr.p90)}); chance of fitting the budget {fmtPct(r.prob_within_budget * 100, 0)}</td></tr>
        <tr><th>People newly within {fmtNum(d.meta.city.access?.distance_m ?? 300, 0)} m of a park, counted once <EvidenceBadge kind="MODELLED" /></th><td>{fmtInt(r.people_newly_served)}</td></tr>
        <tr><th>Cooling, person-degrees <EvidenceBadge kind="MODELLED" /></th><td>{fmtInt(r.cooling_person_degrees.p50)} (range {fmtInt(r.cooling_person_degrees.p10)} to {fmtInt(r.cooling_person_degrees.p90)})</td></tr>
        <tr><th>Carbon stored, t CO₂e, mini-forests only <EvidenceBadge kind="ASSUMED" /></th><td>{fmtInt(r.carbon_t_co2e.p50)} (range {fmtInt(r.carbon_t_co2e.p10)} to {fmtInt(r.carbon_t_co2e.p90)})</td></tr>
        <tr><th>Share of spend in the top third of need</th><td>{fmtPct(r.high_need_share_of_spend * 100, 0)}</td></tr>
        <tr><th>Versus doing nothing</th><td>{fmtInr(0)} and no benefit</td></tr>
        <tr><th>Solver</th><td>{r.solver.status.toLowerCase()}{r.solver.gap ? `, within ${fmtNum(r.solver.gap * 100, 1)}% of the best possible` : ""}</td></tr>
      </tbody></table>

      <h2>Chosen sites</h2>
      <table className="table"><thead><tr><th>Type</th><th>Area (ha)</th><th>Hexagon</th><th>Cost (median)</th><th>Cooling (person-degrees)</th><th>People newly reached</th><th>Note</th></tr></thead>
        <tbody>{[...r.sites].sort((a, c) => c.cost_p50_inr - a.cost_p50_inr).map(s => (
          <tr key={s.site_id}><td>{s.type === "pocket_park" ? "Pocket park" : "Mini-forest"}</td><td>{fmtNum(s.area_ha, 1)}</td><td><code>{s.h3}</code></td><td>{fmtInr(s.cost_p50_inr)}</td>
            <td>{s.cooling_person_degrees_p50 > 0 ? fmtInt(s.cooling_person_degrees_p50) : "n/a"}</td><td>{fmtInt(s.people_newly_served_marginal)}</td><td>{nr.has(s.site_id) ? "no-regret; " : ""}needs field verification</td></tr>))}</tbody></table>

      <h2>How to read this</h2>
      <ul>
        <li>Weights ({Object.entries(P.presets[preset] ?? {}).map(([k, v]) => `${k} ${fmtNum(v * 100, 0)}%`).join(", ")}), budgets and the equity share are policy choices, not facts.</li>
        <li>Candidate sites are estimated open land per hexagon from satellite land cover, not surveyed parcels. Ownership, legality and soil are unknown.</li>
        <li>Cooling is a modelled change in surface temperature (not air temperature) once planting matures. Carbon is not estimated for pocket parks.</li>
        <li>Costs and carbon are sourced ranges, not a verified local rate schedule. No return on investment is claimed: green space earns no revenue in this model.</li>
        <li>Resident vulnerability (age, income, health) is not in the need score.</li>
      </ul>

      <h2>Assumptions used</h2>
      <table className="table"><thead><tr><th>Parameter</th><th>Low / base / high</th><th>Source</th></tr></thead>
        <tbody>{assump.map(a => <tr key={a.path}><td>{a.path}{a.unit && <><br /><span className="muted">{a.unit}</span></>}</td><td>{a.low != null ? `${a.low} / ${a.base} / ${a.high}` : String(a.value ?? "n/a")}</td><td>{a.source}</td></tr>)}</tbody></table>
      <p className="muted">Data sources are listed in the selected city’s data credits and audit. City-specific inventory coverage and source vintages vary.</p>
    </article>
  );
}
