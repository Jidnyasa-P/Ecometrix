import { useEffect, useMemo, useState } from "react";
import { cityPath } from "../lib/city";
import { Link } from "react-router-dom";
import MapStage, { type Camera } from "../components/MapStage";
import { Notice } from "../components/Bits";
import { getJson } from "../lib/api";
import { useData } from "../lib/data";
import { useViewport } from "../lib/hooks";
import { LANG_NAME, t, useLanguage, type Lang } from "../lib/i18n";
import { fmtNum } from "../lib/format";
import { find, usePortfolios } from "../lib/portfolio";
import { toSites } from "../lib/need";
import { useTheme } from "../lib/theme";
import type { Cell, SitesPayload } from "../lib/types";

export default function City() {
  const d = useData();
  const [theme] = useTheme();
  const vp = useViewport();
  const pf = usePortfolios(d.status === "ready" && d.meta.city.finance_enabled === true);
  const [lang, setLang] = useLanguage();
  const [sel, setSel] = useState<Cell | null>(null);
  const [candidateHexes, setCandidates] = useState<Set<string> | null>(null);
  const feedback = import.meta.env.VITE_FEEDBACK_URL as string | undefined;

  useEffect(() => {
    if (d.status !== "ready") return;
    getJson<SitesPayload>("/api/sites").then(p => setCandidates(new Set(toSites(p).map(s => s.h3)))).catch(() => setCandidates(null));
  }, [d.status]);

  const cells = d.status === "ready" ? d.cells : null;
  const plan = useMemo(() => (pf.status === "ready" ? find(pf.data, pf.data.presets.balanced ? "balanced" : Object.keys(pf.data.presets)[0], Math.floor((pf.data.budgets_inr.length - 1) / 2), 0) : null), [pf]);
  const planMap = useMemo(() => new Map((plan?.sites ?? []).map(s => [s.h3, s.type])), [plan]);
  const stats = useMemo(() => {
    if (!cells) return null;
    const trees = cells.map(c => c.v.tree_density_ha).filter((x): x is number => x != null);
    const lst = cells.map(c => c.v.lst_c).filter((x): x is number => x != null).sort((a, b) => a - b);
    return { avgTrees: trees.length ? trees.reduce((s, x) => s + x, 0) / trees.length : null, lst };
  }, [cells]);

  if (d.status === "loading") return <div className="fullstate"><Notice title={d.slow ? "Waking the server…" : "Loading…"} /></div>;
  if (d.status !== "ready" || !cells || !stats) return <div className="fullstate"><Notice tone="warn" title="The baseline is not available.">Build the data first.</Notice></div>;

  const field = d.fields["lst_c"] ?? Object.values(d.fields)[0];
  const pad = vp.mobile ? { top: 80, right: 12, bottom: Math.round(vp.h * 0.5), left: 12 } : { top: 92, right: 40, bottom: 40, left: 540 };
  const camera: Camera = { pitch: 0, bearing: 0, padding: pad, duration: 1200 };

  const lines: string[] = [];
  if (sel) {
    const v = sel.v;
    lines.push(v.tree_density_ha != null ? t(lang, "trees", { n: fmtNum(v.tree_density_ha, 0), avg: stats.avgTrees != null ? fmtNum(stats.avgTrees, 0) : "n/a" }) : t(lang, "noTrees"));
    if (v.lst_c != null && stats.lst.length) {
      const below = stats.lst.filter(x => x < (v.lst_c as number)).length;
      lines.push(t(lang, "heat", { p: fmtNum((100 * below) / stats.lst.length, 0) }));
    } else lines.push(t(lang, "noHeat"));
    lines.push(v.access_share != null ? t(lang, "parkYes", { p: fmtNum(v.access_share, 0), dist: fmtNum(d.meta.city.access?.distance_m ?? 300, 0), area: fmtNum(d.meta.city.access?.min_area_ha ?? 0.5, 1) }) : t(lang, "noPark"));
    const type = planMap.get(sel.h3);
    if (!plan) lines.push(t(lang, "planUnknown"));
    else if (type) lines.push(t(lang, "planYes", { type: t(lang, type) }));
    else if (candidateHexes && !candidateHexes.has(sel.h3)) lines.push(t(lang, "planNoOpen"));
    else lines.push(t(lang, "planNo"));
  }

  return (
    <div className="explore citizen" lang={lang}>
      <div className="explore__map">
        <MapStage cells={cells} field={field} theme={theme} camera={camera} extrude={false} interactive marked={plan?.sites.map(s => s.h3) ?? null}
          selectedHex={sel?.h3 ?? null} onSelect={c => setSel(c)} label={lang === "mr" ? "शहराचा नकाशा" : lang === "el" ? "Χάρτης της πόλης" : `Map of ${d.meta.city.name}`} />
      </div>
      <section className="panel is-open citizen__panel" aria-label={t(lang, "title")}>
        <div className="panel__body">
          <div className="langswitch" role="group" aria-label="Language">
            {(Object.keys(LANG_NAME) as Lang[]).map(l => <button key={l} className={`chip ${lang === l ? "is-on" : ""}`} lang={l} onClick={() => setLang(l)} aria-pressed={lang === l}>{LANG_NAME[l]}</button>)}
          </div>
          <h1 className="citizen__title">{t(lang, "title")}</h1>
          <p className="citizen__lede">{t(lang, "lede")}</p>
          <p className="muted citizen__small">{t(lang, "example")}</p>
          {!sel ? <p className="citizen__pick">{t(lang, "pick")}</p> : (
            <ul className="citizen__facts" aria-live="polite">{lines.map(l => <li key={l}>{l}</li>)}</ul>
          )}
          <p className="muted citizen__small">{t(lang, "simulated")}</p>
          <div className="citizen__feedback">
            <h2>{t(lang, "feedbackTitle")}</h2>
            {feedback ? <a className="btn btn--solid" href={feedback} target="_blank" rel="noreferrer">{t(lang, "feedbackLink")}</a> : <p className="muted">{t(lang, "feedbackMissing")}</p>}
          </div>
          <p><Link to={cityPath("/method")}>{t(lang, "more")}</Link></p>
        </div>
      </section>
    </div>
  );
}
