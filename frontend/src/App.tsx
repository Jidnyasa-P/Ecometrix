import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Footer, Nav } from "./components/Chrome";
import { DataProvider } from "./lib/data";
import Atlas from "./pages/Atlas";
import Explore from "./pages/Explore";
import ForecastPage from "./pages/Forecast";
import Priority from "./pages/Priority";
import Plan from "./pages/Plan";
import Compare from "./pages/Compare";
import Report from "./pages/Report";
import City from "./pages/City";
import Evaluation from "./pages/Evaluation";
import AuditPage from "./pages/Audit";
import Method from "./pages/Method";

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

function Shell() {
  const { pathname } = useLocation();
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <Nav />
      <main id="main"><Routes>
        <Route path="/" element={<Atlas />} />
        <Route path="/forecast" element={<ForecastPage />} />
        <Route path="/priority" element={<Priority />} />
        <Route path="/plan" element={<Plan />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/report" element={<Report />} />
        <Route path="/city" element={<City />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/method" element={<Method />} />
        <Route path="*" element={<div className="fullstate"><h1 className="display display--sm">Page not found</h1></div>} />
      </Routes></main>
      {!["/explore", "/priority", "/plan", "/city"].includes(pathname) && <Footer />}
    </>
  );
}

export default function App() {
  return <BrowserRouter><ScrollTop /><DataProvider><Shell /></DataProvider></BrowserRouter>;
}
