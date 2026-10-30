import { useEffect, useMemo, useState } from "react";
import MapStage, { type Camera } from "../components/MapStage";
import Legend from "../components/Legend";
import ScenarioPanel from "../components/ScenarioPanel";
import { EvidenceBadge, Notice } from "../components/Bits";
import { ApiError, getJson } from "../lib/api";
import { useData } from "../lib/data";
import { useTheme } from "../lib/theme";
import { useViewport } from "../lib/hooks";
import { fmtInt, fmtNum } from "../lib/format";
import { availableComps, COMP_LABEL, COMPONENTS, normalise, toSites, withScores, type Weights } from "../lib/need";
import type { Cell, FieldDef, ModelReport, Site, SitesPayload } from "../lib/types";
import { translatePageText, useLanguage } from "../lib/i18n";

const TYPE_NAME = { pocket_park: "Pocket park", mini_forest: "Mini-forest" } as const;
const PRESET_NAME: Record<string, string> = { balanced: "Balanced", heat_first: "Heat first", access_first: "Access first", growth_aware: "Growth aware" };
const EQUAL: Weights = { heat: 25, people: 25, gap: 25, growth: 25 };

export default function Priority() {
  const d = useData();
  const [lang] = useLanguage();
  const [theme] = useTheme();
  const vp = useViewport();
  const [sites, setSites] = useState<Site[] | null>(null);
  const [rep, setRep] = useState<ModelReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [w, setW] = useState<Weights>(EQUAL);
  const [preset, setPreset] = useState<string>("balanced");
  const [type, setType] = useState<"all" | Site["type"]>("all");
  const [onlySites, setOnlySites] = useState(false);
  const [selId, setSelId] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(true);

  useEffect(() => {
    if (d.status !== "ready") return;
    getJson<SitesPayload>("/api/sites").then(p => setSites(toSites(p))).catch((e: unknown) => setErr(e instanceof ApiError && e.code === "baseline_not_built" ? "not_built" : "failed"));
    getJson<ModelReport>("/api/model-report").then(r => {
      setRep(r);
      const p = r.need?.presets?.balanced;
      if (p) setW(Object.fromEntries(COMPONENTS.map(c => [c, Math.round((p[c] ?? 0) * 100)])) as Weights);
    }).catch(() => setRep(null));
  }, [d.status]);

  const cells = d.status === "ready" ? d.cells : null;
  const fields = d.status === "ready" ? d.fields : null;
  const comps = useMemo(() => (fields ? availableComps(fields) : []), [fields]);
  const nw = useMemo(() => normalise(w, comps), [w, comps]);
  const scored = useMemo(() => (cells && comps.length ? withScores(cells, nw, comps) : null), [cells, comps, nw]);

  const siteHexes = useMemo(() => new Set((sites ?? []).filter(s => type === "all" || s.type === type).map(s => s.h3)), [sites, type]);
  const highlight = useMemo(() => (onlySites ? (c: Cell) => siteHexes.has(c.h3) : null), [onlySites, siteHexes]);

  const ranked = useMemo(() => {
    if (!sites || !scored) return [];
    return sites.filter(s => type === "all" || s.type === type)
      .map(s => ({ s, score: scored.byHex.get(s.h3) ?? null }))
      .filter((x): x is { s: Site; score: number } => x.score != null)
      .sort((a, b) => b.score - a.score).slice(0, 15);
  }, [sites, scored, type]);

  if (d.status === "loading") return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading…"} /></div>;
  if (d.status !== "ready") return <div className="fullstate"><Notice tone="warn" title="The baseline is not available.">Build the data first (README), then reload.</Notice></div>;
  if (!comps.length || !scored) return <div className="fullstate"><Notice tone="warn" title="The need score is not available.">The model step has not produced need components. Check the Data audit page and the model report, then rebuild.</Notice></div>;

  const needField: FieldDef = { key: "need_custom", label: "Need score", unit: "0 to 100", evidence: "MODELLED", group: "Need", decimals: 0, source: "EcoMetrix need score with your weights",
    ramp: "need", about: "Weighted average of percentile ranks.", domain: scored.domain, min: scored.domain[0], max: scored.domain[1], n: cells?.length ?? 0 };
  const selected = sites?.find(s => s.id === selId) ?? null;
  const pad = vp.mobile ? { top: 80, right: 12, bottom: Math.round(vp.h * 0.45), left: 12 } : { top: 92, right: selected ? 440 : 40, bottom: 40, left: 440 };
  const camera: Camera = { pitch: 0, bearing: 0, padding: pad, duration: 1400 };
  const presets = rep?.need?.presets ?? {};
  const stab = rep?.need?.stability;
  const pickPreset = (k: string) => { const p = presets[k]; if (!p) return; setPreset(k); setW(Object.fromEntries(COMPONENTS.map(c => [c, Math.round((p[c] ?? 0) * 100)])) as Weights); };

  return (
    <div className="explore">
      <div className="explore__map">
        <MapStage cells={scored.cells} field={needField} theme={theme} camera={camera} extrude={false} interactive highlight={highlight}
          selectedHex={selected?.h3 ?? null} label={`Map of need score across ${d.meta.city.name} hexagons`}
          onSelect={c => { if (!c || !sites) return; const here = sites.filter(s => s.h3 === c.h3 && (type === "all" || s.type === type)); if (here.length) setSelId(here[0].id); }} />
      </div>

      <aside className={`panel ${drawer ? "is-open" : ""}`} aria-label="Priority controls">
        <button className="panel__toggle" onClick={() => setDrawer(o => !o)} aria-expanded={drawer}>{drawer ? "Hide controls" : "Weights and sites"}</button>
        <div className="panel__body">
          <p className="kicker">{translatePageText(lang, "Where is the need?")} <EvidenceBadge kind="MODELLED" /></p>
          <p className="layer__about">Each hexagon&rsquo;s score is the weighted average of four percentile ranks. The weights are <strong>policy choices, not facts</strong>: pick a preset or set your own.</p>

          {Object.keys(presets).length > 0 && (
            <div className="presets" role="group" aria-label="Weight presets">
              {Object.keys(presets).map(k => <button key={k} className={`chip ${preset === k ? "is-on" : ""}`} onClick={() => pickPreset(k)}>{PRESET_NAME[k] ?? k}</button>)}
            </div>
          )}
          {COMPONENTS.map(c => comps.includes(c) && (
            <label key={c} className="slider">{COMP_LABEL[c]}: <strong>{fmtNum(nw[c] * 100, 0)}%</strong>
              <input type="range" min={0} max={100} step={5} value={w[c]} onChange={e => { setPreset("custom"); setW({ ...w, [c]: Number(e.target.value) }); }} /></label>
          ))}
          {COMPONENTS.filter(c => !comps.includes(c)).length > 0 && <p className="muted">Not available in this build: {COMPONENTS.filter(c => !comps.includes(c)).map(c => COMP_LABEL[c]).join(", ")}. Weights are renormalised over the rest.</p>}
          <Legend field={needField} theme={theme} />
          {stab?.status === "ok" && <p className="muted">How much do weights matter? <strong>{fmtNum(stab.no_regret_share_of_top_pct, 0)}%</strong> of the top-decile hexagons stay in the top decile under all four presets (&ldquo;no-regret&rdquo;).</p>}
          {rep?.need?.excluded && <p className="muted">{rep.need.excluded}</p>}

          <div className="filter">
            <p className="kicker">{translatePageText(lang, "Candidate sites")}</p>
            {err && <Notice tone="warn" title="No candidate sites">{err === "not_built" ? "The model step has not produced sites yet." : "Sites could not be loaded."}</Notice>}
            <div className="presets" role="group" aria-label="Intervention type">
              {(["all", "pocket_park", "mini_forest"] as const).map(k => <button key={k} className={`chip ${type === k ? "is-on" : ""}`} onClick={() => setType(k)}>{k === "all" ? "All" : TYPE_NAME[k]}</button>)}
            </div>
            <label className="switch"><input type="checkbox" checked={onlySites} onChange={e => setOnlySites(e.target.checked)} /><span>Dim hexagons with no candidate site</span></label>
            {!sites && !err && <p className="muted">Loading sites…</p>}
            {sites && <p className="muted">{fmtInt(sites.length)} candidate sites estimated from satellite land cover. Every one needs field verification.</p>}
            <ol className="sitelist">
              {ranked.map(({ s, score }, i) => (
                <li key={s.id}>
                  <button className={`site ${selId === s.id ? "is-on" : ""}`} onClick={() => setSelId(s.id)}>
                    <span className="site__rank">{i + 1}</span>
                    <span className="site__main"><strong>{TYPE_NAME[s.type]}</strong> · {fmtNum(s.area_ha, 1)} ha{s.noRegret && <span className="status status--pass"> no-regret</span>}</span>
                    <span className="site__score">{fmtNum(score, 0)}</span>
                  </button>
                </li>
              ))}
            </ol>
            {sites && ranked.length === 0 && <p className="muted">No scored sites for this filter.</p>}
          </div>
        </div>
      </aside>

      {selected && <ScenarioPanel key={selected.id} site={selected} onClose={() => setSelId(null)} />}
    </div>
  );
}
