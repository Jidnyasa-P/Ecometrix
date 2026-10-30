import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Link, NavLink, useLocation } from "react-router-dom";
import { HexMark } from "./Bits";
import { useTheme } from "../lib/theme";
import { useData } from "../lib/data";
import { fmtDate } from "../lib/format";
import { cityPath } from "../lib/city";
import { LANG_NAME, t, useLanguage, type Lang } from "../lib/i18n";

const LINKS = [
  { to: "/", key: "nav_atlas", end: true },
  { to: "/forecast", key: "nav_forecast" },
  { to: "/priority", key: "nav_priority" },
  { to: "/plan", key: "nav_plan" },
  { to: "/compare", key: "nav_compare" }
] as const;
const MORE = [
  { to: "/city", key: "nav_citizen" },
  { to: "/explore", key: "nav_explore" },
  { to: "/audit", key: "nav_audit" },
  { to: "/evaluation", key: "nav_evaluation" },
  { to: "/method", key: "nav_method" }
] as const;

export function Nav() {
  const [theme, toggle] = useTheme();
  const [lang, setLang] = useLanguage();
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const loc = useLocation();
  const navigate = useNavigate();
  const data = useData();
  const cityMeta = data.status === "ready" ? data.meta.city : data.status === "not_built" ? data.meta?.city : undefined;
  const cities = data.status === "ready" ? data.meta.cities ?? [] : data.status === "not_built" ? data.meta?.cities ?? [] : [];
  const selectedCity = new URLSearchParams(loc.search).get("city") ?? cityMeta?.slug ?? "pune";
  useEffect(() => { setOpen(false); setMore(false); }, [loc.pathname]);
  return (
    <header className="nav" data-open={open}>
      <Link to={cityPath("/", loc.search)} className="nav__brand" aria-label="EcoMetrix home">
        <HexMark /> <span>EcoMetrix</span> <em className="nav__tag">{cityMeta?.name ?? "City platform"}</em>
      </Link>
      <nav className="nav__links" aria-label="Main">
        {LINKS.map(l => <NavLink key={l.to} to={cityPath(l.to, loc.search)} end={"end" in l ? l.end : false} className={({ isActive }) => `pill ${isActive ? "is-active" : ""}`}>{t(lang, l.key)}</NavLink>)}
        <div className="more">
          <button className={`pill ${MORE.some(m => loc.pathname.startsWith(m.to)) ? "is-active" : ""}`} aria-expanded={more} aria-haspopup="true" onClick={() => setMore(m => !m)}>{t(lang, "nav_more")} ▾</button>
          {more && <div className="more__menu">{MORE.map(l => <NavLink key={l.to} to={cityPath(l.to, loc.search)} className={({ isActive }) => `sheetlink ${isActive ? "is-active" : ""}`}>{t(lang, l.key)}</NavLink>)}</div>}
        </div>
      </nav>
      <label className="city-picker" aria-label={t(lang, "nav_city")}>
        <span className="sr-only">{t(lang, "nav_city")}</span>
        <select className="pill city-picker__select" value={selectedCity} onChange={e => navigate({ pathname: loc.pathname, search: `?city=${encodeURIComponent(e.target.value)}` })}>
          {(cities.length ? cities : [{ slug: "pune", name: "Pune", status: "pilot_not_built" }, { slug: "london", name: "London", status: "configuration_only" }, { slug: "new-york", name: "New York City", status: "configuration_only" }, { slug: "athens", name: "Athens", status: "configuration_only" }]).map(c => <option key={c.slug} value={c.slug}>{c.name}{c.status === "built" ? " · built" : c.status === "pilot_not_built" ? " · pilot not built" : " · config only"}</option>)}
        </select>
      </label>
      <label className="language-picker" aria-label={t(lang, "nav_language")}>
        <span className="sr-only">{t(lang, "nav_language")}</span>
        <select className="pill city-picker__select language-picker__select" value={lang} onChange={e => setLang(e.target.value as Lang)}>
          {(Object.keys(LANG_NAME) as Lang[]).map(code => <option key={code} value={code}>{LANG_NAME[code]}</option>)}
        </select>
      </label>
      <button className="pill pill--tool" onClick={toggle} aria-label={`${t(lang, "nav_light")} / ${t(lang, "nav_dark")}`}>
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.500A8 8 0 0 1 9.500 4 8.500 8.500 0 1 0 20 14.500z" fill={theme === "dark" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
        {theme === "dark" ? t(lang, "nav_light") : t(lang, "nav_dark")}
      </button>
      <button className="pill pill--menu" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-controls="mobile-links">{t(lang, "nav_menu")}</button>
      <nav id="mobile-links" className="nav__sheet" aria-label="Mobile">
        {[...LINKS, ...MORE].map(l => <NavLink key={l.to} to={cityPath(l.to, loc.search)} end={"end" in l ? l.end : false} className={({ isActive }) => `sheetlink ${isActive ? "is-active" : ""}`}>{t(lang, l.key)}</NavLink>)}
        <div className="sheet-languages" role="group" aria-label={t(lang, "nav_language")}>
          {(Object.keys(LANG_NAME) as Lang[]).map(code => <button type="button" key={code} className={`chip ${lang === code ? "is-on" : ""}`} onClick={() => setLang(code)} aria-pressed={lang === code}>{LANG_NAME[code]}</button>)}
        </div>
      </nav>
    </header>
  );
}

export function Footer() {
  const d = useData();
  const loc = useLocation();
  const [lang] = useLanguage();
  const built = d.status === "ready" ? d.meta.manifest?.generated_at : d.status === "not_built" ? d.meta?.manifest?.generated_at : undefined;
  const city = d.status === "ready" ? d.meta.city : d.status === "not_built" ? d.meta?.city : undefined;
  const sources = d.status === "ready" ? d.meta.sources : d.status === "not_built" ? d.meta?.sources ?? [] : [];
  return (
    <footer className="footer">
      <div className="wrap footer__grid">
        <div>
          <p className="footer__brand"><HexMark size={24} /> EcoMetrix</p>
          <p className="footer__note">{t(lang, "footer_description")} {t(lang, "footer_selected")}: {city ? `${city.name}${city.country ? `, ${city.country}` : ""}` : t(lang, "footer_choose")}. {t(lang, "footer_evidence")}</p>
          <p className="footer__note">{t(lang, "footer_last_built")}: <strong>{fmtDate(built)}</strong></p>
        </div>
        <div>
          <p className="footer__h">{t(lang, "footer_credits")}</p>
          <ul className="footer__list">
            {sources.map(source => <li key={source.name}><a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> · {source.publisher} ({source.license})</li>)}
          </ul>
        </div>
        <div>
          <p className="footer__h">{t(lang, "footer_explore")}</p>
          <ul className="footer__list">
            <li><Link to={cityPath("/plan", loc.search)}>{t(lang, "footer_best_plan")}</Link></li>
            <li><Link to={cityPath("/priority", loc.search)}>{t(lang, "footer_need")}</Link></li>
            <li><Link to={cityPath("/city", loc.search)}>{t(lang, "footer_citizen")}</Link></li>
            <li><Link to={cityPath("/forecast", loc.search)}>{t(lang, "footer_forecast")}</Link></li>
            <li><Link to={cityPath("/explore", loc.search)}>{t(lang, "footer_map")}</Link></li>
            <li><Link to={cityPath("/audit", loc.search)}>{t(lang, "footer_audit")}</Link></li>
            <li><Link to={cityPath("/method", loc.search)}>{t(lang, "footer_method")}</Link></li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
