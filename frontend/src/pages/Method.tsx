import { useEffect, useState } from "react";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { getJson } from "../lib/api";
import { useData } from "../lib/data";

const LIMITS = [
  ["Surface temperature is not air temperature.", "Landsat sees the ground and rooftops at a mid-morning pass. It shows where heat builds, not what a person feels at 3 pm."],
  ["Population is modelled.", "WorldPop distributes census totals over the map using land features. It is a good guide to where people are, not a head-count."],
  ["Parks come from OpenStreetMap.", "Volunteers map parks. Some may be missing or mis-tagged, which can overstate the gap in access. Private and gated spaces tagged as such are excluded."],
  ["Access uses straight-line distance.", "The WHO recommendation is stated as linear distance. Walking routes (barriers, roads, rivers) will change the answer and are planned for later."],
  ["No land ownership data.", "A hexagon with little green is not proof that land is available to plant. Every site needs field verification."],
  ["The census is a 2019 snapshot.", "Trees have grown and been felled since. Ward boundaries in the census are the pre-2017 ones, so EcoMetrix counts on a regular hexagon grid instead."],
  ["Candidate sites are estimates, not parcels.", "A site is the open land (bare, grass and shrub cover, minus mapped parks and forest) inside one hexagon. Ownership, legality, soil and access are unknown, so every site needs field verification."],
  ["The forecast projects a modelled series.", "WorldPop's yearly history is itself a model, and the uncertainty band is the range of errors seen when testing on past years, not a statistical interval. Policy changes are not modelled."],
  ["Costs and carbon are sourced ranges, not Pune rate schedules.", "Mini-forest costs come from Delhi-region quotes and press estimates; park costs from PMC's average garden spending. Carbon comes from three measured South Indian forests; no pocket-park carbon is estimated. Every value and its source is on this page below."],
  ["Heat response is an association.", "The heat model learns how surface temperature varies with greenness across Pune today. It does not prove that planting a given site will cool it by that amount, and cooling appears as the planting matures."],
  ["Dry-season greenness.", "Pre-monsoon NDVI is low for grass and crops by design. It is chosen so that greenness and heat are measured in the same season."]
];

const NEXT = [
  ["M6", "Budget-constrained portfolio optimiser (avoids double-counting people reached by neighbouring sites); uncertainty on the need score."],
  ["M7", "Side-by-side scenario comparison against doing nothing, evidence cards per site, PDF report, citizen view."],
  ["M8–M9", "Usability testing with planners and residents, full evaluation report, freeze."],
  ["Later", "Street-tree corridors and green roofs (need road-side tree and rooftop data), walking-network distance, a census anchor for population, a municipal park list and rate schedule."]
];

type Row = { path: string; low?: number; base?: number; high?: number; value?: unknown; unit?: string; label?: string; source?: string; note?: string };
function flatten(o: Record<string, unknown>, path = ""): Row[] {
  const out: Row[] = [];
  for (const [k, v] of Object.entries(o)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const e = v as Record<string, unknown>;
      if ("source" in e || "low" in e || "value" in e || "points" in e) out.push({ path: path + k, low: e.low as number, base: e.base as number, high: e.high as number,
        value: e.value ?? (e.points ? JSON.stringify(e.points) : e.estimated === false ? "not estimated" : undefined), unit: e.unit as string, label: e.label as string, source: e.source as string, note: e.note as string });
      else out.push(...flatten(e, path + k + "."));
    }
  }
  return out;
}

export default function Method() {
  const [assump, setAssump] = useState<Row[] | null>(null);
  useEffect(() => { getJson<Record<string, unknown>>("/api/assumptions").then(a => setAssump(flatten(a))).catch(() => setAssump(null)); }, []);
  const d = useData();
  const meta = d.status === "ready" ? d.meta : d.status === "not_built" ? d.meta : null;
  const fields = meta?.fields ?? [];
  return (
    <>
      <PageHead kicker="Method and limits" title="How the baseline is made, and what it cannot tell you.">
        <p>EcoMetrix is deliberately plain about its method. Each layer has a source, a label and a known weakness, and all of them are written down here.</p>
      </PageHead>

      <Section>
        <h2 className="display display--sm">Evidence labels</h2>
        {meta ? <div className="labelgrid">{(Object.entries(meta.evidence_labels) as [never, string][]).map(([k, v]) => <div key={k} className="labelcard"><EvidenceBadge kind={k} /><p>{v}</p></div>)}</div>
          : <Notice title="Loading definitions…" />}
      </Section>

      <Section>
        <h2 className="display display--sm">What each layer means</h2>
        {fields.length ? (
          <div className="tablewrap"><table className="table">
            <thead><tr><th>Layer</th><th>Label</th><th>Meaning</th><th>Source</th></tr></thead>
            <tbody>{fields.map(f => <tr key={f.key}><td><strong>{f.label}</strong><br /><span className="muted">{f.unit}</span></td><td><EvidenceBadge kind={f.evidence} /></td><td>{f.about}</td><td>{f.source}</td></tr>)}</tbody>
          </table></div>
        ) : <Notice tone="warn" title="No layers loaded">Layer definitions appear once the baseline has been built.</Notice>}
      </Section>

      <Section>
        <h2 className="display display--sm">The access rule</h2>
        <p className="lede">Park access follows the WHO Regional Office for Europe&rsquo;s recommendation: a green space of at least 0.5 hectares within 300 metres (straight line) of every home. It comes from a European evidence review, so treat it as a transparent yardstick rather than an Indian statutory standard. The two numbers are set in <code>config/pilot_pune.yaml</code> and can be changed.</p>
      </Section>

      <Section>
        <h2 className="display display--sm">Known limits</h2>
        <ol className="limits">{LIMITS.map(([h, t]) => <li key={h}><strong>{h}</strong> {t}</li>)}</ol>
      </Section>

      <Section>
        <h2 className="display display--sm">Assumptions register</h2>
        <p className="lede">Every number that is not measured, with a range and a source. These feed the cost and carbon in the scenario runner. Values with no direct source are marked as judgement in their note.</p>
        {assump ? (
          <div className="tablewrap"><table className="table">
            <thead><tr><th>Parameter</th><th>Low / base / high</th><th>Label</th><th>Source and note</th></tr></thead>
            <tbody>{assump.map(r => (
              <tr key={r.path}>
                <td><strong>{r.path}</strong>{r.unit && <><br /><span className="muted">{r.unit}</span></>}</td>
                <td>{r.low != null ? `${r.low} / ${r.base} / ${r.high}` : String(r.value ?? "n/a")}</td>
                <td>{r.label === "ASSUMED" ? <EvidenceBadge kind="ASSUMED" /> : <span className="muted">{r.label ?? ""}</span>}</td>
                <td>{r.source}{r.note && <><br /><span className="muted">{r.note}</span></>}</td>
              </tr>))}</tbody>
          </table></div>
        ) : <Notice title="Assumptions not loaded">They appear when the API is reachable.</Notice>}
      </Section>

      <Section>
        <h2 className="display display--sm">What is not built yet</h2>
        <p className="lede">This release covers milestones M0 to M5: baseline, heat model, cost and impact engine, demand forecast, need score, candidate sites and a single-site scenario. Nothing below exists yet.</p>
        <div className="tablewrap"><table className="table"><thead><tr><th>Milestone</th><th>Planned</th></tr></thead><tbody>{NEXT.map(([m, t]) => <tr key={m}><td><strong>{m}</strong></td><td>{t}</td></tr>)}</tbody></table></div>
      </Section>
    </>
  );
}
