import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import MapStage, { type Camera } from "../components/MapStage";
import Legend from "../components/Legend";
import EvidenceCard from "../components/EvidenceCard";
import { FrontierChart } from "../components/Charts";
import { EvidenceBadge, Notice } from "../components/Bits";
import { useData } from "../lib/data";
import { find, PRESET_LABEL, usePortfolios } from "../lib/portfolio";
import { useTheme } from "../lib/theme";
import { useViewport } from "../lib/hooks";
import { fmtInr, fmtInt, fmtNum, fmtPct } from "../lib/format";
import type { Cell, FieldDef } from "../lib/types";

const WEIGHT_LABEL: Record<string, string> = { cooling: "cooling", people: "people reached", carbon: "carbon" };

export default function Plan() {
  const d = useData();
  const [theme] = useTheme();
  const vp = useViewport();
  const pf = usePortfolios(d.status === "ready");
  const [preset, setPreset] = useState<string | null>(null);
  const [bIdx, setBIdx] = useState<number | null>(null);
  const [eq, setEq] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(true);

  useEffect(() => {
    if (pf.status !== "ready") return;
    const keys = Object.keys(pf.data.presets);
    setPreset(p => p ?? (keys.includes("balanced") ? "balanced" : keys[0]));
    setBIdx(b => b ?? Math.floor((pf.data.budgets_inr.length - 1) / 2));
  }, [pf]);

  const res = useMemo(() => (pf.status === "ready" && preset != null && bIdx != null ? find(pf.data, preset, bIdx, eq) : null), [pf, preset, bIdx, eq]);
  const chosenHexes = useMemo(() => res?.sites.map(s => s.h3) ?? [], [res]);
  const chosenSet = useMemo(() => new Set(chosenHexes), [chosenHexes]);
  const highlight = useMemo(() => (res ? (c: Cell) => chosenSet.has(c.h3) : null), [res, chosenSet]);
  const curve = useMemo(() => (pf.status === "ready" && preset ? pf.data.results.filter(r => r.preset === preset && r.equity_pct === eq).sort((a, b) => a.budget_inr - b.budget_inr) : []), [pf, preset, eq]);

  if (d.status === "loading") return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading…"} /></div>;
  if (d.status !== "ready") return <div className="fullstate"><Notice tone="warn" title="The baseline is not available.">Build the data first (README), then reload.</Notice></div>;
  if (pf.status === "loading") return <div className="fullstate"><Notice title="Loading the pre-solved plans…" /></div>;
  if (pf.status === "missing") return <div className="fullstate"><Notice tone="warn" title="No portfolio results yet.">{pf.reason} The optimiser runs in the model step after the data build; see the Data audit page for its status. Nothing is shown in its place.</Notice></div>;

  const P = pf.data;
  const base = d.fields["need_balanced"] ?? d.fields["need_heat"] ?? Object.values(d.fields)[0];
  const field: FieldDef = base;
  const chosen = res?.sites.find(s => s.site_id === sel) ?? null;
  const cell = chosen ? d.cells.find(c => c.h3 === chosen.h3) : undefined;
  const pad = vp.mobile ? { top: 80, right: 12, bottom: Math.round(vp.h * 0.45), left: 12 } : { top: 92, right: chosen ? 440 : 40, bottom: 40, left: 440 };
  const camera: Camera = { pitch: 35, bearing: -10, padding: pad, duration: 1400 };
  const w = preset ? P.presets[preset] : null;
  const nr = new Set(P.no_regret_site_ids);

  return (
    <div className="explore">
      <div className="explore__map">
        <MapStage cells={d.cells} field={field} theme={theme} camera={camera} extrude interactive highlight={highlight} marked={chosenHexes}
          selectedHex={chosen?.h3 ?? null} label="Map of the chosen sites for the selected plan"
          onSelect={c => { if (!c || !res) return; const s = res.sites.find(x => x.h3 === c.h3); if (s) setSel(s.site_id); }} />
      </div>

      <aside className={`panel ${drawer ? "is-open" : ""}`} aria-label="Plan controls">
        <button className="panel__toggle" onClick={() => setDrawer(o => !o)} aria-expanded={drawer}>{drawer ? "Hide controls" : "Plan and results"}</button>
        <div className="panel__body">
          <p className="kicker">Best portfolio under a budget <EvidenceBadge kind="SIMULATED" /></p>
          <p className="layer__about">An exact optimiser picks the set of candidate sites that does the most good within the budget. Nothing is built: every result is a simulation compared with doing nothing. Budgets are pre-solved on a grid so each answer is a proven optimum.</p>

          <div className="presets" role="group" aria-label="Priority">
            {Object.keys(P.presets).map(k => <button key={k} className={`chip ${preset === k ? "is-on" : ""}`} onClick={() => { setPreset(k); setSel(null); }}>{PRESET_LABEL[k] ?? k}</button>)}
          </div>
          {w && <p className="muted">Weights (policy choices): {Object.entries(w).map(([k, v]) => `${WEIGHT_LABEL[k] ?? k} ${fmtNum(v * 100, 0)}%`).join(", ")}.</p>}

          <label className="slider">Budget: <strong>{fmtInr(P.budgets_inr[bIdx ?? 0])}</strong> <span className="muted">(present value)</span>
            <input type="range" min={0} max={P.budgets_inr.length - 1} step={1} value={bIdx ?? 0} onChange={e => { setBIdx(Number(e.target.value)); setSel(null); }} aria-valuetext={fmtInr(P.budgets_inr[bIdx ?? 0])} /></label>
          {P.equity_shares_pct.includes(50) && (
            <label className="switch"><input type="checkbox" checked={eq === 50} onChange={e => { setEq(e.target.checked ? 50 : 0); setSel(null); }} />
              <span>Equity rule: at least half of spend in the top third of need</span></label>)}

          {!res && <Notice tone="warn" title="No solution for this combination.">Try another budget or preset.</Notice>}
          {res && (
            <>
              <section className="summary" aria-live="polite">
                <h3>This plan</h3>
                <dl className="kv kv--nested">
                  <div><dt>Sites funded</dt><dd>{res.n_sites} ({Object.entries(res.by_type).map(([t, n]) => `${n} ${t === "pocket_park" ? "pocket park" : "mini-forest"}${n === 1 ? "" : "s"}`).join(", ")})</dd></div>
                  <div><dt>Cost, present value <EvidenceBadge kind="ASSUMED" /></dt><dd>{fmtInr(res.cost_pv_inr.p50)} <span className="muted">(range {fmtInr(res.cost_pv_inr.p10)} to {fmtInr(res.cost_pv_inr.p90)})</span></dd></div>
                  <div><dt>Chance it fits the budget</dt><dd>{fmtPct(res.prob_within_budget * 100, 0)}</dd></div>
                  <div><dt>People newly within 300 m of a park, counted once <EvidenceBadge kind="MODELLED" /></dt><dd>{fmtInt(res.people_newly_served)}</dd></div>
                  <div><dt>Cooling, person-degrees <EvidenceBadge kind="MODELLED" /></dt><dd>{fmtInt(res.cooling_person_degrees.p50)} <span className="muted">(range {fmtInt(res.cooling_person_degrees.p10)} to {fmtInt(res.cooling_person_degrees.p90)})</span></dd></div>
                  <div><dt>Carbon stored, t CO₂e (mini-forests only) <EvidenceBadge kind="ASSUMED" /></dt><dd>{fmtInt(res.carbon_t_co2e.p50)} <span className="muted">(range {fmtInt(res.carbon_t_co2e.p10)} to {fmtInt(res.carbon_t_co2e.p90)})</span></dd></div>
                  <div><dt>Share of spend in the top third of need</dt><dd>{fmtPct(res.high_need_share_of_spend * 100, 0)}</dd></div>
                  <div><dt>Versus doing nothing</dt><dd>₹ 0 and no benefit. Every figure above is the difference from this.</dd></div>
                  <div><dt>Versus funding the highest-need sites first</dt><dd>{res.gain_vs_top_need_pct == null ? "n/a" : `${fmtNum(res.gain_vs_top_need_pct, 0)}% more weighted benefit`}{res.equity_pct > 0 ? " (the simple list has no equity rule)" : ""}</dd></div>
                  <div><dt>Solver</dt><dd>{res.solver.status.toLowerCase()}{res.solver.gap != null && res.solver.gap > 0 ? `, within ${fmtNum(res.solver.gap * 100, 1)}% of the best possible` : ""}{res.solver.prefiltered ? `, searched the ${res.solver.candidates} most promising sites` : ""}</dd></div>
                </dl>
                <p className="muted">Present value over the horizon. Ranges add up each site's Monte Carlo draws and assume the sites' uncertainties are independent. Benefits are kept separate; there is no single return figure.</p>
                <p><Link className="btn btn--ghost" to={`/report?preset=${preset}&budget=${bIdx}&equity=${eq}`}>Open printable report</Link> <Link className="btn btn--ghost" to="/compare">Compare plans</Link></p>
              </section>

              <FrontierChart results={curve} budgets={P.budgets_inr} current={res.budget_inr} />
              <Legend field={field} theme={theme} />
              <p className="muted">Outlined hexagons are the chosen sites; the rest are dimmed. Colours show the balanced need score. {P.no_regret_rule}.</p>

              <ol className="sitelist" aria-label="Chosen sites">
                {[...res.sites].sort((a, b) => b.cost_p50_inr - a.cost_p50_inr).map(s => (
                  <li key={s.site_id}><button className={`site ${sel === s.site_id ? "is-on" : ""}`} onClick={() => setSel(s.site_id)}>
                    <span className="site__main"><strong>{s.type === "pocket_park" ? "Pocket park" : "Mini-forest"}</strong> · {fmtNum(s.area_ha, 1)} ha{nr.has(s.site_id) && <span className="status status--pass"> no-regret</span>}</span>
                    <span className="site__score">{fmtInr(s.cost_p50_inr).replace("₹ ", "")}</span></button></li>))}
              </ol>
            </>
          )}
        </div>
      </aside>

      {chosen && res && <EvidenceCard key={chosen.site_id} site={chosen} cell={cell} fields={d.fields} result={res} noRegret={nr.has(chosen.site_id)} onClose={() => setSel(null)} />}
    </div>
  );
}
