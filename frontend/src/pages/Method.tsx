import { useEffect, useState } from "react";
import { EvidenceBadge, Notice, PageHead, Section } from "../components/Bits";
import { getJson } from "../lib/api";
import { flattenAssumptions, type AssumptionRow } from "../lib/assumptions";
import { useData } from "../lib/data";

const LIMITS = [
  ["Surface temperature is not air temperature.", "Landsat sees the ground and rooftops at a mid-morning pass. It shows where heat builds, not what a person feels at 3 pm."],
  ["Population is modelled.", "WorldPop distributes census totals over the map using land features. The current baseline is the 2020 constrained product, while the yearly history ends in 2020. It is a guide to where people are, not a current head-count."],
  ["WorldCover is a historical reference.", "The ESA WorldCover product used here has 2020 and 2021 editions. It is a static land-cover classification, not a live or annual current-year layer. The loaded edition is recorded in the data audit."],
  ["Parks come from OpenStreetMap.", "Volunteers map parks. Some may be missing or mis-tagged, which can overstate the gap in access. Private and gated spaces tagged as such are excluded."],
  ["Access uses straight-line distance.", "The WHO recommendation is stated as linear distance. Walking routes (barriers, roads, rivers) will change the answer and are planned for later."],
  ["No land ownership data.", "A hexagon with little green is not proof that land is available to plant. Every site needs field verification."],
  ["The census is a 2019 snapshot.", "Trees have grown and been felled since. Ward boundaries in the census are the pre-2017 ones, so EcoMetrix counts on a regular hexagon grid instead."],
  ["Candidate sites are estimates, not parcels.", "A site is the open land (bare, grass and shrub cover, minus mapped parks and forest) inside one hexagon. Ownership, legality, soil and access are unknown, so every site needs field verification."],
  ["The forecast projects a modelled series.", "WorldPop's yearly history is itself a model, and the uncertainty band is the range of errors seen when testing on past years, not a statistical interval. Policy changes are not modelled."],
  ["Costs and carbon are sourced ranges, not Pune rate schedules.", "Mini-forest costs come from Delhi-region quotes and press estimates; park costs from PMC's average garden spending. Carbon comes from three measured South Indian forests; no pocket-park carbon is estimated. Every value and its source is on this page below."],
  ["Heat response is an association.", "The heat model learns how surface temperature varies with greenness across Pune today. It does not prove that planting a given site will cool it by that amount, and cooling appears as the planting matures."],
  ["Dry-season greenness.", "Pre-monsoon NDVI is low for grass and crops by design. It is chosen so that greenness and heat are measured in the same season. The separate latest NDVI layer is not used to retrain the heat model."],
  ["Latest satellite layers are near-real-time, not live.", "Landsat surface temperature and Sentinel-2 NDVI are queried from the public satellite catalogue over a rolling 180-day window during each daily data build. In Explore, select the 'Latest observations' group to view these separate rolling composites. The audit shows the newest acquisition date, age and percentage of study-area cells with valid pixels. Cloud cover, revisit schedules and catalogue publication delays can leave gaps. Historical tree census, population and WorldCover layers retain their original vintage and are not presented as live data."]
];

const NEXT = [
  ["Human checks", "Five-person usability test, independent spreadsheet recomputation of one site, 30-site satellite spot-check, expert review of 20 sites, fluent-speaker review of the Marathi text, and a comparison of OpenStreetMap parks with the municipality's own list. Protocols are in docs/evaluation."],
  ["Data to add", "A Pune rate schedule for new parks and plantations, a census anchor for population, a vulnerability layer (age, income, health), walking-network distance for access."],
  ["More interventions", "Street-tree corridors (need road-side tree counts) and green or cool roofs (need rooftop areas and a cost source)."],
  ["Real-world evidence", "Before and after satellite greenness and surface temperature for anything that gets built, tree-survival surveys and resident feedback."]
];

export default function Method() {
  const [assump, setAssump] = useState<AssumptionRow[] | null>(null);
  useEffect(() => { getJson<Record<string, unknown>>("/api/assumptions").then(a => setAssump(flattenAssumptions(a))).catch(() => setAssump(null)); }, []);
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
        <h2 className="display display--sm">What is still open</h2>
        <p className="lede">This release covers all ten weeks of the build: baseline, heat model, cost and impact engine, forecast, need score, candidate sites, the portfolio optimiser, plan comparison, evidence cards, report, citizen view and evaluation. What follows is what still needs people, data or a real project.</p>
        <div className="tablewrap"><table className="table"><thead><tr><th>Milestone</th><th>Planned</th></tr></thead><tbody>{NEXT.map(([m, t]) => <tr key={m}><td><strong>{m}</strong></td><td>{t}</td></tr>)}</tbody></table></div>
      </Section>
    </>
  );
}
