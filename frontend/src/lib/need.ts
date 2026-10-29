import type { Cell, FieldDef, Site, SitesPayload } from "./types";

export const COMPONENTS = ["heat", "people", "gap", "growth"] as const;
export type Comp = (typeof COMPONENTS)[number];
export type Weights = Record<Comp, number>;

export const COMP_LABEL: Record<Comp, string> = { heat: "Heat", people: "Residents", gap: "Park-access gap", growth: "Growth to 2035" };

/** Which components exist in the data (a missing layer removes its component; weights renormalise over the rest). */
export function availableComps(fields: Record<string, FieldDef>): Comp[] {
  return COMPONENTS.filter(c => `need_${c}` in fields);
}

/** 0 to 100 score = weighted mean of the percentile ranks. Cells missing any used component get null. */
export function needScore(cell: Cell, w: Weights, comps: Comp[]): number | null {
  const used = comps.filter(c => (w[c] ?? 0) > 0);
  const tot = used.reduce((s, c) => s + w[c], 0);
  if (!used.length || tot <= 0) return null;
  let acc = 0;
  for (const c of used) {
    const v = cell.v[`need_${c}`];
    if (v == null) return null;
    acc += (w[c] / tot) * v;          // need_* arrive already scaled 0 to 100
  }
  return acc;
}

export function withScores(cells: Cell[], w: Weights, comps: Comp[]): { cells: Cell[]; byHex: Map<string, number | null>; domain: [number, number] } {
  const byHex = new Map<string, number | null>();
  const vals: number[] = [];
  const out = cells.map(c => {
    const s = needScore(c, w, comps);
    byHex.set(c.h3, s);
    if (s != null) vals.push(s);
    return { ...c, v: { ...c.v, need_custom: s } };
  });
  vals.sort((a, b) => a - b);
  const q = (p: number) => (vals.length ? vals[Math.min(vals.length - 1, Math.round(p * (vals.length - 1)))] : 0);
  let lo = q(0.02), hi = q(0.98);
  if (hi <= lo) { lo = vals[0] ?? 0; hi = (vals[vals.length - 1] ?? 0) + 1; }
  return { cells: out, byHex, domain: [lo, hi] };
}

export function toSites(p: SitesPayload): Site[] {
  const c = p.columns;
  const num = (k: string, i: number) => (c[k]?.[i] ?? null) as number | null;
  return Array.from({ length: p.n }, (_, i) => ({
    id: c.site_id[i] as string, h3: c.h3[i] as string, type: c.type[i] as Site["type"], area_ha: num("area_ha", i) ?? 0,
    open_land_ha: num("open_land_ha", i) ?? 0, pop: num("pop", i) ?? 0, unserved: num("pop_unserved_300m", i) ?? 0,
    dlst_p50: num("dlst_p50", i), noRegret: (num("need_no_regret", i) ?? 0) > 0, lat: num("lat", i) ?? 0, lng: num("lng", i) ?? 0
  }));
}

export const normalise = (w: Weights, comps: Comp[]): Weights => {
  const t = comps.reduce((s, c) => s + (w[c] ?? 0), 0) || 1;
  return Object.fromEntries(COMPONENTS.map(c => [c, comps.includes(c) ? (w[c] ?? 0) / t : 0])) as Weights;
};
