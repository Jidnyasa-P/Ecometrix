import { useEffect, useRef, useState } from "react";
import { ApiError, postJson } from "../lib/api";
import { fmtInr, fmtInt, fmtNum, fmtPct } from "../lib/format";
import type { Range, ScenarioResult, Site } from "../lib/types";
import { EvidenceBadge, Notice } from "./Bits";
import { useData } from "../lib/data";

const TYPE_NAME = { pocket_park: "Pocket park", mini_forest: "Dense mini-forest" } as const;

function R({ r, f, suffix = "" }: { r: Range | null | undefined; f: (n: number) => string; suffix?: string }) {
  if (!r) return <span className="muted">n/a</span>;
  return <><strong>{f(r.p50)}{suffix}</strong> <span className="muted">(range {f(r.p10)} to {f(r.p90)})</span></>;
}

export default function ScenarioPanel({ site, onClose, embedded = false }: { site: Site; onClose: () => void; embedded?: boolean }) {
  const [area, setArea] = useState(site.area_ha);
  const [budgetAmount, setBudgetAmount] = useState("");
  const data = useData();
  const city = data.status === "ready" ? data.meta.city : undefined;
  const financeEnabled = city?.finance_enabled !== false;
  const [horizon, setHorizon] = useState(10);
  const accessDistance = city?.access?.distance_m ?? 300;
  const [res, setRes] = useState<ScenarioResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  const run = (a = area) => {
    if (!financeEnabled) return;
    const id = ++seq.current;
    setBusy(true); setErr(null);
    const b = budgetAmount.trim() === "" ? null : Number(budgetAmount);
    postJson<ScenarioResult>("/api/scenarios/run", { site_id: site.id, area_ha: a, horizon_years: horizon, budget_amount: b })
      .then(r => { if (id === seq.current) setRes(r); })
      .catch((e: unknown) => { if (id === seq.current) { setRes(null); setErr(e instanceof ApiError ? e.message : "Scenario failed"); } })
      .finally(() => { if (id === seq.current) setBusy(false); });
  };

  useEffect(() => { setArea(site.area_ha); setRes(null); run(site.area_ha); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [site.id]);

  const step = 0.1;
  const min = Math.min(0.1, site.area_ha);
  return (
    <aside className={`scenario ${embedded ? "scenario--embedded" : ""}`} aria-label="Scenario for the selected site">
      <div className="cellcard__head">
        <div>
          <p className="kicker">Scenario · {TYPE_NAME[site.type]}</p>
          <p className="cellcard__loc">Hexagon <code>{site.h3}</code></p>
          <p className="muted">Candidate: needs field verification. Open land is estimated from satellite land cover, not surveyed.</p>
        </div>
        <button className="iconbtn" onClick={onClose} aria-label="Close scenario">✕</button>
      </div>

      {!financeEnabled && <Notice tone="warn" title="Local cost model is not available">{city?.finance_reason ?? "This city's local project cost and carbon assumptions have not been validated. Cost scenarios are disabled rather than converted from another country's prices."}</Notice>}

      {financeEnabled && <div className="scenario__form">
        <label className="slider">Area to develop: <strong>{fmtNum(area, 1)} ha</strong> <span className="muted">(up to {fmtNum(site.area_ha, 1)})</span>
          <input type="range" min={min} max={site.area_ha} step={step} value={area} onChange={e => setArea(Number(e.target.value))} /></label>
        <label className="field">Fixed budget in {city?.currency ?? "local currency"} (optional)
          <input type="number" min="0" inputMode="decimal" value={budgetAmount} onChange={e => setBudgetAmount(e.target.value)} placeholder="Enter the full amount" /></label>
        <label className="field">Horizon
          <select value={horizon} onChange={e => setHorizon(Number(e.target.value))}>{[5, 10, 15].map(y => <option key={y} value={y}>{y} years</option>)}</select></label>
        <button className="btn btn--solid" onClick={() => run()} disabled={busy}>{busy ? "Running…" : "Run scenario"}</button>
      </div>}

      {err && <p className="notice notice--error" role="alert"><strong>{err}</strong></p>}

      {res && (
        <div className="scenario__out" aria-live="polite">
          <section>
            <h3>Cost <EvidenceBadge kind={res.cost.evidence} /></h3>
            <p><R r={res.cost.present_value_inr} f={fmtInr} /></p>
            <p className="muted">Present value over {res.horizon_years} years. {res.cost.basis}</p>
            {res.budget && (
              <p className={res.budget.p50_within_budget ? "okline" : "badline"}>
                Budget {fmtInr(res.budget.budget_inr)}: <strong>{fmtPct(res.budget.probability_within_budget * 100, 0)}</strong> of runs fit.
                {res.budget.max_area_ha_at_p50_cost != null && <> Largest area affordable at median cost: <strong>{fmtNum(res.budget.max_area_ha_at_p50_cost, 2)} ha</strong>.</>}
              </p>
            )}
          </section>

          <section>
            <h3>Cooling <EvidenceBadge kind={res.benefits.cooling.evidence} /></h3>
            {res.benefits.cooling.available && res.benefits.cooling.delta_lst_c ? (
              <>
                <p>Surface temperature of the hexagon: <R r={res.benefits.cooling.delta_lst_c} f={n => fmtNum(n, 2)} suffix=" °C" /></p>
                <p>Person-degrees cooled: <R r={res.benefits.cooling.person_degrees} f={n => fmtInt(n)} /></p>
              </>
            ) : null}
            <p className="muted">{res.benefits.cooling.note}</p>
          </section>

          <section>
            <h3>People newly within {fmtNum(accessDistance, 0)} m of a park <EvidenceBadge kind={res.benefits.people_newly_served.evidence} /></h3>
            <p><strong>{fmtInt(res.benefits.people_newly_served.value)}</strong></p>
            <p className="muted">{res.benefits.people_newly_served.note}</p>
          </section>

          <section>
            <h3>Carbon stored <EvidenceBadge kind={res.benefits.carbon.evidence} /></h3>
            {res.benefits.carbon.available && res.benefits.carbon.t_co2e ? <p><R r={res.benefits.carbon.t_co2e} f={n => fmtNum(n, 0)} suffix=" t CO₂e" /></p> : <p><strong>Not estimated</strong></p>}
            <p className="muted">{res.benefits.carbon.note}</p>
          </section>

          <section>
            <h3>Cost per unit of benefit</h3>
            <dl className="kv kv--nested">
              {res.cost_effectiveness.inr_per_person_newly_served && <div><dt>per person newly served</dt><dd><R r={res.cost_effectiveness.inr_per_person_newly_served} f={fmtInr} /></dd></div>}
              {res.cost_effectiveness.inr_per_t_co2e && <div><dt>per tonne CO₂e</dt><dd><R r={res.cost_effectiveness.inr_per_t_co2e} f={fmtInr} /></dd></div>}
              {res.cost_effectiveness.inr_per_person_degree_c && <div><dt>per person-degree cooled</dt><dd><R r={res.cost_effectiveness.inr_per_person_degree_c} f={fmtInr} /></dd></div>}
            </dl>
            <p className="muted">Each benefit is kept separate. There is no single return figure, because green space earns no revenue in this model.</p>
          </section>
          <p className="scenario__label">{res.label_note} {res.baseline}</p>
        </div>
      )}
    </aside>
  );
}
