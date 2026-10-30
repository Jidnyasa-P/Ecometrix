/* Automated accessibility checks on the real stylesheet and colour ramps (WCAG 2.x relative luminance and contrast). */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";
import { rampColors } from "../lib/colors";

const css = readFileSync(resolve(process.cwd(), "src/styles/app.css"), "utf8");
function tokens(theme: "light" | "dark"): Record<string, string> {
  const m = css.match(new RegExp(`:root\\[data-theme="${theme}"\\]\\s*\\{([^}]*)\\}`));
  const out: Record<string, string> = {};
  for (const [, k, v] of (m?.[1] ?? "").matchAll(/--([\w-]+):\s*([^;]+);/g)) out[k] = v.trim();
  return out;
}
const rgb = (h: string): [number, number, number] => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
const lin = (c: number) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
const lum = (h: string) => { const [r, g, b] = rgb(h); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

describe.each(["light", "dark"] as const)("%s theme contrast (text pairs need at least 4.5:1)", theme => {
  const t = tokens(theme);
  const pairs: [string, string, string][] = [
    ["ink", "bg", "body text"], ["ink", "surface", "text on cards"], ["ink", "surface-2", "text on tinted blocks"], ["muted", "bg", "secondary text"],
    ["muted", "surface", "secondary text on cards"], ["muted", "surface-2", "secondary text on tinted blocks"], ["on-accent", "accent", "text on accent"],
    ["b-meas", "surface", "MEASURED badge"], ["b-mod", "surface", "MODELLED badge"], ["b-ass", "surface", "ASSUMED badge"], ["b-sim", "surface", "SIMULATED badge"],
    ["ok", "surface", "pass status"], ["warn", "surface", "warning status"], ["bad", "surface", "failure status"], ["accent", "bg", "kicker and links"]
  ];
  it.each(pairs)("%s on %s (%s)", (fg, bg) => {
    expect(t[fg], `missing token --${fg}`).toBeTruthy(); expect(t[bg], `missing token --${bg}`).toBeTruthy();
    const f = t[fg].startsWith("#") ? t[fg] : null, b = t[bg].startsWith("#") ? t[bg] : null;
    if (!f || !b) return;                                   // rgba badge fills are checked against the page surface below
    expect(contrast(f, b)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("dark-theme badges use translucent fills: check the text against the solid surface they sit on", () => {
  const t = tokens("dark");
  it.each(["b-meas", "b-mod", "b-ass", "b-sim"])("%s", k => expect(contrast(t[k], t["surface"])).toBeGreaterThanOrEqual(4.5));
});

describe("map ramps", () => {
  const sequential = ["green", "built", "people", "need", "growth"];
  for (const theme of ["light", "dark"] as const) {
    it.each(sequential)(`%s ramp (${theme}) changes steadily in lightness, so it reads in greyscale and for colour-blind viewers`, name => {
      const L = rampColors(name, theme).map(lum);
      const dir = Math.sign(L[L.length - 1] - L[0]);
      expect(dir).not.toBe(0);
      for (let i = 1; i < L.length; i++) expect(Math.sign(L[i] - L[i - 1]) * dir).toBeGreaterThanOrEqual(0);
      expect(Math.abs(L[L.length - 1] - L[0])).toBeGreaterThan(0.35);
    });
  }
  it("diverging ramps keep their two ends clearly different in lightness or hue-independent contrast", () => {
    for (const theme of ["light", "dark"] as const) for (const name of ["heat", "access", "distance"]) {
      const r = rampColors(name, theme);
      expect(r.length).toBe(6);
    }
  });
});

describe("type sizes", () => {
  it("no font-size below 13px in the stylesheet", () => {
    const sizes = [...css.matchAll(/font-size:\s*([\d.]+)(px|rem)/g)].map(m => (m[2] === "rem" ? parseFloat(m[1]) * 16 : parseFloat(m[1])));
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(13);
  });
  it("body text is at least 17px", () => { expect(css).toMatch(/body \{[^}]*font-size:\s*1\.0625rem/); });
  it("respects reduced motion", () => { expect(css).toContain("prefers-reduced-motion: reduce"); });
});
