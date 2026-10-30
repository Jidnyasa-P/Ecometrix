/* UI tests. The API is replaced with a small in-test fixture and the WebGL map is stubbed (jsdom has no WebGL).
   The fixture exists only here; nothing in it is shipped or shown in the real app. */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import App from "../App";
import { toCells } from "../lib/data";
import { colorScale, sample } from "../lib/colors";
import { fmtIndianShort, fmtInt } from "../lib/format";

vi.mock("../components/MapStage", () => ({
  default: (p: { field: { key: string }; highlight: unknown }) => <div data-testid="map" data-field={p.field.key} data-filtered={p.highlight ? "yes" : "no"} />,
  boundsOf: () => [[0, 0], [1, 1]]
}));

const fields = [
  { key: "tree_density_ha", label: "Trees per hectare", unit: "trees/ha", evidence: "MEASURED", group: "Green", decimals: 1, source: "Census", ramp: "green", about: "Trees counted.", domain: [0, 30], min: 0, max: 40, n: 3 },
  { key: "lst_c", label: "Surface temperature", unit: "°C", evidence: "MEASURED", group: "Heat", decimals: 1, source: "Landsat", ramp: "heat", about: "Surface temp.", domain: [34, 44], min: 33, max: 45, n: 3 },
  { key: "pop", label: "People", unit: "people", evidence: "MODELLED", group: "People", decimals: 0, source: "WorldPop", ramp: "people", about: "People.", domain: [0, 900], min: 0, max: 1000, n: 3 },
  { key: "access_share", label: "Park access", unit: "% of people", evidence: "MODELLED", group: "Access", decimals: 3, source: "OSM", ramp: "access", about: "Access.", domain: [0, 100], min: 0, max: 100, n: 3 }
];
const meta = { built: true, manifest: { pipeline_version: "x", generated_at: "2026-10-01T00:00:00+00:00", git_sha: null, city: "Pune", h3_resolution: 9, pixel_m: 30,
  boundary: { source: "OSM", area_km2: 400, fallback: false }, n_cells: 3, columns: [],
  layers: { trees: { title: "Tree census", evidence: "MEASURED", license: "PD", status: "ok", detail: { vintage: "2019" } },
            landsat: { title: "LST", status: "failed", reason: "RuntimeError: stac down" } } },
  fields, evidence_labels: { MEASURED: "m", MODELLED: "mo", ASSUMED: "a", SIMULATED: "s" }, sources: [{ name: "Src", publisher: "Pub", license: "L", url: "https://x.test" }] };
const cells = { n: 3, h3: ["a", "b", "c"], lat: [18.5, 18.51, 18.52], lng: [73.8, 73.81, 73.82], area_km2: [0.1, 0.1, 0.1],
  values: { tree_density_ha: [1, 10, 30], lst_c: [36, 41, 44], pop: [100, 500, 900], access_share: [90, 20, 10] } };
const summary = { city: "Pune", n_cells: 3, area_km2: 0.3, access_rule: "r", trees_total: 4009000, trees_per_ha: 9.1, cells_without_trees_pct: 12, lst_c_median: 41, lst_p90_threshold_c: 44, pop_in_hottest_decile_cells: 900, pop_without_park_access_pct: 33.3 };
const audit = { generated_at: "2026-10-01T00:00:00+00:00", checks: [
  { id: "trees", title: "Tree census loads and is clean", status: "pass", rule: "90% valid", evidence: { rows_loaded: 4009000 }, note: "n" },
  { id: "costs", title: "Cost benchmarks", status: "manual", rule: "3 sources", evidence: {}, note: "Person B" }] };

function mockFetch(routes: Record<string, { status?: number; body: unknown }>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const r = routes[path];
    if (!r) return new Response(JSON.stringify({ detail: { code: "nf" } }), { status: 404 });
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200 });
  }));
}
const ok = { "/api/meta": { body: meta }, "/api/summary": { body: summary }, "/api/cells": { body: cells }, "/api/audit": { body: audit }, "/api/relationship": { body: { status: "unavailable", reason: "no NDVI" } } };

beforeEach(() => { window.history.pushState({}, "", "/"); localStorage.clear(); });

describe("pure helpers", () => {
  it("formats Indian numbering", () => {
    expect(fmtInt(4009000)).toBe("40,09,000");
    expect(fmtIndianShort(4009000)).toBe("40.1 lakh");
    expect(fmtInt(null)).toBe("n/a");
  });
  it("colour scale clamps, interpolates and renders missing as faint", () => {
    expect(sample(["#000000", "#ffffff"], 0.5)).toEqual([128, 128, 128]);
    const s = colorScale("green", "dark", [0, 10]);
    expect(s(-5)).toEqual(s(0)); expect(s(99)).toEqual(s(10)); expect(s(null)[3]).toBeLessThan(60);
  });
  it("columnar payload becomes cells", () => {
    const c = toCells(cells as never);
    expect(c).toHaveLength(3); expect(c[1].v.lst_c).toBe(41); expect(c[2].h3).toBe("c");
  });
});

describe("pages", () => {
  it("Atlas shows live numbers from the API, never invented ones", async () => {
    mockFetch(ok);
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Where does/)).toBeTruthy());
    expect(screen.getByText(/9\.1 trees per hectare/)).toBeTruthy();
    expect(screen.getByText(/33% of residents/)).toBeTruthy();
    expect(screen.getByText(/Every plan is a simulation/)).toBeTruthy();
    expect(screen.getByTestId("map").dataset.field).toBe("tree_density_ha");
  });

  it("reports an unbuilt baseline honestly", async () => {
    mockFetch({ "/api/meta": { body: { ...meta, built: false, manifest: null, fields: [] } } });
    render(<App />);
    await waitFor(() => expect(screen.getByText(/baseline has not been built/i)).toBeTruthy());
    expect(screen.queryByTestId("map")).toBeNull();
  });

  it("reports an unreachable API", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    render(<App />);
    await vi.advanceTimersByTimeAsync(120_000);
    await waitFor(() => expect(screen.getByText(/not reachable/i)).toBeTruthy());
    vi.useRealTimers();
  });

  it("Explore switches layers and applies the exploratory filter", async () => {
    mockFetch(ok);
    window.history.pushState({}, "", "/explore");
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("map")).toBeTruthy());
    fireEvent.click(screen.getByLabelText(/Surface temperature/));
    expect(screen.getByTestId("map").dataset.field).toBe("lst_c");
    expect(screen.getByTestId("map").dataset.filtered).toBe("no");
    fireEvent.click(screen.getByLabelText(/Exploratory filter/));
    expect(screen.getByTestId("map").dataset.filtered).toBe("yes");
    expect(screen.getByText(/people \(modelled\)/)).toBeTruthy();
  });

  it("Audit lists checks, failed layers and manual tasks", async () => {
    mockFetch(ok);
    window.history.pushState({}, "", "/audit");
    render(<App />);
    await waitFor(() => expect(screen.getByText("Tree census loads and is clean")).toBeTruthy());
    expect(screen.getByText("Manual task")).toBeTruthy();
    expect(screen.getByText(/stac down/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/no NDVI/)).toBeTruthy());
  });

  it("Method page lists limits and what is not built", async () => {
    mockFetch(ok);
    window.history.pushState({}, "", "/method");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Surface temperature is not air temperature/)).toBeTruthy());
    expect(screen.getByText(/What is still open/)).toBeTruthy();
  });

  it("theme toggle flips and persists", async () => {
    mockFetch(ok);
    render(<App />);
    const btn = await screen.findByRole("button", { name: /Switch to/ });
    const before = document.documentElement.dataset.theme;
    fireEvent.click(btn);
    await waitFor(() => expect(document.documentElement.dataset.theme).not.toBe(before));
    expect(localStorage.getItem("ecometrix-theme")).toBe(document.documentElement.dataset.theme);
  });
});
