import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ApiError, getJson } from "./api";
import type { ModelReport, Portfolios } from "./types";

export type PortfolioState =
  | { status: "loading" }
  | { status: "missing"; reason: string }
  | { status: "ready"; data: Portfolios };

/** Loads the pre-solved portfolios. If they do not exist, says why (from the model report) instead of showing anything made up. */
export function usePortfolios(enabled: boolean): PortfolioState {
  const [st, setSt] = useState<PortfolioState>({ status: "loading" });
  const location = useLocation();
  const citySlug = new URLSearchParams(location.search).get("city") ?? "pune";
  useEffect(() => {
    let alive = true;
    setSt({ status: "loading" });
    if (!enabled) return () => { alive = false; };
    getJson<Portfolios>("/api/portfolios").then(d => alive && setSt({ status: "ready", data: d })).catch(async (e: unknown) => {
      if (!alive) return;
      let reason = "The optimiser has not produced results yet.";
      if (e instanceof ApiError && e.code === "baseline_not_built") {
        try { const r = await getJson<ModelReport>("/api/model-report"); reason = r.modules?.portfolio?.reason ?? reason; } catch { /* keep default */ }
      } else reason = e instanceof Error ? e.message : reason;
      alive && setSt({ status: "missing", reason });
    });
    return () => { alive = false; };
  }, [enabled, citySlug]);
  return st;
}

export const PRESET_LABEL: Record<string, string> = { balanced: "Balanced", heat_first: "Heat first", access_first: "Access first", carbon_first: "Carbon first" };
export const find = (p: Portfolios, preset: string, budgetIdx: number, equity: number) =>
  p.results.find(r => r.preset === preset && r.budget_inr === p.budgets_inr[budgetIdx] && r.equity_pct === equity) ?? null;
