import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "./theme";

/** Counts from 0 to `target` once `active` becomes true. Respects reduced-motion. */
export function useCountUp(target: number | null | undefined, active: boolean, ms = 1400): number | null {
  const [v, setV] = useState<number | null>(target == null ? null : prefersReducedMotion() ? target : 0);
  const done = useRef(false);
  useEffect(() => {
    if (target == null) { setV(null); return; }
    if (prefersReducedMotion()) { setV(target); return; }
    if (!active || done.current) return;
    done.current = true;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, ms]);
  return v;
}

/** True once the element has entered the viewport (stays true). */
export function useSeen<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { setSeen(true); io.disconnect(); } }, { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, seen];
}

export function useViewport() {
  const get = () => ({ w: window.innerWidth, h: window.innerHeight });
  const [vp, setVp] = useState(get);
  useEffect(() => {
    const on = () => setVp(get());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return { ...vp, mobile: vp.w < 900 };
}
