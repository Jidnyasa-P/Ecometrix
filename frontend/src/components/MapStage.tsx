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
  const valid = cells.filter(c => Number.isFinite(c.lng) && Number.isFinite(c.lat)
    && c.lng >= -180 && c.lng <= 180 && c.lat >= -90 && c.lat <= 90);
  if (!valid.length) return [[-0.01, -0.01], [0.01, 0.01]];
  let w = 180, south = 90, e = -180, north = -90;
  for (const c of valid) {
    w = Math.min(w, c.lng); e = Math.max(e, c.lng);
    south = Math.min(south, c.lat); north = Math.max(north, c.lat);
  }
  const epsilon = 0.001;
  if (e - w < epsilon) { w -= epsilon; e += epsilon; }
  if (north - south < epsilon) { south -= epsilon; north += epsilon; }
  return [[w, south], [e, north]];
}

function safePadding(map: maplibregl.Map, requested: Camera["padding"]) {
  const { clientWidth: width, clientHeight: height } = map.getContainer();
  const maxX = Math.max(0, width * 0.28);
  const maxY = Math.max(0, height * 0.28);
  return {
    top: Math.min(Math.max(0, requested.top), maxY),
    bottom: Math.min(Math.max(0, requested.bottom), maxY),
    left: Math.min(Math.max(0, requested.left), maxX),
    right: Math.min(Math.max(0, requested.right), maxX)
  };
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

  // create the map once
  useEffect(() => {
    if (!host.current) return;
    let map: maplibregl.Map;
    try {
      const [[west, south], [east, north]] = bounds;
      map = new maplibregl.Map({
        container: host.current, style: MAP_STYLE[p.theme],
        center: [(west + east) / 2, (south + north) / 2], zoom: 9,
        pitch: p.camera.pitch, bearing: p.camera.bearing, interactive: !!p.interactive,
        attributionControl: { compact: true }, maxPitch: 55, cooperativeGestures: false,
        fadeDuration: 0, refreshExpiredTiles: false,
      });
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "WebGL unavailable");
      return;
    }
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as maplibregl.IControl);
    if (p.interactive) map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    mapRef.current = map; overlayRef.current = overlay;
    map.on("load", () => {
      requestAnimationFrame(() => {
        if (mapRef.current !== map) return;
        map.resize();
        const { clientWidth, clientHeight } = map.getContainer();
        if (clientWidth > 0 && clientHeight > 0) {
          map.fitBounds(bounds, { padding: safePadding(map, p.camera.padding), pitch: p.camera.pitch,
            bearing: p.camera.bearing, duration: 0, maxZoom: 14, essential: false });
        }
        setReady(true);
      });
    });
    map.on("error", ev => { const err = (ev as unknown as { error?: Error }).error; if (!map.loaded() && /style|WebGL/i.test(String(err?.message))) setFailed(String(err?.message)); });
    return () => { overlay.finalize(); map.remove(); mapRef.current = null; overlayRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // No animation loop runs unless a caller explicitly enables slow camera drift.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !p.drift || !ready || prefersReducedMotion()) return;
    let raf = 0;
    let last = performance.now();
    const tick = (time: number) => {
      if (document.hidden || !map.loaded()) { last = time; raf = requestAnimationFrame(tick); return; }
      map.setBearing(map.getBearing() + ((time - last) / 1000) * 0.5);
      last = time;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [p.drift, ready]);

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
    if (!map.loaded()) return;
    const duration = prefersReducedMotion() ? 0 : (p.camera.duration ?? 900);
    map.resize();
    map.fitBounds(bounds, { padding: safePadding(map, p.camera.padding), pitch: p.camera.pitch,
      bearing: p.camera.bearing, duration, maxZoom: 14, essential: false });
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
        id: "cells", data: p.cells, getHexagon: d => d.h3, extruded: !!p.extrude, coverage: 0.9, pickable: !!p.interactive,
        autoHighlight: !!p.interactive, highlightColor: [255, 255, 255, 90], elevationScale: 900,
        getElevation: d => (hl && !hl(d) ? 0 : norm(d.v[key] ?? null)),
        getFillColor: d => (hl && !hl(d) ? DIM : scale(d.v[key] ?? null)),
        updateTriggers: { getFillColor: [key, p.theme, hl], getElevation: [key, hl, p.extrude] },
        onHover: p.interactive ? info => cb.current.onHover?.((info.object as Cell) ?? null, info.x, info.y) : undefined,
        onClick: p.interactive ? info => cb.current.onSelect?.((info.object as Cell) ?? null) : undefined
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
