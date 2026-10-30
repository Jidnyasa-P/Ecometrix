import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import MapStage, { type Camera } from "../components/MapStage";
import { Arrow, EvidenceBadge, Notice, Section } from "../components/Bits";
import { useData } from "../lib/data";
import { useCountUp, useSeen, useViewport } from "../lib/hooks";
import { fmtIndianShort, fmtInt, fmtNum } from "../lib/format";
import type { Cell, FieldDef, Summary } from "../lib/types";

interface Step {
  id: string; kicker: string; title: string; body: ReactNode; field: string; extrude: boolean; pitch: number; bearing: number;
  drift?: boolean; highlight?: ((c: Cell) => boolean) | null; fieldNote?: ReactNode;
}

function percentile(values: number[], p: number) {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.round((p / 100) * (s.length - 1))))];
}

function buildSteps(summary: Summary | null, cells: Cell[], fields: Record<string, FieldDef>): Step[] {
  const steps: Step[] = [];
  const has = (k: string) => k in fields;
  if (has("tree_density_ha") && summary?.trees_total != null) {
    steps.push({
      id: "trees", kicker: "01 · Trees", title: "The trees we can actually count.", field: "tree_density_ha", extrude: true, pitch: 62, bearing: 28,
      body: <>
        <p>Pune counted its trees in 2019 and published every one with a location. Placed into hexagons of about 10 hectares, the census gives <strong>{fmtNum(summary.trees_per_ha, 1)} trees per hectare</strong> across the study area.</p>
        {summary.cells_without_trees_pct != null && <p><strong>{fmtNum(summary.cells_without_trees_pct, 0)}%</strong> of hexagons hold no counted tree at all. Column height shows where trees are dense.</p>}
      </>
    });
  }
  if (has("lst_c") && summary?.lst_c_median != null) {
    steps.push({
      id: "heat", kicker: "02 · Heat", title: "Where the ground runs hottest.", field: "lst_c", extrude: true, pitch: 48, bearing: -32,
      body: <>
        <p>On pre-monsoon mornings the median hexagon&rsquo;s surface reads <strong>{fmtNum(summary.lst_c_median, 1)}°C</strong>. The hottest tenth starts at <strong>{fmtNum(summary.lst_p90_threshold_c ?? summary.lst_c_p90, 1)}°C</strong>{summary.pop_in_hottest_decile_cells != null && <>, and about <strong>{fmtIndianShort(summary.pop_in_hottest_decile_cells)} people</strong> live in those cells (modelled)</>}.</p>
        <p className="step__caveat">This is surface temperature from a satellite pass, not the air temperature you feel. It shows where heat builds up.</p>
      </>
    });
  }
  if (has("access_share") && summary?.pop_without_park_access_pct != null) {
    steps.push({
      id: "access", kicker: "03 · Parks", title: "Who can walk to a park.", field: "access_share", extrude: false, pitch: 8, bearing: 0,
      body: <>
        <p>The WHO recommends at least 0.5 hectares of green space within 300 metres of home. Using mapped parks and modelled population, <strong>{fmtNum(summary.pop_without_park_access_pct, 0)}% of residents</strong> fall outside that reach.</p>
        <p className="step__caveat">OpenStreetMap can miss parks, so this may overstate the gap. Compare with the municipality&rsquo;s own park list before acting on it.</p>
      </>
    });
  }
  if (has("lst_c") && has("access_share") && has("pop")) {
    const lst = cells.map(c => c.v.lst_c).filter((x): x is number => x != null);
    const hot = percentile(lst, 75);
    if (hot != null) {
      const test = (c: Cell) => (c.v.lst_c ?? -1) >= hot && (c.v.access_share ?? 101) < 50;
      const hit = cells.filter(test);
      const people = hit.reduce((s, c) => s + (c.v.pop ?? 0), 0);
      steps.push({
        id: "overlap", kicker: "04 · Overlap", title: "Where heat meets no green.", field: "lst_c", extrude: true, pitch: 40, bearing: 12, highlight: test,
        body: <>
          <p>Highlighted: <strong>{fmtInt(hit.length)} hexagons</strong> in the hottest quarter (surface at or above {fmtNum(hot, 1)}°C) where fewer than half of residents live within reach of a park. About <strong>{fmtIndianShort(people)} people</strong> live there (modelled).</p>
          <p className="step__caveat">An exploratory filter, not a recommendation. The proper need score arrives in the next milestone.</p>
        </>
      });
    }
  }
  steps.push({
    id: "next", kicker: "05 · Next", title: "From a baseline to a decision.", field: has("tree_density_ha") ? "tree_density_ha" : Object.keys(fields)[0], extrude: true, pitch: 52, bearing: -12, drift: true,
    body: <>
      <p>Everything above is what is on the ground today. The next screens project where the city is heading, score where green space is needed most, choose the best set of sites for a budget with an exact optimiser, and compare plans against doing nothing.</p>
      <p className="step__caveat">Every plan is a simulation, labelled as such. Costs and carbon are sourced ranges, nothing has been built, and no payback is claimed.</p>
      <div className="step__cta"><Link className="btn btn--solid" to="/plan">Best plan under a budget <Arrow /></Link><Link className="btn btn--ghost" to="/priority">Where is the need?</Link></div>
    </>
  });
  return steps;
}

function HeroStat({ value, label, kind, fmt, active }: { value: number | null | undefined; label: string; kind: "MEASURED" | "MODELLED"; fmt: (n: number) => string; active: boolean }) {
  const v = useCountUp(value, active);
  if (value == null) return null;
  return (
    <div className="herostat">
      <div className="herostat__num">{v == null ? "n/a" : fmt(v)}</div>
      <div className="herostat__label">{label} <EvidenceBadge kind={kind} /></div>
    </div>
  );
}

export default function Atlas() {
  const d = useData();
  const vp = useViewport();
  const [active, setActive] = useState(-1);
  const [statsRef, statsSeen] = useSeen<HTMLDivElement>();
  const stepEls = useRef<(HTMLElement | null)[]>([]);
  const heroEl = useRef<HTMLElement | null>(null);

  const ready = d.status === "ready" ? d : null;
  const steps = useMemo(() => (ready ? buildSteps(ready.summary, ready.cells, ready.fields) : []), [ready]);

  useEffect(() => {
    if (!steps.length || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(entries => {
      for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.i));
    }, { rootMargin: "-45% 0px -45% 0px" });
    stepEls.current.forEach(el => el && io.observe(el));
    if (heroEl.current) io.observe(heroEl.current);
    return () => io.disconnect();
  }, [steps.length]);

  if (d.status === "loading") {
    return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading Pune’s baseline…"}>
      {d.slow ? "The free hosting tier sleeps after 15 minutes of inactivity and takes about a minute to wake. The data is real; it just needs a moment." : "Fetching measured layers."}
    </Notice></div>;
  }
  if (d.status === "not_built") {
    return <div className="fullstate"><Notice tone="warn" title="The baseline has not been built yet.">
      The API is running but there is no pipeline output to serve. Run the data pipeline (README, “Build the data”) and redeploy. No placeholder data is shown.
    </Notice></div>;
  }
  if (d.status === "error") {
    return <div className="fullstate"><Notice tone="error" title="The EcoMetrix API is not reachable.">{d.message} Check the API address in the deployment settings.</Notice></div>;
  }

  const { cells, fields, summary, meta } = d;
  const first = Object.keys(fields).includes("tree_density_ha") ? "tree_density_ha" : Object.keys(fields)[0];
  const heroStep: Step = { id: "hero", kicker: "", title: "", body: null, field: first, extrude: true, pitch: 58, bearing: -20, drift: true };
  const cur = active < 0 ? heroStep : steps[Math.min(active, steps.length - 1)];
  const field = fields[cur.field] ?? Object.values(fields)[0];
  const pad = vp.mobile
    ? { top: 84, right: 12, bottom: Math.round(vp.h * 0.5), left: 12 }
    : { top: 96, right: 40, bottom: 48, left: Math.min(680, Math.round(vp.w * 0.46)) };
  const camera: Camera = { pitch: cur.pitch, bearing: cur.bearing, padding: pad, duration: 2600 };

  return (
    <>
      <div className="story">
        <div className="story__map" aria-hidden={false}>
          <MapStage cells={cells} field={field} theme="dark" camera={camera} extrude={cur.extrude} drift={!!cur.drift}
            highlight={cur.highlight ?? null} label={`3D map of Pune hexagons coloured by ${field.label}`} />
          <div className="story__scrim" />
          <div className="story__layerchip" aria-live="polite"><span>Showing</span> <strong>{field.label}</strong> <EvidenceBadge kind={field.evidence} /></div>
        </div>

        <div className="story__steps">
          <section className="step step--hero" data-i={-1} ref={el => { heroEl.current = el; }}>
            <div className="hero">
              <p className="pillnote"><span className="dot" /> Baseline built from open data · {meta.manifest?.city ?? "Pune"} pilot</p>
              <h1 className="hero__title">
                <span className="line"><span style={{ ["--i" as string]: 0 }}>Where does</span></span>
                <span className="line"><span style={{ ["--i" as string]: 1 }}>Pune need <em>green</em></span></span>
                <span className="line"><span style={{ ["--i" as string]: 2 }}>most?</span></span>
              </h1>
              <p className="hero__lede">EcoMetrix measures trees, surface heat and park access across the whole city, one neighbourhood-sized hexagon at a time. It is the evidence base for deciding where the next rupee of greening should go.</p>
              <div className="hero__cta">
                <Link className="btn btn--accent" to="/explore">Explore the map <Arrow /></Link>
                <Link className="btn btn--ghost-dark" to="/audit">See the data audit</Link>
              </div>
              <div className="herostats" ref={statsRef}>
                <HeroStat value={summary?.trees_total} label="trees counted" kind="MEASURED" fmt={n => fmtInt(n)} active={statsSeen} />
                <HeroStat value={summary?.pop_without_park_access_pct} label="of residents beyond 300 m of a park" kind="MODELLED" fmt={n => `${fmtNum(n, 0)}%`} active={statsSeen} />
                <HeroStat value={summary?.lst_p90_threshold_c} label="°C: where the hottest tenth begins" kind="MEASURED" fmt={n => fmtNum(n, 1)} active={statsSeen} />
              </div>
              <p className="scrollcue" aria-hidden="true">Scroll to read the city <span>↓</span></p>
            </div>
          </section>

          {steps.map((s, i) => (
            <section key={s.id} className={`step ${i % 2 && !vp.mobile ? "step--right" : ""}`} data-i={i} ref={el => { stepEls.current[i] = el; }}>
              <article className={`stepcard ${active === i ? "is-active" : ""}`}>
                <p className="kicker">{s.kicker}</p>
                <h2 className="stepcard__title">{s.title}</h2>
                <div className="stepcard__body">{s.body}</div>
                <p className="stepcard__src"><EvidenceBadge kind={fields[s.field]?.evidence ?? "MEASURED"} /> {fields[s.field]?.source}</p>
              </article>
            </section>
          ))}
        </div>
      </div>

      <Section className="section--labels">
        <p className="kicker">How we stay honest</p>
        <h2 className="display display--sm">Every number wears a label.</h2>
        <p className="lede">Cities decide better when they can tell what was counted from what was estimated. Each value in EcoMetrix is tagged, and the tag never gets dropped on the way to a chart.</p>
        <div className="labelgrid">
          {(Object.entries(meta.evidence_labels) as [FieldDef["evidence"], string][]).map(([k, v]) => (
            <div key={k} className="labelcard"><EvidenceBadge kind={k} /><p>{v}</p></div>
          ))}
        </div>
      </Section>

      <Section className="section--sources">
        <p className="kicker">Built on open data</p>
        <h2 className="display display--sm">No paid data. No placeholders.</h2>
        <ul className="sourcelist">
          {meta.sources.map(s => (
            <li key={s.name}><a href={s.url} target="_blank" rel="noreferrer"><strong>{s.name}</strong><span>{s.publisher}</span><em>{s.license}</em></a></li>
          ))}
        </ul>
      </Section>
    </>
  );
}
