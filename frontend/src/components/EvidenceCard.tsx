import { useState } from "react";
import { Link } from "react-router-dom";
import { fmtInr, fmtInt, fmtNum } from "../lib/format";
import type { Cell, FieldDef, PortfolioResult, PortfolioSite, Site } from "../lib/types";
import { EvidenceBadge } from "./Bits";
import ScenarioPanel from "./ScenarioPanel";

const TYPE_NAME = { pocket_park: "Pocket park", mini_forest: "Dense mini-forest" } as const;
const COMPS: [string, string][] = [["need_heat", "Heat"], ["need_people", "Residents"], ["need_gap", "Park-access gap"], ["need_growth", "Growth to 2035"]];
const COST_BASIS = {
  pocket_park: "Median cost uses PMC's average all-in garden spend per m² per year, applied over the horizon. A crude proxy: no Pune rate schedule for new parks was found.",
  mini_forest: "Median cost uses a press-reported quote for dense native planting plus replacing failed saplings and three years of care. No Pune rate schedule was found."
} as const;

export default function EvidenceCard({ site, cell, fields, result, noRegret, onClose }: {
  site: PortfolioSite; cell?: Cell; fields: Record<string, FieldDef>; result: PortfolioResult; noRegret: boolean; onClose: () => void;
}) {
  const [whatIf, setWhatIf] = useState(false);
  const asSite: Site = { id: site.site_id, h3: site.h3, type: site.type, area_ha: site.area_ha, open_land_ha: site.area_ha, pop: cell?.v.pop ?? 0, unserved: 0,
    dlst_p50: null, noRegret, lat: site.lat, lng: site.lng };
  const bars = COMPS.filter(([k]) => k in fields && cell?.v[k] != null);
  return (
    <aside className="scenario evidence" aria-label="Evidence for the selected site">
      <div className="cellcard__head">
        <div>
          <p className="kicker">Evidence card</p>
          <p className="cellcard__loc">{TYPE_NAME[site.type]} · {fmtNum(site.area_ha, 1)} ha</p>
          <p className="muted">Hexagon <code>{site.h3}</code></p>
        </div>
        <button className="iconbtn" onClick={onClose} aria-label="Close evidence card">✕</button>
      </div>
      <p>{noRegret && <span className="status status--pass">no-regret </span>} <span className="status status--warn">needs field verification</span></p>
      <p className="muted">The open land here is estimated from satellite land cover, not surveyed. Ownership, legality and soil are unknown.</p>

      <section className="evidence__sec">
        <h3>Why here <EvidenceBadge kind="MODELLED" /></h3>
        {bars.length ? bars.map(([k, label]) => (
          <div key={k} className="bar"><span className="bar__label">{label}</span>
            <span className="bar__track"><span className="bar__fill" style={{ width: `${Math.min(100, Math.max(0, cell?.v[k] ?? 0))}%` }} /></span>
            <span className="bar__num">{fmtNum(cell?.v[k], 0)}</span></div>)) : <p className="muted">Need components are not available for this build.</p>}
        <p className="muted">Percentile of this hexagon among populated hexagons (100 = highest need). A high percentile means high compared with the rest of Pune, not high in absolute terms.</p>
        {cell?.v.need_balanced != null && <p>Balanced need score: <strong>{fmtNum(cell.v.need_balanced, 0)}</strong> of 100</p>}
      </section>

      <section className="evidence__sec">
        <h3>What this site adds in this plan</h3>
        <dl className="kv kv--nested">
          <div><dt>Cost (median, present value) <EvidenceBadge kind="ASSUMED" /></dt><dd>{fmtInr(site.cost_p50_inr)}</dd></div>
          <div><dt>Cooling (person-degrees) <EvidenceBadge kind="MODELLED" /></dt><dd>{site.cooling_person_degrees_p50 > 0 ? fmtInt(site.cooling_person_degrees_p50) : "not estimated"}</dd></div>
          <div><dt>People newly within 300 m of a park, not reached by another chosen site <EvidenceBadge kind="MODELLED" /></dt><dd>{fmtInt(site.people_newly_served_marginal)}</dd></div>
          <div><dt>Carbon stored (t CO₂e) <EvidenceBadge kind="ASSUMED" /></dt><dd>{site.type === "mini_forest" ? fmtInt(site.carbon_t_co2e_p50) : "not estimated"}</dd></div>
        </dl>
        <p className="muted">Everything is compared with doing nothing here. This is simulated: nothing has been built.</p>
      </section>

      {cell && (
        <section className="evidence__sec">
          <h3>What is there today</h3>
          <dl className="kv kv--nested">
            {(["pop", "tree_density_ha", "lst_c", "dist_park_m"] as const).filter(k => k in fields && cell.v[k] != null).map(k => (
              <div key={k}><dt>{fields[k].label} <EvidenceBadge kind={fields[k].evidence} /></dt><dd>{fmtNum(cell.v[k], fields[k].decimals > 1 ? 2 : fields[k].decimals)} {fields[k].unit}</dd></div>))}
          </dl>
        </section>
      )}

      <section className="evidence__sec">
        <h3>Assumptions behind the cost</h3>
        <p className="muted">{COST_BASIS[site.type]} Every parameter, range and source is in the <Link to="/method">assumptions register</Link>.</p>
      </section>

      <button className="btn btn--ghost" onClick={() => setWhatIf(w => !w)} aria-expanded={whatIf}>{whatIf ? "Hide detailed what-if" : "Run a detailed what-if"}</button>
      {whatIf && <ScenarioPanel embedded site={asSite} onClose={() => setWhatIf(false)} />}
      <p className="muted">Plan: {result.preset.replace(/_/g, " ")}, solver {result.solver.status.toLowerCase()}.</p>
    </aside>
  );
}
