let activeLocale = "en-IN";
let activeCurrency = "INR";

/** Set from the selected city's API metadata, never inferred from the browser. */
export function setFormatContext(currency?: string, locale?: string) {
  if (currency) activeCurrency = currency;
  if (locale) activeLocale = locale;
}

export const fmtInt = (n: number | null | undefined) =>
  n == null || !Number.isFinite(n) ? "n/a" : new Intl.NumberFormat(activeLocale, { maximumFractionDigits: 0 }).format(Math.round(n));
export const fmtNum = (n: number | null | undefined, d = 1) =>
  n == null || !Number.isFinite(n) ? "n/a" : new Intl.NumberFormat(activeLocale, { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
export const fmtPct = (n: number | null | undefined, d = 0) =>
  n == null || !Number.isFinite(n) ? "n/a" : `${fmtNum(n, d)}%`;

/** Compact counts follow the selected locale. India keeps readable lakh/crore labels. */
export function fmtCompact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "n/a";
  if (activeLocale === "en-IN") {
    if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(2)} crore`;
    if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(1)} lakh`;
  }
  return new Intl.NumberFormat(activeLocale, { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/** Currency display is selected from city metadata; backend field names remain legacy-compatible. */
export function fmtCurrency(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "n/a";
  if (activeCurrency === "INR" && activeLocale === "en-IN") {
    if (Math.abs(n) >= 1e7) return `₹ ${(n / 1e7).toFixed(2)} crore`;
    if (Math.abs(n) >= 1e5) return `₹ ${(n / 1e5).toFixed(1)} lakh`;
    return `₹ ${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n)}`;
  }
  return new Intl.NumberFormat(activeLocale, { style: "currency", currency: activeCurrency,
    notation: "compact", maximumFractionDigits: 2 }).format(n);
}

// Backwards-compatible export names for existing screens/tests and older modules.
export const fmtIndianShort = fmtCompact;
export const fmtInr = fmtCurrency;

export const fmtDate = (iso?: string | null) => {
  if (!iso) return "n/a";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(activeLocale, { day: "numeric", month: "short", year: "numeric" });
};
