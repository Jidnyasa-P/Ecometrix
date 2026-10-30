import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/noto-sans-devanagari";
import "maplibre-gl/dist/maplibre-gl.css";

import "./styles/app.css";
import App from "./App";

// Register MapLibre's worker before creating any maps.
setWorkerUrl(workerUrl);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);