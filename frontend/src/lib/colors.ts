export type Theme = "light" | "dark";
export type RGBA = [number, number, number, number];

const RAMPS: Record<Theme, Record<string, string[]>> = {
  light: {
    green: ["#EAF3C8", "#BFE07A", "#79C25B", "#2F9A5B", "#0E6B4A", "#053D2E"],
    heat: ["#2B7BB9", "#79BFC6", "#F4E7A1", "#F6A340", "#DC4A1E", "#8B1224"],
    built: ["#F1ECE0", "#D9CFC0", "#B7A99A", "#8A7B70", "#5E5148", "#33291F"],
    people: ["#F3E9F7", "#D9B6E8", "#B27CD6", "#8446B8", "#58238F", "#2E0B5A"],
    access: ["#D9381E", "#F2874A", "#F4D982", "#9BD36B", "#2FA35E", "#0B6B3F"],
    distance: ["#2FA35E", "#9BD36B", "#F4D982", "#F2874A", "#D9381E", "#7A0F1B"],
    need: ["#FBF3D9", "#F8D486", "#F2A24A", "#E2582B", "#B3261E", "#5E0F2B"],
    growth: ["#F4EEDF", "#F3D9A4", "#EFAF5C", "#E27A2A", "#B4421B", "#6E1B14"]
  },
  dark: {
    green: ["#12392E", "#1B6B45", "#38A15A", "#8BD34E", "#D6F25A", "#F4FFB0"],
    heat: ["#2E86C1", "#5BC0BE", "#F2E394", "#FFAA3B", "#FF5A2E", "#C2124B"],
    built: ["#1F2F2A", "#3B4A45", "#6B7A72", "#A0AAA2", "#D3D9D1", "#F6F7F2"],
    people: ["#2A1547", "#5B2A8F", "#8F4FC9", "#C77DFF", "#E8B4FF", "#FFF0FF"],
    access: ["#FF5A36", "#F2874A", "#F4D982", "#9BD36B", "#38B36A", "#0F8F55"],
    distance: ["#38B36A", "#9BD36B", "#F4D982", "#F2874A", "#FF5A36", "#C2124B"],
    need: ["#2A1F2E", "#6B2C5C", "#B8386B", "#F0584D", "#FFA23B", "#FFE08A"],
    growth: ["#1F2F2A", "#4B4A2E", "#8C6A2B", "#D18A2A", "#FF9A3C", "#FFD08A"]
  }
};

export const rampColors = (name: string, theme: Theme): string[] => RAMPS[theme][name] ?? RAMPS[theme].green;

const hex = (h: string): [number, number, number] => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

/** Linear interpolation along a ramp. t is clamped to [0, 1]. */
export function sample(stops: string[], t: number): [number, number, number] {
  const c = stops.map(hex);
  const x = Math.min(1, Math.max(0, t)) * (c.length - 1);
  const i = Math.min(c.length - 2, Math.floor(x));
  const f = x - i;
  return [0, 1, 2].map(k => Math.round(c[i][k] + (c[i + 1][k] - c[i][k]) * f)) as [number, number, number];
}

export function colorScale(ramp: string, theme: Theme, domain: [number, number], alpha = 215) {
  const stops = rampColors(ramp, theme);
  const [lo, hi] = domain;
  return (v: number | null | undefined): RGBA => {
    if (v == null || !Number.isFinite(v)) return [128, 128, 128, 28];
    const [r, g, b] = sample(stops, (v - lo) / (hi - lo || 1));
    return [r, g, b, alpha];
  };
}

export const cssGradient = (ramp: string, theme: Theme) => `linear-gradient(90deg, ${rampColors(ramp, theme).join(", ")})`;
