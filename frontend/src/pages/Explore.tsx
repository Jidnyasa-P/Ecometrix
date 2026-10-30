import { useMemo, useState } from "react";
import MapStage, { type Camera } from "../components/MapStage";
import Legend from "../components/Legend";
import CellCard from "../components/CellCard";
import { EvidenceBadge, Notice } from "../components/Bits";
import { useData } from "../lib/data";
import { useTheme } from "../lib/theme";
import { useViewport } from "../lib/hooks";
import { fmtInt, fmtNum } from "../lib/format";
import type { Cell, FieldDef } from "../lib/types";
import { translatePageText, useLanguage } from "../lib/i18n";

export default function Explore() {
  const d = useData();
  const [lang] = useLanguage();
  const [theme] = useTheme();
  const vp = useViewport();
  const [key, setKey] = useState<string | null>(null);
  const [extrude, setExtrude] = useState(false);
  const [sel, setSel] = useState<Cell | null>(null);
  const [hover, setHover] = useState<{ c: Cell; x: number; y: number } | null>(null);
  const [filterOn, setFilterOn] = useState(false);
  const [hotPct, setHotPct] = useState(75);
  const [accessMax, setAccessMax] = useState(50);
  const [drawer, setDrawer] = useState(true);

  const ready = d.status === "ready" ? d : null;
  const cells = ready?.cells;
  const fields = ready?.fields;
  const canFilter = !!fields && "lst_c" in fields && "access_share" in fields;

  const hotThreshold = useMemo(() => {
    if (!cells || !canFilter) return null;
    const v = cells.map(c => c.v.lst_c).filter((x): x is number => x != null).sort((a, b) => a - b);
    return v.length ? v[Math.min(v.length - 1, Math.round((hotPct / 100) * (v.length - 1)))] : null;
  }, [cells, canFilter, hotPct]);

  const test = useMemo(() => (filterOn && hotThreshold != null
    ? (c: Cell) => (c.v.lst_c ?? -1) >= hotThreshold && (c.v.access_share ?? 101) < accessMax : null), [filterOn, hotThreshold, accessMax]);

  const result = useMemo(() => {
    if (!test || !cells) return null;
    const hit = cells.filter(test);
    return { n: hit.length, pop: hit.reduce((s, c) => s + (c.v.pop ?? 0), 0), area: hit.reduce((s, c) => s + c.area_km2, 0) };
  }, [test, cells]);

  if (d.status === "loading") return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading layers…"}>{d.slow ? "Free hosting sleeps when idle and takes about a minute to wake." : "Fetching measured layers."}</Notice></div>;
  if (d.status === "not_built") return <div className="fullstate"><Notice tone="warn" title="The baseline has not been built yet.">Run the data pipeline and redeploy. No placeholder data is shown.</Notice></div>;
  if (d.status === "error") return <div className="fullstate"><Notice tone="error" title="The EcoMetrix API is not reachable.">{d.message}</Notice></div>;

  const list = Object.values(d.fields);
  if (!list.length) return <div className="fullstate"><Notice tone="warn" title="No layers were built.">Every layer failed in the last pipeline run. See the Data audit page for the reasons.</Notice></div>;
  const field: FieldDef = d.fields[key ?? ""] ?? d.fields["tree_density_ha"] ?? list[0];
  const groups = [...new Set(list.map(f => f.group))];
  const pad = vp.mobile ? { top: 80, right: 12, bottom: Math.round(vp.h * 0.42), left: 12 } : { top: 92, right: sel ? 380 : 40, bottom: 40, left: 420 };
  const camera: Camera = { pitch: extrude ? 45 : 0, bearing: extrude ? -18 : 0, padding: pad, duration: 1400 };

  return (
    <div className="explore">
      <div className="explore__map">
        <MapStage cells={d.cells} field={field} theme={theme} camera={camera} extrude={extrude} interactive highlight={test}
          selectedHex={sel?.h3 ?? null} onHover={(c, x, y) => setHover(c ? { c, x, y } : null)} onSelect={c => setSel(c)}
          label={`Interactive map of ${d.meta.city.name} hexagons coloured by ${field.label}`} />
        {hover && !vp.mobile && (
          <div className="tip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
            <strong>{hover.c.v[field.key] == null ? "no data" : `${fmtNum(hover.c.v[field.key], field.decimals > 1 ? 2 : field.decimals)} ${field.unit}`}</strong>
            <span>{field.label}</span>
          </div>
        )}
      </div>

      <aside className={`panel ${drawer ? "is-open" : ""}`} aria-label="Map controls">
        <button className="panel__toggle" onClick={() => setDrawer(o => !o)} aria-expanded={drawer}>{drawer ? "Hide controls" : "Layers and filters"}</button>
        <div className="panel__body">
          <p className="kicker">{translatePageText(lang, "Layer")}</p>
          {groups.map(g => (
            <fieldset key={g} className="layers">
              <legend>{g}</legend>
              {list.filter(f => f.group === g).map(f => (
                <label key={f.key} className={`layer ${f.key === field.key ? "is-on" : ""}`}>
                  <input type="radio" name="layer" checked={f.key === field.key} onChange={() => setKey(f.key)} />
                  <span className="layer__name">{f.label}</span>
                  <EvidenceBadge kind={f.evidence} />
                </label>
              ))}
            </fieldset>
          ))}
          <p className="layer__about">{field.about} <span className="muted">Source: {field.source}.</span></p>
          <Legend field={field} theme={theme} />

          <label className="switch"><input type="checkbox" checked={extrude} onChange={e => setExtrude(e.target.checked)} /><span>3D columns (height follows the value)</span></label>

          {canFilter && (
            <div className="filter">
              <label className="switch"><input type="checkbox" checked={filterOn} onChange={e => setFilterOn(e.target.checked)} /><span>Exploratory filter: heat without green</span></label>
              {filterOn && (
                <>
                  <label className="slider">Hotter than <strong>{hotPct}%</strong> of hexagons{hotThreshold != null && <> (≥ {fmtNum(hotThreshold, 1)}°C)</>}
                    <input type="range" min={50} max={95} step={5} value={hotPct} onChange={e => setHotPct(Number(e.target.value))} /></label>
                  <label className="slider">Park access below <strong>{accessMax}%</strong> of residents
                    <input type="range" min={10} max={90} step={10} value={accessMax} onChange={e => setAccessMax(Number(e.target.value))} /></label>
                  {result && <p className="filter__result"><strong>{fmtInt(result.n)}</strong> hexagons · <strong>{fmtInt(result.pop)}</strong> people (modelled) · {fmtNum(result.area, 1)} km²</p>}
                  <p className="muted">A way to look, not a ranking. Thresholds are yours to set; no policy standard is implied.</p>
                </>
              )}
            </div>
          )}
        </div>
      </aside>

      {sel && <CellCard cell={sel} fields={list} onClose={() => setSel(null)} />}
    </div>
  );
}
