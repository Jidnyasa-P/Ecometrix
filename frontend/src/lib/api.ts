const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

interface Opts { onSlow?: () => void; slowAfterMs?: number; retries?: number }

/**
 * GET JSON. Free hosting sleeps when idle and takes about a minute to wake, so network failures and
 * gateway errors are retried for a while, and `onSlow` lets the UI explain the wait honestly.
 */
export async function getJson<T>(path: string, opts: Opts = {}): Promise<T> {
  const { onSlow, slowAfterMs = 3500, retries = 12 } = opts;
  const timer = onSlow ? window.setTimeout(onSlow, slowAfterMs) : undefined;
  try {
    for (let attempt = 0; ; attempt++) {
      try {
        const r = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
        if (r.ok) return (await r.json()) as T;
        const retryable = r.status === 502 || r.status === 503 && !(await isNotBuilt(r)) || r.status === 504;
        if (!retryable || attempt >= retries) {
          let code = `http_${r.status}`, msg = `Request failed (${r.status})`;
          try { const b = await r.clone().json(); if (b?.detail?.code) { code = b.detail.code; msg = b.detail.hint ?? msg; } } catch { /* not json */ }
          throw new ApiError(r.status, code, msg);
        }
      } catch (e) {
        if (e instanceof ApiError) throw e;
        if (attempt >= retries) throw new ApiError(0, "network", "Cannot reach the EcoMetrix API.");
      }
      await new Promise(res => setTimeout(res, Math.min(2000 + attempt * 500, 6000)));
    }
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function isNotBuilt(r: Response): Promise<boolean> {
  try { return (await r.clone().json())?.detail?.code === "baseline_not_built"; } catch { return false; }
}

export const apiBase = BASE || "(same origin, proxied)";

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the EcoMetrix API.");
  }
  if (r.ok) return (await r.json()) as T;
  let code = `http_${r.status}`, msg = `Request failed (${r.status})`;
  try {
    const b = await r.json();
    if (b?.detail?.code) { code = b.detail.code; msg = b.detail.message ?? b.detail.hint ?? msg; }
    else if (Array.isArray(b?.detail)) msg = b.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch { /* not json */ }
  throw new ApiError(r.status, code, msg);
}
