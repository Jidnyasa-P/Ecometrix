export type Evidence = "MEASURED" | "MODELLED" | "ASSUMED" | "SIMULATED";

export interface FieldDef {
  key: string; label: string; unit: string; evidence: Evidence; group: string; decimals: number;
  source: string; ramp: string; about: string; domain: [number, number]; min: number; max: number; n: number; scale?: number;
}
export interface LayerStatus {
  title?: string; evidence?: Evidence; license?: string; source?: string; status: "ok" | "failed" | "skipped";
  reason?: string; detail?: Record<string, unknown>;
}
export interface Manifest {
  pipeline_version: string; generated_at: string; git_sha: string | null; city: string; h3_resolution: number; pixel_m: number;
  boundary: { source: string; area_km2: number; fallback: boolean; osm_ref?: string | null; name?: string; notes?: string[];
    boundary_dataset?: string; boundary_dataset_url?: string; boundary_resource_id?: string; boundary_resource_name?: string;
    boundary_resource_credit?: string; boundary_metadata_modified?: string; boundary_resource_modified?: string;
    boundary_ward_features?: number };
  n_cells: number; columns: string[]; layers: Record<string, LayerStatus>;
}
export interface CityMeta {
  slug: string; name: string; country?: string; country_code?: string; currency: string; locale: string; unit_system: string;
  access?: { distance_m?: number; min_area_ha?: number; standard?: string; method?: string };
  finance_enabled?: boolean; finance_reason?: string;
}
export interface Meta {
  city: CityMeta;
  cities?: { slug: string; name: string; country?: string; currency?: string; status?: string }[];
  built: boolean; manifest: Manifest | null; fields: FieldDef[]; evidence_labels: Record<Evidence, string>;
  sources: { name: string; publisher: string; license: string; url: string }[];
}
export interface Summary {
  city: string; n_cells: number; area_km2: number; access_rule: string;
  trees_total?: number; trees_per_ha?: number; cells_without_trees_pct?: number; trees_rows_loaded?: number;
  trees_species_top?: { species: string; trees: number; share: number }[]; trees_species_distinct?: number;
  ndvi_median?: number | null; lst_c_median?: number | null; lst_c_p10?: number | null; lst_c_p90?: number | null;
  lst_p90_threshold_c?: number; pop_in_hottest_decile_cells?: number;
  builtup_share_pct?: number | null; treecover_share_pct?: number | null;
  pop_total?: number; pop_with_park_access?: number; pop_without_park_access?: number; pop_without_park_access_pct?: number | null;
  public_green_mapped_ha_in_study_area?: number; forest_reserve_mapped_ha_in_study_area?: number;
}
export interface CellsPayload {
  n: number; h3: string[]; lat: number[]; lng: number[]; area_km2: number[]; values: Record<string, (number | null)[]>;
}
export interface Cell { h3: string; lat: number; lng: number; area_km2: number; v: Record<string, number | null> }
export interface AuditCheck { id: string; title: string; status: "pass" | "warn" | "fail" | "manual"; rule: string; evidence: Record<string, unknown>; note: string }
export interface Audit { generated_at: string; checks: AuditCheck[] }
export interface Relationship {
  status: "ok" | "unavailable"; reason?: string; n_cells?: number; pearson_r?: number; spearman_rho?: number;
  slope_c_per_0p1_ndvi?: number; r2_in_sample?: number;
  spatial_block_cv?: { blocks: number; cells_evaluated: number; rmse_ndvi_model_c: number; rmse_mean_only_c: number; rmse_improvement_pct: number | null } | null;
  interpretation?: string; caveat?: string;
}

export interface SitesPayload { n: number; columns: Record<string, (string | number | null)[]> }
export interface Site {
  id: string; h3: string; type: "pocket_park" | "mini_forest"; area_ha: number; open_land_ha: number; pop: number; unserved: number;
  dlst_p50: number | null; noRegret: boolean; lat: number; lng: number;
}
export interface ForecastPoint { year: number; kind: "history" | "forecast"; total: number; low?: number; high?: number }
export interface Forecast {
  status: "ok"; method: string; last_observed_year: number; horizons: number[]; selection_rule: string; caveats: string[];
  backtest: { train_years: [number, number]; test_years: number[];
    methods: Record<string, { wape_pct: number; city_mape_pct: number; city_bias_pct: number; wape_by_horizon_pct: number[] }> };
  city_series: ForecastPoint[];
}
export interface ModelReport {
  built: boolean; modules: Record<string, { status: string; reason?: string; count?: number; by_type?: Record<string, number> }>;
  heat_model: null | {
    status: string; reason?: string; chosen?: string; gain_vs_linear_ndvi_pct?: number | null; note?: string;
    cv?: { blocks: number; folds: number; cells: number; models: Record<string, { rmse_c: number; mae_c: number; r2: number | null }> };
    monotonic?: { ok: boolean; sweep_change_c: number };
    importance_heldout_rmse_increase_c?: Record<string, number>;
    greenness_targets?: Record<string, { available: boolean; ndvi_target?: number; cells?: number; reason?: string }>;
  };
  need: null | { presets: Record<string, Record<string, number>>; components_used: string[]; excluded: string;
    stability: { status: string; no_regret_cells?: number; no_regret_share_of_top_pct?: number; scored_cells?: number;
      pairs?: { a: string; b: string; spearman: number; top_decile_overlap_pct: number }[] } };
}
export interface Range { p10: number; p50: number; p90: number }
export interface ScenarioResult {
  site_id: string; type: string; area_ha: number; max_area_ha: number; horizon_years: number; draws: number; baseline: string; label_note: string;
  cost: { present_value_inr: Range; breakdown_base_inr: Record<string, number>; basis: string; evidence: Evidence };
  benefits: {
    cooling: { available: boolean; delta_lst_c?: Range; person_degrees?: Range; note: string; evidence: Evidence };
    people_newly_served: { value: number; note: string; evidence: Evidence };
    carbon: { available: boolean; t_co2e?: Range; note: string; evidence: Evidence };
  };
  cost_effectiveness: { inr_per_person_newly_served?: Range; inr_per_t_co2e?: Range | null; inr_per_person_degree_c?: Range };
  budget?: { budget_inr: number; probability_within_budget: number; p50_within_budget: boolean; max_area_ha_at_p50_cost: number | null; note: string };
}

export interface PortfolioSite {
  site_id: string; h3: string; type: "pocket_park" | "mini_forest"; area_ha: number; cost_p50_inr: number; cooling_person_degrees_p50: number;
  carbon_t_co2e_p50: number; people_newly_served_marginal: number; high_need: boolean; lat: number; lng: number;
}
export interface PortfolioResult {
  preset: string; budget_inr: number; equity_pct: number; solver: { status: string; gap: number | null; prefiltered: boolean; candidates: number };
  n_sites: number; by_type: Record<string, number>; cost_pv_inr: Range; cooling_person_degrees: Range; carbon_t_co2e: Range; people_newly_served: number;
  prob_within_budget: number; high_need_share_of_spend: number; objective_norm: number; sites: PortfolioSite[];
  baseline_top_need: { n_sites: number; people_newly_served: number; cost_pv_inr: Range; cooling_person_degrees: Range; carbon_t_co2e: Range; objective_norm: number };
  gain_vs_top_need_pct: number | null;
}
export interface Portfolios {
  status: string; presets: Record<string, Record<string, number>>; budgets_inr: number[]; equity_shares_pct: number[]; median_site_cost_inr: number;
  candidate_sites: number; no_regret_site_ids: string[]; no_regret_rule: string; high_need_rule: string; normalisation: string; results: PortfolioResult[];
}
export interface SensitivityRow {
  parameter: string; low: number | null; base: number | null; high: number | null; unit?: string | null; variant?: boolean; max_relative_swing: number;
  effects: Record<string, { at_low: number | null; at_high: number | null }>;
}
export interface Sensitivity {
  status: string; method: string;
  types: Record<string, { site_id: string; type: string; area_ha: number; base: Record<string, number | null>; rows: SensitivityRow[] }>;
}
