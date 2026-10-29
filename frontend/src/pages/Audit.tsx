import { useEffect, useState } from "react";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { ApiError, getJson } from "../lib/api";
import { useData } from "../lib/data";
import { fmtDate } from "../lib/format";
import type { Audit, AuditCheck, ModelReport, Relationship } from "../lib/types";

const STATUS: Record<AuditCheck["status"], string> = { pass: "Pass", warn: "Check", fail: "Fail", manual: "Manual task" };

function Value({ v }: { v: unknown }) {
  if (v == null) return <span className="muted">n/a</span>;
  if (Array.isArray(v)) return <>{v.length ? v.map(x => (typeof x === "object" ? JSON.stringify(x) : String(x))).join("; ") : "none"}</>;
  if (typeof v === "object") {
    return <dl className="kv kv--nested">{Object.entries(v as Record<string, unknown>).map(([k, x]) => (<div key={k}><dt>{k.replace(/_/g, " ")}</dt><dd><Value v={x} /></dd></div>))}</dl>;
  }
  if (typeof v === "number") return <>{new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 }).format(v)}</>;
  return <>{String(v)}</>;
}

export default function AuditPage() {
  const d = useData();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [rel, setRel] = useState<Relationship | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mr, setMr] = useState<ModelReport | null>(null);

  useEffect(() => {
    if (d.status !== "ready" && d.status !== "not_built") return;
    getJson<Audit>("/api/audit").then(setAudit).catch((e: unknown) => setErr(e instanceof ApiError ? e.message : "Could not load the audit"));
    getJson<Relationship>("/api/relationship").then(setRel).catch(() => setRel(null));
    getJson<ModelReport>("/api/model-report").then(setMr).catch(() => setMr(null));
  }, [d.status]);

  const manifest = d.status === "ready" ? d.meta.manifest : d.status === "not_built" ? d.meta?.manifest : null;

  return (
    <>
      <PageHead kicker="Milestone M0 and M2 · Evidence" title="The data audit.">
        <p>Before building on a city, check it. Every result below was measured by the pipeline during its last build; none is typed in by hand. Where a check fails or cannot be automated, it says so.</p>
      </PageHead>

      {d.status === "loading" && <Section><Notice title={d.slow ? "Waking the server…" : "Loading…"} /></Section>}
      {d.status === "error" && <Section><Notice tone="error" title="The EcoMetrix API is not reachable.">{d.message}</Notice></Section>}
      {err && <Section><Notice tone="warn" title="Audit not available">{err}</Notice></Section>}

      {audit && (
        <Section>
          <h2 className="display display--sm">Pilot-city checks</h2>
          <p className="muted">Generated {fmtDate(audit.generated_at)}. Pass rules come from the project roadmap.</p>
          <div className="checks">
            {audit.checks.map(c => (
              <article key={c.id} className={`check check--${c.status}`}>
                <header><h3>{c.title}</h3><span className={`status status--${c.status}`}>{STATUS[c.status]}</span></header>
                <p className="check__rule"><strong>Rule:</strong> {c.rule}</p>
                {Object.keys(c.evidence).length > 0 && <dl className="kv">{Object.entries(c.evidence).map(([k, v]) => (<div key={k}><dt>{k.replace(/_/g, " ")}</dt><dd><Value v={v} /></dd></div>))}</dl>}
                {c.note && <p className="check__note">{c.note}</p>}
              </article>
            ))}
          </div>
        </Section>
      )}

      {manifest && (
        <Section>
          <h2 className="display display--sm">Layers in the baseline</h2>
          <p className="muted">Pipeline {manifest.pipeline_version} · built {fmtDate(manifest.generated_at)} · {manifest.n_cells} hexagons · study area {manifest.boundary.area_km2} km² ({manifest.boundary.source}{manifest.boundary.fallback ? ", fallback in use" : ""}).</p>
          <div className="tablewrap">
            <table className="table">
              <thead><tr><th>Layer</th><th>Label</th><th>Status</th><th>Vintage and detail</th><th>Licence</th></tr></thead>
              <tbody>
                {Object.entries(manifest.layers).map(([k, l]) => (
                  <tr key={k}>
                    <td><strong>{l.title ?? k}</strong>{l.source && <><br /><a href={l.source} target="_blank" rel="noreferrer">source</a></>}</td>
                    <td>{l.evidence ? <EvidenceBadge kind={l.evidence} /> : null}</td>
                    <td><span className={`status status--${l.status === "ok" ? "pass" : l.status === "failed" ? "fail" : "manual"}`}>{l.status === "ok" ? "Built" : l.status === "failed" ? "Failed" : "Skipped"}</span></td>
                    <td>{l.status === "failed" ? <span className="check__note">{l.reason}</span> : l.detail ? <Value v={l.detail} /> : <span className="muted">n/a</span>}</td>
                    <td>{l.license}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {mr?.built && (
        <Section>
          <h2 className="display display--sm">Model validation (milestones M4 and M5)</h2>
          <p className="muted">Each analytical module and whether it ran. A model is only used if it beats a simple baseline on held-out neighbourhoods.</p>
          <div className="tablewrap"><table className="table">
            <thead><tr><th>Module</th><th>Status</th><th>Detail</th></tr></thead>
            <tbody>{Object.entries(mr.modules).map(([k, m]) => (
              <tr key={k}><td><strong>{k.replace(/_/g, " ")}</strong></td>
                <td><span className={`status status--${m.status === "ok" ? "pass" : "fail"}`}>{m.status === "ok" ? "Ran" : "Failed"}</span></td>
                <td>{m.status === "ok" ? (m.count != null ? `${m.count} candidate sites ${m.by_type ? JSON.stringify(m.by_type) : ""}` : "") : <span className="check__note">{m.reason}</span>}</td></tr>))}</tbody>
          </table></div>
          {mr.heat_model?.status === "ok" && mr.heat_model.cv && (
            <div className="relcard">
              <h3>Heat–greenery model: spatial cross-validation</h3>
              <p>{mr.heat_model.cv.cells} hexagons, {mr.heat_model.cv.blocks} spatial blocks held out in {mr.heat_model.cv.folds} folds. Chosen: <strong>{mr.heat_model.chosen?.replace(/_/g, " ")}</strong>
                {mr.heat_model.gain_vs_linear_ndvi_pct != null && <> ({mr.heat_model.gain_vs_linear_ndvi_pct}% error change versus the NDVI-only line)</>}.
                {mr.heat_model.monotonic && <> More greenery never predicts hotter: <strong>{mr.heat_model.monotonic.ok ? "checked, holds" : "VIOLATED"}</strong>.</>}</p>
              <div className="tablewrap"><table className="table">
                <thead><tr><th>Model</th><th>Error RMSE (°C)</th><th>MAE (°C)</th><th>R²</th></tr></thead>
                <tbody>{Object.entries(mr.heat_model.cv.models).map(([k, v]) => (
                  <tr key={k} className={k === mr.heat_model?.chosen ? "row--chosen" : ""}><td><strong>{k.replace(/_/g, " ")}</strong>{k === mr.heat_model?.chosen && <> <span className="status status--pass">chosen</span></>}</td><td>{v.rmse_c}</td><td>{v.mae_c}</td><td>{v.r2}</td></tr>))}</tbody>
              </table></div>
              <p className="muted">{mr.heat_model.note}</p>
            </div>
          )}
          {mr.need?.stability?.status === "ok" && mr.need.stability.pairs && (
            <div className="relcard">
              <h3>Need score: do the rankings depend on the weights?</h3>
              <div className="tablewrap"><table className="table">
                <thead><tr><th>Preset pair</th><th>Spearman correlation</th><th>Top-decile overlap</th></tr></thead>
                <tbody>{mr.need.stability.pairs.map(p => <tr key={p.a + p.b}><td>{p.a.replace(/_/g, " ")} vs {p.b.replace(/_/g, " ")}</td><td>{p.spearman}</td><td>{p.top_decile_overlap_pct}%</td></tr>)}</tbody>
              </table></div>
            </div>
          )}
        </Section>
      )}

      {rel && (
        <Section>
          <h2 className="display display--sm">First look: greenness against surface temperature</h2>
          {rel.status !== "ok" ? <Notice title="Not available">{rel.reason}</Notice> : (
            <div className="relcard">
              <dl className="kv kv--big">
                <div><dt>Cells compared</dt><dd><Value v={rel.n_cells} /></dd></div>
                <div><dt>Pearson correlation</dt><dd><Value v={rel.pearson_r} /></dd></div>
                <div><dt>Change in surface °C per +0.1 NDVI</dt><dd><Value v={rel.slope_c_per_0p1_ndvi} /></dd></div>
                {rel.spatial_block_cv && <div><dt>Error vs. mean-only guess, held-out areas</dt><dd>{rel.spatial_block_cv.rmse_ndvi_model_c} vs {rel.spatial_block_cv.rmse_mean_only_c} °C</dd></div>}
              </dl>
              <p>{rel.interpretation} {rel.caveat} This simple line is the baseline that the machine-learning model in Milestone M4 must beat.</p>
            </div>
          )}
        </Section>
      )}
    </>
  );
}
