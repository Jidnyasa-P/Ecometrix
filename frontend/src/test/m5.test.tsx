/* UI tests for the Forecast and Priority screens and the need-score logic. API replaced by in-test fixtures; WebGL map stubbed. */
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import App from "../App";
import { needScore, normalise, withScores, toSites, availableComps } from "../lib/need";
import { fmtInr } from "../lib/format";

vi.mock("../components/MapStage", () => ({
  default: (p: { field: { key: string } }) => <div data-testid="map" data-field={p.field.key} />,
  boundsOf: () => [[0, 0], [1, 1]]
}));

const F = (key: string, label: string, group: string, extra = {}) => ({ key, label, unit: "u", evidence: "MODELLED", group, decimals: 0, source: "s", ramp: "need", about: "a", domain: [0, 100], min: 0, max: 100, n: 3, ...extra });
const fields = [F("pop", "People", "People"), F("need_heat", "Need: heat", "Need"), F("need_people", "Need: residents", "Need"), F("need_gap", "Need: park-access gap", "Need"),
  F("need_growth", "Need: growth", "Need"), F("pop_growth_2035", "Projected growth 2020 to 2035", "Future"), F("pop_2035", "Projected people (2035)", "Future")];
const meta = { built: true, manifest: { pipeline_version: "x", generated_at: "2026-10-01T00:00:00+00:00", git_sha: null, city: "Pune", h3_resolution: 9, pixel_m: 30,
  boundary: { source: "OSM", area_km2: 400, fallback: false }, n_cells: 3, columns: [], layers: {} }, fields,
  evidence_labels: { MEASURED: "m", MODELLED: "mo", ASSUMED: "a", SIMULATED: "s" }, sources: [] };
const cells = { n: 3, h3: ["a", "b", "c"], lat: [18.5, 18.51, 18.52], lng: [73.8, 73.81, 73.82], area_km2: [0.1, 0.1, 0.1], values: {
  pop: [100, 200, 300], need_heat: [90, 10, 50], need_people: [50, 50, 50], need_gap: [10, 90, 50], need_growth: [50, 50, 50],
  pop_growth_2035: [5, 10, 15], pop_2035: [105, 210, 315] } };
const sites = { n: 3, columns: { site_id: ["a:mini_forest", "b:pocket_park", "c:pocket_park"], h3: ["a", "b", "c"], type: ["mini_forest", "pocket_park", "pocket_park"],
  area_ha: [1, 1, 0.6], open_land_ha: [1.2, 1.3, 0.7], pop: [100, 200, 300], pop_unserved_300m: [80, 150, 200], dlst_p50: [-0.5, -0.4, null],
  need_no_regret: [0, 1, 0], lat: [18.5, 18.51, 18.52], lng: [73.8, 73.81, 73.82] } };
const report = { built: true, modules: { forecast: { status: "ok" } }, heat_model: { status: "ok", chosen: "linear_ndvi" },
  need: { presets: { balanced: { heat: .25, people: .25, gap: .25, growth: .25 }, heat_first: { heat: .55, people: .2, gap: .15, growth: .1 },
    access_first: { heat: .15, people: .25, gap: .5, growth: .1 } }, components_used: ["heat", "people", "gap", "growth"], excluded: "Vulnerability not included.",
    stability: { status: "ok", no_regret_share_of_top_pct: 42 } } };
const forecast = { status: "ok", method: "linear_all", last_observed_year: 2020, horizons: [2025, 2030, 2035], selection_rule: "lowest WAPE", caveats: ["History is modelled."],
  backtest: { train_years: [2000, 2014], test_years: [2015, 2020], methods: {
    naive: { wape_pct: 9.5, city_mape_pct: 8.1, city_bias_pct: -8.1, wape_by_horizon_pct: [] }, linear_all: { wape_pct: 4.2, city_mape_pct: 2.0, city_bias_pct: -1.0, wape_by_horizon_pct: [] } } },
  city_series: [...Array.from({ length: 21 }, (_, i) => ({ year: 2000 + i, kind: "history", total: 3e6 + i * 1e5 })),
    ...Array.from({ length: 15 }, (_, i) => ({ year: 2021 + i, kind: "forecast", total: 5.1e6 + i * 1e5, low: 4.9e6 + i * 8e4, high: 5.3e6 + i * 1.2e5 }))] };
const scenario = { site_id: "a:mini_forest", type: "mini_forest", area_ha: 1, max_area_ha: 1, horizon_years: 10, draws: 2000, baseline: "vs nothing", label_note: "SIMULATED: nothing built.",
  cost: { present_value_inr: { p10: 5e6, p50: 7e6, p90: 9e6 }, breakdown_base_inr: {}, basis: "capex plus upkeep", evidence: "ASSUMED" },
  benefits: { cooling: { available: true, delta_lst_c: { p10: -0.8, p50: -0.5, p90: -0.2 }, person_degrees: { p10: 20, p50: 50, p90: 80 }, note: "modelled", evidence: "MODELLED" },
    people_newly_served: { value: 0, note: "Not counted: dense plantations are not assumed to be open to the public.", evidence: "MODELLED" },
    carbon: { available: true, t_co2e: { p10: 100, p50: 200, p90: 300 }, note: "from three plots", evidence: "ASSUMED" } },
  cost_effectiveness: { inr_per_t_co2e: { p10: 20000, p50: 35000, p90: 60000 } } };
const assumptions = { common: { discount_rate: { low: 0.0372, base: 0.06, high: 0.08, unit: "fraction", label: "ASSUMED", source: "NABARD; IEG" } }, pocket_park: { carbon: { estimated: false, source: "No Indian measurement found" } } };

function mockApi(extra: Record<string, { status?: number; body: unknown }> = {}) {
  const routes: Record<string, { status?: number; body: unknown }> = { "/api/meta": { body: meta }, "/api/summary": { body: { city: "Pune", n_cells: 3, area_km2: 0.3, access_rule: "r" } },
    "/api/cells": { body: cells }, "/api/sites": { body: sites }, "/api/model-report": { body: report }, "/api/forecast": { body: forecast },
    "/api/assumptions": { body: assumptions }, "/api/scenarios/run": { body: scenario }, ...extra };
  const fn = vi.fn(async (url: string) => {
    const r = routes[String(url).replace(/^https?:\/\/[^/]+/, "")];
    if (!r) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
beforeEach(() => { localStorage.clear(); });

describe("need score logic", () => {
  const comps = availableComps(Object.fromEntries(fields.map(f => [f.key, f])) as never);
  const cell = { h3: "a", lat: 0, lng: 0, area_km2: 0.1, v: { need_heat: 80, need_people: 40, need_gap: 20, need_growth: 60 } };
  it("weights renormalise and the score stays on the 0 to 100 scale", () => {
    expect(comps).toEqual(["heat", "people", "gap", "growth"]);
    expect(needScore(cell, { heat: 1, people: 1, gap: 1, growth: 1 }, comps)).toBe(50);
    expect(needScore(cell, { heat: 2, people: 0, gap: 0, growth: 0 }, comps)).toBe(80);
    expect(needScore(cell, { heat: 0, people: 0, gap: 0, growth: 0 }, comps)).toBeNull();
    expect(needScore({ ...cell, v: { ...cell.v, need_gap: null } }, { heat: 1, people: 1, gap: 1, growth: 1 }, comps)).toBeNull();
  });
  it("normalise sums to one, ignoring missing components", () => {
    const n = normalise({ heat: 50, people: 50, gap: 100, growth: 100 }, ["heat", "people", "gap"]);
    expect(n.heat + n.people + n.gap).toBeCloseTo(1); expect(n.growth).toBe(0);
  });
  it("withScores returns a usable colour domain", () => {
    const s = withScores([cell, { ...cell, h3: "b", v: { ...cell.v, need_heat: 10 } }], { heat: 1, people: 0, gap: 0, growth: 0 }, comps);
    expect(s.domain[0]).toBeLessThan(s.domain[1]); expect(s.byHex.get("a")).toBe(80);
  });
  it("sites payload becomes rows", () => {
    const s = toSites(sites as never);
    expect(s).toHaveLength(3); expect(s[1].noRegret).toBe(true); expect(s[2].dlst_p50).toBeNull();
  });
  it("rupee formatting uses lakh and crore", () => { expect(fmtInr(2530000)).toBe("₹ 25.3 lakh"); expect(fmtInr(14000000)).toBe("₹ 1.40 crore"); });
});

describe("forecast screen", () => {
  it("shows the chosen method and the backtest, with the plain-language limits", async () => {
    mockApi(); window.history.pushState({}, "", "/forecast");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/How it was tested/)).toBeTruthy());
    expect(screen.getAllByText(/Straight line, all years/).length).toBeGreaterThan(0);
    expect(screen.getByText("chosen")).toBeTruthy();
    expect(screen.getByText(/History is modelled/)).toBeTruthy();
    expect(screen.getByRole("img", { name: /City population/ })).toBeTruthy();
  });
  it("explains why the projection is missing instead of inventing one", async () => {
    mockApi({ "/api/forecast": { status: 503, body: { detail: { code: "baseline_not_built" } } },
      "/api/model-report": { body: { ...report, modules: { forecast: { status: "failed", reason: "popseries.parquet not found" } } } } });
    window.history.pushState({}, "", "/forecast");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/popseries.parquet not found/)).toBeTruthy());
    expect(screen.queryByText(/How it was tested/)).toBeNull();
  });
});

describe("priority screen", () => {
  const topType = () => within(screen.getAllByRole("list").find(l => l.tagName === "OL")!).getAllByRole("listitem")[0].textContent ?? "";
  it("ranks sites by the chosen weights and the ranking responds to presets", async () => {
    mockApi(); window.history.pushState({}, "", "/priority");
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Heat first" }));
    await waitFor(() => expect(topType()).toMatch(/Mini-forest/));       // cell a is the hottest
    fireEvent.click(screen.getByRole("button", { name: "Access first" }));
    await waitFor(() => expect(topType()).toMatch(/Pocket park/));       // cell b has the largest access gap
    expect(screen.getByText(/42%/)).toBeTruthy();                        // no-regret share comes from the model report
    expect(screen.getByText(/Vulnerability not included/)).toBeTruthy();
  });
  it("runs a scenario for a site and shows labelled ranges, and says when something is not estimated", async () => {
    const f = mockApi(); window.history.pushState({}, "", "/priority");
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Heat first" }));
    await waitFor(() => expect(topType()).toMatch(/Mini-forest/));
    fireEvent.click(within(screen.getAllByRole("list").find(l => l.tagName === "OL")!).getAllByRole("button")[0]);
    await waitFor(() => expect(screen.getByLabelText(/Scenario for the selected site/)).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/₹ 70.0 lakh/)).toBeTruthy());
    expect(screen.getByText(/range ₹ 50.0 lakh to ₹ 90.0 lakh/)).toBeTruthy();
    expect(screen.getByText(/SIMULATED: nothing built/)).toBeTruthy();
    expect(screen.getByText(/Not counted: dense plantations/)).toBeTruthy();
    const post = f.mock.calls.find(c => String(c[0]).includes("/api/scenarios/run"));
    expect(post).toBeTruthy();
  });
  it("shows the server's message when a scenario is invalid", async () => {
    mockApi({ "/api/scenarios/run": { status: 400, body: { detail: { code: "invalid_scenario", message: "area must be above 0" } } } });
    window.history.pushState({}, "", "/priority");
    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0));
    fireEvent.click(within(screen.getAllByRole("list").find(l => l.tagName === "OL")!).getAllByRole("button")[0]);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/area must be above 0/));
  });
});

describe("method page", () => {
  it("lists the assumptions register from the API, with sources", async () => {
    mockApi(); window.history.pushState({}, "", "/method");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/NABARD; IEG/)).toBeTruthy());
    expect(screen.getByText(/No Indian measurement found/)).toBeTruthy();
  });
});
