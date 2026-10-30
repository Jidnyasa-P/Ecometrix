import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import type { Cell, FieldDef } from "../lib/types";
import { colorScale, type RGBA, type Theme } from "../lib/colors";
import { MAP_STYLE, prefersReducedMotion } from "../lib/theme";

export interface Camera {
  pitch: number;
  bearing: number;
  padding: { top: number; right: number; bottom: number; left: number };
  duration?: number;
}

export interface MapStageProps {
  cells: Cell[];
  field: FieldDef;
  theme: Theme;
  camera: Camera;
  extrude?: boolean;
  interactive?: boolean;
  drift?: boolean;
  /** When set, cells that fail the test are dimmed and flattened (exploratory filter). */
  highlight?: ((c: Cell) => boolean) | null;
  selectedHex?: string | null;
  /** Hexagons to outline (for example the sites chosen in a plan). */
  marked?: string[] | null;
  onHover?: (c: Cell | null, x: number, y: number) => void;
  onSelect?: (c: Cell | null) => void;
  label: string;
}

const DIM: RGBA = [120, 128, 124, 38];

export function boundsOf(cells: Cell[]): [[number, number], [number, number]] {
  let w = 180, s = 90, e = -180, n = -90;
  for (const c of cells) { if (c.lng < w) w = c.lng; if (c.lng > e) e = c.lng; if (c.lat < s) s = c.lat; if (c.lat > n) n = c.lat; }
  return [[w, s], [e, n]];
}

export default function MapStage(p: MapStageProps) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const bounds = useMemo(() => boundsOf(p.cells), [p.cells]);
  const cb = useRef({ onHover: p.onHover, onSelect: p.onSelect });
  cb.current = { onHover: p.onHover, onSelect: p.onSelect };
  const drift = useRef(!!p.drift);
  drift.current = !!p.drift;

  // create the map once
  useEffect(() => {
    if (!host.current) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: host.current, style: MAP_STYLE[p.theme], bounds, fitBoundsOptions: { padding: p.camera.padding },
        pitch: p.camera.pitch, bearing: p.camera.bearing, interactive: !!p.interactive, attributionControl: { compact: true },
        maxPitch: 70, cooperativeGestures: false
      });
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "WebGL unavailable");
      return;
    }
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as maplibregl.IControl);
    if (p.interactive) map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    mapRef.current = map; overlayRef.current = overlay;
    map.on("load", () => setReady(true));
    map.on("error", ev => { const err = (ev as unknown as { error?: Error }).error; if (!map.loaded() && /style|WebGL/i.test(String(err?.message))) setFailed(String(err?.message)); });
    let raf = 0, last = performance.now();
    const tick = (t: number) => {
      raf = requestAnimationFrame(tick);
      if (!drift.current || document.hidden || prefersReducedMotion() || !map.loaded()) { last = t; return; }
      map.setBearing(map.getBearing() + ((t - last) / 1000) * 1.6);   // 1.6 degrees per second
      last = t;
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); overlay.finalize(); map.remove(); mapRef.current = null; overlayRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // theme -> basemap style
  const firstTheme = useRef(true);
  useEffect(() => {
    if (firstTheme.current) { firstTheme.current = false; return; }
    mapRef.current?.setStyle(MAP_STYLE[p.theme]);
  }, [p.theme]);

  // camera choreography
  const firstCam = useRef(true);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (firstCam.current) { firstCam.current = false; return; }
    const duration = prefersReducedMotion() ? 0 : (p.camera.duration ?? 2400);
    map.fitBounds(bounds, { padding: p.camera.padding, pitch: p.camera.pitch, bearing: p.camera.bearing, duration, maxZoom: 14, essential: false });
  }, [p.camera.pitch, p.camera.bearing, p.camera.padding.top, p.camera.padding.right, p.camera.padding.bottom, p.camera.padding.left, p.camera.duration, bounds]);

  // data layers
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const scale = colorScale(p.field.ramp, p.theme, p.field.domain);
    const [lo, hi] = p.field.domain;
    const norm = (v: number | null) => (v == null ? 0 : Math.min(1, Math.max(0, (v - lo) / (hi - lo || 1))));
    const key = p.field.key;
    const hl = p.highlight ?? null;
    const layers: unknown[] = [
      new H3HexagonLayer<Cell>({
        id: "cells", data: p.cells, getHexagon: d => d.h3, extruded: !!p.extrude, coverage: 0.95, pickable: true,
        autoHighlight: !!p.interactive, highlightColor: [255, 255, 255, 90], elevationScale: 900,
        getElevation: d => (hl && !hl(d) ? 0 : norm(d.v[key] ?? null)),
        getFillColor: d => (hl && !hl(d) ? DIM : scale(d.v[key] ?? null)),
        material: { ambient: 0.55, diffuse: 0.6, shininess: 24, specularColor: [255, 255, 255] },
        transitions: { getFillColor: 700, getElevation: 900 },
        updateTriggers: { getFillColor: [key, p.theme, hl], getElevation: [key, hl, p.extrude] },
        onHover: info => cb.current.onHover?.((info.object as Cell) ?? null, info.x, info.y),
        onClick: info => cb.current.onSelect?.((info.object as Cell) ?? null)
      })
    ];
    if (p.marked && p.marked.length) {
      const set = new Set(p.marked);
      layers.push(new H3HexagonLayer<Cell>({
        id: "marked", data: p.cells.filter(c => set.has(c.h3)), getHexagon: d => d.h3, filled: false, stroked: true, extruded: false, pickable: false,
        getLineColor: p.theme === "dark" ? [200, 240, 60, 255] : [11, 122, 75, 255], lineWidthMinPixels: 2.5
      }));
    }
    if (p.selectedHex) {
      const sel = p.cells.find(c => c.h3 === p.selectedHex);
      if (sel) layers.push(new H3HexagonLayer<Cell>({
        id: "selected", data: [sel], getHexagon: d => d.h3, filled: false, stroked: true, extruded: false,
        getLineColor: p.theme === "dark" ? [255, 255, 255, 255] : [13, 43, 34, 255], lineWidthMinPixels: 3
      }));
    }
    overlay.setProps({ layers: layers as never });
  }, [p.cells, p.field, p.theme, p.extrude, p.highlight, p.selectedHex, p.marked, p.interactive, ready]);

  return (
    <div className="mapstage" role="img" aria-label={p.label}>
      <div ref={host} className="mapstage__canvas" />
      {failed && (
        <div className="mapstage__fail" role="alert">
          <strong>The map could not start.</strong>
          <span>Your browser or device may not support WebGL. The numbers on this page are still real.</span>
        </div>
      )}
    </div>
  );
}
