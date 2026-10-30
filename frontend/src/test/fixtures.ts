/* In-test API fixtures. Never shipped: the app only ever reads real API responses. */
import { vi } from "vitest";

const F = (key: string, label: string, group: string, extra = {}) => ({ key, label, unit: "u", evidence: "MODELLED", group, decimals: 0, source: "s", ramp: "need", about: "a", domain: [0, 100], min: 0, max: 100, n: 3, ...extra });
export const fields = [F("pop", "People", "People"), F("tree_density_ha", "Trees per hectare", "Green", { evidence: "MEASURED", decimals: 1 }),
  F("lst_c", "Surface temperature", "Heat", { evidence: "MEASURED" }), F("access_share", "Park access", "Access"), F("dist_park_m", "Distance to nearest park", "Access", { evidence: "MEASURED" }),
  F("need_balanced", "Need score (balanced weights)", "Need"), F("need_heat", "Need: heat", "Need"), F("need_people", "Need: residents", "Need"), F("need_gap", "Need: park-access gap", "Need"), F("need_growth", "Need: growth", "Need")];
export const meta = { built: true, manifest: { pipeline_version: "x", generated_at: "2026-10-01T00:00:00+00:00", git_sha: null, city: "Pune", h3_resolution: 9, pixel_m: 30,
  boundary: { source: "OSM", area_km2: 400, fallback: false }, n_cells: 3, columns: [], layers: {} }, fields, evidence_labels: { MEASURED: "m", MODELLED: "mo", ASSUMED: "a", SIMULATED: "s" }, sources: [] };
export const cells = { n: 3, h3: ["a", "b", "c"], lat: [18.5, 18.51, 18.52], lng: [73.8, 73.81, 73.82], area_km2: [0.1, 0.1, 0.1], values: {
  pop: [100, 200, 300], tree_density_ha: [4, 10, 20], lst_c: [44, 40, 36], access_share: [10, 60, 90], dist_park_m: [900, 200, 50], need_balanced: [70, 50, 20],
  need_heat: [90, 50, 10], need_people: [40, 60, 50], need_gap: [80, 40, 10], need_growth: [50, 50, 50] } };
const R = (p10: number, p50: number, p90: number) => ({ p10, p50, p90 });
const site = (id: string, h3: string, type: string, cost: number, cool: number, people: number, carbon: number, hn: boolean) => ({ site_id: id, h3, type, area_ha: 1, cost_p50_inr: cost,
  cooling_person_degrees_p50: cool, carbon_t_co2e_p50: carbon, people_newly_served_marginal: people, high_need: hn, lat: 18.5, lng: 73.8 });
export const result = (preset: string, bi: number, eq: number, scale = 1) => ({ preset, budget_inr: [5e6, 1e7, 2e7][bi], equity_pct: eq, solver: { status: "OPTIMAL", gap: 0, prefiltered: false, candidates: 6 },
  n_sites: 2, by_type: { pocket_park: 1, mini_forest: 1 }, cost_pv_inr: R(4e6 * scale, 5e6 * scale, 6e6 * scale), cooling_person_degrees: R(10, 20 * scale, 30), carbon_t_co2e: R(50, 100, 150),
  people_newly_served: 120 * scale, prob_within_budget: 0.9, high_need_share_of_spend: eq ? 0.6 : 0.3, objective_norm: 1 * scale,
  sites: [site("a:mini_forest", "a", "mini_forest", 3e6, 20, 0, 100, true), site("b:pocket_park", "b", "pocket_park", 2e6, 0, 120 * scale, 0, false)],
  baseline_top_need: { n_sites: 2, people_newly_served: 80, cost_pv_inr: R(4e6, 5e6, 6e6), cooling_person_degrees: R(5, 10, 15), carbon_t_co2e: R(10, 20, 30), objective_norm: 0.8 }, gain_vs_top_need_pct: 25 });
export const portfolios = { status: "ok", presets: { balanced: { cooling: .34, people: .33, carbon: .33 }, heat_first: { cooling: .6, people: .2, carbon: .2 } },
  budgets_inr: [5e6, 1e7, 2e7], equity_shares_pct: [0, 50], median_site_cost_inr: 1e6, candidate_sites: 6, no_regret_site_ids: ["a:mini_forest"],
  no_regret_rule: "chosen in at least 75% of solutions", high_need_rule: "top third", normalisation: "n",
  results: ["balanced", "heat_first"].flatMap((p, pi) => [0, 1, 2].flatMap(bi => [0, 50].map(eq => result(p, bi, eq, 1 + pi * 0.5 + bi * 0.2)))) };
export const sites = { n: 2, columns: { site_id: ["a:mini_forest", "b:pocket_park"], h3: ["a", "b"], type: ["mini_forest", "pocket_park"], area_ha: [1, 1], open_land_ha: [1.2, 1.3], pop: [100, 200],
  pop_unserved_300m: [80, 150], dlst_p50: [-0.5, -0.4], need_no_regret: [1, 0], lat: [18.5, 18.51], lng: [73.8, 73.81] } };
export const assumptions = { common: { discount_rate: { low: 0.0372, base: 0.06, high: 0.08, unit: "fraction", label: "ASSUMED", source: "NABARD; IEG" } } };
export const sensitivity = { status: "ok", method: "m", types: {
  mini_forest: { site_id: "a:mini_forest", type: "mini_forest", area_ha: 1, base: { cost_pv_inr: 7e6, carbon_t_co2e: 200 }, rows: [
    { parameter: "mini_forest.capex_inr_per_m2", low: 300, base: 550, high: 800, max_relative_swing: 0.6, effects: { cost_pv_inr: { at_low: 4e6, at_high: 9e6 }, carbon_t_co2e: { at_low: 200, at_high: 200 } } },
    { parameter: "mini_forest.carbon_scale", low: .5, base: .8, high: 1, max_relative_swing: 0.4, effects: { cost_pv_inr: { at_low: 7e6, at_high: 7e6 }, carbon_t_co2e: { at_low: 120, at_high: 250 } } }] },
  pocket_park: { site_id: "b:pocket_park", type: "pocket_park", area_ha: 1, base: { cost_pv_inr: 5e6 }, rows: [] } } };
export const report = { built: true, modules: {}, heat_model: { status: "ok", chosen: "linear_ndvi", cv: { blocks: 12, folds: 5, cells: 100, models: {} } }, need: null };
export const forecast = { status: "ok", method: "linear_all", last_observed_year: 2020, horizons: [2035], selection_rule: "r", caveats: [], backtest: { train_years: [2000, 2014], test_years: [2015, 2020],
  methods: { naive: { wape_pct: 9, city_mape_pct: 8, city_bias_pct: -8, wape_by_horizon_pct: [] }, linear_all: { wape_pct: 4, city_mape_pct: 2, city_bias_pct: -1, wape_by_horizon_pct: [] } } }, city_series: [] };
export const scenario = { site_id: "a:mini_forest", type: "mini_forest", area_ha: 1, max_area_ha: 1, horizon_years: 10, draws: 2000, baseline: "vs nothing", label_note: "SIMULATED: nothing built.",
  cost: { present_value_inr: R(5e6, 7e6, 9e6), breakdown_base_inr: {}, basis: "capex", evidence: "ASSUMED" },
  benefits: { cooling: { available: true, delta_lst_c: R(-0.8, -0.5, -0.2), person_degrees: R(20, 50, 80), note: "modelled", evidence: "MODELLED" },
    people_newly_served: { value: 0, note: "Not counted", evidence: "MODELLED" }, carbon: { available: true, t_co2e: R(100, 200, 300), note: "plots", evidence: "ASSUMED" } }, cost_effectiveness: {} };

export function mockApi(extra: Record<string, { status?: number; body: unknown }> = {}) {
  const routes: Record<string, { status?: number; body: unknown }> = { "/api/meta": { body: meta }, "/api/summary": { body: { city: "Pune", n_cells: 3, area_km2: 0.3, access_rule: "r" } },
    "/api/cells": { body: cells }, "/api/sites": { body: sites }, "/api/portfolios": { body: portfolios }, "/api/sensitivity": { body: sensitivity }, "/api/model-report": { body: report },
    "/api/forecast": { body: forecast }, "/api/assumptions": { body: assumptions }, "/api/scenarios/run": { body: scenario }, ...extra };
  const fn = vi.fn(async (url: string) => {
    const r = routes[String(url).replace(/^https?:\/\/[^/]+/, "")];
    if (!r) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
