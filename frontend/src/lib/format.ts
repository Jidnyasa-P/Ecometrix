const IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
export const fmtInt = (n: number | null | undefined) => (n == null || !Number.isFinite(n) ? "n/a" : IN.format(Math.round(n)));
export const fmtNum = (n: number | null | undefined, d = 1) =>
  n == null || !Number.isFinite(n) ? "n/a" : new Intl.NumberFormat("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
export const fmtPct = (n: number | null | undefined, d = 0) => (n == null || !Number.isFinite(n) ? "n/a" : `${fmtNum(n, d)}%`);

/** "4,00,9xx" -> "40 lakh" style short form for headlines (Indian numbering). */
export function fmtIndianShort(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "n/a";
  const a = Math.abs(n);
  if (a >= 1e7) return `${fmtNum(n / 1e7, 2)} crore`;
  if (a >= 1e5) return `${fmtNum(n / 1e5, 1)} lakh`;
  return fmtInt(n);
}
export const fmtDate = (iso?: string | null) => {
  if (!iso) return "n/a";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
};

/** Rupees in Indian short form: "₹ 25.3 lakh", "₹ 1.40 crore". */
export function fmtInr(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "n/a";
  const a = Math.abs(n);
  if (a >= 1e7) return `₹ ${fmtNum(n / 1e7, 2)} crore`;
  if (a >= 1e5) return `₹ ${fmtNum(n / 1e5, 1)} lakh`;
  return `₹ ${fmtInt(n)}`;
}
