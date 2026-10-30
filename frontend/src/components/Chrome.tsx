import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { HexMark } from "./Bits";
import { useTheme } from "../lib/theme";
import { useData } from "../lib/data";
import { fmtDate } from "../lib/format";

const LINKS = [
  { to: "/", label: "Atlas", end: true },
  { to: "/forecast", label: "Forecast" },
  { to: "/priority", label: "Priority" },
  { to: "/plan", label: "Plan" },
  { to: "/compare", label: "Compare" }
];
const MORE = [
  { to: "/city", label: "Citizen view" },
  { to: "/explore", label: "Explore" },
  { to: "/audit", label: "Data audit" },
  { to: "/evaluation", label: "Evaluation" },
  { to: "/method", label: "Method" }
];

export function Nav() {
  const [theme, toggle] = useTheme();
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); setMore(false); }, [loc.pathname]);
  return (
    <header className="nav" data-open={open}>
      <Link to="/" className="nav__brand" aria-label="EcoMetrix home">
        <HexMark /> <span>EcoMetrix</span> <em className="nav__tag">Pune pilot</em>
      </Link>
      <nav className="nav__links" aria-label="Main">
        {LINKS.map(l => <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `pill ${isActive ? "is-active" : ""}`}>{l.label}</NavLink>)}
        <div className="more">
          <button className={`pill ${MORE.some(m => loc.pathname.startsWith(m.to)) ? "is-active" : ""}`} aria-expanded={more} aria-haspopup="true" onClick={() => setMore(m => !m)}>More ▾</button>
          {more && <div className="more__menu">{MORE.map(l => <NavLink key={l.to} to={l.to} className={({ isActive }) => `sheetlink ${isActive ? "is-active" : ""}`}>{l.label}</NavLink>)}</div>}
        </div>
      </nav>
      <button className="pill pill--tool" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.500A8 8 0 0 1 9.500 4 8.500 8.500 0 1 0 20 14.500z" fill={theme === "dark" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
        {theme === "dark" ? "Light" : "Dark"}
      </button>
      <button className="pill pill--menu" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-controls="mobile-links">Menu</button>
      <nav id="mobile-links" className="nav__sheet" aria-label="Mobile">
        {[...LINKS, ...MORE].map(l => <NavLink key={l.to} to={l.to} end={(l as { end?: boolean }).end} className={({ isActive }) => `sheetlink ${isActive ? "is-active" : ""}`}>{l.label}</NavLink>)}
      </nav>
    </header>
  );
}

export function Footer() {
  const d = useData();
  const built = d.status === "ready" ? d.meta.manifest?.generated_at : d.status === "not_built" ? d.meta?.manifest?.generated_at : undefined;
  return (
    <footer className="footer">
      <div className="wrap footer__grid">
        <div>
          <p className="footer__brand"><HexMark size={24} /> EcoMetrix</p>
          <p className="footer__note">An evidence base for urban greening decisions. Pilot city: Pune, India. The baseline you see is built only from open data, and every number carries an evidence label.</p>
          <p className="footer__note">Data last built: <strong>{fmtDate(built)}</strong></p>
        </div>
        <div>
          <p className="footer__h">Data and map credits</p>
          <ul className="footer__list">
            <li>Tree census: Pune Municipal Corporation via OpenCity (public domain)</li>
            <li>Map data © OpenStreetMap contributors (ODbL); basemap by OpenFreeMap</li>
            <li>Landsat (USGS/NASA), Sentinel-2 (ESA Copernicus), ESA WorldCover (CC BY 4.0) via Microsoft Planetary Computer</li>
            <li>Population: WorldPop (CC BY 4.0)</li>
          </ul>
        </div>
        <div>
          <p className="footer__h">Explore</p>
          <ul className="footer__list">
            <li><Link to="/plan">Best plan under a budget</Link></li>
            <li><Link to="/priority">Where is the need?</Link></li>
            <li><Link to="/city">Citizen view (English, मराठी)</Link></li>
            <li><Link to="/forecast">Where the city is heading</Link></li>
            <li><Link to="/explore">Open the map</Link></li>
            <li><Link to="/audit">See the data audit</Link></li>
            <li><Link to="/method">Read the method and limits</Link></li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
