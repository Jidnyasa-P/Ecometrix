import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, getJson } from "./api";
import type { Cell, CellsPayload, FieldDef, Meta, Summary } from "./types";

export type DataState =
  | { status: "loading"; slow: boolean }
  | { status: "not_built"; meta: Meta | null }
  | { status: "error"; message: string }
  | { status: "ready"; meta: Meta; summary: Summary | null; cells: Cell[]; fields: Record<string, FieldDef> };

const Ctx = createContext<DataState>({ status: "loading", slow: false });
export const useData = () => useContext(Ctx);

export function toCells(p: CellsPayload): Cell[] {
  const keys = Object.keys(p.values);
  const out: Cell[] = new Array(p.n);
  for (let i = 0; i < p.n; i++) {
    const v: Record<string, number | null> = {};
    for (const k of keys) v[k] = p.values[k][i];
    out[i] = { h3: p.h3[i], lat: p.lat[i], lng: p.lng[i], area_km2: p.area_km2[i], v };
  }
  return out;
}

export function DataProvider({ children }: { children: ReactNode }) {
  const [slow, setSlow] = useState(false);
  const [state, setState] = useState<DataState | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const meta = await getJson<Meta>("/api/meta", { onSlow: () => alive && setSlow(true) });
        if (!meta.built) { alive && setState({ status: "not_built", meta }); return; }
        const [summary, cellsPayload] = await Promise.all([
          getJson<Summary>("/api/summary").catch((e: unknown) => (e instanceof ApiError && e.code === "baseline_not_built" ? null : Promise.reject(e))),
          getJson<CellsPayload>("/api/cells")
        ]);
        const fields = Object.fromEntries(meta.fields.map(f => [f.key, f]));
        alive && setState({ status: "ready", meta, summary, cells: toCells(cellsPayload), fields });
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.code === "baseline_not_built") setState({ status: "not_built", meta: null });
        else setState({ status: "error", message: e instanceof Error ? e.message : "Unknown error" });
      }
    })();
    return () => { alive = false; };
  }, []);

  const value = useMemo<DataState>(() => state ?? { status: "loading", slow }, [state, slow]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
