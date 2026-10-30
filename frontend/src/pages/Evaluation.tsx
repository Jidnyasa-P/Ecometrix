import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { METRIC_LABEL, Tornado } from "../components/Charts";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { getJson } from "../lib/api";
import { useData } from "../lib/data";
import { usePortfolios } from "../lib/portfolio";
import { fmtNum } from "../lib/format";
import type { Forecast, ModelReport, Sensitivity } from "../lib/types";

const CAN = [
  "There are N trees in the 2019 Pune census (MEASURED).",
  "In Pune, greener hexagons have lower modelled surface temperature, by about X °C per unit of greenness in our model, with a stated range (MODELLED).",
  "Under these stated assumptions, option A costs ₹ N per tonne of CO₂e, with a P10 to P90 range (ASSUMED, SIMULATED).",
  "On our own held-out tests, the optimiser's portfolio is at least as good as funding the highest-need sites first (tested)."
];
const CANNOT = [
  "\"EcoMetrix reduces emissions by X%\": nothing has been built.",
  "\"Our forecast is X% accurate\" without quoting the backtest it came from.",
  "\"This lowers air temperature\": we only see surface temperature from a satellite.",
  "\"This pays back in N years\": green space earns no revenue in this model.",
  "Any figure copied from another city and presented as Pune's."
];

export default function Evaluation() {
  const d = useData();
  const pf = usePortfolios(d.status === "ready");
  const [mr, setMr] = useState<ModelReport | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [sv, setSv] = useState<Sensitivity | null>(null);
  const [svErr, setSvErr] = useState(false);
  const [metric, setMetric] = useState("cost_pv_inr");
  const [type, setType] = useState<"mini_forest" | "pocket_park">("mini_forest");

  useEffect(() => {
    if (d.status !== "ready") return;
    getJson<ModelReport>("/api/model-report").then(setMr).catch(() => setMr(null));
    getJson<Forecast>("/api/forecast").then(setFc).catch(() => setFc(null));
    getJson<Sensitivity>("/api/sensitivity").then(setSv).catch(() => setSvErr(true));
  }, [d.status]);

  const gains = pf.status === "ready" ? pf.data.results.filter(r => r.equity_pct === 0 && r.gain_vs_top_need_pct != null).map(r => r.gain_vs_top_need_pct as number) : [];
  const optimal = pf.status === "ready" ? pf.data.results.filter(r => r.solver.status === "OPTIMAL").length : 0;
  const cur = sv?.types?.[type];
  const metrics = cur ? Object.keys(cur.base).filter(k => cur.base[k] != null) : [];

  return (
    <>
      <PageHead kicker="Milestone M8 · Evaluation" title="Proof, limits, and what we cannot claim.">
        <p>What was tested, what the tests found, and where the numbers stop being evidence. Results appear here only when the build produced them.</p>
      </PageHead>

      <Section>
        <h2 className="display display--sm">Model quality</h2>
        {d.status !== "ready" && <Notice title="Loading…" />}
        {mr?.heat_model?.status === "ok" && mr.heat_model.cv && <p className="lede">Heat model: <strong>{mr.heat_model.chosen?.replace(/_/g, " ")}</strong> chosen on spatial cross-validation across {mr.heat_model.cv.blocks} held-out blocks, with a simple-baseline comparison on the <Link to="/audit">Data audit</Link> page.</p>}
        {fc && <p className="lede">Forecast: <strong>{fc.method.replace(/_/g, " ")}</strong>, tested by training on {fc.backtest.train_years[0]} to {fc.backtest.train_years[1]} and predicting {fc.backtest.test_years[0]} to {fc.backtest.test_years[fc.backtest.test_years.length - 1]}; its error across hexagons was {fmtNum(fc.backtest.methods[fc.method].wape_pct, 1)}% against {fmtNum(fc.backtest.methods.naive.wape_pct, 1)}% for &ldquo;no change&rdquo;.</p>}
        {pf.status === "ready" && gains.length > 0 && <p className="lede">Optimiser: {optimal} of {pf.data.results.length} solutions were proven optimal; with no equity rule it delivered {fmtNum(Math.min(...gains), 0)}% to {fmtNum(Math.max(...gains), 0)}% more weighted benefit than funding the highest-need sites first (median {fmtNum([...gains].sort((a, b) => a - b)[Math.floor(gains.length / 2)], 0)}%). Exactness is proven against brute force on small cases in the test suite.</p>}
        {!mr && !fc && pf.status !== "ready" && <Notice tone="warn" title="No model results yet">Run the model step after the data build.</Notice>}
      </Section>

      <Section>
        <h2 className="display display--sm">Which assumptions matter most?</h2>
        <p className="lede">Each assumption is moved to its low and high value, one at a time, for the median-cost site of each type. The longest bars are the numbers to research first. <EvidenceBadge kind="ASSUMED" /></p>
        {svErr && !sv && <Notice tone="warn" title="Sensitivity results are not available.">The model step has not produced them yet.</Notice>}
        {sv && (
          <>
            <div className="tabs" role="tablist" aria-label="Site type">
              {(Object.keys(sv.types) as ("mini_forest" | "pocket_park")[]).map(k => <button key={k} role="tab" aria-selected={type === k} className={`tab ${type === k ? "is-on" : ""}`} onClick={() => { setType(k); setMetric("cost_pv_inr"); }}>{k === "mini_forest" ? "Mini-forest" : "Pocket park"}</button>)}
            </div>
            <div className="tabs" role="tablist" aria-label="Metric">
              {metrics.map(m => <button key={m} role="tab" aria-selected={metric === m} className={`tab ${metric === m ? "is-on" : ""}`} onClick={() => setMetric(m)}>{METRIC_LABEL[m] ?? m}</button>)}
            </div>
            {cur && <Tornado rows={cur.rows} metric={metric} base={cur.base[metric]} />}
          </>
        )}
      </Section>

      <Section>
        <h2 className="display display--sm">What we can say, and what we must not.</h2>
        <div className="claims">
          <div className="claims__col claims__col--can"><h3>We can say</h3><ul>{CAN.map(c => <li key={c}>{c}</li>)}</ul></div>
          <div className="claims__col claims__col--cannot"><h3>We must not say</h3><ul>{CANNOT.map(c => <li key={c}>{c}</li>)}</ul></div>
        </div>
        <p className="muted">Real-world evidence would come later: satellite greenness and surface temperature before and after planting, field surveys of tree survival and resident feedback. Only then could a label move from SIMULATED to MEASURED.</p>
      </Section>

      <Section>
        <h2 className="display display--sm">Human checks still to do.</h2>
        <p className="lede">These cannot be automated and have <strong>not been done yet</strong>: the five-person usability test, the independent spreadsheet recomputation of one site, the 30-site satellite spot-check, expert review of 20 sites, a fluent-speaker review of the Marathi text, and comparing OpenStreetMap parks with the municipality&rsquo;s own list. Protocols and templates are in <code>docs/evaluation/</code>.</p>
      </Section>
    </>
  );
}
