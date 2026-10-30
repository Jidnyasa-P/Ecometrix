export type AssumptionRow = { path: string; low?: number; base?: number; high?: number; value?: unknown; unit?: string; label?: string; source?: string; note?: string };

export function flattenAssumptions(o: Record<string, unknown>, path = ""): AssumptionRow[] {
  const out: AssumptionRow[] = [];
  for (const [k, v] of Object.entries(o)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const e = v as Record<string, unknown>;
      if ("source" in e || "low" in e || "value" in e || "points" in e) out.push({ path: path + k, low: e.low as number, base: e.base as number, high: e.high as number,
        value: e.value ?? (e.points ? JSON.stringify(e.points) : e.estimated === false ? "not estimated" : undefined), unit: e.unit as string, label: e.label as string, source: e.source as string, note: e.note as string });
      else out.push(...flattenAssumptions(e, path + k + "."));
    }
  }
  return out;
}
