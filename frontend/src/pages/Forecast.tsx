import { useEffect, useMemo, useState } from "react";
import MapStage, { type Camera } from "../components/MapStage";
import Legend from "../components/Legend";
import PopChart from "../components/PopChart";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { ApiError, getJson } from "../lib/api";
import { useData } from "../lib/data";
import { useTheme } from "../lib/theme";
import { fmtIndianShort, fmtInt, fmtNum } from "../lib/format";
import type { FieldDef, Forecast, ModelReport } from "../lib/types";

const METHOD_NAME: Record<string, string> = {
  naive: "No change (last observed value)", linear_recent10: "Straight line, last 10 years", linear_all: "Straight line, all years", exponential_all: "Exponential growth, all years"
};

export default function ForecastPage() {
  const d = useData();
  const [theme] = useTheme();
  const [fc, setFc] = useState<Forecast | null>(null);
  const [rep, setRep] = useState<ModelReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [key, setKey] = useState("pop_growth_2035");

  useEffect(() => {
    if (d.status !== "ready") return;
    getJson<Forecast>("/api/forecast").then(setFc).catch((e: unknown) => setErr(e instanceof ApiError && e.code === "baseline_not_built" ? "not_built" : "failed"));
    getJson<ModelReport>("/api/model-report").then(setRep).catch(() => setRep(null));
  }, [d.status]);

  const mapFields = useMemo(() => (d.status === "ready" ? (["pop_growth_2035", "pop_2035", "pop_unserved_2035"].map(k => d.fields[k]).filter(Boolean) as FieldDef[]) : []), [d]);
  const camera: Camera = { pitch: 0, bearing: 0, padding: { top: 30, right: 30, bottom: 30, left: 30 }, duration: 1200 };

  if (d.status === "loading") return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading…"} /></div>;
  if (d.status !== "ready") return <div className="fullstate"><Notice tone="warn" title="The baseline is not available.">Build the data first (README), then reload.</Notice></div>;

  const reason = rep?.modules?.forecast?.reason;
  const hs = fc ? fc.city_series.filter(p => p.kind === "forecast") : [];
  const last = fc ? fc.city_series.find(p => p.year === fc.last_observed_year) : undefined;
  const field = d.fields[key] ?? mapFields[0];

  return (
    <>
      <PageHead kicker="Milestone M5 · Screen 2" title="Where the city is heading.">
        <p>A projection of residents per hexagon to 2035, built from twenty years of WorldPop&rsquo;s modelled series. The method was picked by testing it on years it had not seen, and it had to beat &ldquo;no change&rdquo; to be used.</p>
      </PageHead>

      {!fc && !err && <Section><Notice title="Loading the projection…" /></Section>}
      {err && <Section><Notice tone="warn" title="The projection is not available.">
        {reason ? `Reason from the last build: ${reason}` : "The forecast module has not produced output yet. See the Data audit page for the status of each layer."}
      </Notice></Section>}

      {fc && (
        <>
          <Section>
            <p className="kicker">City total <EvidenceBadge kind="MODELLED" /></p>
            <h2 className="display display--sm">{last && hs.length ? <>From {fmtIndianShort(last.total)} in {fc.last_observed_year} to about {fmtIndianShort(hs[hs.length - 1].total)} in {hs[hs.length - 1].year}.</> : "Population projection."}</h2>
            <p className="lede">Method chosen by the test: <strong>{METHOD_NAME[fc.method] ?? fc.method}</strong>. This is a projection of a modelled series, so it describes where the trend leads, not what will happen.</p>
            <PopChart series={fc.city_series} lastObserved={fc.last_observed_year} />
            <div className="tablewrap"><table className="table">
              <thead><tr><th>Year</th><th>Projected people</th><th>Backtest-error envelope</th></tr></thead>
              <tbody>{hs.filter(p => fc.horizons.includes(p.year)).map(p => (
                <tr key={p.year}><td><strong>{p.year}</strong></td><td>{fmtInt(p.total)}</td><td>{fmtInt(p.low)} to {fmtInt(p.high)}</td></tr>))}</tbody>
            </table></div>
          </Section>

          <Section>
            <h2 className="display display--sm">How it was tested.</h2>
            <p className="lede">Trained on {fc.backtest.train_years[0]} to {fc.backtest.train_years[1]}, then asked to predict {fc.backtest.test_years[0]} to {fc.backtest.test_years[fc.backtest.test_years.length - 1]}, which it never saw. Lower error is better. {fc.selection_rule}.</p>
            <div className="tablewrap"><table className="table">
              <thead><tr><th>Method</th><th>Error across hexagons (WAPE)</th><th>Error on the city total</th><th>Bias on the city total</th></tr></thead>
              <tbody>{Object.entries(fc.backtest.methods).map(([m, v]) => (
                <tr key={m} className={m === fc.method ? "row--chosen" : ""}>
                  <td><strong>{METHOD_NAME[m] ?? m}</strong>{m === fc.method && <> <span className="status status--pass">chosen</span></>}</td>
                  <td>{fmtNum(v.wape_pct, 1)}%</td><td>{fmtNum(v.city_mape_pct, 1)}%</td><td>{fmtNum(v.city_bias_pct, 1)}%</td></tr>))}</tbody>
            </table></div>
            <ul className="limits limits--plain">{fc.caveats.map(c => <li key={c}>{c}</li>)}</ul>
          </Section>

          {mapFields.length > 0 && field && (
            <Section>
              <h2 className="display display--sm">Where growth lands.</h2>
              <div className="tabs" role="tablist" aria-label="Forecast layer">
                {mapFields.map(f => <button key={f.key} role="tab" aria-selected={f.key === field.key} className={`tab ${f.key === field.key ? "is-on" : ""}`} onClick={() => setKey(f.key)}>{f.label}</button>)}
              </div>
              <p className="layer__about">{field.about}</p>
              <div className="mapbox"><MapStage cells={d.cells} field={field} theme={theme} camera={camera} extrude={false} interactive label={`Map of ${field.label}`} /></div>
              <div className="mapbox__legend"><Legend field={field} theme={theme} /></div>
            </Section>
          )}
        </>
      )}
    </>
  );
}
